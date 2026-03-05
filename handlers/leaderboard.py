"""
Формирование текста лидерборда.
"""
import database as db


async def build_leaderboard_text(student: dict | None = None) -> str:
    """Сформировать текст лидерборда групп + студентов."""
    lines = []

    # ─── ТОП групп ───────────────────────────────────
    groups = await db.leaderboard_groups(limit=10)
    lines.append("🏆 <b>Лидерборд групп</b>\n")
    if groups:
        for i, g in enumerate(groups, 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
            lines.append(f"{medal} {g['group_name']} — {g['cnt']} рефералов")

        # Показать позицию группы студента, если не в ТОП-10
        if student:
            rank = await db.get_group_rank(student["group_name"])
            if rank and rank > 10:
                lines.append(f"\n📍 Твоя группа ({student['group_name']}): {rank}-е место")
    else:
        lines.append("Пока нет данных. Будь первым!")

    lines.append("")

    # ─── ТОП студентов ───────────────────────────────
    students = await db.leaderboard_students(limit=10)
    lines.append("👤 <b>Лидерборд студентов</b>\n")
    if students:
        for i, s in enumerate(students, 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
            lines.append(f"{medal} {s['full_name']} ({s['group_name']}) — {s['cnt']}")

        # Показать позицию студента, если не в ТОП-10
        if student:
            rank = await db.get_student_rank(student["id"])
            if rank and rank > 10:
                lines.append(f"\n📍 Ты: {rank}-е место")
    else:
        lines.append("Пока нет данных.")

    return "\n".join(lines)
