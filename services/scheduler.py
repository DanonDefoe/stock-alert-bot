"""
services/scheduler.py — фоновый цикл, который в заданное расписанием время
проверяет цены и рассылает уведомления по сработавшим порогам.

Работает как отдельная asyncio-задача внутри того же процесса, что и сам
бот (запускается из main.py через asyncio.create_task). Использует
asyncio.sleep, а не блокирующий time.sleep — иначе на время ожидания
"замер" бы весь бот и не отвечал на команды меню.
"""

import asyncio
import logging
from datetime import datetime, time, timedelta, timezone

from aiogram import Bot

from bot import notifier
from config import PRICE_CHECK_TIMES_UTC
from db import repository
from services import market_calendar, price_checker

logger = logging.getLogger(__name__)


async def run_scheduler(bot: Bot) -> None:
    """
    Бесконечный цикл: вычисляет ближайшее время проверки из
    config.PRICE_CHECK_TIMES_UTC, засыпает до него, затем проверяет цены —
    и так постоянно. Не делает ничего при первом запуске сразу — ждёт
    первого запланированного времени.
    """
    logger.info(f"Scheduler запущен. Расписание проверок (UTC): {PRICE_CHECK_TIMES_UTC}")

    while True:
        now = datetime.now(timezone.utc)
        next_run = _next_check_time(PRICE_CHECK_TIMES_UTC, now)
        sleep_seconds = (next_run - now).total_seconds()

        logger.info(f"Следующая проверка цен: {next_run} UTC (через {sleep_seconds:.0f} сек)")
        await asyncio.sleep(sleep_seconds)

        await _run_check_cycle(bot)


async def _run_check_cycle(bot: Bot) -> None:
    """Одна плановая проверка: пропускает нерабочие дни, иначе сверяет цены и уведомляет."""
    today = datetime.now(timezone.utc).date()

    if not market_calendar.is_trading_day(today):
        logger.info(f"{today} — нерабочий день биржи, проверку пропускаю")
        return

    logger.info("Начинаю плановую проверку цен")

    # check_all_thresholds — синхронная функция с блокирующими HTTP-запросами
    # к Finnhub, поэтому выполняем её в отдельном потоке, чтобы не мешать
    # боту отвечать на сообщения в это время.
    triggered = await asyncio.to_thread(price_checker.check_all_thresholds)
    logger.info(f"Проверка завершена. Сработавших порогов: {len(triggered)}")

    for item in triggered:
        text = notifier.format_threshold_notification(
            symbol=item.symbol,
            direction=item.direction,
            target_price=item.target_price,
            current_price=item.current_price,
            comment=item.comment,
        )
        sent = await notifier.send_message(bot, item.telegram_chat_id, text)

        if sent:
            # Удаляем порог только при успешной отправке — уведомление
            # разовое, и если сейчас его не удалось доставить (например,
            # временный сбой Telegram), лучше попробовать ещё раз в
            # следующую плановую проверку, чем молча потерять его навсегда.
            repository.delete_threshold(item.threshold_id)
        else:
            logger.warning(
                f"Не удалось отправить уведомление (threshold_id={item.threshold_id}), "
                f"порог не удалён — повторим попытку в следующей проверке."
            )


def _next_check_time(check_times: list[str], now: datetime) -> datetime:
    """
    Находит ближайший момент в будущем (по UTC) из списка времён проверки
    (например, ["15:00", "20:00"]). Если все сегодняшние времена уже
    прошли — возвращает самое раннее время завтрашнего дня.
    """
    parsed_times: list[time] = sorted(
        datetime.strptime(t, "%H:%M").time() for t in check_times
    )

    today_candidates = [
        datetime.combine(now.date(), t, tzinfo=timezone.utc) for t in parsed_times
    ]
    upcoming_today = [candidate for candidate in today_candidates if candidate > now]

    if upcoming_today:
        return min(upcoming_today)

    tomorrow = now.date() + timedelta(days=1)
    return datetime.combine(tomorrow, parsed_times[0], tzinfo=timezone.utc)


if __name__ == "__main__":
    # run_scheduler целиком протестировать без реального Bot и без ожидания
    # реального времени нельзя. Но саму логику расчёта "какое время
    # следующее" можно проверить прямо сейчас, на нескольких сценариях.
    sample_before = datetime(2026, 8, 17, 10, 0, tzinfo=timezone.utc)
    sample_between = datetime(2026, 8, 17, 17, 0, tzinfo=timezone.utc)
    sample_after = datetime(2026, 8, 17, 23, 0, tzinfo=timezone.utc)

    for label, sample_now in [
        ("до обеих сегодняшних проверок", sample_before),
        ("между проверками", sample_between),
        ("после обеих сегодняшних проверок", sample_after),
    ]:
        next_time = _next_check_time(PRICE_CHECK_TIMES_UTC, sample_now)
        print(f"{label}: сейчас {sample_now} -> следующая проверка {next_time}")