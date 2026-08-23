"""
main.py — точка входа: собирает бота воедино и запускает.

Здесь и только здесь создаются Bot и Dispatcher, регистрируются все
роутеры из bot/handlers/, инициализируется БД и запускается фоновый
планировщик проверки цен (services/scheduler.py) параллельно с приёмом
сообщений от Telegram.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers import add_ticker, calendar_info, edit_ticker, list_tickers, manage_tickers, start, stats
from config import BOT_TOKEN
from db.database import init_db
from services.scheduler import run_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("Инициализация БД...")
    init_db()

    bot = Bot(token=BOT_TOKEN)
    dispatcher = Dispatcher(storage=MemoryStorage())

    dispatcher.include_router(start.router)
    dispatcher.include_router(add_ticker.router)
    dispatcher.include_router(edit_ticker.router)
    dispatcher.include_router(manage_tickers.router)
    dispatcher.include_router(list_tickers.router)
    dispatcher.include_router(calendar_info.router)
    dispatcher.include_router(stats.router)

    # На случай, если раньше был настроен webhook (например, при экспериментах) —
    # снимаем его и сбрасываем накопленные апдейты, иначе polling не запустится.
    await bot.delete_webhook(drop_pending_updates=True)

    scheduler_task = asyncio.create_task(run_scheduler(bot))
    logger.info("Планировщик запущен как фоновая задача.")

    try:
        logger.info("Бот запущен, начинаю polling...")
        await dispatcher.start_polling(bot)
    finally:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен вручную (Ctrl+C).")