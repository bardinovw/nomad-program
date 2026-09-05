"""
Telegram-бот: ежедневные задачи с детальным экраном и статусами.
Работает с облачной базой Postgres (Supabase) — DATABASE_URL должна быть задана.

Статусы задачи: pending -> in_progress -> done (и обратно через отмену).

Команды:
    /start — привязать чат
    /today — активные задачи на сегодня (не выполненные)
    /done  — задачи, выполненные сегодня, с кнопкой отмены
"""

import os
import datetime
import urllib.parse
import telebot
from telebot import types
from apscheduler.schedulers.background import BackgroundScheduler
from db import get_connection

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID_FILE = "chat_id.txt"
SEND_TIME = "08:00"

bot = telebot.TeleBot(BOT_TOKEN)

TYPE_LABELS = {
    "conspect": "Конспект",
    "memorize": "Заучивание",
    "vocab": "Слова",
    "video": "Видео",
    "grammar": "Грамматика",
}

STATUS_ICONS = {
    "pending": "⬜",
    "in_progress": "▶️",
    "done": "✅",
}


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


def today_str():
    return datetime.date.today().isoformat()


def get_day_info(target_date=None):
    target_date = target_date or today_str()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT day_number, week, theme, is_rest FROM days WHERE date = %s",
        (target_date,),
    )
    row = cur.fetchone()
    conn.close()
    if row is None:
        return None
    day_number, week, theme, is_rest = row
    return {"day_number": day_number, "week": week, "theme": theme, "is_rest": is_rest}


def get_active_tasks(day_number):
    """Задачи дня, которые ещё не выполнены (pending или in_progress)."""
    conn = get_connection()
    cur = conn.cursor()
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
    return tasks


def get_done_tasks(day_number):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT task_id, type, title, status FROM tasks
        WHERE day_number = %s AND status = 'done'
        ORDER BY task_id
        """,
        (day_number,),
    )
    tasks = cur.fetchall()
    conn.close()
    return tasks


def get_task(task_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT task_id, type, title, status, day_number FROM tasks WHERE task_id = %s", (task_id,))
    row = cur.fetchone()
    conn.close()
    return row


def recalc_theme_status(cur, theme):
    cur.execute(
        """
        SELECT COUNT(*) FILTER (WHERE status = 'done'), COUNT(*)
        FROM tasks JOIN days USING (day_number)
        WHERE days.theme = %s
        """,
        (theme,),
    )
    done_count, total_count = cur.fetchone()

    if done_count == 0:
        new_status = "not_started"
    elif done_count == total_count:
        new_status = "learned"
    else:
        new_status = "in_progress"

    cur.execute("UPDATE knowledge_map SET status = %s WHERE theme = %s", (new_status, theme))
    return new_status


def set_task_status(task_id, new_status):
    """Меняет статус задачи, пересчитывает прогресс темы. Возвращает (title, theme, theme_status) или None."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT title, day_number FROM tasks WHERE task_id = %s", (task_id,))
    row = cur.fetchone()
    if row is None:
        conn.close()
        return None

    title, day_number = row
    cur.execute("UPDATE tasks SET status = %s WHERE task_id = %s", (new_status, task_id))

    cur.execute("SELECT theme FROM days WHERE day_number = %s", (day_number,))
    theme = cur.fetchone()[0]

    theme_status = recalc_theme_status(cur, theme)

    conn.commit()
    conn.close()
    return title, theme, theme_status


def youtube_search_url(theme: str) -> str:
    query = urllib.parse.quote_plus(f"{theme} English lesson")
    return f"https://www.youtube.com/results?search_query={query}"


def build_list_message(day_info, tasks, chat_id=None):
    if day_info is None:
        return "На сегодня в программе нет данных.", None

    if day_info["is_rest"]:
        return f"Неделя {day_info['week']}, тема: {day_info['theme']}\n\nСегодня день отдыха.", None

    text = f"Неделя {day_info['week']}, тема: {day_info['theme']}\n\nАктивные задачи ({len(tasks)}):"

    if not tasks:
        text += "\n\nВсё выполнено! Проверь /done или отдыхай."
        return text, None

    markup = types.InlineKeyboardMarkup()
    for task_id, t_type, title, status in tasks:
        icon = STATUS_ICONS.get(status, "⬜")
        label = f"{icon} #{task_id} [{TYPE_LABELS.get(t_type, t_type)}] {title[:30]}"
        markup.add(types.InlineKeyboardButton(label, callback_data=f"view:{task_id}"))

    return text, markup


def build_detail_message(task):
    task_id, t_type, title, status, day_number = task

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT theme, date FROM days WHERE day_number = %s", (day_number,))
    theme, date = cur.fetchone()
    conn.close()

    status_ru = {"pending": "не начато", "in_progress": "в работе", "done": "выполнено"}.get(status, status)

    text = (
        f"{TYPE_LABELS.get(t_type, t_type)}\n\n"
        f"{title}\n\n"
        f"Тема: {theme}\n"
        f"Срок: {date}\n"
        f"Статус: {status_ru}"
    )

    if t_type == "video":
        text += f"\n\nПоиск видео: {youtube_search_url(theme)}"

    markup = types.InlineKeyboardMarkup()
    if status == "pending":
        markup.add(types.InlineKeyboardButton("▶️ Взять в работу", callback_data=f"start:{task_id}"))
        markup.add(types.InlineKeyboardButton("✅ Выполнено", callback_data=f"done:{task_id}"))
    elif status == "in_progress":
        markup.add(types.InlineKeyboardButton("✅ Выполнено", callback_data=f"done:{task_id}"))
        markup.add(types.InlineKeyboardButton("↩️ Вернуть в очередь", callback_data=f"reset:{task_id}"))

    markup.add(types.InlineKeyboardButton("⬅️ К списку", callback_data="list"))

    return text, markup


def build_done_message(day_info, tasks):
    if day_info is None or day_info["is_rest"]:
        return "На сегодня нет выполненных задач.", None

    text = f"Выполнено сегодня ({len(tasks)}):"
    if not tasks:
        text += "\n\nПока ничего не отмечено."
        return text, None

    markup = types.InlineKeyboardMarkup()
    for task_id, t_type, title, status in tasks:
        label = f"↩️ #{task_id} [{TYPE_LABELS.get(t_type, t_type)}] {title[:30]}"
        markup.add(types.InlineKeyboardButton(label, callback_data=f"undo:{task_id}"))

    return text, markup


@bot.message_handler(commands=["start"])
def handle_start(message):
    save_chat_id(message.chat.id)
    bot.reply_to(
        message,
        f"Бот подключён. Каждый день в {SEND_TIME} буду присылать задачи.\n"
        f"/today — активные задачи\n/done — выполненные сегодня",
    )


@bot.message_handler(commands=["today"])
def handle_today(message):
    day_info = get_day_info()
    tasks = get_active_tasks(day_info["day_number"]) if day_info and not day_info["is_rest"] else []
    text, markup = build_list_message(day_info, tasks)
    bot.send_message(message.chat.id, text, reply_markup=markup)


@bot.message_handler(commands=["done"])
def handle_done_command(message):
    day_info = get_day_info()
    tasks = get_done_tasks(day_info["day_number"]) if day_info and not day_info["is_rest"] else []
    text, markup = build_done_message(day_info, tasks)
    bot.send_message(message.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "list")
def handle_back_to_list(call):
    day_info = get_day_info()
    tasks = get_active_tasks(day_info["day_number"]) if day_info and not day_info["is_rest"] else []
    text, markup = build_list_message(day_info, tasks)
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("view:"))
def handle_view(call):
    task_id = int(call.data.split(":")[1])
    task = get_task(task_id)
    if task is None:
        bot.answer_callback_query(call.id, "Задача не найдена")
        return
    text, markup = build_detail_message(task)
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("start:"))
def handle_start_task(call):
    task_id = int(call.data.split(":")[1])
    result = set_task_status(task_id, "in_progress")
    if result is None:
        bot.answer_callback_query(call.id, "Задача не найдена")
        return
    bot.answer_callback_query(call.id, "Взято в работу")
    task = get_task(task_id)
    text, markup = build_detail_message(task)
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("reset:"))
def handle_reset_task(call):
    task_id = int(call.data.split(":")[1])
    result = set_task_status(task_id, "pending")
    if result is None:
        bot.answer_callback_query(call.id, "Задача не найдена")
        return
    bot.answer_callback_query(call.id, "Возвращено в очередь")
    task = get_task(task_id)
    text, markup = build_detail_message(task)
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("done:"))
def handle_done_task(call):
    task_id = int(call.data.split(":")[1])
    result = set_task_status(task_id, "done")
    if result is None:
        bot.answer_callback_query(call.id, "Задача не найдена")
        return

    title, theme, theme_status = result
    bot.answer_callback_query(call.id, f"Готово: {title[:60]}")

    day_info = get_day_info()
    tasks = get_active_tasks(day_info["day_number"])
    text, markup = build_list_message(day_info, tasks)
    if theme_status == "learned":
        text += f"\n\nТема «{theme}» полностью освоена."

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("undo:"))
def handle_undo_task(call):
    task_id = int(call.data.split(":")[1])
    result = set_task_status(task_id, "pending")
    if result is None:
        bot.answer_callback_query(call.id, "Задача не найдена")
        return

    title, theme, theme_status = result
    bot.answer_callback_query(call.id, f"Отменено: {title[:60]}")

    day_info = get_day_info()
    tasks = get_done_tasks(day_info["day_number"])
    text, markup = build_done_message(day_info, tasks)
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)


def send_daily_tasks():
    chat_id = load_chat_id()
    if chat_id is None:
        return
    day_info = get_day_info()
    tasks = get_active_tasks(day_info["day_number"]) if day_info and not day_info["is_rest"] else []
    text, markup = build_list_message(day_info, tasks)
    bot.send_message(chat_id, text, reply_markup=markup)


if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    hour, minute = map(int, SEND_TIME.split(":"))
    scheduler.add_job(send_daily_tasks, "cron", hour=hour, minute=minute)
    scheduler.start()

    print("Бот запущен. Отправь /start в Telegram, чтобы подключиться.")
    bot.infinity_polling()