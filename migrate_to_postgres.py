"""
Переносит текущие данные (все дни, задачи, прогресс тем) из локального
english_program_b1.db в облачную базу Postgres (Supabase).

Уже отмеченные выполненными задачи и статусы тем переносятся как есть —
прогресс не теряется.

Использование:
    1. Задай переменную окружения DATABASE_URL (см. db.py)
    2. python migrate_to_postgres.py
"""

import sqlite3
from db import get_connection

SQLITE_PATH = "english_program_b1.db"


def apply_schema(pg_conn):
    with open("schema.sql", "r", encoding="utf-8") as f:
        schema_sql = f.read()
    cur = pg_conn.cursor()
    cur.execute(schema_sql)
    pg_conn.commit()
    print("Схема применена.")


def migrate():
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_cur = sqlite_conn.cursor()

    pg_conn = get_connection()
    apply_schema(pg_conn)
    pg_cur = pg_conn.cursor()

    # --- days ---
    sqlite_cur.execute("SELECT day_number, date, week, theme, is_rest FROM days")
    days = sqlite_cur.fetchall()
    for day_number, date, week, theme, is_rest in days:
        pg_cur.execute(
            """
            INSERT INTO days (day_number, date, week, theme, is_rest)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (day_number) DO NOTHING
            """,
            (day_number, date, week, theme, bool(is_rest)),
        )
    print(f"Перенесено дней: {len(days)}")

    # --- tasks ---
    sqlite_cur.execute("SELECT task_id, day_number, type, title, status, deadline FROM tasks")
    tasks = sqlite_cur.fetchall()
    for task_id, day_number, t_type, title, status, deadline in tasks:
        pg_cur.execute(
            """
            INSERT INTO tasks (task_id, day_number, type, title, status, deadline)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (task_id) DO NOTHING
            """,
            (task_id, day_number, t_type, title, status, deadline),
        )
    print(f"Перенесено задач: {len(tasks)}")

    # --- knowledge_map ---
    sqlite_cur.execute("SELECT theme, status FROM knowledge_map")
    themes = sqlite_cur.fetchall()
    for theme, status in themes:
        pg_cur.execute(
            """
            INSERT INTO knowledge_map (theme, status)
            VALUES (%s, %s)
            ON CONFLICT (theme) DO UPDATE SET status = EXCLUDED.status
            """,
            (theme, status),
        )
    print(f"Перенесено тем: {len(themes)}")

    pg_conn.commit()
    sqlite_conn.close()
    pg_conn.close()
    print("\nГотово. Данные перенесены в Postgres.")


if __name__ == "__main__":
    migrate()