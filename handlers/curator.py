"""
Хендлеры куратора:
- Рефералы группы
- Баланс куратора
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import database as db
from config import STATUSES, STATUS_EMOJI

router = Router()


# ─── Рефералы группы ─────────────────────────────────────────
@router.callback_query(F.data == "group_referrals")
async def cb_group_referrals(callback: CallbackQuery):
    student = await db.get_student_by_telegram_id(callback.from_user.id)
    if not student or student["role"] != "curator":
        await callback.answer("Доступно только кураторам", show_alert=True)
        return

    referrals = await db.get_referrals_by_group(student["group_name"])

    if not referrals:
        text = (
            f"📊 <b>Рефералы группы {student['group_name']}</b>\n\n"
            "Пока нет рефералов."
        )
    else:
        # Группируем по статусу
        by_status: dict[str, list] = {}
        for r in referrals:
            st = r["status"]
            by_status.setdefault(st, []).append(r)

        lines = [f"📊 <b>Рефералы группы {student['group_name']}</b> ({len(referrals)})\n"]

        for st_key in ("new", "consultation", "contract", "enrolled"):
            refs = by_status.get(st_key, [])
            if refs:
                emoji = STATUS_EMOJI.get(st_key, "•")
                label = STATUSES.get(st_key, st_key)
                lines.append(f"\n{emoji} <b>{label}</b> ({len(refs)}):")
                for r in refs:
                    lines.append(f"  • {r['full_name']} (от {r.get('referrer_name', '?')})")

        text = "\n".join(lines)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_menu")]
    ])
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


# ─── Баланс куратора ──────────────────────────────────────────
@router.callback_query(F.data == "curator_balance")
async def cb_curator_balance(callback: CallbackQuery):
    student = await db.get_student_by_telegram_id(callback.from_user.id)
    if not student or student["role"] != "curator":
        await callback.answer("Доступно только кураторам", show_alert=True)
        return

    payments = await db.get_payments_by_recipient(student["id"])
    # Считаем только кураторские выплаты
    curator_payments = [p for p in payments if "curator" in p.get("type", "")]

    total = sum(p["amount"] for p in curator_payments)
    paid = sum(p["amount"] for p in curator_payments if p["status"] == "paid")
    pending = total - paid

    lines = [
        f"💰 <b>Баланс куратора</b>\n",
        f"┌ Начислено:  <b>{total} ₽</b>",
        f"├ Выплачено:  {paid} ₽",
        f"└ К выплате:  <b>{pending} ₽</b>",
    ]

    if curator_payments:
        lines.append("\n📊 <b>Последние начисления:</b>")
        for p in curator_payments[:10]:
            icon = "✅" if p["status"] == "paid" else "⏳"
            lines.append(f"  {icon} {p.get('referral_name', '?')} — {p['amount']} ₽")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_menu")]
    ])
    await callback.message.answer("\n".join(lines), parse_mode="HTML", reply_markup=kb)
    await callback.answer()
