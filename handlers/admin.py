"""Admin panel handlers for status management, payments, analytics and exports."""

import io
import json
from datetime import datetime
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, Document
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import get_db, fuzzy_find_students, get_student_by_id, get_student_referrals
from config import (
    ADMIN_IDS, ADMIN_NOTIFY_CHAT_ID, STATUSES, STATUS_ORDER,
    PAYMENT_MIN, PAYMENT_MAX, PAYMENT_DEFAULT, STATUS_EMOJI
)
from utils.notifications import notify_admin, notify_student, notify_curator
from utils.excel_export import export_full_report

router = Router()


class AdminStates(StatesGroup):
    """States for admin operations."""
    search_student = State()
    select_student = State()
    change_status = State()
    manual_payment = State()
    payment_amount = State()
    payment_reason = State()
    broadcast_message = State()
    add_student_name = State()
    add_student_group = State()
    add_student_email = State()


def admin_only(func):
    """Decorator to check admin access."""
    async def wrapper(query_or_msg):
        user_id = query_or_msg.from_user.id if hasattr(query_or_msg, 'from_user') else query_or_msg.user_id
        if user_id not in ADMIN_IDS:
            await query_or_msg.answer("❌ Доступ запрещен", show_alert=True)
            return
        return await func(query_or_msg)
    return wrapper


async def admin_menu_keyboard():
    """Build admin menu keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Поиск студента", callback_data="admin_search")],
        [InlineKeyboardButton(text="💰 Реестр платежей", callback_data="admin_payments")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📥 Экспорт", callback_data="admin_export")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="➕ Добавить студента", callback_data="admin_add_student")],
    ])


@router.callback_query(F.data == "admin_menu")
async def admin_menu_callback(query: CallbackQuery):
    """Show admin menu."""
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("❌ Доступ запрещен", show_alert=True)
        return

    keyboard = await admin_menu_keyboard()
    await query.message.edit_text(
        "🔐 *Админ-панель*\n\nВыберите действие:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await query.answer()


@router.callback_query(F.data == "admin_search")
async def admin_search_callback(query: CallbackQuery, state: FSMContext):
    """Start student search."""
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("❌ Доступ запрещен", show_alert=True)
        return

    await state.set_state(AdminStates.search_student)
    await query.message.edit_text(
        "🔍 Введите имя или ID студента для поиска:",
        parse_mode="Markdown"
    )
    await query.answer()


@router.message(AdminStates.search_student)
async def search_student_handler(message: Message, state: FSMContext):
    """Handle student search."""
    if message.from_user.id not in ADMIN_IDS:
        return

    db = await get_db()

    try:
        search_query = message.text.strip()
        students = await fuzzy_find_students(db, search_query, limit=10)

        if not students:
            await message.answer("❌ Студентов не найдено")
            return

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{s['name']} (ID: {s['user_id']})",
                callback_data=f"admin_student:{s['user_id']}"
            )]
            for s in students
        ])

        await message.answer(
            "📋 Найденные студенты:",
            reply_markup=keyboard
        )
        await state.clear()

    finally:
        await db.close()


@router.callback_query(F.data.startswith("admin_student:"))
async def admin_student_callback(query: CallbackQuery, state: FSMContext):
    """Show student admin panel."""
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("❌ Доступ запрещен", show_alert=True)
        return

    user_id = int(query.data.split(":")[1])
    db = await get_db()

    try:
        student = await get_student_by_id(db, user_id)
        if not student:
            await query.answer("❌ Студент не найден", show_alert=True)
            return

        referrals = await get_student_referrals(db, user_id)

        text = f"👤 *{student['name']}*\n\n"
        text += f"ID: `{user_id}`\n"
        text += f"Группа: *{student['group']}*\n"
        text += f"Email: `{student['email']}`\n"
        text += f"Статус: {STATUS_EMOJI.get(student['status'], '•')} {student['status']}\n"
        text += f"Рефералов: *{len(referrals)}*\n"

        # Count referrals by status
        for status in STATUSES:
            count = len([r for r in referrals if r['status'] == status])
            if count > 0:
                text += f"  {STATUS_EMOJI.get(status, '•')} {status}: {count}\n"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Изменить статус", callback_data=f"admin_change_status:{user_id}")],
            [InlineKeyboardButton(text="💸 Ручная выплата", callback_data=f"admin_manual_payment:{user_id}")],
            [InlineKeyboardButton(text="📋 Рефералы", callback_data=f"student_referrals:{user_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")],
        ])

        await query.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

    finally:
        await db.close()

    await query.answer()


@router.callback_query(F.data.startswith("admin_change_status:"))
async def admin_change_status_callback(query: CallbackQuery, state: FSMContext):
    """Show status change options."""
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("❌ Доступ запрещен", show_alert=True)
        return

    user_id = int(query.data.split(":")[1])

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{STATUS_EMOJI.get(status, '•')} {status}",
            callback_data=f"confirm_status:{user_id}:{i}"
        )]
        for i, status in enumerate(STATUS_ORDER)
    ] + [[InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin_student:{user_id}")]])

    await query.message.edit_text(
        "🔄 Выберите новый статус:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await query.answer()


@router.callback_query(F.data.startswith("confirm_status:"))
async def confirm_status_callback(query: CallbackQuery):
    """Confirm and apply status change with auto-payment."""
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("❌ Доступ запрещен", show_alert=True)
        return

    parts = query.data.split(":")
    user_id = int(parts[1])
    status_idx = int(parts[2])

    new_status = STATUS_ORDER[status_idx]

    db = await get_db()

    try:
        student = await get_student_by_id(db, user_id)
        old_status = student['status']

        # Update student status
        await db.execute(
            "UPDATE students SET status = ? WHERE user_id = ?",
            [new_status, user_id]
        )

        # Auto-payment if status changed to accepted
        payment_made = False
        if new_status == "✅ Принят" and old_status != "✅ Принят":
            amount = PAYMENT_DEFAULT
            await db.execute(
                """
                INSERT INTO payments (user_id, amount, reason, status, created_at)
                VALUES (?, ?, ?, 'completed', ?)
                """,
                [user_id, amount, "Автоматическая выплата при принятии", datetime.now().isoformat()]
            )
            payment_made = True

        # Handle "Оплачен" status
        if new_status == "💸 Оплачен":
            # Check if payment exists
            payment = await db.fetchone(
                "SELECT * FROM payments WHERE user_id = ? AND status = 'completed' ORDER BY created_at DESC LIMIT 1",
                [user_id]
            )
            if not payment:
                # Create payment if not exists
                await db.execute(
                    """
                    INSERT INTO payments (user_id, amount, reason, status, created_at)
                    VALUES (?, ?, ?, 'completed', ?)
                    """,
                    [user_id, PAYMENT_DEFAULT, "Выплата при смене статуса", datetime.now().isoformat()]
                )
                payment_made = True

        await db.commit()

        # Notify student
        await notify_student(
            user_id,
            f"✅ Ваш статус обновлен: {new_status}\n" +
            (f"💰 Вам выплачено: {PAYMENT_DEFAULT}₽" if payment_made else "")
        )

        # Notify admin
        await notify_admin(
            f"📝 Статус {student['name']} изменен на {new_status}\n" +
            (f"💰 Автоматическая выплата: {PAYMENT_DEFAULT}₽" if payment_made else "")
        )

        await query.answer("✅ Статус изменен", show_alert=True)

        # Return to student panel
        await admin_student_callback(query, None)

    finally:
        await db.close()


@router.callback_query(F.data.startswith("admin_manual_payment:"))
async def admin_manual_payment_callback(query: CallbackQuery, state: FSMContext):
    """Start manual payment flow."""
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("❌ Доступ запрещен", show_alert=True)
        return

    user_id = int(query.data.split(":")[1])
    await state.update_data(payment_user_id=user_id)
    await state.set_state(AdminStates.payment_amount)

    await query.message.edit_text(
        f"💸 Введите сумму выплаты (мин: {PAYMENT_MIN}, макс: {PAYMENT_MAX}):",
        parse_mode="Markdown"
    )
    await query.answer()


@router.message(AdminStates.payment_amount)
async def payment_amount_handler(message: Message, state: FSMContext):
    """Handle payment amount input."""
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        amount = float(message.text)
        if amount < PAYMENT_MIN or amount > PAYMENT_MAX:
            await message.answer(f"❌ Сумма должна быть от {PAYMENT_MIN} до {PAYMENT_MAX}")
            return

        await state.update_data(payment_amount=amount)
        await state.set_state(AdminStates.payment_reason)
        await message.answer("📝 Введите причину выплаты:")

    except ValueError:
        await message.answer("❌ Введите корректное число")


@router.message(AdminStates.payment_reason)
async def payment_reason_handler(message: Message, state: FSMContext):
    """Handle payment reason and create payment."""
    if message.from_user.id not in ADMIN_IDS:
        return

    data = await state.get_data()
    user_id = data['payment_user_id']
    amount = data['payment_amount']
    reason = message.text

    db = await get_db()

    try:
        # Create payment
        await db.execute(
            """
            INSERT INTO payments (user_id, amount, reason, status, created_at)
            VALUES (?, ?, ?, 'completed', ?)
            """,
            [user_id, amount, reason, datetime.now().isoformat()]
        )
        await db.commit()

        student = await get_student_by_id(db, user_id)

        # Notify student
        await notify_student(user_id, f"💰 Вам выплачено: {amount}₽\nПричина: {reason}")

        # Notify admin
        await notify_admin(f"✅ Выплата {student['name']}: {amount}₽\nПричина: {reason}")

        await message.answer(f"✅ Выплата {amount}₽ выполнена для {student['name']}")

    finally:
        await db.close()

    await state.clear()


@router.callback_query(F.data == "admin_payments")
async def admin_payments_callback(query: CallbackQuery):
    """Show payment registry."""
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("❌ Доступ запрещен", show_alert=True)
        return

    db = await get_db()

    try:
        payments = await db.fetchall(
            """
            SELECT p.*, s.name FROM payments p
            JOIN students s ON p.user_id = s.user_id
            ORDER BY p.created_at DESC
            LIMIT 50
            """
        )

        text = "💰 *Реестр платежей (последние 50)*\n\n"

        total = 0
        for p in payments:
            total += p['amount']
            status_emoji = "✅" if p['status'] == "completed" else "⏳"
            text += f"{status_emoji} {p['name']}: {p['amount']}₽ ({p['reason']})\n"

        text += f"\n*Всего: {total}₽*"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")],
        ])

        await query.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

    finally:
        await db.close()

    await query.answer()


@router.callback_query(F.data == "admin_stats")
async def admin_stats_callback(query: CallbackQuery):
    """Show statistics dashboard."""
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("❌ Доступ запрещен", show_alert=True)
        return

    db = await get_db()

    try:
        # Get stats
        total_students = await db.fetchval("SELECT COUNT(*) FROM students")
        total_referrals = await db.fetchval("SELECT COUNT(*) FROM referrals")
        total_payments = await db.fetchval("SELECT SUM(amount) FROM payments WHERE status = 'completed'") or 0

        # Count by status
        status_counts = await db.fetchall(
            "SELECT status, COUNT(*) as count FROM students GROUP BY status"
        )

        text = "📊 *Статистика*\n\n"
        text += f"👥 Студентов: *{total_students}*\n"
        text += f"🔗 Рефералов: *{total_referrals}*\n"
        text += f"💰 Выплачено: *{total_payments}₽*\n\n"

        text += "*По статусам:*\n"
        for sc in status_counts:
            emoji = STATUS_EMOJI.get(sc['status'], '•')
            text += f"{emoji} {sc['status']}: {sc['count']}\n"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")],
        ])

        await query.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

    finally:
        await db.close()

    await query.answer()


@router.callback_query(F.data == "admin_export")
async def admin_export_callback(query: CallbackQuery):
    """Export data to Excel."""
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("❌ Доступ запрещен", show_alert=True)
        return

    db = await get_db()

    try:
        # Generate Excel report
        xlsx_data = await export_full_report(db)

        # Send as document
        await query.message.answer_document(
            document=xlsx_data,
            caption="📥 Полный отчет"
        )
        await query.answer("✅ Экспорт завершен")

    finally:
        await db.close()


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_callback(query: CallbackQuery, state: FSMContext):
    """Start broadcast flow."""
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("❌ Доступ запрещен", show_alert=True)
        return

    await state.set_state(AdminStates.broadcast_message)
    await query.message.edit_text(
        "📢 Введите сообщение для рассылки всем студентам:"
    )
    await query.answer()


@router.message(AdminStates.broadcast_message)
async def broadcast_message_handler(message: Message, state: FSMContext):
    """Send broadcast to all students."""
    if message.from_user.id not in ADMIN_IDS:
        return

    db = await get_db()

    try:
        students = await db.fetchall("SELECT user_id FROM students")

        sent = 0
        for student in students:
            try:
                await notify_student(student['user_id'], message.text)
                sent += 1
            except Exception:
                pass

        await message.answer(f"✅ Рассылка отправлена {sent} студентам")

    finally:
        await db.close()

    await state.clear()


@router.callback_query(F.data == "admin_add_student")
async def admin_add_student_callback(query: CallbackQuery, state: FSMContext):
    """Start add student flow."""
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("❌ Доступ запрещен", show_alert=True)
        return

    await state.set_state(AdminStates.add_student_name)
    await query.message.edit_text("👤 Введите имя студента:")
    await query.answer()


@router.message(AdminStates.add_student_name)
async def add_student_name_handler(message: Message, state: FSMContext):
    """Handle student name."""
    if message.from_user.id not in ADMIN_IDS:
        return

    await state.update_data(add_name=message.text)
    await state.set_state(AdminStates.add_student_group)
    await message.answer("📚 Введите группу:")


@router.message(AdminStates.add_student_group)
async def add_student_group_handler(message: Message, state: FSMContext):
    """Handle student group."""
    if message.from_user.id not in ADMIN_IDS:
        return

    await state.update_data(add_group=message.text)
    await state.set_state(AdminStates.add_student_email)
    await message.answer("📧 Введите email:")


@router.message(AdminStates.add_student_email)
async def add_student_email_handler(message: Message, state: FSMContext):
    """Handle student email and create account."""
    if message.from_user.id not in ADMIN_IDS:
        return

    data = await state.get_data()

    db = await get_db()

    try:
        # Check if email exists
        existing = await db.fetchone("SELECT * FROM students WHERE email = ?", [message.text])
        if existing:
            await message.answer("❌ Студент с таким email уже существует")
            return

        # Create new student
        import uuid
        new_user_id = int(uuid.uuid4().int % 1000000000)

        await db.execute(
            """
            INSERT INTO students (user_id, name, group, email, status, created_at)
            VALUES (?, ?, ?, ?, '📋 заявка', ?)
            """,
            [new_user_id, data['add_name'], data['add_group'], message.text, datetime.now().isoformat()]
        )
        await db.commit()

        await message.answer(
            f"✅ Студент добавлен\n"
            f"ID: `{new_user_id}`\n"
            f"Имя: {data['add_name']}\n"
            f"Группа: {data['add_group']}\n"
            f"Email: {message.text}",
            parse_mode="Markdown"
        )

        # Notify admin
        await notify_admin(f"➕ Добавлен новый студент: {data['add_name']}")

    finally:
        await db.close()

    await state.clear()
