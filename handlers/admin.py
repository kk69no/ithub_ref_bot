"""
Админ-панель:
- Изменение статусов абитуриентов (с автоматическим начислением)
- Все заявки (фильтры, поиск)
- Реестр выплат
- Выгрузка в Excel
- Статистика (дашборд)
- Рассылка
- Добавление студента
"""
import io
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, BufferedInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from config import (
    ADMIN_IDS, STATUSES, STATUS_ORDER,
    PAYMENT_CONTRACT_STUDENT, PAYMENT_CONTRACT_CURATOR,
    PAYMENT_ENROLLED_STUDENT, PAYMENT_ENROLLED_CURATOR,
)
from utils.notifications import (
    notify_student_status_change, notify_curator_status_change,
)
from utils.excel_export import export_full_report

router = Router()


# ─── Фильтр: только админы ──────────────────────────────────
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ─── FSM для админ-действий ─────────────────────────────────
class AdminStates(StatesGroup):
    search_query = State()
    broadcast_target = State()
    broadcast_text = State()
    add_student_name = State()
    add_student_group = State()
    add_student_role = State()


# ─── /admin — главное меню админа ────────────────────────────
ADMIN_MENU_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📋 Все заявки", callback_data="adm_all_referrals")],
    [InlineKeyboardButton(text="🔍 Поиск", callback_data="adm_search")],
    [InlineKeyboardButton(text="💳 Реестр выплат", callback_data="adm_payments")],
    [InlineKeyboardButton(text="📊 Статистика", callback_data="adm_stats")],
    [InlineKeyboardButton(text="📥 Выгрузка Excel", callback_data="adm_export")],
    [InlineKeyboardButton(text="📢 Рассылка", callback_data="adm_broadcast")],
    [InlineKeyboardButton(text="➕ Добавить студента", callback_data="adm_add_student")],
])


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа.")
        return
    await message.answer(
        "🔧 <b>Админ-панель</b>",
        parse_mode="HTML",
        reply_markup=ADMIN_MENU_KB,
    )


# ─── Все заявки ──────────────────────────────────────────────
@router.callback_query(F.data == "adm_all_referrals")
async def cb_all_referrals(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return

    # Показываем фильтры по статусу
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📋 {STATUSES[s]}", callback_data=f"adm_filter_{s}")]
        for s in STATUS_ORDER
    ] + [
        [InlineKeyboardButton(text="Все статусы", callback_data="adm_filter_all")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm_back")],
    ])
    await callback.message.answer("Фильтр по статусу:", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("adm_filter_"))
async def cb_filter_referrals(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    status_key = callback.data.replace("adm_filter_", "")
    status_filter = None if status_key == "all" else status_key
    referrals = await db.get_all_referrals(status_filter=status_filter)

    if not referrals:
        await callback.message.answer("Нет заявок с таким фильтром.")
        await callback.answer()
        return

    # Показываем до 20 записей
    lines = [f"📋 <b>Заявки</b> ({len(referrals)} всего):\n"]
    for r in referrals[:20]:
        status_label = STATUSES.get(r["status"], r["status"])
        lines.append(
            f"• <b>{r['full_name']}</b> ({r['phone']})\n"
            f"  Статус: {status_label} | Реферер: {r.get('referrer_name', '?')} ({r.get('group_name', '')})"
        )

    # Кнопки для изменения статуса
    kb_buttons = []
    for r in referrals[:10]:
        kb_buttons.append([InlineKeyboardButton(
            text=f"✏️ {r['full_name']} [{STATUSES.get(r['status'], '')}]",
            callback_data=f"adm_status_{r['id']}",
        )])
    kb_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="adm_back")])

    await callback.message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons),
    )
    await callback.answer()


# ─── Изменение статуса ───────────────────────────────────────
@router.callback_query(F.data.startswith("adm_status_"))
async def cb_change_status_select(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    referral_id = int(callback.data.replace("adm_status_", ""))
    referral = await db.get_referral_by_id(referral_id)
    if not referral:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return

    current_idx = STATUS_ORDER.index(referral["status"]) if referral["status"] in STATUS_ORDER else 0
    # Показать только следующие статусы
    available = STATUS_ORDER[current_idx + 1:]

    if not available:
        await callback.answer("Этот абитуриент уже на максимальном статусе.", show_alert=True)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"→ {STATUSES[s]}",
            callback_data=f"adm_set_{referral_id}_{s}",
        )]
        for s in available
    ] + [[InlineKeyboardButton(text="❌ Отмена", callback_data="adm_back")]])

    await callback.message.answer(
        f"Изменить статус <b>{referral['full_name']}</b>\n"
        f"Текущий: {STATUSES.get(referral['status'], referral['status'])}\n\n"
        f"Выберите новый статус:",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_set_"))
async def cb_set_status(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return

    parts = callback.data.replace("adm_set_", "").split("_", 1)
    referral_id = int(parts[0])
    new_status = parts[1]

    referral = await db.get_referral_by_id(referral_id)
    if not referral:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return

    # Обновляем статус
    await db.update_referral_status(referral_id, new_status)

    # ─── Автоначисление при contract / enrolled ──────
    referrer = await db.get_student_by_id(referral["referrer_id"])
    student_amount = 0
    curator_amount = 0

    if new_status == "contract":
        # Проверяем, что ещё не начисляли
        if not await db.check_payment_exists(referral_id, "contract_referrer"):
            await db.add_payment(referrer["id"], referral_id,
                                 PAYMENT_CONTRACT_STUDENT, "contract_referrer")
            student_amount = PAYMENT_CONTRACT_STUDENT

        curator = await db.get_curator_for_group(referrer["group_name"])
        if curator and not await db.check_payment_exists(referral_id, "contract_curator"):
            await db.add_payment(curator["id"], referral_id,
                                 PAYMENT_CONTRACT_CURATOR, "contract_curator")
            curator_amount = PAYMENT_CONTRACT_CURATOR

    elif new_status == "enrolled":
        if not await db.check_payment_exists(referral_id, "enrolled_referrer"):
            await db.add_payment(referrer["id"], referral_id,
                                 PAYMENT_ENROLLED_STUDENT, "enrolled_referrer")
            student_amount = PAYMENT_ENROLLED_STUDENT

        curator = await db.get_curator_for_group(referrer["group_name"])
        if curator and not await db.check_payment_exists(referral_id, "enrolled_curator"):
            await db.add_payment(curator["id"], referral_id,
                                 PAYMENT_ENROLLED_CURATOR, "enrolled_curator")
            curator_amount = PAYMENT_ENROLLED_CURATOR

    # ─── Уведомления ─────────────────────────────────
    if referrer and referrer.get("telegram_id") and student_amount:
        await notify_student_status_change(
            bot, referrer["telegram_id"],
            referral["full_name"], new_status, student_amount,
        )

    if new_status in ("contract", "enrolled"):
        curator = await db.get_curator_for_group(referrer["group_name"])
        if curator and curator.get("telegram_id") and curator_amount:
            await notify_curator_status_change(
                bot, curator["telegram_id"],
                referrer["full_name"], referral["full_name"],
                new_status, curator_amount,
            )

    status_label = STATUSES.get(new_status, new_status)
    pay_info = ""
    if student_amount:
        pay_info += f"\n💰 Начислено студенту: {student_amount} ₽"
    if curator_amount:
        pay_info += f"\n💰 Начислено куратору: {curator_amount} ₽"

    await callback.message.answer(
        f"✅ Статус <b>{referral['full_name']}</b> изменён на «{status_label}».{pay_info}",
        parse_mode="HTML",
    )
    await callback.answer()


# ─── Поиск ───────────────────────────────────────────────────
@router.callback_query(F.data == "adm_search")
async def cb_search(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStates.search_query)
    await callback.message.answer("🔍 Введите имя или телефон для поиска:")
    await callback.answer()


@router.message(AdminStates.search_query)
async def process_search(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    results = await db.search_referrals(message.text.strip())
    await state.clear()

    if not results:
        await message.answer("Ничего не найдено.")
        return

    lines = [f"🔍 Результаты ({len(results)}):\n"]
    kb_buttons = []
    for r in results[:10]:
        status_label = STATUSES.get(r["status"], r["status"])
        lines.append(
            f"• <b>{r['full_name']}</b> ({r['phone']})\n"
            f"  Статус: {status_label} | Реферер: {r.get('referrer_name', '?')}"
        )
        kb_buttons.append([InlineKeyboardButton(
            text=f"✏️ {r['full_name']}",
            callback_data=f"adm_status_{r['id']}",
        )])

    kb_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="adm_back")])
    await message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons),
    )


# ─── Реестр выплат ───────────────────────────────────────────
@router.callback_query(F.data == "adm_payments")
async def cb_payments(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏳ К выплате", callback_data="adm_pay_pending")],
        [InlineKeyboardButton(text="✅ Выплачено", callback_data="adm_pay_paid")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm_back")],
    ])
    await callback.message.answer("Реестр выплат — выберите фильтр:", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("adm_pay_"))
async def cb_payments_filter(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    status = callback.data.replace("adm_pay_", "")
    payments = await db.get_all_payments(status_filter=status)

    if not payments:
        await callback.message.answer("Нет записей.")
        await callback.answer()
        return

    type_labels = {
        "contract_referrer": "Договор (студ.)",
        "contract_curator": "Договор (кур.)",
        "enrolled_referrer": "Зачисл. (студ.)",
        "enrolled_curator": "Зачисл. (кур.)",
    }

    lines = [f"💳 <b>Выплаты [{status}]</b> ({len(payments)}):\n"]
    kb_buttons = []
    for p in payments[:15]:
        label = type_labels.get(p["type"], p["type"])
        lines.append(
            f"• {p.get('recipient_name', '?')} — {p['amount']} ₽ ({label})\n"
            f"  За: {p.get('referral_name', '?')}"
        )
        if status == "pending":
            kb_buttons.append([InlineKeyboardButton(
                text=f"✅ Выплатить: {p.get('recipient_name', '?')} {p['amount']}₽",
                callback_data=f"adm_markpaid_{p['id']}",
            )])

    kb_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="adm_back")])
    await callback.message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_markpaid_"))
async def cb_mark_paid(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    payment_id = int(callback.data.replace("adm_markpaid_", ""))
    await db.mark_payment_paid(payment_id)
    await callback.message.answer(f"✅ Платёж #{payment_id} отмечен как выплаченный.")
    await callback.answer()


# ─── Статистика ──────────────────────────────────────────────
@router.callback_query(F.data == "adm_stats")
async def cb_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    stats = await db.get_stats()
    bs = stats["by_status"]

    # Конверсия
    total = stats["total_referrals"]
    conv_consult = f"{bs['consultation'] / total * 100:.0f}%" if total else "—"
    conv_contract = f"{bs['contract'] / total * 100:.0f}%" if total else "—"
    conv_enrolled = f"{bs['enrolled'] / total * 100:.0f}%" if total else "—"

    text = (
        f"📊 <b>Статистика</b>\n\n"
        f"📋 Всего заявок: <b>{total}</b>\n"
        f"  • Новые: {bs['new']}\n"
        f"  • Консультация: {bs['consultation']}\n"
        f"  • Договор: {bs['contract']}\n"
        f"  • Учится: {bs['enrolled']}\n\n"
        f"📈 Конверсия:\n"
        f"  Заявка → Консультация: {conv_consult}\n"
        f"  Заявка → Договор: {conv_contract}\n"
        f"  Заявка → Учится: {conv_enrolled}\n\n"
        f"💰 Начислено всего: <b>{stats['total_earned']} ₽</b>\n"
        f"💸 Выплачено: {stats['total_paid']} ₽\n"
        f"⏳ К выплате: {stats['total_earned'] - stats['total_paid']} ₽"
    )

    # ТОП-3 группы
    top_groups = await db.leaderboard_groups(3)
    if top_groups:
        text += "\n\n🏆 ТОП-3 группы:"
        for i, g in enumerate(top_groups, 1):
            text += f"\n  {i}. {g['group_name']} — {g['cnt']}"

    top_students = await db.leaderboard_students(3)
    if top_students:
        text += "\n\n👤 ТОП-3 студента:"
        for i, s in enumerate(top_students, 1):
            text += f"\n  {i}. {s['full_name']} — {s['cnt']}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm_back")]
    ])
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


# ─── Выгрузка Excel ──────────────────────────────────────────
@router.callback_query(F.data == "adm_export")
async def cb_export(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    referrals = await db.get_all_referrals()
    payments = await db.get_all_payments()

    buf = await export_full_report(referrals, payments)
    file = BufferedInputFile(buf.read(), filename="ithub_referrals_report.xlsx")

    await callback.message.answer_document(
        document=file,
        caption="📥 Отчёт по реферальной программе",
    )
    await callback.answer()


# ─── Рассылка ────────────────────────────────────────────────
@router.callback_query(F.data == "adm_broadcast")
async def cb_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍🎓 Всем студентам", callback_data="adm_bc_students")],
        [InlineKeyboardButton(text="👨‍🏫 Всем кураторам", callback_data="adm_bc_curators")],
        [InlineKeyboardButton(text="📋 Всем абитуриентам", callback_data="adm_bc_applicants")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm_back")],
    ])
    await callback.message.answer("📢 Кому отправить рассылку?", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("adm_bc_"))
async def cb_broadcast_target(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    target = callback.data.replace("adm_bc_", "")
    await state.update_data(broadcast_target=target)
    await state.set_state(AdminStates.broadcast_text)
    await callback.message.answer(
        "✏️ Введите текст рассылки (поддерживается HTML-разметка):"
    )
    await callback.answer()


@router.message(AdminStates.broadcast_text)
async def process_broadcast(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    target = data["broadcast_target"]
    text = message.text

    await state.clear()

    sent = 0
    failed = 0

    if target == "students":
        recipients = await db.get_students_with_telegram()
        for s in recipients:
            try:
                await bot.send_message(s["telegram_id"], text, parse_mode="HTML")
                sent += 1
            except Exception:
                failed += 1

    elif target == "curators":
        curators = await db.get_curators()
        for c in curators:
            if c.get("telegram_id"):
                try:
                    await bot.send_message(c["telegram_id"], text, parse_mode="HTML")
                    sent += 1
                except Exception:
                    failed += 1

    elif target == "applicants":
        # У абитуриентов может быть telegram_id
        all_refs = await db.get_all_referrals()
        for r in all_refs:
            if r.get("telegram_id"):
                try:
                    await bot.send_message(r["telegram_id"], text, parse_mode="HTML")
                    sent += 1
                except Exception:
                    failed += 1

    await message.answer(
        f"📢 Рассылка завершена.\n"
        f"✅ Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}"
    )


# ─── Добавление студента ────────────────────────────────────
@router.callback_query(F.data == "adm_add_student")
async def cb_add_student(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStates.add_student_name)
    await callback.message.answer("Введите <b>ФИО</b> нового студента:", parse_mode="HTML")
    await callback.answer()


@router.message(AdminStates.add_student_name)
async def process_add_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(new_student_name=message.text.strip())
    await state.set_state(AdminStates.add_student_group)
    await message.answer("Введите <b>группу</b>:", parse_mode="HTML")


@router.message(AdminStates.add_student_group)
async def process_add_group(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(new_student_group=message.text.strip())
    await state.set_state(AdminStates.add_student_role)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Студент", callback_data="adm_role_student")],
        [InlineKeyboardButton(text="Куратор", callback_data="adm_role_curator")],
    ])
    await message.answer("Выберите роль:", reply_markup=kb)


@router.callback_query(AdminStates.add_student_role, F.data.startswith("adm_role_"))
async def process_add_role(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    role = callback.data.replace("adm_role_", "")
    data = await state.get_data()
    await state.clear()

    student = await db.add_student(
        full_name=data["new_student_name"],
        group_name=data["new_student_group"],
        role=role,
    )

    await callback.message.answer(
        f"✅ Добавлен: <b>{student['full_name']}</b>\n"
        f"Группа: {student['group_name']}\n"
        f"Роль: {role}\n"
        f"Реф-код: <code>{student['ref_code']}</code>",
        parse_mode="HTML",
    )
    await callback.answer()


# ─── Назад в админ-меню ─────────────────────────────────────
@router.callback_query(F.data == "adm_back")
async def cb_admin_back(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.answer(
        "🔧 <b>Админ-панель</b>",
        parse_mode="HTML",
        reply_markup=ADMIN_MENU_KB,
    )
    await callback.answer()
