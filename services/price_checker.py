"""
services/price_checker.py — бизнес-логика сравнения цены с порогами.

Ничего не знает про Telegram и не пишет в БД — только читает активные
пороги, получает текущие цены и возвращает список сработавших. Отправка
уведомлений и удаление сработавших порогов (разовое срабатывание) —
задача вызывающего кода, services/scheduler.py.
"""

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from db import repository
from services import finnhub_client


@dataclass(frozen=True)
class TriggeredThreshold:
    """Всё, что нужно scheduler.py, чтобы отправить уведомление и удалить порог."""
    threshold_id: int
    ticker_id: int
    symbol: str
    target_price: int
    direction: str  # 'above' или 'below'
    comment: str | None
    telegram_chat_id: int
    current_price: float
    quote_timestamp: datetime


def check_all_thresholds() -> list[TriggeredThreshold]:
    """
    Проходит по всем активным порогам, получает текущую цену для каждого
    уникального тикера (один раз, даже если на тикере несколько порогов —
    экономим запросы к Finnhub), сравнивает с условием и возвращает список
    сработавших порогов.

    Важно: это СИНХРОННАЯ функция — внутри делаются блокирующие HTTP-запросы
    через finnhub_client. При вызове из async-кода (services/scheduler.py)
    оборачивай весь вызов в asyncio.to_thread(check_all_thresholds).
    """
    active_rows = repository.list_active_thresholds_with_context()

    if not active_rows:
        return []

    thresholds_by_symbol: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in active_rows:
        thresholds_by_symbol[row["symbol"]].append(row)

    triggered: list[TriggeredThreshold] = []

    for symbol, rows in thresholds_by_symbol.items():
        result = finnhub_client.get_quote(symbol)

        if result.quote is None:
            print(
                f"[price_checker] Не удалось получить цену {symbol} "
                f"(причина: {result.error}) — пропускаю его {len(rows)} "
                f"порог(ов) в этот раз, попробую в следующей плановой проверке."
            )
            continue

        for row in rows:
            if _is_triggered(
                current_price=result.quote.price,
                target_price=row["target_price"],
                direction=row["direction"],
            ):
                triggered.append(
                    TriggeredThreshold(
                        threshold_id=row["threshold_id"],
                        ticker_id=row["ticker_id"],
                        symbol=row["symbol"],
                        target_price=row["target_price"],
                        direction=row["direction"],
                        comment=row["comment"],
                        telegram_chat_id=row["telegram_chat_id"],
                        current_price=result.quote.price,
                        quote_timestamp=result.quote.timestamp,
                    )
                )

    return triggered


def _is_triggered(current_price: float, target_price: int, direction: str) -> bool:
    """
    'above' — уведомляем, когда цена ВЫРОСЛА ДО таргета или выше.
    'below' — уведомляем, когда цена УПАЛА ДО таргета или ниже.
    """
    if direction == "above":
        return current_price >= target_price
    if direction == "below":
        return current_price <= target_price
    raise ValueError(f"Неизвестное направление порога: '{direction}'")


if __name__ == "__main__":
    # Ручной smoke-тест без Telegram: создаём тестовый тикер с двумя
    # порогами — один заведомо сработает, другой заведомо нет — и
    # проверяем, что check_all_thresholds() различает их правильно.
    test_chat_id = 111111111
    user_id = repository.get_or_create_user(test_chat_id)
    ticker_id = repository.add_ticker(user_id, "AAPL")

    should_trigger_id = repository.add_threshold(
        ticker_id, target_price=1, direction="above", comment="Должен сработать"
    )
    should_not_trigger_id = repository.add_threshold(
        ticker_id, target_price=999_999, direction="above", comment="Не должен сработать"
    )

    print("Проверяю пороги...")
    results = check_all_thresholds()

    print(f"\nСработало порогов: {len(results)}")
    for result in results:
        print(
            f"  {result.symbol}: цена {result.current_price} "
            f"{'>=' if result.direction == 'above' else '<='} "
            f"{result.target_price} ({result.direction}) — '{result.comment}'"
        )

    triggered_ids = {r.threshold_id for r in results}
    assert should_trigger_id in triggered_ids, "Ошибка: заведомо срабатывающий порог не сработал!"
    assert should_not_trigger_id not in triggered_ids, "Ошибка: заведомо НЕ срабатывающий порог сработал!"
    print("\nПроверка пройдена: оба случая сработали как ожидалось.")

    repository.delete_ticker(ticker_id)
    print("Тестовые данные удалены.")