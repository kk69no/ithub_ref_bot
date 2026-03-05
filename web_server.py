"""
Веб-сервер для авторизации студентов через newlxp.

Флоу:
1. Бот генерирует токен и отправляет студента на GET /auth?token=xxx
2. Студент видит форму, вводит email + пароль от newlxp.ru
3. Форма отправляет POST /auth/verify с { token, email, password }
4. Сервер проверяет креды через GraphQL API newlxp (api.newlxp.ru/graphql)
5. Если ок — ищет студента в нашей БД, верифицирует токен
6. Уведомляет студента в Telegram
"""
import logging
import os
import aiohttp as aiohttp_client
from aiohttp import web

import database as db
from config import WEBHOOK_SECRET

logger = logging.getLogger(__name__)

bot_instance = None

# Путь к HTML-шаблону
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "templates", "auth.html")

NEWLXP_GRAPHQL = "https://api.newlxp.ru/graphql"

SIGN_IN_QUERY = """
query SignIn($input: SignInInput!) {
  signIn(input: $input) {
    accessToken
    user {
      id
      firstName
      lastName
      middleName
      email
      roles
      student {
        learningGroups {
          learningGroup {
            name
          }
        }
      }
    }
  }
}
"""


def set_bot(bot):
    global bot_instance
    bot_instance = bot


# ─── GET /auth?token=xxx — страница авторизации ──────────────

async def handle_auth_page(request: web.Request) -> web.Response:
    """Отдаёт HTML-форму авторизации."""
    token = request.query.get("token", "")
    if not token:
        return web.Response(
            text="<h1>Ошибка: отсутствует токен</h1>"
                 "<p>Перейдите по ссылке из Telegram-бота.</p>",
            content_type="text/html",
            status=400,
        )

    # Проверяем что токен существует
    auth_token = await db.get_auth_token(token)
    if not auth_token:
        return web.Response(
            text="<h1>Ссылка недействительна</h1>"
                 "<p>Токен не найден. Запросите новую ссылку в боте (/start).</p>",
            content_type="text/html",
            status=404,
        )
    if auth_token["status"] != "pending":
        return web.Response(
            text="<h1>Уже подтверждено</h1>"
                 "<p>Вы уже подтвердили личность. Вернитесь в Telegram.</p>",
            content_type="text/html",
            status=200,
        )

    # Читаем и отдаём HTML-шаблон
    try:
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            html = f.read()
        html = html.replace("{{TOKEN}}", token)
        return web.Response(text=html, content_type="text/html")
    except FileNotFoundError:
        return web.Response(text="Template not found", status=500)


# ─── POST /auth/verify — проверка через newlxp GraphQL ───────

async def handle_auth_verify(request: web.Request) -> web.Response:
    """Проверяет логин/пароль через GraphQL API newlxp."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Неверный формат данных"}, status=400)

    token = data.get("token", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not token or not email or not password:
        return web.json_response(
            {"error": "Заполните все поля"}, status=400
        )

    # 1. Проверяем токен в нашей БД
    auth_token = await db.get_auth_token(token)
    if not auth_token:
        return web.json_response({"error": "Токен не найден"}, status=404)
    if auth_token["status"] != "pending":
        return web.json_response({"error": "Токен уже использован"}, status=409)

    # 2. Проверяем креды через newlxp GraphQL API
    try:
        async with aiohttp_client.ClientSession() as session:
            async with session.post(
                NEWLXP_GRAPHQL,
                json={
                    "operationName": "SignIn",
                    "query": SIGN_IN_QUERY,
                    "variables": {
                        "input": {"email": email, "password": password}
                    },
                },
                headers={"Content-Type": "application/json"},
                timeout=aiohttp_client.ClientTimeout(total=15),
            ) as resp:
                result = await resp.json()
    except Exception as e:
        logger.error(f"Ошибка запроса к newlxp: {e}")
        return web.json_response(
            {"error": "Не удалось связаться с newlxp. Попробуйте позже."},
            status=502,
        )

    # 3. Проверяем ответ
    if "errors" in result:
        error_msg = result["errors"][0].get("message", "Ошибка авторизации")
        logger.info(f"newlxp auth failed for {email}: {error_msg}")
        return web.json_response(
            {"error": "Неправильная почта или пароль"}, status=401
        )

    sign_in_data = result.get("data", {}).get("signIn", {})
    user = sign_in_data.get("user")
    if not user:
        return web.json_response(
            {"error": "Не удалось получить данные пользователя"}, status=500
        )

    # 4. Извлекаем ФИО и группу
    first_name = user.get("firstName", "")
    last_name = user.get("lastName", "")
    middle_name = user.get("middleName", "")

    # Формируем полное имя: Фамилия Имя Отчество
    name_parts = [last_name, first_name, middle_name]
    student_name = " ".join(p for p in name_parts if p).strip()

    # Группа из student.learningGroups[].learningGroup.name
    student_data = user.get("student") or {}
    learning_groups = student_data.get("learningGroups") or []
    student_group = ""
    if learning_groups:
        lg = learning_groups[0].get("learningGroup") or {}
        student_group = lg.get("name", "")

    if not student_name:
        student_name = email  # fallback

    logger.info(f"newlxp auth OK: {student_name} ({student_group}), email={email}")

    # 5. Ищем студента в нашей БД
    student = None
    if student_name and student_group:
        student = await db.find_student_by_name_and_group(student_name, student_group)

    if not student:
        # Fuzzy поиск
        fuzzy = await db.fuzzy_find_students(student_name, only_unregistered=True)
        if fuzzy and student_group:
            for f in fuzzy:
                if f["group_name"].lower() == student_group.lower():
                    student = f
                    break
        if not student and fuzzy:
            student = fuzzy[0]

    if not student:
        return web.json_response(
            {
                "error": f"Студент «{student_name}» не найден в базе реферальной программы. "
                         "Обратитесь к администратору."
            },
            status=404,
        )

    if student.get("telegram_id"):
        return web.json_response(
            {"error": "Этот студент уже зарегистрирован в боте."}, status=409
        )

    # 6. Верифицируем токен
    await db.verify_auth_token(token, student["id"])

    # 7. Уведомляем в Telegram
    if bot_instance:
        try:
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="✅ Завершить регистрацию",
                    callback_data="complete_registration",
                )]
            ])
            await bot_instance.send_message(
                auth_token["telegram_id"],
                f"🎉 <b>Личность подтверждена!</b>\n\n"
                f"👤 {student['full_name']}\n"
                f"📚 Группа: {student['group_name']}\n\n"
                f"Нажми кнопку ниже, чтобы завершить регистрацию:",
                parse_mode="HTML",
                reply_markup=kb,
            )
        except Exception as e:
            logger.warning(f"Не удалось уведомить в Telegram: {e}")

    logger.info(
        f"Verified: {student['full_name']} ({student['group_name']}) "
        f"-> tg_id={auth_token['telegram_id']}"
    )

    return web.json_response({
        "ok": True,
        "student_name": student["full_name"],
        "student_group": student["group_name"],
    })


# ─── POST /api/verify — обратная совместимость (webhook) ─────

async def handle_api_verify(request: web.Request) -> web.Response:
    """Старый эндпоинт для прямого вызова (webhook от newlxp)."""
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {WEBHOOK_SECRET}":
        return web.json_response({"error": "Unauthorized"}, status=401)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    token = data.get("token")
    student_name = data.get("student_name", "").strip()
    student_group = data.get("student_group", "").strip()

    if not token or not student_name:
        return web.json_response(
            {"error": "Missing token or student_name"}, status=400
        )

    auth_token = await db.get_auth_token(token)
    if not auth_token:
        return web.json_response({"error": "Token not found"}, status=404)
    if auth_token["status"] != "pending":
        return web.json_response({"error": "Token already used"}, status=409)

    student = await db.find_student_by_name_and_group(student_name, student_group)
    if not student:
        fuzzy = await db.fuzzy_find_students(student_name, only_unregistered=True)
        if fuzzy and student_group:
            for f in fuzzy:
                if f["group_name"].lower() == student_group.lower():
                    student = f
                    break
        if not student and fuzzy:
            student = fuzzy[0]

    if not student:
        return web.json_response(
            {"error": "Student not found in database"}, status=404
        )

    if student.get("telegram_id"):
        return web.json_response(
            {"error": "Student already registered"}, status=409
        )

    await db.verify_auth_token(token, student["id"])

    if bot_instance:
        try:
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="✅ Завершить регистрацию",
                    callback_data="complete_registration",
                )]
            ])
            await bot_instance.send_message(
                auth_token["telegram_id"],
                f"🎉 <b>Личность подтверждена!</b>\n\n"
                f"👤 {student['full_name']}\n"
                f"📚 Группа: {student['group_name']}\n\n"
                f"Нажми кнопку ниже, чтобы завершить регистрацию:",
                parse_mode="HTML",
                reply_markup=kb,
            )
        except Exception as e:
            logger.warning(f"Не удалось уведомить пользователя: {e}")

    return web.json_response({
        "ok": True,
        "student_name": student["full_name"],
        "student_group": student["group_name"],
    })


# ─── Health check ─────────────────────────────────────────────

async def handle_health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "ithub-ref-bot"})


# ─── Создание приложения ─────────────────────────────────────

def create_app() -> web.Application:
    app = web.Application()
    # Новый OAuth флоу через нашу страницу
    app.router.add_get("/auth", handle_auth_page)
    app.router.add_post("/auth/verify", handle_auth_verify)
    # Обратная совместимость + health
    app.router.add_post("/api/verify", handle_api_verify)
    app.router.add_get("/api/health", handle_health)
    return app
