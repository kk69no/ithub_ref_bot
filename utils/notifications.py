"""Notification utilities for admins, students, and curators."""

from config import ADMIN_IDS, ADMIN_NOTIFY_CHAT_ID, STATUSES


async def notify_admin(message: str, bot=None) -> bool:
    """Send notification to admin chat.

    Args:
        message: Message text
        bot: Aiogram bot instance

    Returns:
        True if sent successfully, False otherwise
    """
    if not bot or not ADMIN_NOTIFY_CHAT_ID:
        return False

    try:
        await bot.send_message(
            chat_id=ADMIN_NOTIFY_CHAT_ID,
            text=message,
            parse_mode="Markdown"
        )
        return True
    except Exception:
        return False


async def notify_admins_list(message: str, bot=None) -> int:
    """Send notification to all admins in list.

    Args:
        message: Message text
        bot: Aiogram bot instance

    Returns:
        Number of admins notified
    """
    if not bot or not ADMIN_IDS:
        return 0

    sent = 0
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=message,
                parse_mode="Markdown"
            )
            sent += 1
        except Exception:
            pass

    return sent


async def notify_student(user_id: int, message: str, bot=None) -> bool:
    """Send notification to student.

    Args:
        user_id: Student user ID
        message: Message text
        bot: Aiogram bot instance

    Returns:
        True if sent successfully, False otherwise
    """
    if not bot:
        return False

    try:
        await bot.send_message(
            chat_id=user_id,
            text=message,
            parse_mode="Markdown"
        )
        return True
    except Exception:
        return False


async def notify_curator(user_id: int, message: str, bot=None) -> bool:
    """Send notification to curator.

    Args:
        user_id: Curator user ID
        message: Message text
        bot: Aiogram bot instance

    Returns:
        True if sent successfully, False otherwise
    """
    if not bot:
        return False

    try:
        await bot.send_message(
            chat_id=user_id,
            text=message,
            parse_mode="Markdown"
        )
        return True
    except Exception:
        return False


async def notify_group(group_id: int, message: str, db=None, bot=None) -> int:
    """Send notification to all students in group.

    Args:
        group_id: Group ID
        message: Message text
        db: Database connection
        bot: Aiogram bot instance

    Returns:
        Number of students notified
    """
    if not db or not bot:
        return 0

    students = await db.fetchall(
        "SELECT user_id FROM students WHERE group = ?",
        [group_id]
    )

    sent = 0
    for student in students:
        try:
            await bot.send_message(
                chat_id=student['user_id'],
                text=message,
                parse_mode="Markdown"
            )
            sent += 1
        except Exception:
            pass

    return sent


async def notify_status_change(user_id: int, old_status: str, new_status: str, bot=None) -> bool:
    """Send status change notification.

    Args:
        user_id: User ID
        old_status: Previous status
        new_status: New status
        bot: Aiogram bot instance

    Returns:
        True if sent successfully, False otherwise
    """
    message = f"📝 Ваш статус изменен:\n`{old_status}` → `{new_status}`"
    return await notify_student(user_id, message, bot)


async def notify_payment(user_id: int, amount: float, reason: str = None, bot=None) -> bool:
    """Send payment notification.

    Args:
        user_id: User ID
        amount: Payment amount
        reason: Optional payment reason
        bot: Aiogram bot instance

    Returns:
        True if sent successfully, False otherwise
    """
    message = f"💰 Вам выполнена выплата на сумму *{amount}₽*"

    if reason:
        message += f"\n\nПричина: {reason}"

    return await notify_student(user_id, message, bot)


async def notify_referral_status(student_id: int, new_status: str, bot=None) -> bool:
    """Send referral status change notification.

    Args:
        student_id: Student ID
        new_status: New status
        bot: Aiogram bot instance

    Returns:
        True if sent successfully, False otherwise
    """
    message = f"🔗 Ваш реферал обновлен: *{new_status}*"
    return await notify_student(student_id, message, bot)
