"""
Хендлеры модуля куратора:
- Рефералы своей группы
- Баланс куратора
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import database as db
from config import STATUSES

router = Router()


# ─── Рефералы группы куратора ────────────────────────────────
@router.callback_query(F.data == "group_referrals")
async def cb_group_referrals(callback: CallbackQuery):
    student = await db.get_student_by_telegram_id(callback.from_user.id)
    if not student or student["role"] != "curator":
        await callback.answer("Доступно только кураторам.", show_alert=True)
        return

    referrals = await db.get_referrals_by_group(student["group_name"])

    if not referrals:
        text = f"В группе {student['group_name']} пока нет рефералов."
    else:
        lines = [f"👥 <b>Рефералы группы {student['group_name']}</b> ({len(referrals)}):\n"]
        for i, r in enumerate(referrals, 1):
            status_label = STATUSES.get(r["status"], r["status"])
            emoji = {"new": "📋", "consultation": "💬", "contract": "📝", "enrolled": "🎓"}.get(r["status"], "•")
            lines.append(
                f"{i}. {r['full_name']} — {emoji} {status_label}\n"
                f"   Привёл: {r.get('referrer_name', '?')}"
            )
        text = "\n".join(lines)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_menu")]
    ])
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


# ─── Баланс куратора ─────────────────────────────────────────
@router.callback_query(F.data == "curator_balance")
async def cb_curator_balance(callback: CallbackQuery):
    student = await db.get_student_by_telegram_id(callback.from_user.id)
    if not student or student["role"] != "curator":
        await callback.answer("Доступно только кураторам.", show_alert=True)
        return

    earned = student["balance_earned"]
    paid = student["balance_paid"]
    pending = earned - paid

    payments = await db.get_payments_by_recipient(student["id"])
    curator_payments = [p for p in payments if "curator" in p["type"]]

    lines = [
        f"💰 <b>Баланс куратора</b> ({student['group_name']})\n",
        f"Начислено: <b>{earned} ₽</b>",
        f"Выплачено: {paid} ₽",
        f"К выплате: <b>{pending} ₽</b>",
    ]

    if curator_payments:
        lines.append("\n📊 <b>Детализация (кураторские):</b>")
        for p in curator_payments[:10]:
            label = "Договор" if "contract" in p["type"] else "Зачисление"
            status = "✅" if p["status"] == "paid" else "⏳"
            lines.append(f"  {status} {p.get('referral_name', '?')} — {label}: {p['amount']} ₽")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_menu")]
    ])
    await callback.message.answer("\n".join(lines), parse_mode="HTML", reply_markup=kb)
    await callback.answer()
