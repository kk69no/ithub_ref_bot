"""
Загрузка студентов из CSV.

CSV формат (без заголовков или с заголовками):
  ФИО,Группа,Роль

Роль: student / curator (по умолчанию student)

Пример:
  Тестов Ислам Тестович,ИС-11,curator
  Иванов Иван Иванович,ИС-11,student

Скрипт:
  1) Сначала грузит кураторов
  2) Потом студентов, автоматически привязывая к куратору группы
"""
import csv
import sys
import asyncio
from pathlib import Path

import database as db


async def load_csv(csv_path: str):
    await db.init_db()

    path = Path(csv_path)
    if not path.exists():
        print(f"Файл не найден: {csv_path}")
        return

    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for line in reader:
            if not line or not line[0].strip():
                continue
            name = line[0].strip()
            group = line[1].strip() if len(line) > 1 else ""
            role = line[2].strip().lower() if len(line) > 2 else "student"
            if role not in ("student", "curator"):
                role = "student"
            rows.append((name, group, role))

    if not rows:
        print("CSV пуст")
        return

    # 1. Кураторы
    curators = [r for r in rows if r[2] == "curator"]
    students = [r for r in rows if r[2] == "student"]

    added = 0
    skipped = 0

    for name, group, role in curators:
        existing = await db.find_student_by_name_and_group(name, group)
        if existing:
            skipped += 1
            continue
        await db.add_student(full_name=name, group_name=group, role="curator")
        print(f"  [КУРАТОР] {name} — {group}")
        added += 1

    # 2. Студенты
    for name, group, role in students:
        existing = await db.find_student_by_name_and_group(name, group)
        if existing:
            skipped += 1
            continue
        curator = await db.get_curator_for_group(group)
        curator_id = curator["id"] if curator else None
        await db.add_student(full_name=name, group_name=group, role="student",
                             curator_id=curator_id)
        added += 1

    print(f"Готово! Добавлено: {added}, пропущено (уже есть): {skipped}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python load_students.py <файл.csv>")
        sys.exit(1)
    asyncio.run(load_csv(sys.argv[1]))
