"""
Экспорт данных в Excel (.xlsx) через openpyxl.
"""
import io
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

from config import STATUSES


HEADER_FILL = PatternFill(start_color="2E75B6", end_color="2E75B6", fill_type="solid")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
THIN_BORDER = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin"),
)


def _style_header(ws, headers: list[str]):
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center")
        cell.border = THIN_BORDER


async def export_full_report(referrals: list[dict], payments: list[dict]) -> io.BytesIO:
    """
    Экспорт в Excel: лист «Абитуриенты» и лист «Начисления».
    Возвращает BytesIO с .xlsx.
    """
    wb = Workbook()

    # ─── Лист «Абитуриенты» ──────────────────────────
    ws1 = wb.active
    ws1.title = "Абитуриенты"
    headers1 = ["ID", "ФИО абитуриента", "Телефон", "Класс", "Школа",
                 "Статус", "Реферер", "Группа реферера", "Дата заявки"]
    _style_header(ws1, headers1)
    for i, r in enumerate(referrals, 2):
        ws1.cell(row=i, column=1, value=r["id"]).border = THIN_BORDER
        ws1.cell(row=i, column=2, value=r["full_name"]).border = THIN_BORDER
        ws1.cell(row=i, column=3, value=r["phone"]).border = THIN_BORDER
        ws1.cell(row=i, column=4, value=r.get("grade", "")).border = THIN_BORDER
        ws1.cell(row=i, column=5, value=r.get("school", "")).border = THIN_BORDER
        ws1.cell(row=i, column=6, value=STATUSES.get(r["status"], r["status"])).border = THIN_BORDER
        ws1.cell(row=i, column=7, value=r.get("referrer_name", "")).border = THIN_BORDER
        ws1.cell(row=i, column=8, value=r.get("group_name", "")).border = THIN_BORDER
        ws1.cell(row=i, column=9, value=r["created_at"]).border = THIN_BORDER

    for col in range(1, len(headers1) + 1):
        ws1.column_dimensions[chr(64 + col)].width = 18

    # ─── Лист «Начисления» ───────────────────────────
    ws2 = wb.create_sheet("Начисления")
    headers2 = ["ID", "Получатель", "За абитуриента", "Сумма (₽)",
                 "Тип", "Статус", "Дата начисления", "Дата выплаты"]
    _style_header(ws2, headers2)
    type_labels = {
        "contract_referrer": "Договор (студент)",
        "contract_curator": "Договор (куратор)",
        "enrolled_referrer": "Зачисление (студент)",
        "enrolled_curator": "Зачисление (куратор)",
    }
    for i, p in enumerate(payments, 2):
        ws2.cell(row=i, column=1, value=p["id"]).border = THIN_BORDER
        ws2.cell(row=i, column=2, value=p.get("recipient_name", "")).border = THIN_BORDER
        ws2.cell(row=i, column=3, value=p.get("referral_name", "")).border = THIN_BORDER
        ws2.cell(row=i, column=4, value=p["amount"]).border = THIN_BORDER
        ws2.cell(row=i, column=5, value=type_labels.get(p["type"], p["type"])).border = THIN_BORDER
        ws2.cell(row=i, column=6, value="Выплачено" if p["status"] == "paid" else "К выплате").border = THIN_BORDER
        ws2.cell(row=i, column=7, value=p["created_at"]).border = THIN_BORDER
        ws2.cell(row=i, column=8, value=p.get("paid_at", "")).border = THIN_BORDER

    for col in range(1, len(headers2) + 1):
        ws2.column_dimensions[chr(64 + col)].width = 20

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
