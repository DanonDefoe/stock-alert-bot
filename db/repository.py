"""
db/repository.py — единственное место в проекте, которое читает и пишет
данные в SQLite (кроме создания таблиц — этим занимается db/database.py).
Все остальные модули (price_checker, scheduler, хендлеры бота) работают
с базой только через функции отсюда, а не через прямой SQL.
"""

import sqlite3
from datetime import datetime, timezone

from db.database import get_connection


# --- Пользователи -------------------------------------------------------------

def get_or_create_user(telegram_chat_id: int) -> int:
    """
    Возвращает id пользователя по его telegram_chat_id.
    Если пользователь обращается впервые — создаёт запись.
    """
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT id FROM users WHERE telegram_chat_id = ?;",
        (telegram_chat_id,),
    )
    row = cursor.fetchone()

    if row is not None:
        connection.close()
        return row["id"]

    cursor.execute(
        "INSERT INTO users (telegram_chat_id) VALUES (?);",
        (telegram_chat_id,),
    )
    connection.commit()
    user_id = cursor.lastrowid
    connection.close()
    return user_id


# --- Тикеры ---------------------------------------------------------------------

def add_ticker(user_id: int, symbol: str) -> int:
    """
    Добавляет новый тикер для пользователя. Не проверяет дубликаты —
    вызывающий код (хендлер бота) должен сам сначала спросить
    get_ticker_by_symbol и решить, что делать, если тикер уже есть.
    """
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO tickers (user_id, symbol, status) VALUES (?, ?, 'active');",
        (user_id, symbol.strip().upper()),
    )
    connection.commit()
    ticker_id = cursor.lastrowid
    connection.close()
    return ticker_id


def get_ticker_by_symbol(user_id: int, symbol: str) -> sqlite3.Row | None:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "SELECT * FROM tickers WHERE user_id = ? AND symbol = ?;",
        (user_id, symbol.strip().upper()),
    )
    row = cursor.fetchone()
    connection.close()
    return row


def get_ticker(ticker_id: int) -> sqlite3.Row | None:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM tickers WHERE id = ?;", (ticker_id,))
    row = cursor.fetchone()
    connection.close()
    return row


def list_tickers(user_id: int, status: str | None = None) -> list[sqlite3.Row]:
    """
    Возвращает тикеры пользователя. Если status не передан — все тикеры,
    иначе только с указанным статусом ('active' или 'paused').
    """
    connection = get_connection()
    cursor = connection.cursor()
    if status is None:
        cursor.execute(
            "SELECT * FROM tickers WHERE user_id = ? ORDER BY symbol;",
            (user_id,),
        )
    else:
        cursor.execute(
            "SELECT * FROM tickers WHERE user_id = ? AND status = ? ORDER BY symbol;",
            (user_id, status),
        )
    rows = cursor.fetchall()
    connection.close()
    return rows


def set_ticker_status(ticker_id: int, status: str) -> None:
    """status: 'active' или 'paused'."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "UPDATE tickers SET status = ?, updated_at = ? WHERE id = ?;",
        (status, _utc_now_str(), ticker_id),
    )
    connection.commit()
    connection.close()


def delete_ticker(ticker_id: int) -> None:
    """
    Удаляет тикер и ВСЕ его пороги. Каскадное удаление порогов настроено
    в схеме через ON DELETE CASCADE и работает благодаря
    PRAGMA foreign_keys = ON, которая включается в get_connection().
    """
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM tickers WHERE id = ?;", (ticker_id,))
    connection.commit()
    connection.close()


def update_ticker_check_frequency(ticker_id: int, check_frequency: str | None) -> None:
    """
    Задел на будущую фичу кастомной частоты проверки — пока никем не
    вызывается, но колонка уже есть в схеме, поэтому и функция готова.
    check_frequency: None (использовать общее расписание), '3', '4', '6'
    или 'hourly' — точный формат значения определим при реализации фичи.
    """
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "UPDATE tickers SET check_frequency = ?, updated_at = ? WHERE id = ?;",
        (check_frequency, _utc_now_str(), ticker_id),
    )
    connection.commit()
    connection.close()


# --- Пороги -----------------------------------------------------------------------

def add_threshold(
    ticker_id: int,
    target_price: int,
    direction: str,
    comment: str | None = None,
) -> int:
    """direction: 'above' или 'below'. comment: до 200 символов или None."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO thresholds (ticker_id, target_price, direction, comment)
        VALUES (?, ?, ?, ?);
        """,
        (ticker_id, target_price, direction, comment),
    )
    connection.commit()
    threshold_id = cursor.lastrowid
    connection.close()
    return threshold_id


def get_threshold(threshold_id: int) -> sqlite3.Row | None:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM thresholds WHERE id = ?;", (threshold_id,))
    row = cursor.fetchone()
    connection.close()
    return row


def list_thresholds_for_ticker(ticker_id: int) -> list[sqlite3.Row]:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "SELECT * FROM thresholds WHERE ticker_id = ? ORDER BY target_price;",
        (ticker_id,),
    )
    rows = cursor.fetchall()
    connection.close()
    return rows


# Сигнальное значение "не менять это поле" для update_threshold.
# Нужно, потому что None — валидное значение для comment (означает
# "удалить комментарий"), и его нельзя использовать как признак пропуска.
_NO_CHANGE = object()


def update_threshold(
    threshold_id: int,
    target_price: int | None = None,
    direction: str | None = None,
    comment=_NO_CHANGE,
) -> None:
    """
    Обновляет только переданные поля.
    - target_price / direction: None = не менять.
    - comment: если параметр вообще не передан — не менять; если передать
      comment=None явно — комментарий будет очищен.
    """
    current = get_threshold(threshold_id)
    if current is None:
        raise ValueError(f"Порог с id={threshold_id} не найден")

    new_target_price = target_price if target_price is not None else current["target_price"]
    new_direction = direction if direction is not None else current["direction"]
    new_comment = current["comment"] if comment is _NO_CHANGE else comment

    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE thresholds
        SET target_price = ?, direction = ?, comment = ?, updated_at = ?
        WHERE id = ?;
        """,
        (new_target_price, new_direction, new_comment, _utc_now_str(), threshold_id),
    )
    connection.commit()
    connection.close()


def delete_threshold(threshold_id: int) -> None:
    """
    Используется и при ручном удалении порога через меню, и автоматически
    из scheduler.py сразу после того, как порог сработал и уведомление
    отправлено (разовое срабатывание — порог "исчезает").
    """
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM thresholds WHERE id = ?;", (threshold_id,))
    connection.commit()
    connection.close()


def list_active_thresholds_with_context() -> list[sqlite3.Row]:
    """
    Главная функция для services/price_checker.py: возвращает все пороги,
    которые сейчас нужно проверять — то есть принадлежащие тикерам со
    статусом 'active'. Одним запросом подтягивает всё, что понадобится
    для проверки цены и отправки уведомления (без отдельных запросов
    в цикле на каждый порог).
    """
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT
            thresholds.id AS threshold_id,
            thresholds.target_price,
            thresholds.direction,
            thresholds.comment,
            tickers.id AS ticker_id,
            tickers.symbol,
            users.telegram_chat_id
        FROM thresholds
        JOIN tickers ON tickers.id = thresholds.ticker_id
        JOIN users ON users.id = tickers.user_id
        WHERE tickers.status = 'active';
        """
    )
    rows = cursor.fetchall()
    connection.close()
    return rows


# --- Статистика запросов к Finnhub -------------------------------------------------

def increment_api_usage() -> None:
    """
    Увеличивает счётчик запросов к Finnhub за сегодня (по UTC-дате, а не
    по локальной дате сервера — так показания не "уедут" при переезде
    на хостинг в другом часовом поясе). Создаёт запись за сегодня,
    если её ещё нет.
    """
    today = _utc_today_str()
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO api_usage (date, calls_count)
        VALUES (?, 1)
        ON CONFLICT(date) DO UPDATE SET calls_count = calls_count + 1;
        """,
        (today,),
    )
    connection.commit()
    connection.close()


def get_api_usage_today() -> int:
    """Возвращает количество запросов к Finnhub, сделанных сегодня (UTC)."""
    today = _utc_today_str()
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "SELECT calls_count FROM api_usage WHERE date = ?;",
        (today,),
    )
    row = cursor.fetchone()
    connection.close()
    return row["calls_count"] if row is not None else 0


# --- Вспомогательные функции ---------------------------------------------------------

def _utc_now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _utc_today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


if __name__ == "__main__":
    # Быстрый ручной тест: создаём тестового пользователя, тикер и порог,
    # читаем всё обратно и печатаем — проверяем модуль изолированно,
    # не трогая ни Telegram, ни Finnhub. В конце удаляем за собой.
    test_chat_id = 111111111

    user_id = get_or_create_user(test_chat_id)
    print(f"user_id: {user_id}")

    ticker_id = add_ticker(user_id, "aapl")
    print(f"ticker_id: {ticker_id}")

    threshold_id = add_threshold(
        ticker_id, target_price=250, direction="above", comment="Тестовый порог"
    )
    print(f"threshold_id: {threshold_id}")

    print("\nАктивные пороги для проверки:")
    for row in list_active_thresholds_with_context():
        print(dict(row))

    increment_api_usage()
    increment_api_usage()
    print(f"\nЗапросов к API сегодня: {get_api_usage_today()}")

    delete_ticker(ticker_id)
    print("\nТестовые данные удалены.")