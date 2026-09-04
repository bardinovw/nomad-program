"""
Отмечает задачу выполненной и обновляет прогресс темы в knowledge_map.
Работает с облачной базой Postgres (Supabase) — DATABASE_URL должна быть задана.
"""

import sys
from db import get_connection


def mark_done(task_id: int):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT title, day_number FROM tasks WHERE task_id = %s", (task_id,))
    row = cur.fetchone()
    if row is None:
        print(f"Задача с task_id={task_id} не найдена.")
        conn.close()
        return

    title, day_number = row
    cur.execute("UPDATE tasks SET status = 'done' WHERE task_id = %s", (task_id,))
    print(f"Готово: {title}")

    cur.execute("SELECT theme FROM days WHERE day_number = %s", (day_number,))
    theme = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(*) FROM tasks
        JOIN days USING (day_number)
        WHERE days.theme = %s AND tasks.status != 'done'
        """,
        (theme,),
    )
    remaining = cur.fetchone()[0]

    if remaining == 0:
        cur.execute("UPDATE knowledge_map SET status = 'learned' WHERE theme = %s", (theme,))
        print(f"Тема освоена: {theme}")
    else:
        cur.execute(
            "UPDATE knowledge_map SET status = 'in_progress' WHERE theme = %s AND status = 'not_started'",
            (theme,),
        )
        print(f"Осталось задач по теме '{theme}': {remaining}")

    conn.commit()
    conn.close()


def show_progress():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT theme, status FROM knowledge_map")
    print("\nПрогресс по темам:")
    for theme, status in cur.fetchall():
        print(f"  [{status}] {theme}")
    conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python mark_done.py <task_id>")
        sys.exit(1)

    task_id = int(sys.argv[1])
    mark_done(task_id)
    show_progress()