"""
Полностью сбрасывает программу в облачной базе (Supabase) и создаёт её заново,
начиная с ЗАВТРАШНЕГО дня как днём 1. Весь текущий прогресс удаляется безвозвратно.

Использование:
    python restart_program.py
"""

import datetime
from db import get_connection

START_DATE = datetime.date.today() + datetime.timedelta(days=1)

WEEK_THEMES = [
    "Daily life & routines vocabulary",
    "Travel & directions",
    "Work & study English",
    "Opinions & simple argumentation",
    "Phrasal verbs (common, everyday)",
    "Listening: everyday conversations",
    "Informal & semi-formal writing (emails, messages)",
    "Exam-style practice & review",
]

GRAMMAR_TOPICS = [
    "Present perfect vs past simple",
    "First and second conditionals",
    "Passive voice (present & past)",
    "Relative clauses (who, which, that)",
    "Modal verbs of obligation & advice (must, should, have to)",
    "Reported speech: statements",
    "Comparatives and superlatives (review & extension)",
    "Future forms (will, going to, present continuous)",
    "Used to / would for past habits",
    "Gerunds and infinitives",
    "Question tags",
    "Linking words (because, although, however, so)",
]

TASK_TYPES = ["conspect", "memorize", "vocab", "video", "grammar"]

DAILY_DISTRIBUTION = {
    "conspect": 2,
    "memorize": 2,
    "vocab": 2,
    "video": 2,
    "grammar": 2,
}

TEMPLATES = {
    "conspect": "Составить конспект по теме: {theme} (раздел {n})",
    "memorize": "Заучить 10 новых слов/выражений по теме: {theme}",
    "vocab": "Выполнить упражнения на новые слова по теме: {theme} (составить 10 предложений в контексте)",
    "video": "Посмотреть видео/документальный фильм по теме: {theme}, выписать новую лексику",
    "grammar": "Грамматика: {topic} — теория + 15 практических упражнений",
}


def build_schedule(start_date):
    schedule = []
    grammar_idx = 0
    conspect_counter = {}
    task_id = 1
    current_date = start_date
    day_number = 0

    for week in range(8):
        theme = WEEK_THEMES[week]
        for weekday in range(7):
            day_number += 1
            is_rest = weekday == 6

            day_entry = {
                "day_number": day_number,
                "date": current_date.isoformat(),
                "week": week + 1,
                "theme": theme,
                "is_rest": is_rest,
                "tasks": [],
            }

            if not is_rest:
                for t_type in TASK_TYPES:
                    for _ in range(DAILY_DISTRIBUTION[t_type]):
                        if t_type == "grammar":
                            topic = GRAMMAR_TOPICS[grammar_idx % len(GRAMMAR_TOPICS)]
                            grammar_idx += 1
                            title = TEMPLATES["grammar"].format(topic=topic)
                        elif t_type == "conspect":
                            conspect_counter[theme] = conspect_counter.get(theme, 0) + 1
                            title = TEMPLATES["conspect"].format(theme=theme, n=conspect_counter[theme])
                        else:
                            title = TEMPLATES[t_type].format(theme=theme)

                        day_entry["tasks"].append(
                            {
                                "task_id": task_id,
                                "type": t_type,
                                "title": title,
                                "status": "pending",
                                "deadline": current_date.isoformat(),
                            }
                        )
                        task_id += 1

            schedule.append(day_entry)
            current_date += datetime.timedelta(days=1)

    return schedule


def wipe_database(cur):
    cur.execute("DELETE FROM tasks")
    cur.execute("DELETE FROM days")
    cur.execute("DELETE FROM knowledge_map")
    print("Старые данные удалены.")


def load_schedule(cur, schedule):
    for theme in WEEK_THEMES:
        cur.execute(
            "INSERT INTO knowledge_map (theme, status) VALUES (%s, 'not_started')",
            (theme,),
        )

    for day in schedule:
        cur.execute(
            "INSERT INTO days (day_number, date, week, theme, is_rest) VALUES (%s, %s, %s, %s, %s)",
            (day["day_number"], day["date"], day["week"], day["theme"], day["is_rest"]),
        )
        for task in day["tasks"]:
            cur.execute(
                """
                INSERT INTO tasks (task_id, day_number, type, title, status, deadline)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    task["task_id"],
                    day["day_number"],
                    task["type"],
                    task["title"],
                    task["status"],
                    task["deadline"],
                ),
            )


if __name__ == "__main__":
    confirm = input(
        f"Это удалит ВЕСЬ текущий прогресс и создаст программу заново, "
        f"начиная с {START_DATE.isoformat()}. Продолжить? (yes/no): "
    )
    if confirm.strip().lower() != "yes":
        print("Отменено.")
        exit(0)

    schedule = build_schedule(START_DATE)

    conn = get_connection()
    cur = conn.cursor()

    wipe_database(cur)
    load_schedule(cur, schedule)

    conn.commit()
    conn.close()

    total_days = len(schedule)
    study_days = sum(1 for d in schedule if not d["is_rest"])
    total_tasks = sum(len(d["tasks"]) for d in schedule)

    print(f"\nГотово. Программа пересоздана.")
    print(f"День 1: {START_DATE.isoformat()}")
    print(f"Дней всего: {total_days}, учебных: {study_days}, задач: {total_tasks}")