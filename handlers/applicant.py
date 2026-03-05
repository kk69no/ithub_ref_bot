"""
Хендлеры модуля абитуриента:
- Заполнение заявки (FSM): имя, телефон, класс, школа
- Защита от дублей по номеру телефона
"""
import re
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import database as db
from utils.notifications import (
    notify_new_referral, notify_student_new_referral, notify_curator_new_referral,
)

router = Router()


# ─── FSM заявки абитуриента ─────────────────────────────────
class ApplicantForm(StatesGroup):
    waiting_name = State()
    waiting_phone = State()
    waiting_grade = State()
    waiting_school = State()


GRADE_KB = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="8 класс", callback_data="grade_8"),
        InlineKeyboardButton(text="9 класс", callback_data="grade_9"),
    ],
    [
        InlineKeyboardButton(text="10 класс", callback_data="grade_10"),
        InlineKeyboardButton(text="11 класс", callback_data="grade_11"),
    ],
    [InlineKeyboardButton(text="Другое", callback_data="grade_other")],
])


def normalize_phone(phone: str) -> str:
    """Убрать всё кроме цифр и +."""
    return re.sub(r"[^\d+]", "", phone)


def validate_phone(phone: str) -> bool:
    """Валидация формата телефона."""
    clean = normalize_phone(phone)
    return bool(re.match(r"^\+?\d{10,15}$", clean))


# ─── Шаг 1: Имя (state ставится из student.py deep link) ────
@router.message(ApplicantForm.waiting_name)
async def process_applicant_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Пожалуйста, введи своё имя и фамилию:")
        return

    await state.update_data(applicant_name=name)
    await state.set_state(ApplicantForm.waiting_phone)
    await message.answer(
        "📞 Введи свой <b>номер телефона</b>:\n"
        "(например: +79281234567)",
        parse_mode="HTML",
    )


# ─── Шаг 2: Телефон ─────────────────────────────────────────
@router.message(ApplicantForm.waiting_phone)
async def process_applicant_phone(message: Message, state: FSMContext):
    phone = normalize_phone(message.text.strip())

    if not validate_phone(phone):
        await message.answer(
            "❌ Неверный формат телефона. Введи номер в формате +79281234567:"
        )
        return

    # Защита от дублей
    existing = await db.get_referral_by_phone(phone)
    if existing:
        await message.answer("⚠️ Ты уже оставлял заявку! Мы свяжемся с тобой.")
        await state.clear()
        return

    await state.update_data(applicant_phone=phone)
    await state.set_state(ApplicantForm.waiting_grade)
    await message.answer(
        "🎓 В каком ты классе?",
        reply_markup=GRADE_KB,
    )


# ─── Шаг 3: Класс (inline-кнопки) ──────────────────────────
@router.callback_query(ApplicantForm.waiting_grade, F.data.startswith("grade_"))
async def process_applicant_grade(callback: CallbackQuery, state: FSMContext):
    grade_map = {
        "grade_8": "8",
        "grade_9": "9",
        "grade_10": "10",
        "grade_11": "11",
        "grade_other": "другое",
    }
    grade = grade_map.get(callback.data, "другое")
    await state.update_data(applicant_grade=grade)
    await state.set_state(ApplicantForm.waiting_school)
    await callback.message.answer(
        "🏫 Напиши <b>название школы</b> и <b>населённый пункт</b>:",
        parse_mode="HTML",
    )
    await callback.answer()


# ─── Шаг 4: Школа → сохранение заявки ───────────────────────
@router.message(ApplicantForm.waiting_school)
async def process_applicant_school(message: Message, state: FSMContext, bot: Bot):
    school = message.text.strip()
    if len(school) < 2:
        await message.answer("Пожалуйста, напиши название школы и город:")
        return

    data = await state.get_data()
    referrer_id = data.get("referrer_id")
    applicant_name = data["applicant_name"]
    phone = data["applicant_phone"]
    grade = data["applicant_grade"]

    # Защита: студент не может отправить заявку сам на себя
    if referrer_id:
        referrer = await db.get_student_by_id(referrer_id)
        if referrer and referrer.get("telegram_id") == message.from_user.id:
            await message.answer("❌ Нельзя отправить заявку самому себе.")
            await state.clear()
            return

    # Повторная проверка дубля (на случай race condition)
    existing = await db.get_referral_by_phone(phone)
    if existing:
        await message.answer("⚠️ Заявка с таким номером уже существует!")
        await state.clear()
        return

    # Сохраняем заявку
    referral = await db.add_referral(
        referrer_id=referrer_id,
        full_name=applicant_name,
        phone=phone,
        grade=grade,
        school=school,
        telegram_id=message.from_user.id,
    )

    await state.clear()

    await message.answer(
        "✅ <b>Спасибо!</b> Твоя заявка принята.\n"
        "Мы свяжемся с тобой в ближайшее время! 📞",
        parse_mode="HTML",
    )

    # ─── Уведомления ─────────────────────────────────
    if referrer_id:
        referrer = await db.get_student_by_id(referrer_id)
        if referrer:
            # Уведомляем админов
            await notify_new_referral(bot, referral, referrer)

            # Уведомляем студента-реферера
            if referrer.get("telegram_id"):
                await notify_student_new_referral(
                    bot, referrer["telegram_id"], applicant_name
                )

            # Уведомляем куратора группы
            curator = await db.get_curator_for_group(referrer["group_name"])
            if curator and curator.get("telegram_id"):
                await notify_curator_new_referral(
                    bot, curator["telegram_id"],
                    referrer["full_name"], applicant_name,
                )
