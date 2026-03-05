"""CSV loader for students with curator support."""

import csv
import asyncio
from pathlib import Path
from database import get_db
from datetime import datetime


async def load_students_from_csv(csv_path: str) -> tuple[int, list[str]]:
    """Load students from CSV file with curator support.

    CSV format:
    name,email,group,curator_id (optional),user_id (optional)

    Args:
        csv_path: Path to CSV file

    Returns:
        Tuple of (loaded_count, errors_list)
    """
    errors = []
    loaded = 0

    csv_file = Path(csv_path)
    if not csv_file.exists():
        return 0, [f"File not found: {csv_path}"]

    db = await get_db()

    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            if not reader.fieldnames:
                return 0, ["CSV file is empty"]

            required_fields = {'name', 'email', 'group'}
            if not required_fields.issubset(set(reader.fieldnames or [])):
                return 0, [f"CSV must contain columns: {', '.join(required_fields)}"]

            for row_num, row in enumerate(reader, start=2):
                try:
                    name = row.get('name', '').strip()
                    email = row.get('email', '').strip()
                    group = row.get('group', '').strip()
                    curator_id_str = row.get('curator_id', '').strip()
                    user_id_str = row.get('user_id', '').strip()

                    # Validate required fields
                    if not name or not email or not group:
                        errors.append(f"Row {row_num}: Missing required fields")
                        continue

                    # Check if student already exists
                    existing = await db.fetchone(
                        "SELECT user_id FROM students WHERE email = ?",
                        [email]
                    )
                    if existing:
                        errors.append(f"Row {row_num}: Student with email {email} already exists")
                        continue

                    # Parse user_id if provided, else generate
                    if user_id_str:
                        try:
                            user_id = int(user_id_str)
                        except ValueError:
                            errors.append(f"Row {row_num}: Invalid user_id {user_id_str}")
                            continue
                    else:
                        import uuid
                        user_id = int(uuid.uuid4().int % 1000000000)

                    # Parse curator_id if provided
                    curator_id = None
                    if curator_id_str:
                        try:
                            curator_id = int(curator_id_str)

                            # Verify curator exists
                            curator = await db.fetchone(
                                "SELECT user_id FROM students WHERE user_id = ?",
                                [curator_id]
                            )
                            if not curator:
                                errors.append(f"Row {row_num}: Curator with ID {curator_id} not found")
                                continue
                        except ValueError:
                            errors.append(f"Row {row_num}: Invalid curator_id {curator_id_str}")
                            continue

                    # Insert student
                    await db.execute(
                        """
                        INSERT INTO students (user_id, name, email, group, curator_id, status, created_at)
                        VALUES (?, ?, ?, ?, ?, '📋 заявка', ?)
                        """,
                        [user_id, name, email, group, curator_id, datetime.now().isoformat()]
                    )
                    loaded += 1

                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")

        await db.commit()

    except Exception as e:
        errors.append(f"CSV read error: {str(e)}")
    finally:
        await db.close()

    return loaded, errors


async def export_students_to_csv(output_path: str) -> tuple[int, str]:
    """Export all students to CSV file.

    Args:
        output_path: Path where to save CSV

    Returns:
        Tuple of (exported_count, status_message)
    """
    db = await get_db()

    try:
        students = await db.fetchall(
            """
            SELECT user_id, name, email, group, curator_id, status, created_at
            FROM students
            ORDER BY name
            """
        )

        if not students:
            return 0, "No students to export"

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['user_id', 'name', 'email', 'group', 'curator_id', 'status', 'created_at']
            writer = csv.DictWriter(f, fieldnames=fieldnames)

            writer.writeheader()
            for student in students:
                writer.writerow({
                    'user_id': student['user_id'],
                    'name': student['name'],
                    'email': student['email'],
                    'group': student['group'],
                    'curator_id': student['curator_id'] or '',
                    'status': student['status'],
                    'created_at': student['created_at']
                })

        return len(students), f"Exported {len(students)} students to {output_path}"

    except Exception as e:
        return 0, f"Export error: {str(e)}"
    finally:
        await db.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python load_students.py <csv_file>")
        sys.exit(1)

    csv_file = sys.argv[1]

    # Run loader
    loaded, errors = asyncio.run(load_students_from_csv(csv_file))

    print(f"\nLoaded: {loaded} students")
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for error in errors:
            print(f"  - {error}")
    else:
        print("No errors!")
