"""
Конфигурация бота реферальной программы IThub Нальчик.
"""
import os

# ─── Telegram ───────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
BOT_USERNAME = os.getenv("BOT_USERNAME", "ithub_nalchik_ref_bot")

# ─── Админы (Telegram ID) ──────────────────────────────────
ADMIN_IDS: list[int] = [
    int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
]

# ─── Чат для уведомлений админам ────────────────────────────
ADMIN_NOTIFY_CHAT_ID = int(os.getenv("ADMIN_NOTIFY_CHAT_ID", "0"))

# ─── База данных ────────────────────────────────────────────
DATABASE_PATH = os.getenv("DATABASE_PATH", "ithub_ref.db")

# ─── Реферальная ссылка ─────────────────────────────────────
REF_LINK_TEMPLATE = f"https://t.me/{BOT_USERNAME}?start={{ref_code}}"

# ─── OAuth через newlxp ────────────────────────────────────
NEWLXP_URL = os.getenv("NEWLXP_URL", "https://newlxp.ru")
NEWLXP_AUTH_URL = NEWLXP_URL + "/telegram-auth?token={token}"
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8443"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "ithub-ref-bot-secret-key-2026")

# ─── Выплаты ────────────────────────────────────────────────
PAYMENT_CONTRACT_STUDENT = 1000
PAYMENT_CONTRACT_CURATOR = 500
PAYMENT_ENROLLED_STUDENT = 4000
PAYMENT_ENROLLED_CURATOR = 500

# ─── QR-код ─────────────────────────────────────────────────
QR_SIZE = 300
QR_LOGO_PATH = os.getenv("QR_LOGO_PATH", "logo.png")

# ─── Статусы абитуриентов ───────────────────────────────────
STATUSES = {
    "new": "📋 заявка",
    "consultation": "💬 консультация",
    "contract": "📝 договор",
    "enrolled": "🎓 учится",
}

STATUS_EMOJI = {
    "new": "📋",
    "consultation": "💬",
    "contract": "📝",
    "enrolled": "🎓",
}

STATUS_ORDER = ["new", "consultation", "contract", "enrolled"]
