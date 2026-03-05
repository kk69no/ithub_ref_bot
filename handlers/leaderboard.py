"""Leaderboard handlers for referral groups and student rankings."""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database import get_db, get_student_referrals, get_group_referrals, get_student_by_id
from config import STATUSES, STATUS_EMOJI

router = Router()


async def build_leaderboard_text(db, group_id: int = None) -> str:
    """Build leaderboard text for groups or all students.

    Args:
        db: Database connection
        group_id: Optional group ID to filter by

    Returns:
        Formatted leaderboard text with rankings
    """
    if group_id:
        # Group referrals leaderboard
        referrals = await get_group_referrals(db, group_id)
    else:
        # All students leaderboard
        referrals = await db.fetchall(
            """
            SELECT user_id, COUNT(*) as count FROM referrals
            WHERE status IN (?, ?)
            GROUP BY user_id
            ORDER BY count DESC
            LIMIT 20
            """,
            ["✅ Принят", "💸 Оплачен"]
        )

    if not referrals:
        return "📊 Лидерборд пуст"

    text = "🏆 *Лидерборд по рефералам*\n\n"

    for i, ref in enumerate(referrals, 1):
        user_id = ref[0]
        count = ref[1] if isinstance(ref, tuple) else ref.get('count', 0)

        student = await get_student_by_id(db, user_id)
        name = student['name'] if student else f"ID {user_id}"

        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} {name}: *{count}* рефералов\n"

    return text


@router.message(F.text == "📊 Лидерборд")
async def leaderboard_handler(message: Message, state: FSMContext):
    """Show student leaderboard."""
    db = await get_db()

    try:
        text = await build_leaderboard_text(db)
        await message.answer(text, parse_mode="Markdown")
    finally:
        await db.close()


@router.callback_query(F.data == "leaderboard")
async def leaderboard_callback(query: CallbackQuery):
    """Handle leaderboard callback."""
    db = await get_db()

    try:
        text = await build_leaderboard_text(db)
        await query.message.edit_text(text, parse_mode="Markdown")
    finally:
        await db.close()

    await query.answer()


@router.callback_query(F.data.startswith("group_leaderboard:"))
async def group_leaderboard_callback(query: CallbackQuery):
    """Show group leaderboard."""
    group_id = int(query.data.split(":")[1])

    db = await get_db()

    try:
        text = await build_leaderboard_text(db, group_id)
        await query.message.edit_text(text, parse_mode="Markdown")
    finally:
        await db.close()

    await query.answer()
