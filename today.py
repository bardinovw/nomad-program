"""
Показывает задачи на сегодня (или на конкретную дату).

Использование:
    python today.py
    python today.py 2026-09-05
"""

import sqlite3
import sys
import datetime

DB_PATH = "english_program_b1.db"


def get_target_date():
    if len(sys.argv) == 2:
        return sys.argv[1]
    return datetime.date.today().isoformat()


def show_today(target_date: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        "SELECT day_number, week, theme, is_rest FROM days WHERE date = ?",
        (target_date,),
    )
    row = cur.fetchone()

    if row is None:
        print(f"На дату {target_date} в программе нет данных (вне диапазона расписания).")
        conn.close()
        return

    day_number, week, theme, is_rest = row

    print(f"Дата: {target_date}  |  День {day_number}, неделя {week}")
    print(f"Тема недели: {theme}")

    if is_rest:
        print("\nСегодня день отдыха. Задач нет.")
        conn.close()
        return

    cur.execute(
        "SELECT task_id, type, title, status FROM tasks WHERE day_number = ? ORDER BY task_id",
        (day_number,),
    )
    tasks = cur.fetchall()

    pending = [t for t in tasks if t[3] != "done"]
    done = [t for t in tasks if t[3] == "done"]

    print(f"\nЗадачи на сегодня ({len(pending)} осталось / {len(tasks)} всего):\n")
    for task_id, t_type, title, status in pending:
        print(f"  [ ] #{task_id} ({t_type}): {title}")

    if done:
        print(f"\nУже выполнено сегодня ({len(done)}):")
        for task_id, t_type, title, status in done:
            print(f"  [x] #{task_id} ({t_type}): {title}")

    conn.close()


if __name__ == "__main__":
    target_date = get_target_date()
    show_today(target_date)