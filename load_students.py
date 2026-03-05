"""
Скрипт для предзагрузки списка студентов и кураторов из CSV-файла.

Формат CSV (с заголовками):
  full_name,group_name,role
  Иванов Иван Иванович,ИС-11,student
  Петрова Мария Петровна,ИС-11,curator

role: student / curator

Запуск:
  python load_students.py students.csv
"""
import asyncio
import csv
import sys

from database import init_db, add_student, get_curator_for_group, find_student_by_name_and_group


async def load_csv(filepath: str):
    await init_db()

    added = 0
    skipped = 0

    with open(filepath, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Первый проход — добавляем кураторов
    for row in rows:
        role = row.get("role", "student").strip().lower()
        if role != "curator":
            continue
        full_name = row["full_name"].strip()
        group_name = row["group_name"].strip()

        existing = await find_student_by_name_and_group(full_name, group_name)
        if existing:
            skipped += 1
            continue

        await add_student(full_name=full_name, group_name=group_name, role="curator")
        added += 1
        print(f"  [КУРАТОР] {full_name} — {group_name}")

    # Второй проход — добавляем студентов и привязываем к кураторам
    for row in rows:
        role = row.get("role", "student").strip().lower()
        if role == "curator":
            continue
        full_name = row["full_name"].strip()
        group_name = row["group_name"].strip()

        existing = await find_student_by_name_and_group(full_name, group_name)
        if existing:
            skipped += 1
            continue

        curator = await get_curator_for_group(group_name)
        curator_id = curator["id"] if curator else None

        await add_student(
            full_name=full_name,
            group_name=group_name,
            role="student",
            curator_id=curator_id,
        )
        added += 1

    print(f"\nГотово! Добавлено: {added}, пропущено (уже есть): {skipped}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python load_students.py <путь_к_csv>")
        sys.exit(1)
    asyncio.run(load_csv(sys.argv[1]))
