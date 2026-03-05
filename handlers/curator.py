"""Curator handlers for managing group referrals and balances."""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import get_db, get_group_referrals, get_student_by_id, get_curator_balance
from config import STATUSES, STATUS_EMOJI

router = Router()


class CuratorStates(StatesGroup):
    """States for curator operations."""
    payment_amount = State()
    payment_reason = State()


async def build_group_referrals_text(db, group_id: int) -> str:
    """Build text showing group referrals with status emojis.

    Args:
        db: Database connection
        group_id: Group ID

    Returns:
        Formatted group referrals text
    """
    referrals = await get_group_referrals(db, group_id)

    if not referrals:
        return "📋 Рефералы в этой группе отсутствуют"

    # Group by status
    by_status = {}
    for ref in referrals:
        status = ref['status']
        if status not in by_status:
            by_status[status] = []
        by_status[status].append(ref)

    text = "📊 *Рефералы группы*\n\n"

    for status in STATUSES:
        if status in by_status:
            emoji = STATUS_EMOJI.get(status, "•")
            text += f"{emoji} {status}: {len(by_status[status])}\n"

    text += "\n"

    for status in STATUSES:
        if status in by_status:
            text += f"\n*{STATUS_EMOJI.get(status, '•')} {status}:*\n"
            for ref in by_status[status]:
                student = await get_student_by_id(db, ref['student_id'])
                name = student['name'] if student else f"ID {ref['student_id']}"
                text += f"  • {name}\n"

    return text


async def build_curator_balance_text(db, curator_id: int) -> str:
    """Build text showing curator balance.

    Args:
        db: Database connection
        curator_id: Curator user ID

    Returns:
        Formatted balance text
    """
    balance = await get_curator_balance(db, curator_id)
    pending = await db.fetchval(
        "SELECT SUM(amount) FROM curator_payments WHERE curator_id = ? AND status = 'pending'",
        [curator_id]
    ) or 0

    text = "💰 *Баланс куратора*\n\n"
    text += f"Доступно: *{balance}* ₽\n"
    text += f"В ожидании: *{pending}* ₽\n"
    text += f"Всего заработано: *{balance + pending}* ₽\n"

    return text


@router.callback_query(F.data.startswith("group_referrals:"))
async def group_referrals_callback(query: CallbackQuery):
    """Show group referrals."""
    group_id = int(query.data.split(":")[1])

    db = await get_db()

    try:
        text = await build_group_referrals_text(db, group_id)
        await query.message.edit_text(text, parse_mode="Markdown")
    finally:
        await db.close()

    await query.answer()


@router.callback_query(F.data == "curator_balance")
async def curator_balance_callback(query: CallbackQuery, state: FSMContext):
    """Show curator balance."""
    user_id = query.from_user.id

    db = await get_db()

    try:
        text = await build_curator_balance_text(db, user_id)
        await query.message.edit_text(text, parse_mode="Markdown")
    finally:
        await db.close()

    await query.answer()


@router.callback_query(F.data == "request_payment")
async def request_payment_callback(query: CallbackQuery, state: FSMContext):
    """Start payment request flow."""
    await state.set_state(CuratorStates.payment_amount)
    await query.message.edit_text(
        "💸 Введите сумму для запроса выплаты:",
        parse_mode="Markdown"
    )
    await query.answer()


@router.message(CuratorStates.payment_amount)
async def payment_amount_handler(message: Message, state: FSMContext):
    """Handle payment amount input."""
    try:
        amount = float(message.text)
        if amount <= 0:
            await message.answer("❌ Сумма должна быть положительной")
            return

        await state.update_data(amount=amount)
        await state.set_state(CuratorStates.payment_reason)
        await message.answer("📝 Укажите причину выплаты:")

    except ValueError:
        await message.answer("❌ Введите корректное число")


@router.message(CuratorStates.payment_reason)
async def payment_reason_handler(message: Message, state: FSMContext):
    """Handle payment reason input."""
    data = await state.get_data()
    amount = data.get('amount')

    db = await get_db()

    try:
        # Create payment request
        await db.execute(
            """
            INSERT INTO curator_payments (curator_id, amount, reason, status)
            VALUES (?, ?, ?, 'pending')
            """,
            [message.from_user.id, amount, message.text]
        )
        await db.commit()

        await message.answer(
            f"✅ Запрос на выплату {amount}₽ отправлен администратору",
            parse_mode="Markdown"
        )

    finally:
        await db.close()

    await state.clear()
