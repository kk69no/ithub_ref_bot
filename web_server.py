"""
Мини-веб-сервер для приёма OAuth-callback от newlxp.

newlxp после авторизации студента делает POST-запрос:
  POST http://ВАШ_VPS:8443/api/verify
  Headers: Authorization: Bearer <WEBHOOK_SECRET>
  Body JSON: {
      "token": "abc123...",
      "student_name": "Иванов Иван Иванович",
      "student_group": "ИС-11"
  }

Бот находит студента в базе, верифицирует токен, уведомляет студента в Telegram.
"""
import logging
from aiohttp import web

import database as db
from config import WEBHOOK_SECRET, WEBHOOK_PORT

logger = logging.getLogger(__name__)

bot_instance = None  # будет установлен при запуске


def set_bot(bot):
    global bot_instance
    bot_instance = bot


async def handle_verify(request: web.Request) -> web.Response:
    """Эндпоинт для подтверждения авторизации от newlxp."""
    # Проверяем секретный ключ
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

    # Проверяем токен
    auth_token = await db.get_auth_token(token)
    if not auth_token:
        return web.json_response({"error": "Token not found"}, status=404)
    if auth_token["status"] != "pending":
        return web.json_response({"error": "Token already used"}, status=409)

    # Ищем студента в базе
    student = await db.find_student_by_name_and_group(student_name, student_group)

    if not student:
        # Пробуем fuzzy поиск
        fuzzy = await db.fuzzy_find_students(student_name)
        if fuzzy and student_group:
            # Фильтруем по группе
            for f in fuzzy:
                if f["group_name"].lower() == student_group.lower():
                    student = f
                    break
        if not student and fuzzy:
            student = fuzzy[0]  # берём лучшее совпадение

    if not student:
        return web.json_response(
            {"error": "Student not found in database"}, status=404
        )

    if student.get("telegram_id"):
        return web.json_response(
            {"error": "Student already registered"}, status=409
        )

    # Верифицируем токен
    await db.verify_auth_token(token, student["id"])

    # Уведомляем студента в Telegram
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

    logger.info(
        f"Verified: {student['full_name']} ({student['group_name']}) "
        f"-> tg_id={auth_token['telegram_id']}"
    )

    return web.json_response({
        "ok": True,
        "student_name": student["full_name"],
        "student_group": student["group_name"],
    })


async def handle_health(request: web.Request) -> web.Response:
    """Проверка что сервер работает."""
    return web.json_response({"status": "ok", "service": "ithub-ref-bot"})


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/api/verify", handle_verify)
    app.router.add_get("/api/health", handle_health)
    return app
