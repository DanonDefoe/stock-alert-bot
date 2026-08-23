"""
services/finnhub_client.py — обёртка над Finnhub API.

Единственное место в проекте, которое делает HTTP-запросы к Finnhub.
Каждый вызов также логируется в БД (для пункта меню со статистикой запросов) —
саму запись в базу делает db/repository.py, здесь только вызывается его функция.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

import requests

from config import FINNHUB_API_KEY
from db import repository

FINNHUB_QUOTE_URL = "https://finnhub.io/api/v1/quote"
REQUEST_TIMEOUT_SECONDS = 10


class QuoteError:
    """
    Категории ошибок при запросе котировки. Специально хранят только
    "тип" проблемы, а не сырой текст исключения — у requests текст
    ошибки часто содержит полный URL запроса, а в нашем URL есть
    FINNHUB_API_KEY. Такую категорию уже безопасно показывать
    пользователю в Telegram.
    """
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    RATE_LIMITED = "rate_limited"
    SERVER_ERROR = "server_error"
    INVALID_RESPONSE = "invalid_response"
    INVALID_TICKER = "invalid_ticker"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Quote:
    """Результат запроса котировки: цена + момент времени, к которому она относится."""
    price: float
    timestamp: datetime  # в UTC


@dataclass(frozen=True)
class QuoteResult:
    """
    quote — заполнено при успешном запросе, иначе None.
    error — одна из констант QuoteError.*, заполнена только при неудаче.
    Ровно одно из двух полей всегда None, второе — нет.
    """
    quote: Quote | None
    error: str | None


def get_quote(symbol: str) -> QuoteResult:
    """
    Запрашивает текущую цену и время котировки для тикера у Finnhub.

    Важно: это СИНХРОННАЯ (блокирующая) функция. При вызове из async-кода
    (обработчики бота, services/scheduler.py) её нужно оборачивать в
    asyncio.to_thread(get_quote, symbol) — иначе на время сетевого запроса
    "заморозится" весь бот и не будет отвечать на команды меню.
    """
    symbol = symbol.strip().upper()

    # Логируем сам факт обращения к API — независимо от того, успешным
    # окажется запрос или нет: он всё равно расходует лимит Finnhub.
    repository.increment_api_usage()

    try:
        response = requests.get(
            FINNHUB_QUOTE_URL,
            params={"symbol": symbol, "token": FINNHUB_API_KEY},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.Timeout:
        print(f"[finnhub_client] Таймаут при запросе {symbol}")
        return QuoteResult(quote=None, error=QuoteError.TIMEOUT)
    except requests.ConnectionError:
        print(f"[finnhub_client] Нет соединения при запросе {symbol}")
        return QuoteResult(quote=None, error=QuoteError.CONNECTION_ERROR)
    except requests.RequestException as error:
        # Общий случай — в лог пишем только ТИП ошибки, не str(error):
        # у requests текст исключения нередко включает полный URL запроса,
        # а вместе с ним — и токен Finnhub.
        print(f"[finnhub_client] Сетевая ошибка при запросе {symbol}: {type(error).__name__}")
        return QuoteResult(quote=None, error=QuoteError.UNKNOWN)

    if response.status_code == 429:
        print(f"[finnhub_client] Превышен лимит запросов Finnhub (429) при запросе {symbol}")
        return QuoteResult(quote=None, error=QuoteError.RATE_LIMITED)

    if response.status_code != 200:
        print(f"[finnhub_client] Finnhub вернул код {response.status_code} для {symbol}")
        return QuoteResult(quote=None, error=QuoteError.SERVER_ERROR)

    data = _parse_json_response(response, symbol)
    if data is None:
        return QuoteResult(quote=None, error=QuoteError.INVALID_RESPONSE)

    current_price = data.get("c")
    unix_timestamp = data.get("t")

    # Finnhub возвращает c=0 (и обычно все остальные поля тоже 0),
    # если тикер не существует или по нему нет данных.
    if current_price is None or current_price == 0:
        print(f"[finnhub_client] Не удалось получить цену для тикера '{symbol}' — возможно, неверный тикер")
        return QuoteResult(quote=None, error=QuoteError.INVALID_TICKER)

    # t иногда может отсутствовать (0 или None) даже при валидном тикере —
    # подстраховываемся текущим временем на такой случай.
    if unix_timestamp:
        quote_time = datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)
    else:
        quote_time = datetime.now(tz=timezone.utc)

    return QuoteResult(
        quote=Quote(price=float(current_price), timestamp=quote_time),
        error=None,
    )


def _parse_json_response(response: requests.Response, symbol: str) -> dict | None:
    """
    Безопасно парсит тело ответа как JSON. Возвращает None, если тело
    пустое или не является валидным JSON — такое бывает при
    кратковременных сбоях на стороне Finnhub даже при HTTP 200.
    """
    try:
        return response.json()
    except ValueError:
        # response.text — это тело ОТВЕТА Finnhub, а не наш запрос,
        # поэтому в нём нет токена и его безопасно логировать.
        print(
            f"[finnhub_client] Finnhub вернул non-parce response для "
            f"{symbol} (тело: {response.text[:200]!r})"
        )
        return None


if __name__ == "__main__":
    test_symbol = "AAPL"
    result = get_quote(test_symbol)
    if result.quote is not None:
        print(f"Текущая цена {test_symbol}: ${result.quote.price} (время котировки: {result.quote.timestamp} UTC)")
    else:
        print(f"Не удалось получить цену для {test_symbol}. Причина: {result.error}")