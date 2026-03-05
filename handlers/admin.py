"""
Админ-панель:
- /admin — главное меню
- Поиск студентов (fuzzy)
- Просмотр рефералов студента
- Смена статуса реферала + автоначисление
- Реестр платежей, отметка «выплачено»
- Статистика
- Excel-экспорт
- Рассылка
- Ручное добавление студента
"""
from aiogram import Router, F, Bot
from aiogram.types import (
    CallbackQuery, Message,
    InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from config import (
    ADMIN_IDS, STATUSES, STATUS_ORDER, STATUS_EMOJI,
    PAYMENT_CONTRACT_STUDENT, PAYMENT_CONTRACT_CURATOR,
    PAYMENT_ENROLLED_STUDENT, PAYMENT_ENROLLED_CURATOR,
)

router = Router()


class AdminStates(StatesGroup):
    search_query = State()
    broadcast_text = State()
    add_student_name = State()
    add_student_group = State()
    add_student_role = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ═══════════════════════════════════════════════════
#  ГЛАВНОЕ МЕНЮ
# ═══════════════════════════════════════════════════

def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Поиск студента", callback_data="adm_search")],
        [InlineKeyboardButton(text="📋 Все рефералы", callback_data="adm_referrals")],
        [InlineKeyboardButton(text="💰 Платежи", callback_data="adm_payments")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="adm_stats")],
        [InlineKeyboardButton(text="📥 Excel-экспорт", callback_data="adm_export")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="adm_broadcast")],
        [InlineKeyboardButton(text="➕ Добавить студента", callback_data="adm_add_student")],
    ])


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "🔐 <b>Админ-панель</b>\n\nВыберите действие:",
        parse_mode="HTML", reply_markup=admin_menu_kb(),
    )


@router.callback_query(F.data == "adm_menu")
async def cb_admin_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.message.edit_text(
        "🔐 <b>Админ-панель</b>\n\nВыберите действие:",
        parse_mode="HTML", reply_markup=admin_menu_kb(),
    )
    await callback.answer()


# ═══════════════════════════════════════════════════
#  ПОИСК СТУДЕНТА
# ═══════════════════════════════════════════════════

@router.callback_query(F.data == "adm_search")
async def cb_adm_search(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStates.search_query)
    await callback.message.edit_text("🔍 Введите ФИО студента для поиска:")
    await callback.answer()


@router.message(AdminStates.search_query)
async def process_search(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()

    results = await db.fuzzy_find_students(message.text.strip())
    if not results:
        # Попробуем найти среди всех студентов
        all_students = await db.get_all_students()
        query_lower = message.text.strip().lower()
        results = [s for s in all_students if query_lower in s["full_name"].lower()][:5]

    if not results:
        await message.answer(
            "❌ Студентов не найдено.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="adm_menu")]
            ]),
        )
        return

    buttons = []
    for s in results:
        tg = "✅" if s.get("telegram_id") else "❌"
        buttons.append([InlineKeyboardButton(
            text=f"{tg} {s['full_name']} ({s['group_name']})",
            callback_data=f"adm_student:{s['id']}",
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="adm_menu")])

    await message.answer(
        f"📋 Найдено: {len(results)}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


# ═══════════════════════════════════════════════════
#  ПРОФИЛЬ СТУДЕНТА
# ═══════════════════════════════════════════════════

@router.callback_query(F.data.startswith("adm_student:"))
async def cb_student_profile(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    student_id = int(callback.data.split(":")[1])
    student = await db.get_student_by_id(student_id)
    if not student:
        await callback.answer("Студент не найден", show_alert=True)
        return

    referrals = await db.get_referrals_by_referrer(student_id)

    tg_status = f"tg: <code>{student['telegram_id']}</code>" if student.get("telegram_id") else "tg: не привязан"
    lines = [
        f"👤 <b>{student['full_name']}</b>",
        f"📚 Группа: {student['group_name']}",
        f"🏷 Роль: {student['role']}",
        f"🔗 Реф. код: <code>{student['ref_code']}</code>",
        f"💰 Баланс: {student['balance_earned']} ₽ (выплачено: {student['balance_paid']} ₽)",
        f"📱 {tg_status}",
        f"👥 Рефералов: {len(referrals)}",
    ]

    # Счёт по статусам
    if referrals:
        for st_key in STATUS_ORDER:
            cnt = len([r for r in referrals if r["status"] == st_key])
            if cnt:
                lines.append(f"  {STATUS_EMOJI.get(st_key, '•')} {STATUSES[st_key]}: {cnt}")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Рефералы", callback_data=f"adm_refs:{student_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm_menu")],
    ])

    await callback.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=kb)
    await callback.answer()


# ═══════════════════════════════════════════════════
#  РЕФЕРАЛЫ СТУДЕНТА
# ═══════════════════════════════════════════════════

@router.callback_query(F.data.startswith("adm_refs:"))
async def cb_student_referrals(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    student_id = int(callback.data.split(":")[1])
    referrals = await db.get_referrals_by_referrer(student_id)
    student = await db.get_student_by_id(student_id)

    if not referrals:
        await callback.message.edit_text(
            f"👥 У {student['full_name'] if student else '?'} нет рефералов.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_student:{student_id}")],
            ]),
        )
        await callback.answer()
        return

    buttons = []
    for r in referrals:
        emoji = STATUS_EMOJI.get(r["status"], "•")
        buttons.append([InlineKeyboardButton(
            text=f"{emoji} {r['full_name']} — {STATUSES.get(r['status'], r['status'])}",
            callback_data=f"adm_ref:{r['id']}",
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_student:{student_id}")])

    await callback.message.edit_text(
        f"👥 <b>Рефералы {student['full_name'] if student else '?'}</b>:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await callback.answer()


# ═══════════════════════════════════════════════════
#  СМЕНА СТАТУСА РЕФЕРАЛА + АВТОНАЧИСЛЕНИЕ
# ═══════════════════════════════════════════════════

@router.callback_query(F.data.startswith("adm_ref:"))
async def cb_referral_detail(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    ref_id = int(callback.data.split(":")[1])
    ref = await db.get_referral_by_id(ref_id)
    if not ref:
        await callback.answer("Реферал не найден", show_alert=True)
        return

    referrer = await db.get_student_by_id(ref["referrer_id"])
    emoji = STATUS_EMOJI.get(ref["status"], "•")

    lines = [
        f"📋 <b>Реферал #{ref['id']}</b>",
        f"👤 {ref['full_name']}",
        f"📞 {ref['phone']}",
        f"🎓 Класс: {ref.get('grade', '?')}",
        f"🏫 Школа: {ref.get('school', '?')}",
        f"{emoji} Статус: <b>{STATUSES.get(ref['status'], ref['status'])}</b>",
        f"🔗 Привёл: {referrer['full_name'] if referrer else '?'}",
    ]

    # Кнопки смены статуса — только следующие статусы
    current_idx = STATUS_ORDER.index(ref["status"]) if ref["status"] in STATUS_ORDER else -1
    status_buttons = []
    for i, st_key in enumerate(STATUS_ORDER):
        if i > current_idx:
            status_buttons.append(InlineKeyboardButton(
                text=f"{STATUS_EMOJI[st_key]} → {STATUSES[st_key]}",
                callback_data=f"adm_setstatus:{ref_id}:{st_key}",
            ))

    kb_rows = []
    if status_buttons:
        kb_rows.append(status_buttons)
    kb_rows.append([InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=f"adm_refs:{ref['referrer_id']}",
    )])

    await callback.message.edit_text(
        "\n".join(lines), parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_setstatus:"))
async def cb_set_status(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    parts = callback.data.split(":")
    ref_id = int(parts[1])
    new_status = parts[2]

    ref = await db.get_referral_by_id(ref_id)
    if not ref:
        await callback.answer("Реферал не найден", show_alert=True)
        return

    old_status = ref["status"]
    await db.update_referral_status(ref_id, new_status)

    # Автоначисление при смене статуса
    referrer = await db.get_student_by_id(ref["referrer_id"])
    if referrer:
        # contract → начислить студенту и куратору
        if new_status == "contract" and old_status != "contract":
            if not await db.check_payment_exists(ref_id, "contract_referrer"):
                await db.add_payment(referrer["id"], ref_id,
                                     PAYMENT_CONTRACT_STUDENT, "contract_referrer")
                # Уведомить студента
                if referrer.get("telegram_id"):
                    try:
                        await bot.send_message(
                            referrer["telegram_id"],
                            f"🎉 <b>+{PAYMENT_CONTRACT_STUDENT} ₽!</b>\n\n"
                            f"Твой реферал <b>{ref['full_name']}</b> подписал договор!",
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass

            # Куратор
            if referrer.get("curator_id"):
                curator = await db.get_student_by_id(referrer["curator_id"])
                if curator and not await db.check_payment_exists(ref_id, "contract_curator"):
                    await db.add_payment(curator["id"], ref_id,
                                         PAYMENT_CONTRACT_CURATOR, "contract_curator")
                    if curator.get("telegram_id"):
                        try:
                            await bot.send_message(
                                curator["telegram_id"],
                                f"💰 <b>+{PAYMENT_CONTRACT_CURATOR} ₽ (куратор)</b>\n\n"
                                f"Реферал от {referrer['full_name']} подписал договор.",
                                parse_mode="HTML",
                            )
                        except Exception:
                            pass

        # enrolled → начислить студенту и куратору
        if new_status == "enrolled" and old_status != "enrolled":
            if not await db.check_payment_exists(ref_id, "enrolled_referrer"):
                await db.add_payment(referrer["id"], ref_id,
                                     PAYMENT_ENROLLED_STUDENT, "enrolled_referrer")
                if referrer.get("telegram_id"):
                    try:
                        await bot.send_message(
                            referrer["telegram_id"],
                            f"🎓 <b>+{PAYMENT_ENROLLED_STUDENT} ₽!</b>\n\n"
                            f"Твой реферал <b>{ref['full_name']}</b> зачислен!",
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass

            if referrer.get("curator_id"):
                curator = await db.get_student_by_id(referrer["curator_id"])
                if curator and not await db.check_payment_exists(ref_id, "enrolled_curator"):
                    await db.add_payment(curator["id"], ref_id,
                                         PAYMENT_ENROLLED_CURATOR, "enrolled_curator")
                    if curator.get("telegram_id"):
                        try:
                            await bot.send_message(
                                curator["telegram_id"],
                                f"🎓 <b>+{PAYMENT_ENROLLED_CURATOR} ₽ (куратор)</b>\n\n"
                                f"Реферал от {referrer['full_name']} зачислен!",
                                parse_mode="HTML",
                            )
                        except Exception:
                            pass

    await callback.answer(
        f"✅ Статус → {STATUSES.get(new_status, new_status)}", show_alert=True
    )
    # Обновляем карточку реферала
    await cb_referral_detail(callback)


# ═══════════════════════════════════════════════════
#  ВСЕ РЕФЕРАЛЫ
# ═══════════════════════════════════════════════════

@router.callback_query(F.data == "adm_referrals")
async def cb_all_referrals(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    referrals = await db.get_all_referrals()

    if not referrals:
        await callback.message.edit_text(
            "📋 Рефералов пока нет.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="adm_menu")]
            ]),
        )
        await callback.answer()
        return

    # Показать последние 20
    lines = [f"📋 <b>Все рефералы</b> ({len(referrals)})\n"]
    for r in referrals[:20]:
        emoji = STATUS_EMOJI.get(r["status"], "•")
        lines.append(
            f"  {emoji} {r['full_name']} — от {r.get('referrer_name', '?')} ({r.get('group_name', '?')})"
        )
    if len(referrals) > 20:
        lines.append(f"\n<i>...и ещё {len(referrals) - 20}</i>")

    await callback.message.edit_text(
        "\n".join(lines), parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="adm_menu")]
        ]),
    )
    await callback.answer()


# ═══════════════════════════════════════════════════
#  ПЛАТЕЖИ
# ═══════════════════════════════════════════════════

@router.callback_query(F.data == "adm_payments")
async def cb_payments(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    pending = await db.get_all_payments(status_filter="pending")
    paid = await db.get_all_payments(status_filter="paid")

    lines = [f"💰 <b>Платежи</b>\n"]
    lines.append(f"⏳ Ожидают: {len(pending)} ({sum(p['amount'] for p in pending)} ₽)")
    lines.append(f"✅ Выплачено: {len(paid)} ({sum(p['amount'] for p in paid)} ₽)")

    buttons = []
    if pending:
        lines.append("\n<b>Ожидающие выплаты:</b>")
        for p in pending[:15]:
            lines.append(f"  ⏳ {p.get('recipient_name', '?')} — {p['amount']} ₽ ({p['type']})")
            buttons.append([InlineKeyboardButton(
                text=f"✅ Выплатить: {p.get('recipient_name', '?')} {p['amount']}₽",
                callback_data=f"adm_pay:{p['id']}",
            )])

    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="adm_menu")])

    await callback.message.edit_text(
        "\n".join(lines), parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_pay:"))
async def cb_mark_paid(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    pay_id = int(callback.data.split(":")[1])
    await db.mark_payment_paid(pay_id)
    await callback.answer("✅ Отмечено как выплачено", show_alert=True)
    await cb_payments(callback)


# ═══════════════════════════════════════════════════
#  СТАТИСТИКА
# ═══════════════════════════════════════════════════

@router.callback_query(F.data == "adm_stats")
async def cb_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    stats = await db.get_stats()
    all_students = await db.get_all_students()
    registered = len([s for s in all_students if s.get("telegram_id")])

    lines = [
        "📊 <b>Статистика</b>\n",
        f"👥 Студентов в базе: <b>{len(all_students)}</b>",
        f"📱 Зарегистрировано в боте: <b>{registered}</b>",
        f"🔗 Всего рефералов: <b>{stats['total_referrals']}</b>",
        "",
        "<b>По статусам:</b>",
    ]
    for st_key in STATUS_ORDER:
        cnt = stats["by_status"].get(st_key, 0)
        lines.append(f"  {STATUS_EMOJI[st_key]} {STATUSES[st_key]}: {cnt}")

    lines.append("")
    lines.append(f"💰 Начислено всего: <b>{stats['total_earned']} ₽</b>")
    lines.append(f"✅ Выплачено: <b>{stats['total_paid']} ₽</b>")
    lines.append(f"⏳ К выплате: <b>{stats['total_earned'] - stats['total_paid']} ₽</b>")

    if stats["total_referrals"] > 0:
        conversion = stats["by_status"].get("enrolled", 0) / stats["total_referrals"] * 100
        lines.append(f"\n📈 Конверсия (зачислено): <b>{conversion:.1f}%</b>")

    await callback.message.edit_text(
        "\n".join(lines), parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="adm_menu")]
        ]),
    )
    await callback.answer()


# ═══════════════════════════════════════════════════
#  EXCEL-ЭКСПОРТ
# ═══════════════════════════════════════════════════

@router.callback_query(F.data == "adm_export")
async def cb_export(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    from utils.excel_export import export_full_report
    xlsx_bytes = await export_full_report()
    doc = BufferedInputFile(xlsx_bytes.read(), filename="ithub_report.xlsx")
    await callback.message.answer_document(doc, caption="📥 Полный отчёт")
    await callback.answer()


# ═══════════════════════════════════════════════════
#  РАССЫЛКА
# ═══════════════════════════════════════════════════

@router.callback_query(F.data == "adm_broadcast")
async def cb_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStates.broadcast_text)
    await callback.message.edit_text("📢 Введите текст рассылки (получат все студенты с Telegram):")
    await callback.answer()


@router.message(AdminStates.broadcast_text)
async def process_broadcast(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    await state.clear()

    students = await db.get_students_with_telegram()
    sent = 0
    for s in students:
        try:
            await bot.send_message(s["telegram_id"], message.text, parse_mode="HTML")
            sent += 1
        except Exception:
            pass

    await message.answer(f"✅ Рассылка отправлена: {sent}/{len(students)} студентов")


# ═══════════════════════════════════════════════════
#  ДОБАВИТЬ СТУДЕНТА
# ═══════════════════════════════════════════════════

@router.callback_query(F.data == "adm_add_student")
async def cb_add_student(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStates.add_student_name)
    await callback.message.edit_text("👤 Введите ФИО студента:")
    await callback.answer()


@router.message(AdminStates.add_student_name)
async def process_add_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(name=message.text.strip())
    await state.set_state(AdminStates.add_student_group)
    await message.answer("📚 Введите группу:")


@router.message(AdminStates.add_student_group)
async def process_add_group(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(group=message.text.strip())
    await state.set_state(AdminStates.add_student_role)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Студент", callback_data="adm_role:student")],
        [InlineKeyboardButton(text="Куратор", callback_data="adm_role:curator")],
    ])
    await message.answer("🏷 Выберите роль:", reply_markup=kb)


@router.callback_query(AdminStates.add_student_role, F.data.startswith("adm_role:"))
async def process_add_role(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    role = callback.data.split(":")[1]
    data = await state.get_data()
    await state.clear()

    # Если куратор — ищем куратора группы для привязки
    curator_id = None
    if role == "student":
        curator = await db.get_curator_for_group(data["group"])
        if curator:
            curator_id = curator["id"]

    student = await db.add_student(
        full_name=data["name"],
        group_name=data["group"],
        role=role,
        curator_id=curator_id,
    )

    await callback.message.edit_text(
        f"✅ Студент добавлен!\n\n"
        f"👤 {student['full_name']}\n"
        f"📚 {student['group_name']}\n"
        f"🏷 {student['role']}\n"
        f"🔗 <code>{student['ref_code']}</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ В админку", callback_data="adm_menu")]
        ]),
    )
    await callback.answer()
