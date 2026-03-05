"""
Система уведомлений — отправка сообщений админам, студентам, кураторам.
"""
import logging
from aiogram import Bot

from config import ADMIN_IDS, ADMIN_NOTIFY_CHAT_ID, STATUSES

logger = logging.getLogger(__name__)


async def notify_admins(bot: Bot, text: str):
    """Отправить сообщение в чат админов или каждому админу лично."""
    if ADMIN_NOTIFY_CHAT_ID:
        try:
            await bot.send_message(ADMIN_NOTIFY_CHAT_ID, text)
            return
        except Exception as e:
            logger.warning(f"Не удалось отправить в чат админов: {e}")

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception as e:
            logger.warning(f"Не удалось отправить админу {admin_id}: {e}")


async def notify_new_referral(bot: Bot, referral: dict, referrer: dict):
    """Уведомить админов о новой заявке."""
    text = (
        f"📋 <b>Новая заявка</b>\n\n"
        f"👤 {referral['full_name']}\n"
        f"📞 {referral['phone']}\n"
        f"🎓 Класс: {referral.get('grade', '—')}\n"
        f"🏫 Школа: {referral.get('school', '—')}\n\n"
        f"Привёл: <b>{referrer['full_name']}</b> из группы {referrer['group_name']}"
    )
    await notify_admins(bot, text)


async def notify_student_new_referral(bot: Bot, student_telegram_id: int, referral_name: str):
    """Уведомить студента, что его друг оставил заявку."""
    try:
        await bot.send_message(
            student_telegram_id,
            f"🎉 Твой друг <b>{referral_name}</b> оставил заявку! "
            f"Мы свяжемся с ним. Спасибо!",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"Не удалось уведомить студента {student_telegram_id}: {e}")


async def notify_student_status_change(bot: Bot, student_telegram_id: int,
                                       referral_name: str, new_status: str, amount: int):
    """Уведомить студента об изменении статуса его реферала."""
    status_label = STATUSES.get(new_status, new_status)
    if new_status == "contract":
        text = (
            f"🎉 Отличная новость! <b>{referral_name}</b> подписал договор.\n"
            f"Тебе начислено <b>{amount} ₽</b>!"
        )
    elif new_status == "enrolled":
        text = (
            f"🎓 <b>{referral_name}</b> начал учиться в IThub!\n"
            f"Тебе начислено ещё <b>{amount} ₽</b>."
        )
    else:
        text = (
            f"ℹ️ Статус <b>{referral_name}</b> изменён на «{status_label}»."
        )
    try:
        await bot.send_message(student_telegram_id, text, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Не удалось уведомить студента: {e}")


async def notify_curator_new_referral(bot: Bot, curator_telegram_id: int,
                                      student_name: str, referral_name: str):
    """Уведомить куратора о новом реферале из его группы."""
    try:
        await bot.send_message(
            curator_telegram_id,
            f"👥 Студент <b>{student_name}</b> из вашей группы привёл "
            f"абитуриента <b>{referral_name}</b>. Статус: заявка.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"Не удалось уведомить куратора: {e}")


async def notify_curator_status_change(bot: Bot, curator_telegram_id: int,
                                       student_name: str, referral_name: str,
                                       new_status: str, amount: int):
    """Уведомить куратора об изменении статуса."""
    if new_status == "contract":
        text = (
            f"📝 Абитуриент <b>{referral_name}</b> (привёл {student_name}) "
            f"подписал договор. Вам начислено <b>{amount} ₽</b>."
        )
    elif new_status == "enrolled":
        text = (
            f"🎓 <b>{referral_name}</b> начал учиться. "
            f"Вам начислено ещё <b>{amount} ₽</b>."
        )
    else:
        return  # куратора уведомляем только при contract / enrolled
    try:
        await bot.send_message(curator_telegram_id, text, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Не удалось уведомить куратора: {e}")
