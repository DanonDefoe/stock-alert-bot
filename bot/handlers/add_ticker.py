"""
bot/handlers/add_ticker.py — многошаговый диалог добавления тикера и порога(ов).

Сценарий:
1. Тикер (текст) -> проверяем через Finnhub, что такой тикер существует
2. Целевая цена (текст, целое положительное число)
3. Направление (кнопки: выше / ниже)
4. Комментарий (текст до 200 символов, либо кнопка "Пропустить")
5. Порог сохраняется в БД. Дальше — "Добавить ещё порог" (возврат к шагу 2
   для того же тикера) или "Готово" (в главное меню).
"""

import asyncio

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.keyboards import (
    add_another_threshold_keyboard,
    cancel_keyboard,
    comment_step_keyboard,
    direction_keyboard,
    main_menu_keyboard,
)
from db import repository
from services import finnhub_client

router = Router()

MAX_COMMENT_LENGTH = 200

# Категории ошибок из finnhub_client.QuoteError -> человекочитаемый текст.
# INVALID_TICKER сюда не входит — для него отдельная, более полезная
# формулировка (см. handle_symbol).
_NETWORK_ERROR_MESSAGES_RU = {
    finnhub_client.QuoteError.TIMEOUT: "Finnhub не ответил вовремя (таймаут)",
    finnhub_client.QuoteError.CONNECTION_ERROR: "не удалось соединиться с Finnhub",
    finnhub_client.QuoteError.RATE_LIMITED: "превышен лимит запросов к Finnhub",
    finnhub_client.QuoteError.SERVER_ERROR: "Finnhub вернул ошибку на своей стороне",
    finnhub_client.QuoteError.UNKNOWN: "сетевая ошибка при обращении к Finnhub",
}


class AddTickerStates(StatesGroup):
    waiting_for_symbol = State()
    waiting_for_price = State()
    waiting_for_direction = State()
    waiting_for_comment = State()
    waiting_for_next_action = State()  # после сохранения порога, ждём "ещё" / "готово"


# --- Шаг 1: старт диалога, запрос тикера ---------------------------------------

@router.callback_query(F.data == "menu:add_ticker")
async def start_add_ticker(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddTickerStates.waiting_for_symbol)
    await callback.message.edit_text(
        "Введите тикер акции (например, AAPL):",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


# --- Шаг 2: получили тикер, проверяем через Finnhub, находим/создаём в БД -------

@router.message(AddTickerStates.waiting_for_symbol)
async def handle_symbol(message: Message, state: FSMContext) -> None:
    if message.text is None:
        await message.answer("Пришлите тикер текстом, например AAPL.", reply_markup=cancel_keyboard())
        return

    symbol = message.text.strip().upper()

    if not symbol or len(symbol) > 10:
        await message.answer(
            "Вероятно, некорректный тикер. Введите ещё раз (например, AAPL):",
            reply_markup=cancel_keyboard(),
        )
        return

    await message.answer(f"Проверяю тикер {symbol}...")

    # get_quote — блокирующая функция (реальный HTTP-запрос), поэтому
    # оборачиваем в отдельный поток, чтобы не "заморозить" бота на время запроса.
    result = await asyncio.to_thread(finnhub_client.get_quote, symbol)

    if result.quote is None:
        if result.error == finnhub_client.QuoteError.INVALID_TICKER:
            await message.answer(
                f"Не нашёл тикер '{symbol}' на Finnhub. Проверьте написание и введите ещё раз:",
                reply_markup=cancel_keyboard(),
            )
        else:
            error_text = _NETWORK_ERROR_MESSAGES_RU.get(
                result.error, "не удалось связаться с Finnhub"
            )
            await message.answer(
                f"⚠️ {error_text}. Попробуйте ввести тикер ещё раз через минуту, или проверьте API URL",
                reply_markup=cancel_keyboard(),
            )
        return

    quote = result.quote

    user_id = repository.get_or_create_user(message.chat.id)
    existing_ticker = repository.get_ticker_by_symbol(user_id, symbol)

    if existing_ticker is not None:
        ticker_id = existing_ticker["id"]
        status_note = (
            "\n⚠️ Этот тикер сейчас на паузе — новый порог добавится, но "
            "уведомления по нему не будут приходить, пока не возобновится "
            "отслеживание через меню."
            if existing_ticker["status"] == "paused"
            else ""
        )
        intro = f"Тикер {symbol} уже отслеживается — добавляю к нему ещё один порог.{status_note}"
    else:
        ticker_id = repository.add_ticker(user_id, symbol)
        intro = f"Тикер {symbol} добавлен (текущая цена: ${quote.price:.2f})."

    await state.update_data(ticker_id=ticker_id, symbol=symbol)
    await state.set_state(AddTickerStates.waiting_for_price)
    await message.answer(
        f"{intro}\n\nВведи целевую цену в USD (целое число):",
        reply_markup=cancel_keyboard(),
    )


# --- Шаг 3: получили цену, запрашиваем направление -------------------------------

@router.message(AddTickerStates.waiting_for_price)
async def handle_price(message: Message, state: FSMContext) -> None:
    if message.text is None:
        await message.answer("Пришлите цену текстом, например 250.", reply_markup=cancel_keyboard())
        return

    raw_price = message.text.strip()

    if not raw_price.isdigit() or int(raw_price) <= 0:
        await message.answer(
            "Цена должна быть целым положительным числом в USD. Попробуйте ещё раз:",
            reply_markup=cancel_keyboard(),
        )
        return

    await state.update_data(target_price=int(raw_price))
    await state.set_state(AddTickerStates.waiting_for_direction)
    await message.answer(
        "При каком условии присылать уведомление?",
        reply_markup=direction_keyboard(),
    )


# --- Шаг 4: получили направление, запрашиваем комментарий ------------------------

@router.callback_query(AddTickerStates.waiting_for_direction, F.data.startswith("direction:"))
async def handle_direction(callback: CallbackQuery, state: FSMContext) -> None:
    direction = callback.data.split(":", 1)[1]  # "above" или "below"

    await state.update_data(direction=direction)
    await state.set_state(AddTickerStates.waiting_for_comment)
    await callback.message.edit_text(
        f"Можно добавить комментарий к уведомлению (до {MAX_COMMENT_LENGTH} символов) "
        f"или пропустить этот шаг:",
        reply_markup=comment_step_keyboard(),
    )
    await callback.answer()


# --- Шаг 5а: комментарий пропущен -------------------------------------------------

@router.callback_query(AddTickerStates.waiting_for_comment, F.data == "comment:skip")
async def handle_comment_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await _save_threshold(comment=None, state=state)
    confirmation_text = await _build_confirmation_text(state)
    await state.set_state(AddTickerStates.waiting_for_next_action)
    await callback.message.edit_text(confirmation_text, reply_markup=add_another_threshold_keyboard())
    await callback.answer()


# --- Шаг 5б: комментарий введён текстом --------------------------------------------

@router.message(AddTickerStates.waiting_for_comment)
async def handle_comment_text(message: Message, state: FSMContext) -> None:
    if message.text is None:
        await message.answer("Пришлите комментарий текстом или нажмите «Пропустить».", reply_markup=comment_step_keyboard())
        return

    comment = message.text.strip()

    if len(comment) > MAX_COMMENT_LENGTH:
        await message.answer(
            f"Комментарий длиннее {MAX_COMMENT_LENGTH} символов "
            f"(сейчас {len(comment)}). Сократите и отправьте ещё раз:",
            reply_markup=comment_step_keyboard(),
        )
        return

    await _save_threshold(comment=comment, state=state)
    confirmation_text = await _build_confirmation_text(state)
    await state.set_state(AddTickerStates.waiting_for_next_action)
    await message.answer(confirmation_text, reply_markup=add_another_threshold_keyboard())


# --- Шаг 6: "Добавить ещё порог" или "Готово" ---------------------------------------

@router.callback_query(AddTickerStates.waiting_for_next_action, F.data == "threshold:add_another")
async def handle_add_another(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.set_state(AddTickerStates.waiting_for_price)
    await callback.message.edit_text(
        f"Тикер {data['symbol']}. Введите ещё одну целевую цену в USD:",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@router.callback_query(AddTickerStates.waiting_for_next_action, F.data == "threshold:done")
async def handle_threshold_done(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Готово! Главное меню:", reply_markup=main_menu_keyboard())
    await callback.answer()


# --- Вспомогательные функции ----------------------------------------------------------

async def _save_threshold(comment: str | None, state: FSMContext) -> None:
    data = await state.get_data()
    repository.add_threshold(
        ticker_id=data["ticker_id"],
        target_price=data["target_price"],
        direction=data["direction"],
        comment=comment,
    )


async def _build_confirmation_text(state: FSMContext) -> str:
    data = await state.get_data()
    direction_text = "выше" if data["direction"] == "above" else "ниже"
    return (
        f"✅ Порог добавлен: {data['symbol']} {direction_text} ${data['target_price']}.\n\n"
        f"Добавить ещё один порог для {data['symbol']} или закончить?"
    )