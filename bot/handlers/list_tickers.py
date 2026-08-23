"""
bot/handlers/list_tickers.py — пункт меню "список тикеров".

Простой хендлер без FSM-состояния: по нажатию кнопки сразу показывает
список отслеживаемых тикеров с текущей ценой (запрашивается у Finnhub
на лету) и всеми порогами по каждому. Если список пуст — отдельный экран
с предложением добавить первый тикер.
"""

import asyncio

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.keyboards import empty_list_keyboard, main_menu_keyboard
from db import repository
from services import finnhub_client

router = Router()


@router.callback_query(F.data == "menu:list_tickers")
async def show_ticker_list(callback: CallbackQuery) -> None:
    user_id = repository.get_or_create_user(callback.message.chat.id)
    tickers = repository.list_tickers(user_id)

    if not tickers:
        await callback.message.edit_text(
            "Список пуст, добавьте первый тикер.",
            reply_markup=empty_list_keyboard(),
        )
        await callback.answer()
        return

    lines = ["Ваши тикеры:", ""]

    for ticker in tickers:
        status_icon = "⏸" if ticker["status"] == "paused" else "▶️"

        # Блокирующий запрос к Finnhub — оборачиваем в отдельный поток,
        # чтобы не "замораживать" бота, пока идёт список тикеров.
        result = await asyncio.to_thread(finnhub_client.get_quote, ticker["symbol"])
        price_text = f"${result.quote.price:.2f}" if result.quote is not None else "цена недоступна"

        lines.append(f"{status_icon} {ticker['symbol']} — текущая цена: {price_text}")

        thresholds = repository.list_thresholds_for_ticker(ticker["id"])
        if not thresholds:
            lines.append("   (нет порогов)")
        else:
            for threshold in thresholds:
                comparator = "выше" if threshold["direction"] == "above" else "ниже"
                comment_part = f" — 💬 {threshold['comment']}" if threshold["comment"] else ""
                lines.append(f"   • {comparator} ${threshold['target_price']}{comment_part}")

        lines.append("")  # пустая строка между тикерами

    text = "\n".join(lines).rstrip()

    await callback.message.edit_text(text, reply_markup=main_menu_keyboard())
    await callback.answer()