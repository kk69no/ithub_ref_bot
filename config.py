"""
Конфигурация бота реферальной программы IThub Нальчик.
"""
import os

# ─── Telegram ───────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
BOT_USERNAME = os.getenv("BOT_USERNAME", "ithub_nalchik_ref_bot")

# ─── Админы (Telegram ID) ──────────────────────────────────
# Арсен и Ислам — прописать реальные ID
ADMIN_IDS: list[int] = [
    int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
]

# ─── Чат для уведомлений админам ────────────────────────────
ADMIN_NOTIFY_CHAT_ID = int(os.getenv("ADMIN_NOTIFY_CHAT_ID", "0"))

# ─── База данных ────────────────────────────────────────────
DATABASE_PATH = os.getenv("DATABASE_PATH", "ithub_ref.db")

# ─── Реферальная ссылка ─────────────────────────────────────
REF_LINK_TEMPLATE = f"https://t.me/{BOT_USERNAME}?start={{ref_code}}"

# ─── Выплаты ────────────────────────────────────────────────
PAYMENT_CONTRACT_STUDENT = 1000   # студенту за договор
PAYMENT_CONTRACT_CURATOR = 500    # куратору за договор
PAYMENT_ENROLLED_STUDENT = 4000   # студенту за оплату/зачисление
PAYMENT_ENROLLED_CURATOR = 500    # куратору за зачисление

# ─── QR-код ─────────────────────────────────────────────────
QR_SIZE = 300          # px
QR_LOGO_PATH = os.getenv("QR_LOGO_PATH", "logo.png")  # логотип IThub

# ─── Статусы абитуриентов ───────────────────────────────────
STATUSES = {
    "new": "заявка",
    "consultation": "консультация",
    "contract": "договор",
    "enrolled": "учится",
}

STATUS_ORDER = ["new", "consultation", "contract", "enrolled"]
