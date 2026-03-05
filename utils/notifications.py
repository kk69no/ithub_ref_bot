"""
Утилиты для уведомлений.
"""
from aiogram import Bot
from config import ADMIN_IDS


async def notify_new_referral(bot: Bot, referral: dict, referrer: dict):
    """Уведомить админов о новом реферале."""
    text = (
        f"📋 <b>Новый реферал!</b>\n\n"
        f"👤 {referral['full_name']}\n"
        f"📞 {referral['phone']}\n"
        f"🎓 Класс: {referral.get('grade', '?')}\n"
        f"🏫 Школа: {referral.get('school', '?')}\n\n"
        f"🔗 Привёл: {referrer['full_name']} ({referrer['group_name']})"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception:
            pass


async def notify_student_new_referral(bot: Bot, telegram_id: int, applicant_name: str):
    """Уведомить студента что кто-то заполнил заявку по его ссылке."""
    try:
        await bot.send_message(
            telegram_id,
            f"🎉 <b>Новый реферал!</b>\n\n"
            f"<b>{applicant_name}</b> заполнил заявку по твоей ссылке.\n"
            f"Мы свяжемся с ним — следи за статусом!",
            parse_mode="HTML",
        )
    except Exception:
        pass


async def notify_curator_new_referral(
    bot: Bot, curator_tg_id: int,
    referrer_name: str, applicant_name: str,
):
    """Уведомить куратора о новом реферале в его группе."""
    try:
        await bot.send_message(
            curator_tg_id,
            f"📋 <b>Новый реферал в группе</b>\n\n"
            f"Студент <b>{referrer_name}</b> привёл <b>{applicant_name}</b>.",
            parse_mode="HTML",
        )
    except Exception:
        pass
