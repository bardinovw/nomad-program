"""
Отметка задачи как выполненной + обновление knowledge_map.

Использование:
    python mark_done.py <task_id>
    python mark_done.py <task_id> <task_id> <task_id> ...   (можно несколько сразу)

Логика:
- задача помечается status='done'
- если все задачи недели (theme), к которой относится задача, выполнены —
  тема в knowledge_map переводится в статус 'learned'
"""

import sqlite3
import sys
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "english_program_b1.db")


def mark_done(task_ids):
    if not os.path.exists(DB_PATH):
        print(f"База не найдена: {DB_PATH}")
        print("Сначала запусти generate_program.py")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    affected_themes = set()

    for task_id in task_ids:
        cur.execute("SELECT day_number FROM tasks WHERE task_id = ?", (task_id,))
        row = cur.fetchone()
        if row is None:
            print(f"Задача {task_id} не найдена — пропускаю")
            continue

        day_number = row[0]
        cur.execute("UPDATE tasks SET status = 'done' WHERE task_id = ?", (task_id,))
        print(f"Задача {task_id} отмечена как выполненная")

        cur.execute("SELECT theme FROM days WHERE day_number = ?", (day_number,))
        theme = cur.fetchone()[0]
        affected_themes.add(theme)

    for theme in affected_themes:
        cur.execute(
            """
            SELECT COUNT(*) FROM tasks t
            JOIN days d ON t.day_number = d.day_number
            WHERE d.theme = ? AND t.status != 'done'
            """,
            (theme,),
        )
        remaining = cur.fetchone()[0]

        if remaining == 0:
            cur.execute(
                "UPDATE knowledge_map SET status = 'learned' WHERE theme = ?",
                (theme,),
            )
            print(f"Тема «{theme}» полностью закрыта -> статус 'learned'")
        else:
            print(f"Тема «{theme}»: осталось задач — {remaining}")

    conn.commit()
    conn.close()


def show_status():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT theme, status FROM knowledge_map")
    print("\nТекущий статус тем:")
    for theme, status in cur.fetchall():
        print(f"  [{status:12}] {theme}")
    conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python mark_done.py <task_id> [<task_id> ...]")
        show_status()
        sys.exit(1)

    task_ids = [int(x) for x in sys.argv[1:]]
    mark_done(task_ids)
    show_status()