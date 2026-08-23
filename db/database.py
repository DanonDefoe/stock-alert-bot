"""
db/database.py — подключение к SQLite и создание структуры таблиц.

Это единственное место, где описана СХЕМА базы данных (CREATE TABLE).
Функции для чтения/записи данных в эти таблицы находятся в db/repository.py —
здесь их быть не должно.
"""

import sqlite3

from config import DB_PATH


def get_connection() -> sqlite3.Connection:
    """
    Открывает соединение с файлом БД. Создаёт папку data/, если её ещё нет.
    Включает поддержку внешних ключей — в SQLite она по умолчанию выключена
    для каждого нового соединения, а без неё ON DELETE CASCADE не сработает.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    """
    Создаёт все таблицы, если их ещё нет. Безопасно вызывать при каждом
    старте бота — если таблица уже существует, эта функция её не трогает
    и не меняет (см. предупреждение об этом в инструкции ниже).
    """
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id               INTEGER PRIMARY KEY,
            telegram_chat_id INTEGER UNIQUE NOT NULL,
            created_at       TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickers (
            id               INTEGER PRIMARY KEY,
            user_id          INTEGER NOT NULL REFERENCES users(id),
            symbol           TEXT NOT NULL,
            status           TEXT NOT NULL DEFAULT 'active'
                             CHECK (status IN ('active', 'paused')),
            check_frequency  TEXT DEFAULT NULL,
            created_at       TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS thresholds (
            id            INTEGER PRIMARY KEY,
            ticker_id     INTEGER NOT NULL REFERENCES tickers(id) ON DELETE CASCADE,
            target_price  INTEGER NOT NULL,
            direction     TEXT NOT NULL CHECK (direction IN ('above', 'below')),
            comment       TEXT DEFAULT NULL,
            created_at    TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_usage (
            date         TEXT PRIMARY KEY,
            calls_count  INTEGER NOT NULL DEFAULT 0
        );
    """)

    connection.commit()
    connection.close()


def _print_schema_for_verification() -> None:
    """
    Только для ручной проверки: выводит в консоль реальную структуру всех
    таблиц, которая сейчас есть в файле БД. Используется исключительно при
    запуске этого файла напрямую — см. блок if __name__ ниже.
    """
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table';")
    table_names = [row[0] for row in cursor.fetchall() if row[0] != "sqlite_sequence"]

    print(f"Файл БД: {DB_PATH}")
    print(f"Найдено таблиц: {len(table_names)}\n")

    for table_name in sorted(table_names):
        print(f"--- {table_name} ---")
        cursor.execute(f"PRAGMA table_info({table_name});")
        for column in cursor.fetchall():
            # column: (cid, name, type, notnull, default_value, is_pk)
            _, name, col_type, notnull, default, is_pk = column
            flags = []
            if is_pk:
                flags.append("PK")
            if notnull:
                flags.append("NOT NULL")
            flags_str = f" [{', '.join(flags)}]" if flags else ""
            print(f"  {name}: {col_type}{flags_str}")
        print()

    connection.close()


if __name__ == "__main__":
    init_db()
    _print_schema_for_verification()