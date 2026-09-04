"""
Общее подключение к облачной базе (Supabase Postgres).

Строка подключения берётся из переменной окружения DATABASE_URL.
Задать её можно двумя способами:

  Windows PowerShell (для текущей сессии терминала):
      $env:DATABASE_URL = "postgresql://postgres:...@db.xxxxx.supabase.co:5432/postgres"

  Или создать файл .env в этой же папке со строкой:
      DATABASE_URL=postgresql://postgres:...@db.xxxxx.supabase.co:5432/postgres
  (тогда нужен пакет python-dotenv — pip install python-dotenv)
"""

import os
import psycopg2

DATABASE_URL = os.environ.get("DATABASE_URL")


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError(
            "Переменная окружения DATABASE_URL не задана. "
            "Смотри инструкцию в начале файла db.py"
        )
    return psycopg2.connect(DATABASE_URL)