"""
Excel-экспорт: студенты, рефералы, платежи — три листа.
"""
import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

import database as db


async def export_full_report() -> io.BytesIO:
    """Сформировать полный XLSX-отчёт. Возвращает BytesIO."""
    wb = Workbook()
    if "Sheet" in wb.sheetnames:
        wb.remove(wb["Sheet"])

    await _sheet_students(wb)
    await _sheet_referrals(wb)
    await _sheet_payments(wb)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ── Студенты ──────────────────────────────────────────────────

async def _sheet_students(wb: Workbook):
    ws = wb.create_sheet("Студенты")
    headers = ["ID", "ФИО", "Группа", "Роль", "Telegram", "Реф.код",
               "Баланс", "Выплачено", "Рефералов"]
    ws.append(headers)
    _style_headers(ws, len(headers))

    students = await db.get_all_students()
    for s in students:
        refs = await db.get_referrals_by_referrer(s["id"])
        ws.append([
            s["id"],
            s["full_name"],
            s["group_name"],
            s["role"],
            s.get("telegram_id") or "",
            s["ref_code"],
            s["balance_earned"],
            s["balance_paid"],
            len(refs),
        ])
    _auto_width(ws)


# ── Рефералы ─────────────────────────────────────────────────

async def _sheet_referrals(wb: Workbook):
    ws = wb.create_sheet("Рефералы")
    headers = ["ID", "ФИО", "Телефон", "Класс", "Школа", "Статус",
               "Привёл", "Группа", "Дата"]
    ws.append(headers)
    _style_headers(ws, len(headers))

    referrals = await db.get_all_referrals()
    for r in referrals:
        ws.append([
            r["id"],
            r["full_name"],
            r["phone"],
            r.get("grade", ""),
            r.get("school", ""),
            r["status"],
            r.get("referrer_name", ""),
            r.get("group_name", ""),
            r.get("created_at", ""),
        ])
    _auto_width(ws)


# ── Платежи ───────────────────────────────────────────────────

async def _sheet_payments(wb: Workbook):
    ws = wb.create_sheet("Платежи")
    headers = ["ID", "Получатель", "Реферал", "Сумма", "Тип", "Статус", "Дата"]
    ws.append(headers)
    _style_headers(ws, len(headers))

    payments = await db.get_all_payments()
    for p in payments:
        ws.append([
            p["id"],
            p.get("recipient_name", ""),
            p.get("referral_name", ""),
            p["amount"],
            p["type"],
            p["status"],
            p.get("created_at", ""),
        ])
    _auto_width(ws)


# ── Стили ─────────────────────────────────────────────────────

HEADER_FILL = PatternFill("solid", fgColor="366092")
HEADER_FONT = Font(bold=True, color="FFFFFF")
HEADER_ALIGN = Alignment(horizontal="center", vertical="center", wrap_text=True)
THIN_BORDER = Border(
    left=Side("thin"), right=Side("thin"),
    top=Side("thin"), bottom=Side("thin"),
)


def _style_headers(ws, col_count: int):
    for col in range(1, col_count + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = HEADER_ALIGN
        cell.border = THIN_BORDER


def _auto_width(ws):
    for column in ws.columns:
        letter = get_column_letter(column[0].column)
        max_len = max((len(str(c.value or "")) for c in column), default=0)
        ws.column_dimensions[letter].width = min(max_len + 3, 50)
