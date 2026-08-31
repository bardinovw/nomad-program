"""
Генератор программы изучения английского языка.
Локальная база (SQLite) + JSON-экспорт.

Схема: 8 недель x (6 учебных дней + 1 день отдыха) = 56 дней,
из них 48 учебных дней x 10 задач = 480 задач.

Уровень: B1, прогрессия по неделям от базовой бытовой лексики
к практике простого экзаменационного формата.
"""

import json
import sqlite3
import datetime
import os

OUTPUT_DIR = "."
os.makedirs(OUTPUT_DIR, exist_ok=True)

DB_PATH = os.path.join(OUTPUT_DIR, "english_program_b1.db")
JSON_PATH = os.path.join(OUTPUT_DIR, "english_program_b1.json")

START_DATE = datetime.date.today()

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


def build_schedule():
    schedule = []
    grammar_idx = 0
    conspect_counter = {}
    task_id = 1
    current_date = START_DATE
    day_number = 0

    for week in range(8):
        theme = WEEK_THEMES[week]
        for weekday in range(7):  # 6 учебных + 1 отдых
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
                    count = DAILY_DISTRIBUTION[t_type]
                    for _ in range(count):
                        if t_type == "grammar":
                            topic = GRAMMAR_TOPICS[grammar_idx % len(GRAMMAR_TOPICS)]
                            grammar_idx += 1
                            title = TEMPLATES["grammar"].format(topic=topic)
                        elif t_type == "conspect":
                            conspect_counter[theme] = conspect_counter.get(theme, 0) + 1
                            title = TEMPLATES["conspect"].format(
                                theme=theme, n=conspect_counter[theme]
                            )
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


def save_json(schedule):
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(schedule, f, ensure_ascii=False, indent=2)


def save_sqlite(schedule):
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE days (
            day_number INTEGER PRIMARY KEY,
            date TEXT,
            week INTEGER,
            theme TEXT,
            is_rest INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE tasks (
            task_id INTEGER PRIMARY KEY,
            day_number INTEGER,
            type TEXT,
            title TEXT,
            status TEXT DEFAULT 'pending',
            deadline TEXT,
            FOREIGN KEY (day_number) REFERENCES days(day_number)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE knowledge_map (
            theme TEXT PRIMARY KEY,
            status TEXT DEFAULT 'not_started'
        )
        """
    )

    for theme in WEEK_THEMES:
        cur.execute(
            "INSERT INTO knowledge_map (theme, status) VALUES (?, 'not_started')",
            (theme,),
        )

    for day in schedule:
        cur.execute(
            "INSERT INTO days (day_number, date, week, theme, is_rest) VALUES (?, ?, ?, ?, ?)",
            (day["day_number"], day["date"], day["week"], day["theme"], int(day["is_rest"])),
        )
        for task in day["tasks"]:
            cur.execute(
                "INSERT INTO tasks (task_id, day_number, type, title, status, deadline) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    task["task_id"],
                    day["day_number"],
                    task["type"],
                    task["title"],
                    task["status"],
                    task["deadline"],
                ),
            )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    schedule = build_schedule()
    save_json(schedule)
    save_sqlite(schedule)

    total_days = len(schedule)
    study_days = sum(1 for d in schedule if not d["is_rest"])
    total_tasks = sum(len(d["tasks"]) for d in schedule)

    print(f"Дней всего: {total_days}")
    print(f"Учебных дней: {study_days}")
    print(f"Задач всего: {total_tasks}")
    print(f"JSON: {JSON_PATH}")
    print(f"SQLite DB: {DB_PATH}")