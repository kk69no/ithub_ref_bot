"""
Хендлеры модуля студента:
- /start (регистрация)
- Главное меню: ссылка, рефералы, баланс, лидерборд, правила
"""
import re
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from config import STATUSES, ADMIN_IDS
from utils.qr_generator import generate_qr
from handlers.leaderboard import build_leaderboard_text
from handlers.applicant import ApplicantForm

router = Router()


# ─── FSM для регистрации ────────────────────────────────────
class Registration(StatesGroup):
    waiting_full_name = State()
    waiting_group = State()


# ─── Inline-клавиатура главного меню ────────────────────────
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu_kb(is_curator: bool = False) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🔗 Моя ссылка", callback_data="my_link")],
        [InlineKeyboardButton(text="👥 Мои рефералы", callback_data="my_referrals")],
        [InlineKeyboardButton(text="💰 Мой баланс", callback_data="my_balance")],
        [InlineKeyboardButton(text="🏆 Лидерборд", callback_data="leaderboard")],
        [InlineKeyboardButton(text="❓ Правила", callback_data="rules")],
    ]
    if is_curator:
        buttons.insert(2, [
            InlineKeyboardButton(text="👥 Рефералы группы", callback_data="group_referrals"),
            InlineKeyboardButton(text="💰 Баланс куратора", callback_data="curator_balance"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─── /start ─────────────────────────────────────────────────
@router.message(CommandStart(deep_link=True))
async def cmd_start_deep(message: Message, command: CommandObject, state: FSMContext):
    """Переход по реферальной ссылке (абитуриент)."""
    ref_code = command.args
    if ref_code:
        referrer = await db.get_student_by_ref_code(ref_code)
        if referrer:
            # Проверяем, не студент ли это сам
            existing = await db.get_student_by_telegram_id(message.from_user.id)
            if existing:
                await message.answer(
                    "Ты уже зарегистрирован как студент! Используй главное меню.",
                )
                await show_main_menu(message, existing)
                return

            await state.update_data(referrer_id=referrer["id"], referrer_name=referrer["full_name"])
            await state.set_state(ApplicantForm.waiting_name)
            await message.answer(
                f"Привет! Тебя пригласил <b>{referrer['full_name']}</b> из IThub.\n"
                f"Заполни заявку — мы свяжемся с тобой!\n\n"
                f"Введи своё <b>имя и фамилию</b>:",
                parse_mode="HTML",
            )
            return

    # Если реф-код невалидный — обычный старт
    await cmd_start(message, state)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обычный /start — регистрация студента."""
    student = await db.get_student_by_telegram_id(message.from_user.id)
    if student:
        await show_main_menu(message, student)
        return

    # Проверяем, не админ ли
    if message.from_user.id in ADMIN_IDS:
        await message.answer(
            "👋 Добро пожаловать, админ! Используйте /admin для управления."
        )
        return

    await message.answer(
        "👋 <b>Добро пожаловать в реферальную программу IThub!</b>\n\n"
        "Для регистрации введи своё <b>ФИО</b> (как в списке колледжа):",
        parse_mode="HTML",
    )
    await state.set_state(Registration.waiting_full_name)


@router.message(Registration.waiting_full_name)
async def process_full_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text.strip())
    await message.answer("Теперь введи <b>номер/название своей группы</b>:", parse_mode="HTML")
    await state.set_state(Registration.waiting_group)


@router.message(Registration.waiting_group)
async def process_group(message: Message, state: FSMContext):
    data = await state.get_data()
    full_name = data["full_name"]
    group_name = message.text.strip()

    # Пробуем найти в предзагруженной базе
    student = await db.find_student_by_name_and_group(full_name, group_name)

    if student:
        if student["telegram_id"]:
            await message.answer(
                "⚠️ Этот студент уже зарегистрирован в боте. "
                "Если это ошибка — обратитесь к куратору или Арсену."
            )
            await state.clear()
            return

        # Привязываем Telegram ID
        await db.register_student_telegram(student["id"], message.from_user.id)
        student = await db.get_student_by_id(student["id"])
        await state.clear()
        await message.answer(
            f"✅ Отлично, <b>{student['full_name']}</b>! Ты зарегистрирован.\n"
            f"Группа: {student['group_name']}\n\n"
            f"Твоя реферальная ссылка готова! 👇",
            parse_mode="HTML",
        )
        await show_main_menu(message, student)
    else:
        await message.answer(
            "❌ Не нашли тебя в базе студентов.\n"
            "Проверь правильность ФИО и группы. "
            "Если проблема сохраняется — обратись к куратору или Арсену.\n\n"
            "Попробуй ещё раз. Введи <b>ФИО</b>:",
            parse_mode="HTML",
        )
        await state.set_state(Registration.waiting_full_name)


async def show_main_menu(message: Message, student: dict):
    is_curator = student["role"] == "curator"
    await message.answer(
        "📋 <b>Главное меню</b>",
        reply_markup=main_menu_kb(is_curator),
        parse_mode="HTML",
    )


# ─── Моя ссылка ─────────────────────────────────────────────
@router.callback_query(F.data == "my_link")
async def cb_my_link(callback: CallbackQuery):
    student = await db.get_student_by_telegram_id(callback.from_user.id)
    if not student:
        await callback.answer("Сначала зарегистрируйся!", show_alert=True)
        return

    # QR-код
    qr_buf = generate_qr(student["ref_link"])
    qr_file = BufferedInputFile(qr_buf.read(), filename="qr.png")

    share_text = (
        f"Привет! Я учусь в IThub Нальчик 🎓\n"
        f"Переходи по ссылке и оставляй заявку:\n{student['ref_link']}"
    )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    share_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📤 Поделиться",
            switch_inline_query=share_text,
        )],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_menu")],
    ])

    await callback.message.answer_photo(
        photo=qr_file,
        caption=(
            f"🔗 <b>Твоя реферальная ссылка:</b>\n"
            f"<code>{student['ref_link']}</code>\n\n"
            f"Покажи QR-код или отправь ссылку другу!"
        ),
        parse_mode="HTML",
        reply_markup=share_kb,
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
        text = "У тебя пока нет рефералов. Отправь свою ссылку друзьям! 🔗"
    else:
        lines = [f"👥 <b>Твои рефералы ({len(referrals)}):</b>\n"]
        for i, r in enumerate(referrals, 1):
            status_label = STATUSES.get(r["status"], r["status"])
            emoji = {"new": "📋", "consultation": "💬", "contract": "📝", "enrolled": "🎓"}.get(r["status"], "•")
            lines.append(f"{i}. {r['full_name']} — {emoji} {status_label}")
        text = "\n".join(lines)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
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
        f"Начислено: <b>{earned} ₽</b>",
        f"Выплачено: {paid} ₽",
        f"К выплате: <b>{pending} ₽</b>",
    ]

    if payments:
        lines.append("\n📊 <b>Детализация:</b>")
        type_labels = {
            "contract_referrer": "Договор",
            "enrolled_referrer": "Зачисление",
            "contract_curator": "Договор (кур.)",
            "enrolled_curator": "Зачисление (кур.)",
        }
        for p in payments[:10]:
            label = type_labels.get(p["type"], p["type"])
            status = "✅" if p["status"] == "paid" else "⏳"
            lines.append(
                f"  {status} {p.get('referral_name', '?')} — {label}: {p['amount']} ₽"
            )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
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

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_menu")]
    ])
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


# ─── Правила ────────────────────────────────────────────────
@router.callback_query(F.data == "rules")
async def cb_rules(callback: CallbackQuery):
    text = (
        "📖 <b>Правила реферальной программы IThub</b>\n\n"
        "1️⃣ Получи свою реферальную ссылку или QR-код в боте.\n\n"
        "2️⃣ Отправь ссылку другу — школьнику, который хочет учиться в IThub.\n\n"
        "3️⃣ Друг переходит по ссылке и заполняет заявку.\n\n"
        "4️⃣ Наш менеджер связывается с ним, проводит консультацию.\n\n"
        "5️⃣ Если друг подписывает договор — тебе начисляется <b>1 000 ₽</b>, "
        "а куратору твоей группы — 500 ₽.\n\n"
        "6️⃣ Когда друг оплачивает и начинает учиться (сентябрь) — "
        "тебе ещё <b>4 000 ₽</b>, куратору — ещё 500 ₽.\n\n"
        "💰 <b>Итого за одного друга: до 5 000 ₽!</b>\n\n"
        "⚠️ Один номер телефона = один реферал. "
        "Реферал принадлежит тому, кто первым пригласил."
    )
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
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
        is_curator = student["role"] == "curator"
        await callback.message.answer(
            "📋 <b>Главное меню</b>",
            reply_markup=main_menu_kb(is_curator),
            parse_mode="HTML",
        )
    await callback.answer()
