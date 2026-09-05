"""
Telegram-бот: ежедневная отправка задач + отметка выполнения кнопками.
Работает с облачной базой Postgres (Supabase) — DATABASE_URL должна быть задана.

Установка:
    pip install pyTelegramBotAPI APScheduler psycopg2-binary

Настройка:
    1. Задай переменную окружения DATABASE_URL (см. db.py)
    2. Задай переменную окружения BOT_TOKEN (токен от @BotFather)
    3. Запусти: python bot.py
    4. Напиши боту /start в Telegram — это привяжет твой чат
"""

import os
import datetime
import telebot
from telebot import types
from apscheduler.schedulers.background import BackgroundScheduler
from db import get_connection

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID_FILE = "chat_id.txt"
SEND_TIME = "08:00"  # формат HH:MM, время ежедневной отправки

bot = telebot.TeleBot(BOT_TOKEN)


def save_chat_id(chat_id):
    with open(CHAT_ID_FILE, "w") as f:
        f.write(str(chat_id))


def load_chat_id():
    env_chat_id = os.environ.get("CHAT_ID")
    if env_chat_id:
        return int(env_chat_id)
    if not os.path.exists(CHAT_ID_FILE):
        return None
    with open(CHAT_ID_FILE) as f:
        return int(f.read().strip())


def get_today_tasks(target_date=None):
    if target_date is None:
        target_date = datetime.date.today().isoformat()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT day_number, week, theme, is_rest FROM days WHERE date = %s",
        (target_date,),
    )
    row = cur.fetchone()
    if row is None:
        conn.close()
        return None, []

    day_number, week, theme, is_rest = row
    if is_rest:
        conn.close()
        return {"day_number": day_number, "week": week, "theme": theme, "is_rest": True}, []

    cur.execute(
        """
        SELECT task_id, type, title, status FROM tasks
        WHERE day_number = %s AND status != 'done'
        ORDER BY task_id
        """,
        (day_number,),
    )
    tasks = cur.fetchall()
    conn.close()
    return {"day_number": day_number, "week": week, "theme": theme, "is_rest": False}, tasks


def mark_task_done(task_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT title, day_number FROM tasks WHERE task_id = %s", (task_id,))
    row = cur.fetchone()
    if row is None:
        conn.close()
        return None

    title, day_number = row
    cur.execute("UPDATE tasks SET status = 'done' WHERE task_id = %s", (task_id,))

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

    theme_learned = False
    if remaining == 0:
        cur.execute("UPDATE knowledge_map SET status = 'learned' WHERE theme = %s", (theme,))
        theme_learned = True
    else:
        cur.execute(
            """
            UPDATE knowledge_map SET status = 'in_progress'
            WHERE theme = %s AND status = 'not_started'
            """,
            (theme,),
        )

    conn.commit()
    conn.close()
    return title, theme, theme_learned


def build_tasks_message(day_info, tasks):
    if day_info is None:
        return "На сегодня в программе нет данных.", None

    if day_info["is_rest"]:
        text = f"Неделя {day_info['week']}, тема: {day_info['theme']}\n\nСегодня день отдыха."
        return text, None

    text = f"Неделя {day_info['week']}, тема: {day_info['theme']}\n\nЗадачи на сегодня ({len(tasks)}):"

    if not tasks:
        text += "\n\nВсе задачи на сегодня уже выполнены."
        return text, None

    markup = types.InlineKeyboardMarkup()
    for task_id, t_type, title, status in tasks:
        label = f"✅ #{task_id} [{t_type}] {title[:40]}"
        markup.add(types.InlineKeyboardButton(label, callback_data=f"done:{task_id}"))

    return text, markup


@bot.message_handler(commands=["start"])
def handle_start(message):
    save_chat_id(message.chat.id)
    bot.reply_to(
        message,
        f"Бот подключён. Каждый день в {SEND_TIME} буду присылать задачи.\n"
        f"Команда /today покажет их прямо сейчас.",
    )


@bot.message_handler(commands=["today"])
def handle_today(message):
    day_info, tasks = get_today_tasks()
    text, markup = build_tasks_message(day_info, tasks)
    bot.send_message(message.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("done:"))
def handle_done_callback(call):
    task_id = int(call.data.split(":")[1])
    result = mark_task_done(task_id)

    if result is None:
        bot.answer_callback_query(call.id, "Задача не найдена")
        return

    title, theme, theme_learned = result
    bot.answer_callback_query(call.id, f"Готово: {title[:60]}")

    day_info, tasks = get_today_tasks()
    text, markup = build_tasks_message(day_info, tasks)
    if theme_learned:
        text += f"\n\nТема «{theme}» полностью освоена."

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)


def send_daily_tasks():
    chat_id = load_chat_id()
    if chat_id is None:
        return
    day_info, tasks = get_today_tasks()
    text, markup = build_tasks_message(day_info, tasks)
    bot.send_message(chat_id, text, reply_markup=markup)


if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    hour, minute = map(int, SEND_TIME.split(":"))
    scheduler.add_job(send_daily_tasks, "cron", hour=hour, minute=minute)
    scheduler.start()

    print("Бот запущен. Отправь /start в Telegram, чтобы подключиться.")
    bot.infinity_polling()