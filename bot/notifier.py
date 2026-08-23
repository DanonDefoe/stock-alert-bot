"""
bot/notifier.py — отправка сообщений пользователю в Telegram.

Единственное место, которое напрямую дёргает bot.send_message(). И хендлеры,
и services/scheduler.py должны отправлять сообщения только через функцию
отсюда, а не через объект бота напрямую — так вся обработка ошибок отправки
живёт в одном месте.
"""

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardMarkup

logger = logging.getLogger(__name__)


async def send_message(
    bot: Bot,
    chat_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    """
    Отправляет сообщение пользователю. Возвращает True при успехе, False —
    если отправка не удалась (например, пользователь заблокировал бота).

    Специально не бросает исключение наружу: если уведомлений несколько
    (сработало сразу два-три порога), ошибка на одном не должна прерывать
    отправку остальных.
    """
    try:
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
        return True
    except TelegramAPIError as error:
        logger.warning(f"Не удалось отправить сообщение chat_id={chat_id}: {error}")
        return False


def format_threshold_notification(
    symbol: str,
    direction: str,
    target_price: int,
    current_price: float,
    comment: str | None,
) -> str:
    """
    Собирает текст уведомления о сработавшем пороге. Вынесено в отдельную
    функцию, чтобы формат сообщения отлаживался в одном месте — используется
    из services/scheduler.py при обработке результата price_checker.py.
    """
    direction_text = "выросла до" if direction == "above" else "упала до"
    lines = [
        f"🔔 {symbol}: цена {direction_text} ${target_price}",
        f"Текущая цена: ${current_price:.2f}",
    ]
    if comment:
        lines.append(f"💬 {comment}")
    return "\n".join(lines)


if __name__ == "__main__":
    # send_message нельзя протестировать в изоляции — нужен реальный
    # объект Bot с валидным токеном (будет доступен только внутри main.py).
    # Но текст уведомления собрать и проверить можно уже сейчас:
    sample_text = format_threshold_notification(
        symbol="AAPL",
        direction="above",
        target_price=250,
        current_price=253.10,
        comment="Точка входа для покупки",
    )
    print(sample_text)