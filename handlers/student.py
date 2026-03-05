"""
Хендлеры модуля студента:
- /start с OAuth через newlxp
- Главное меню: ссылка, рефералы, баланс, лидерборд, правила
- /help
"""
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, BufferedInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.fsm.context import FSMContext

import database as db
from config import ADMIN_IDS, STATUSES, STATUS_EMOJI, NEWLXP_AUTH_URL
from utils.qr_generator import generate_qr
from handlers.leaderboard import build_leaderboard_text
from handlers.applicant import ApplicantForm

router = Router()


# ─── Клавиатуры ─────────────────────────────────────────────

def main_menu_kb(is_curator: bool = False) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🔗 Моя ссылка", callback_data="my_link")],
        [InlineKeyboardButton(text="👥 Мои рефералы", callback_data="my_referrals")],
        [InlineKeyboardButton(text="💰 Мой баланс", callback_data="my_balance")],
        [InlineKeyboardButton(text="🏆 Лидерборд", callback_data="leaderboard")],
        [InlineKeyboardButton(text="❓ Правила", callback_data="rules")],
        [InlineKeyboardButton(text="💬 Помощь", callback_data="help")],
    ]
    if is_curator:
        buttons.insert(2, [
            InlineKeyboardButton(text="👥 Группа", callback_data="group_referrals"),
            InlineKeyboardButton(text="💰 Куратор", callback_data="curator_balance"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─── /start с deep link (абитуриент) ────────────────────────
@router.message(CommandStart(deep_link=True))
async def cmd_start_deep(message: Message, command: CommandObject, state: FSMContext):
    ref_code = command.args
    if ref_code:
        referrer = await db.get_student_by_ref_code(ref_code)
        if referrer:
            # Уже студент?
            existing = await db.get_student_by_telegram_id(message.from_user.id)
            if existing:
                await message.answer(
                    "😊 Ты уже зарегистрирован как студент!",
                )
                await show_main_menu(message, existing)
                return

            await state.update_data(referrer_id=referrer["id"])
            await state.set_state(ApplicantForm.waiting_name)
            await message.answer(
                f"👋 <b>Привет!</b>\n\n"
                f"Тебя пригласил <b>{referrer['full_name']}</b> из IThub Нальчик.\n"
                f"Заполни короткую заявку — мы свяжемся с тобой!\n\n"
                f"Введи своё <b>имя и фамилию</b>:",
                parse_mode="HTML",
            )
            return

    await cmd_start(message, state)


# ─── /start (регистрация студента через newlxp OAuth) ───────
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    student = await db.get_student_by_telegram_id(message.from_user.id)
    if student:
        await show_main_menu(message, student)
        return

    if message.from_user.id in ADMIN_IDS:
        await message.answer(
            "👋 Добро пожаловать, админ!\n"
            "Используй /admin для управления.",
        )
        return

    # Проверяем, может есть верифицированный токен (вернулся после newlxp)
    verified = await db.get_verified_token_for_user(message.from_user.id)
    if verified:
        student = await db.get_student_by_id(verified["student_id"])
        if student and not student.get("telegram_id"):
            await db.register_student_telegram(student["id"], message.from_user.id)
            await db.mark_token_used(verified["token"])
            student = await db.get_student_by_id(student["id"])
            await message.answer(
                f"🎉 <b>Добро пожаловать, {student['full_name']}!</b>\n\n"
                f"📚 Группа: {student['group_name']}\n"
                f"🔗 Твоя реферальная ссылка готова!\n\n"
                f"Приглашай друзей и зарабатывай до <b>5 000 ₽</b> за каждого!",
                parse_mode="HTML",
            )
            await show_main_menu(message, student)
            return

    # Генерируем токен и отправляем на newlxp
    token = await db.create_auth_token(message.from_user.id)
    auth_url = NEWLXP_AUTH_URL.format(token=token)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Войти через newlxp", url=auth_url)],
        [InlineKeyboardButton(text="🔄 Я авторизовался", callback_data="check_auth")],
    ])

    await message.answer(
        "👋 <b>Добро пожаловать в реферальную программу IThub!</b>\n\n"
        "Для регистрации нужно подтвердить личность через сайт колледжа.\n\n"
        "1️⃣ Нажми кнопку <b>«Войти через newlxp»</b>\n"
        "2️⃣ Авторизуйся на сайте\n"
        "3️⃣ Вернись сюда и нажми <b>«Я авторизовался»</b>",
        parse_mode="HTML",
        reply_markup=kb,
    )


# ─── Проверка OAuth-авторизации ─────────────────────────────
@router.callback_query(F.data == "check_auth")
async def cb_check_auth(callback: CallbackQuery):
    verified = await db.get_verified_token_for_user(callback.from_user.id)

    if not verified:
        token = await db.create_auth_token(callback.from_user.id)
        auth_url = NEWLXP_AUTH_URL.format(token=token)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔑 Войти через newlxp", url=auth_url)],
            [InlineKeyboardButton(text="🔄 Я авторизовался", callback_data="check_auth")],
        ])
        await callback.message.answer(
            "⏳ Авторизация ещё не завершена.\n\n"
            "Нажми <b>«Войти через newlxp»</b>, авторизуйся на сайте, "
            "а затем вернись и нажми <b>«Я авторизовался»</b>.",
            parse_mode="HTML",
            reply_markup=kb,
        )
        await callback.answer()
        return

    student = await db.get_student_by_id(verified["student_id"])
    if not student:
        await callback.answer("Ошибка: студент не найден.", show_alert=True)
        return

    if student.get("telegram_id"):
        await callback.answer("Этот аккаунт уже зарегистрирован.", show_alert=True)
        return

    # Регистрируем!
    await db.register_student_telegram(student["id"], callback.from_user.id)
    await db.mark_token_used(verified["token"])
    student = await db.get_student_by_id(student["id"])

    await callback.message.answer(
        f"🎉 <b>Добро пожаловать, {student['full_name']}!</b>\n\n"
        f"📚 Группа: {student['group_name']}\n"
        f"🔗 Твоя реферальная ссылка готова!\n\n"
        f"Приглашай друзей и зарабатывай до <b>5 000 ₽</b> за каждого!",
        parse_mode="HTML",
    )
    await show_main_menu(callback.message, student)
    await callback.answer("Регистрация завершена!")


# ─── Завершение регистрации (callback от web_server) ────────
@router.callback_query(F.data == "complete_registration")
async def cb_complete_registration(callback: CallbackQuery):
    # Тот же механизм что и check_auth
    await cb_check_auth(callback)


async def show_main_menu(message: Message, student: dict):
    is_curator = student["role"] == "curator"
    await message.answer(
        "📋 <b>Главное меню</b>\n\n"
        "Выбери, что тебя интересует:",
        reply_markup=main_menu_kb(is_curator),
        parse_mode="HTML",
    )


# ─── /help ──────────────────────────────────────────────────
@router.message(Command("help"))
async def cmd_help(message: Message):
    await send_help(message)


@router.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery):
    await send_help(callback.message)
    await callback.answer()


async def send_help(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_menu")]
    ])
    await message.answer(
        "💬 <b>Помощь</b>\n\n"
        "<b>Как работает реферальная программа?</b>\n"
        "Ты получаешь ссылку → отправляешь другу → он заполняет заявку → "
        "мы связываемся с ним → при подписании договора тебе начисляется бонус.\n\n"
        "<b>Сколько можно заработать?</b>\n"
        "До 5 000 ₽ за каждого друга (1 000 ₽ за договор + 4 000 ₽ за оплату).\n\n"
        "<b>Как получить выплату?</b>\n"
        "Начисления видны в разделе «Мой баланс». Выплаты проводит бухгалтерия колледжа.\n\n"
        "<b>Не могу зарегистрироваться?</b>\n"
        "Убедись, что ты авторизовался на newlxp.ru. Если проблема сохраняется — напиши куратору.\n\n"
        "<b>Нашёл ошибку?</b>\n"
        "Напиши Арсену — @{admin_contact}\n\n"
        "<b>Команды:</b>\n"
        "/start — главное меню\n"
        "/help — эта справка\n"
        "/admin — панель администратора",
        parse_mode="HTML",
        reply_markup=kb,
    )


# ─── Моя ссылка ─────────────────────────────────────────────
@router.callback_query(F.data == "my_link")
async def cb_my_link(callback: CallbackQuery):
    student = await db.get_student_by_telegram_id(callback.from_user.id)
    if not student:
        await callback.answer("Сначала зарегистрируйся!", show_alert=True)
        return

    qr_buf = generate_qr(student["ref_link"])
    qr_file = BufferedInputFile(qr_buf.read(), filename="qr.png")

    share_text = (
        f"Привет! Я учусь в IThub Нальчик 🎓\n"
        f"Переходи по ссылке и оставляй заявку:\n{student['ref_link']}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Поделиться", switch_inline_query=share_text)],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_menu")],
    ])

    await callback.message.answer_photo(
        photo=qr_file,
        caption=(
            f"🔗 <b>Твоя реферальная ссылка:</b>\n\n"
            f"<code>{student['ref_link']}</code>\n\n"
            f"📱 Покажи QR-код или отправь ссылку другу!\n"
            f"💰 За каждого друга — до 5 000 ₽"
        ),
        parse_mode="HTML",
        reply_markup=kb,
    )
    await callback.answer()


# ─── Мои рефералы ───────────────────────────────────────────
@router.callback_query(F.data == "my_referrals")
async def cb_my_referrals(callback: CallbackQuery):
    student = await db.get_student_by_telegram_id(callback.from_user.id)
    if not student:
        await callback.answer("Сначала зарегистрируйся!", show_alert=True)
        return

    referrals = await db.get_referrals_by_referrer(student["id"])
    if not referrals:
        text = (
            "👥 <b>Мои рефералы</b>\n\n"
            "У тебя пока нет рефералов.\n"
            "Отправь свою ссылку друзьям — нажми 🔗 <b>Моя ссылка</b>!"
        )
    else:
        lines = [f"👥 <b>Мои рефералы</b> ({len(referrals)})\n"]
        for i, r in enumerate(referrals, 1):
            emoji = STATUS_EMOJI.get(r["status"], "•")
            status = STATUSES.get(r["status"], r["status"])
            lines.append(f"  {i}. {r['full_name']} — {status}")
        text = "\n".join(lines)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_menu")]
    ])
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


# ─── Мой баланс ─────────────────────────────────────────────
@router.callback_query(F.data == "my_balance")
async def cb_my_balance(callback: CallbackQuery):
    student = await db.get_student_by_telegram_id(callback.from_user.id)
    if not student:
        await callback.answer("Сначала зарегистрируйся!", show_alert=True)
        return

    earned = student["balance_earned"]
    paid = student["balance_paid"]
    pending = earned - paid

    payments = await db.get_payments_by_recipient(student["id"])

    lines = [
        f"💰 <b>Мой баланс</b>\n",
        f"┌ Начислено:  <b>{earned} ₽</b>",
        f"├ Выплачено:  {paid} ₽",
        f"└ К выплате:  <b>{pending} ₽</b>",
    ]

    if payments:
        lines.append("\n📊 <b>Последние начисления:</b>\n")
        type_labels = {
            "contract_referrer": "Договор",
            "enrolled_referrer": "Зачисление",
            "contract_curator": "Договор (кур.)",
            "enrolled_curator": "Зачисление (кур.)",
        }
        for p in payments[:10]:
            label = type_labels.get(p["type"], p["type"])
            icon = "✅" if p["status"] == "paid" else "⏳"
            lines.append(f"  {icon} {p.get('referral_name', '?')} — {label}: {p['amount']} ₽")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_menu")]
    ])
    await callback.message.answer("\n".join(lines), parse_mode="HTML", reply_markup=kb)
    await callback.answer()


# ─── Лидерборд ──────────────────────────────────────────────
@router.callback_query(F.data == "leaderboard")
async def cb_leaderboard(callback: CallbackQuery):
    student = await db.get_student_by_telegram_id(callback.from_user.id)
    text = await build_leaderboard_text(student)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_menu")]
    ])
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


# ─── Правила ────────────────────────────────────────────────
@router.callback_query(F.data == "rules")
async def cb_rules(callback: CallbackQuery):
    text = (
        "📖 <b>Правила реферальной программы</b>\n\n"
        "┌ 1. Получи ссылку в разделе 🔗 Моя ссылка\n"
        "├ 2. Отправь её другу-школьнику\n"
        "├ 3. Друг заполняет заявку в боте\n"
        "├ 4. Наш менеджер проведёт консультацию\n"
        "├ 5. Договор → тебе <b>1 000 ₽</b>\n"
        "└ 6. Начало учёбы → тебе ещё <b>4 000 ₽</b>\n\n"
        "💰 <b>Итого: до 5 000 ₽ за каждого друга!</b>\n\n"
        "⚠️ <b>Важно:</b>\n"
        "• Один телефон = один реферал\n"
        "• Реферал принадлежит тому, кто пригласил первым\n"
        "• Куратор группы тоже получает бонус: 500 ₽ × 2"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_menu")]
    ])
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


# ─── Назад в меню ───────────────────────────────────────────
@router.callback_query(F.data == "back_menu")
async def cb_back_menu(callback: CallbackQuery):
    student = await db.get_student_by_telegram_id(callback.from_user.id)
    if student:
        await show_main_menu(callback.message, student)
    await callback.answer()
