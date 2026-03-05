"""
Модуль базы данных — SQLite через aiosqlite.
Таблицы: students, referrals, payments.
"""
import aiosqlite
import string
import random
from datetime import datetime

from config import DATABASE_PATH

DB_PATH = DATABASE_PATH


# ═══════════════════════════════════════════════════════════════
#  ИНИЦИАЛИЗАЦИЯ
# ═══════════════════════════════════════════════════════════════

async def init_db():
    """Создать таблицы, если их нет."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id     INTEGER UNIQUE,
                full_name       TEXT NOT NULL,
                group_name      TEXT NOT NULL,
                curator_id      INTEGER REFERENCES students(id),
                ref_code        TEXT UNIQUE NOT NULL,
                ref_link        TEXT NOT NULL,
                role            TEXT NOT NULL DEFAULT 'student'
                                CHECK(role IN ('student','curator','admin')),
                balance_earned  INTEGER NOT NULL DEFAULT 0,
                balance_paid    INTEGER NOT NULL DEFAULT 0,
                created_at      TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id       INTEGER NOT NULL REFERENCES students(id),
                telegram_id       INTEGER,
                full_name         TEXT NOT NULL,
                phone             TEXT UNIQUE NOT NULL,
                grade             TEXT,
                school            TEXT,
                status            TEXT NOT NULL DEFAULT 'new'
                                  CHECK(status IN ('new','consultation','contract','enrolled')),
                status_updated_at TEXT,
                created_at        TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient_id  INTEGER NOT NULL REFERENCES students(id),
                referral_id   INTEGER NOT NULL REFERENCES referrals(id),
                amount        INTEGER NOT NULL,
                type          TEXT NOT NULL
                              CHECK(type IN ('contract_referrer','contract_curator',
                                             'enrolled_referrer','enrolled_curator')),
                status        TEXT NOT NULL DEFAULT 'pending'
                              CHECK(status IN ('pending','paid')),
                created_at    TEXT NOT NULL DEFAULT (datetime('now')),
                paid_at       TEXT
            )
        """)
        await db.commit()


def _generate_ref_code(length: int = 6) -> str:
    """Сгенерировать случайный реферальный код."""
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


# ═══════════════════════════════════════════════════════════════
#  СТУДЕНТЫ
# ═══════════════════════════════════════════════════════════════

async def get_student_by_telegram_id(telegram_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM students WHERE telegram_id = ?", (telegram_id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_student_by_ref_code(ref_code: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM students WHERE ref_code = ?", (ref_code,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_student_by_id(student_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM students WHERE id = ?", (student_id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def find_student_by_name_and_group(full_name: str, group_name: str) -> dict | None:
    """Найти предзагруженного студента по ФИО и группе (без telegram_id)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT * FROM students
               WHERE LOWER(full_name) = LOWER(?) AND LOWER(group_name) = LOWER(?)""",
            (full_name.strip(), group_name.strip()),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def register_student_telegram(student_id: int, telegram_id: int):
    """Привязать Telegram ID к существующему студенту."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE students SET telegram_id = ? WHERE id = ?",
            (telegram_id, student_id),
        )
        await db.commit()


async def add_student(full_name: str, group_name: str, role: str = "student",
                      telegram_id: int | None = None, curator_id: int | None = None) -> dict:
    """Добавить нового студента в базу. Возвращает запись."""
    from config import REF_LINK_TEMPLATE
    ref_code = _generate_ref_code()
    ref_link = REF_LINK_TEMPLATE.format(ref_code=ref_code)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO students (telegram_id, full_name, group_name, curator_id,
                                    ref_code, ref_link, role)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (telegram_id, full_name.strip(), group_name.strip(),
             curator_id, ref_code, ref_link, role),
        )
        await db.commit()
        student_id = cur.lastrowid

    return await get_student_by_id(student_id)


async def get_all_students() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM students ORDER BY group_name, full_name")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_students_by_group(group_name: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM students WHERE LOWER(group_name) = LOWER(?)",
            (group_name.strip(),),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_students_with_telegram() -> list[dict]:
    """Все студенты с привязанным Telegram."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM students WHERE telegram_id IS NOT NULL"
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_curators() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM students WHERE role = 'curator'"
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_curator_for_group(group_name: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT * FROM students
               WHERE role = 'curator' AND LOWER(group_name) = LOWER(?)""",
            (group_name.strip(),),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


# ═══════════════════════════════════════════════════════════════
#  РЕФЕРАЛЫ (абитуриенты)
# ═══════════════════════════════════════════════════════════════

async def get_referral_by_phone(phone: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM referrals WHERE phone = ?", (phone,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_referral_by_id(referral_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM referrals WHERE id = ?", (referral_id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def add_referral(referrer_id: int, full_name: str, phone: str,
                       grade: str, school: str, telegram_id: int | None = None) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO referrals (referrer_id, telegram_id, full_name, phone, grade, school)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (referrer_id, telegram_id, full_name.strip(), phone.strip(),
             grade, school.strip()),
        )
        await db.commit()
        ref_id = cur.lastrowid
    return await get_referral_by_id(ref_id)


async def get_referrals_by_referrer(referrer_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM referrals WHERE referrer_id = ? ORDER BY created_at DESC",
            (referrer_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_referrals_by_group(group_name: str) -> list[dict]:
    """Рефералы всех студентов определённой группы."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT r.*, s.full_name AS referrer_name, s.group_name
               FROM referrals r
               JOIN students s ON r.referrer_id = s.id
               WHERE LOWER(s.group_name) = LOWER(?)
               ORDER BY r.created_at DESC""",
            (group_name.strip(),),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def update_referral_status(referral_id: int, new_status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE referrals SET status = ?, status_updated_at = ?
               WHERE id = ?""",
            (new_status, datetime.now().isoformat(), referral_id),
        )
        await db.commit()


async def get_all_referrals(status_filter: str | None = None,
                            group_filter: str | None = None) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """SELECT r.*, s.full_name AS referrer_name, s.group_name
                   FROM referrals r
                   JOIN students s ON r.referrer_id = s.id WHERE 1=1"""
        params = []
        if status_filter:
            query += " AND r.status = ?"
            params.append(status_filter)
        if group_filter:
            query += " AND LOWER(s.group_name) = LOWER(?)"
            params.append(group_filter.strip())
        query += " ORDER BY r.created_at DESC"
        cur = await db.execute(query, params)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def search_referrals(query: str) -> list[dict]:
    """Поиск по имени или телефону."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT r.*, s.full_name AS referrer_name, s.group_name
               FROM referrals r
               JOIN students s ON r.referrer_id = s.id
               WHERE LOWER(r.full_name) LIKE LOWER(?) OR r.phone LIKE ?
               ORDER BY r.created_at DESC""",
            (f"%{query}%", f"%{query}%"),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════
#  ПЛАТЕЖИ
# ═══════════════════════════════════════════════════════════════

async def add_payment(recipient_id: int, referral_id: int,
                      amount: int, pay_type: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO payments (recipient_id, referral_id, amount, type)
               VALUES (?, ?, ?, ?)""",
            (recipient_id, referral_id, amount, pay_type),
        )
        # Обновляем баланс получателя
        await db.execute(
            "UPDATE students SET balance_earned = balance_earned + ? WHERE id = ?",
            (amount, recipient_id),
        )
        await db.commit()
        pay_id = cur.lastrowid

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM payments WHERE id = ?", (pay_id,))
        row = await cur.fetchone()
        return dict(row)


async def get_payments_by_recipient(recipient_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT p.*, r.full_name AS referral_name
               FROM payments p
               JOIN referrals r ON p.referral_id = r.id
               WHERE p.recipient_id = ?
               ORDER BY p.created_at DESC""",
            (recipient_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_all_payments(status_filter: str | None = None) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """SELECT p.*, s.full_name AS recipient_name, r.full_name AS referral_name
                   FROM payments p
                   JOIN students s ON p.recipient_id = s.id
                   JOIN referrals r ON p.referral_id = r.id WHERE 1=1"""
        params = []
        if status_filter:
            query += " AND p.status = ?"
            params.append(status_filter)
        query += " ORDER BY p.created_at DESC"
        cur = await db.execute(query, params)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def mark_payment_paid(payment_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        # Получаем данные платежа
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
        pay = await cur.fetchone()
        if pay and pay["status"] == "pending":
            await db.execute(
                "UPDATE payments SET status = 'paid', paid_at = ? WHERE id = ?",
                (datetime.now().isoformat(), payment_id),
            )
            await db.execute(
                "UPDATE students SET balance_paid = balance_paid + ? WHERE id = ?",
                (pay["amount"], pay["recipient_id"]),
            )
            await db.commit()


async def check_payment_exists(referral_id: int, pay_type: str) -> bool:
    """Проверить, что начисление данного типа уже было."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM payments WHERE referral_id = ? AND type = ?",
            (referral_id, pay_type),
        )
        return (await cur.fetchone()) is not None


# ═══════════════════════════════════════════════════════════════
#  ЛИДЕРБОРД
# ═══════════════════════════════════════════════════════════════

async def leaderboard_groups(limit: int = 10) -> list[dict]:
    """ТОП групп по количеству рефералов со статусом >= contract."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT s.group_name, COUNT(r.id) AS cnt
               FROM referrals r
               JOIN students s ON r.referrer_id = s.id
               WHERE r.status IN ('contract', 'enrolled')
               GROUP BY s.group_name
               ORDER BY cnt DESC
               LIMIT ?""",
            (limit,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def leaderboard_students(limit: int = 10) -> list[dict]:
    """ТОП студентов по количеству рефералов со статусом >= contract."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT s.id, s.full_name, s.group_name, COUNT(r.id) AS cnt
               FROM referrals r
               JOIN students s ON r.referrer_id = s.id
               WHERE r.status IN ('contract', 'enrolled')
               GROUP BY s.id
               ORDER BY cnt DESC
               LIMIT ?""",
            (limit,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_group_rank(group_name: str) -> int | None:
    """Позиция группы в рейтинге."""
    board = await leaderboard_groups(limit=999)
    for i, row in enumerate(board, 1):
        if row["group_name"].lower() == group_name.lower():
            return i
    return None


async def get_student_rank(student_id: int) -> int | None:
    """Позиция студента в рейтинге."""
    board = await leaderboard_students(limit=999)
    for i, row in enumerate(board, 1):
        if row["id"] == student_id:
            return i
    return None


# ═══════════════════════════════════════════════════════════════
#  СТАТИСТИКА (для админ-дашборда)
# ═══════════════════════════════════════════════════════════════

async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        total = (await (await db.execute("SELECT COUNT(*) FROM referrals")).fetchone())[0]
        by_status = {}
        for st in ("new", "consultation", "contract", "enrolled"):
            cnt = (await (await db.execute(
                "SELECT COUNT(*) FROM referrals WHERE status = ?", (st,)
            )).fetchone())[0]
            by_status[st] = cnt

        total_earned = (await (await db.execute(
            "SELECT COALESCE(SUM(amount),0) FROM payments"
        )).fetchone())[0]
        total_paid = (await (await db.execute(
            "SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='paid'"
        )).fetchone())[0]

    return {
        "total_referrals": total,
        "by_status": by_status,
        "total_earned": total_earned,
        "total_paid": total_paid,
    }
