"""
Лидерборд — ТОП групп и студентов по рефералам.
"""
import database as db


async def build_leaderboard_text(student: dict | None = None) -> str:
    """Собрать текст лидерборда для отправки."""
    groups = await db.leaderboard_groups(limit=10)
    students = await db.leaderboard_students(limit=10)

    lines = ["🏆 <b>Лидерборд</b>\n"]

    # --- ТОП групп ---
    if groups:
        lines.append("<b>👥 ТОП групп:</b>")
        for i, g in enumerate(groups, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            lines.append(f"  {medal} {g['group_name']} — {g['cnt']} реф.")
    else:
        lines.append("<i>Пока нет данных по группам</i>")

    lines.append("")

    # --- ТОП студентов ---
    if students:
        lines.append("<b>🎯 ТОП студентов:</b>")
        for i, s in enumerate(students, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            lines.append(f"  {medal} {s['full_name']} ({s['group_name']}) — {s['cnt']} реф.")
    else:
        lines.append("<i>Пока нет данных по студентам</i>")

    # Если передан студент — показать его позицию
    if student:
        rank = await db.get_student_rank(student["id"])
        group_rank = await db.get_group_rank(student["group_name"])
        lines.append("")
        if rank:
            lines.append(f"📍 Ты на <b>{rank}</b> месте среди студентов")
        if group_rank:
            lines.append(f"📍 Твоя группа на <b>{group_rank}</b> месте")

    return "\n".join(lines)
