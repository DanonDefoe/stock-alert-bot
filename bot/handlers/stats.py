"""
bot/handlers/stats.py — пункт меню "статистика запросов" к Finnhub.

Как и calendar_info.py — простой хендлер без диалога и без FSM-состояния.
"""

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.keyboards import main_menu_keyboard
from config import DAILY_API_CALL_SOFT_LIMIT
from db import repository

router = Router()


@router.callback_query(F.data == "menu:stats")
async def show_stats(callback: CallbackQuery) -> None:
    calls_today = repository.get_api_usage_today()

    if DAILY_API_CALL_SOFT_LIMIT > 0:
        percent_used = round(calls_today / DAILY_API_CALL_SOFT_LIMIT * 100)
        percent_line = f" ({percent_used}%)"
    else:
        percent_line = ""

    text = (
        f"Запросов к Finnhub сегодня: {calls_today} из {DAILY_API_CALL_SOFT_LIMIT}"
        f"{percent_line}\n\n"
        f"ℹ️ Это не официальный лимит Finnhub, ограничения бесплатного пользователя = 60 запросов в минуту."
        f"Лимит задаётся в config.py."
    )

    await callback.message.edit_text(text, reply_markup=main_menu_keyboard())
    await callback.answer()