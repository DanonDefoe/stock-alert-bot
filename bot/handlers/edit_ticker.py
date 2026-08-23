"""
bot/handlers/edit_ticker.py — диалог редактирования порога у существующего тикера.

Сценарий:
1. Выбор тикера из списка отслеживаемых.
2. Выбор порога (если у тикера их несколько).
3. Выбор, что менять: цену / направление / комментарий / удалить порог.
4. После правки — снова экран "что менять" (можно поправить сразу несколько
   полей), пока не нажмут "Готово".
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.keyboards import (
    cancel_keyboard,
    comment_step_keyboard,
    direction_keyboard,
    edit_field_choice_keyboard,
    main_menu_keyboard,
    threshold_selection_keyboard,
    ticker_selection_keyboard,
)
from db import repository

router = Router()

MAX_COMMENT_LENGTH = 200


class EditTickerStates(StatesGroup):
    choosing_ticker = State()
    choosing_threshold = State()
    choosing_field = State()
    editing_price = State()
    editing_direction = State()
    editing_comment = State()


# --- Шаг 1: выбор тикера ------------------------------------------------------------

@router.callback_query(F.data == "menu:edit_ticker")
async def start_edit_ticker(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = repository.get_or_create_user(callback.message.chat.id)
    tickers = repository.list_tickers(user_id)

    if not tickers:
        await callback.message.edit_text(
            "У тебя пока нет отслеживаемых тикеров — сначала добавь через «Добавить тикер».",
            reply_markup=main_menu_keyboard(),
        )
        await callback.answer()
        return

    await state.set_state(EditTickerStates.choosing_ticker)
    await callback.message.edit_text(
        "Какой тикер редактировать?",
        reply_markup=ticker_selection_keyboard(tickers, callback_prefix="edit_select"),
    )
    await callback.answer()


# --- Шаг 2: выбор порога у тикера ----------------------------------------------------

@router.callback_query(EditTickerStates.choosing_ticker, F.data.startswith("edit_select:"))
async def handle_ticker_selected(callback: CallbackQuery, state: FSMContext) -> None:
    ticker_id = int(callback.data.split(":", 1)[1])
    ticker = repository.get_ticker(ticker_id)
    thresholds = repository.list_thresholds_for_ticker(ticker_id)

    await state.update_data(ticker_id=ticker_id, symbol=ticker["symbol"])

    if not thresholds:
        # В норме такого не бывает — у тикера всегда есть хотя бы один
        # порог. Но на всякий случай не даём диалогу зайти в тупик.
        await state.clear()
        await callback.message.edit_text(
            f"У тикера {ticker['symbol']} почему-то нет порогов. Возвращаю в меню.",
            reply_markup=main_menu_keyboard(),
        )
        await callback.answer()
        return

    await state.set_state(EditTickerStates.choosing_threshold)
    await callback.message.edit_text(
        f"Тикер {ticker['symbol']}. Какой порог редактировать?",
        reply_markup=threshold_selection_keyboard(thresholds, callback_prefix="edit_threshold_select"),
    )
    await callback.answer()


# --- Шаг 3: выбор поля для редактирования ---------------------------------------------

@router.callback_query(EditTickerStates.choosing_threshold, F.data.startswith("edit_threshold_select:"))
async def handle_threshold_selected(callback: CallbackQuery, state: FSMContext) -> None:
    threshold_id = int(callback.data.split(":", 1)[1])
    await state.update_data(threshold_id=threshold_id)
    await state.set_state(EditTickerStates.choosing_field)

    text = await _field_choice_screen_text(state)
    await callback.message.edit_text(text, reply_markup=edit_field_choice_keyboard())
    await callback.answer()


# --- Изменение цены -----------------------------------------------------------------------

@router.callback_query(EditTickerStates.choosing_field, F.data == "field:price")
async def ask_new_price(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(EditTickerStates.editing_price)
    await callback.message.edit_text(
        "Введи новую целевую цену в USD (целое число):",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@router.message(EditTickerStates.editing_price)
async def save_new_price(message: Message, state: FSMContext) -> None:
    if message.text is None:
        await message.answer("Пришли цену текстом, например 250.", reply_markup=cancel_keyboard())
        return

    raw_price = message.text.strip()
    if not raw_price.isdigit() or int(raw_price) <= 0:
        await message.answer(
            "Цена должна быть целым положительным числом в USD. Попробуй ещё раз:",
            reply_markup=cancel_keyboard(),
        )
        return

    data = await state.get_data()
    repository.update_threshold(data["threshold_id"], target_price=int(raw_price))
    await state.set_state(EditTickerStates.choosing_field)

    text = await _field_choice_screen_text(state)
    await message.answer(text, reply_markup=edit_field_choice_keyboard())


# --- Изменение направления ------------------------------------------------------------------

@router.callback_query(EditTickerStates.choosing_field, F.data == "field:direction")
async def ask_new_direction(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(EditTickerStates.editing_direction)
    await callback.message.edit_text(
        "При каком условии присылать уведомление?",
        reply_markup=direction_keyboard(),
    )
    await callback.answer()


@router.callback_query(EditTickerStates.editing_direction, F.data.startswith("direction:"))
async def save_new_direction(callback: CallbackQuery, state: FSMContext) -> None:
    direction = callback.data.split(":", 1)[1]  # "above" или "below"

    data = await state.get_data()
    repository.update_threshold(data["threshold_id"], direction=direction)
    await state.set_state(EditTickerStates.choosing_field)

    text = await _field_choice_screen_text(state)
    await callback.message.edit_text(text, reply_markup=edit_field_choice_keyboard())
    await callback.answer()


# --- Изменение комментария --------------------------------------------------------------------

@router.callback_query(EditTickerStates.choosing_field, F.data == "field:comment")
async def ask_new_comment(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(EditTickerStates.editing_comment)
    await callback.message.edit_text(
        f"Отправь новый комментарий (до {MAX_COMMENT_LENGTH} символов) "
        f"или нажми «Пропустить», чтобы убрать текущий:",
        reply_markup=comment_step_keyboard(),
    )
    await callback.answer()


@router.callback_query(EditTickerStates.editing_comment, F.data == "comment:skip")
async def clear_comment(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    repository.update_threshold(data["threshold_id"], comment=None)
    await state.set_state(EditTickerStates.choosing_field)

    text = await _field_choice_screen_text(state)
    await callback.message.edit_text(text, reply_markup=edit_field_choice_keyboard())
    await callback.answer()


@router.message(EditTickerStates.editing_comment)
async def save_new_comment(message: Message, state: FSMContext) -> None:
    if message.text is None:
        await message.answer(
            "Пришли комментарий текстом или нажми «Пропустить».",
            reply_markup=comment_step_keyboard(),
        )
        return

    comment = message.text.strip()
    if len(comment) > MAX_COMMENT_LENGTH:
        await message.answer(
            f"Комментарий длиннее {MAX_COMMENT_LENGTH} символов "
            f"(сейчас {len(comment)}). Сократи и отправь ещё раз:",
            reply_markup=comment_step_keyboard(),
        )
        return

    data = await state.get_data()
    repository.update_threshold(data["threshold_id"], comment=comment)
    await state.set_state(EditTickerStates.choosing_field)

    text = await _field_choice_screen_text(state)
    await message.answer(text, reply_markup=edit_field_choice_keyboard())


# --- Удаление порога и завершение редактирования -------------------------------------------------

@router.callback_query(EditTickerStates.choosing_field, F.data == "field:delete")
async def handle_delete_threshold(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    repository.delete_threshold(data["threshold_id"])

    remaining = repository.list_thresholds_for_ticker(data["ticker_id"])

    if remaining:
        await state.set_state(EditTickerStates.choosing_threshold)
        await callback.message.edit_text(
            f"Порог удалён. У тикера {data['symbol']} остались другие пороги — "
            f"выбери, какой редактировать:",
            reply_markup=threshold_selection_keyboard(remaining, callback_prefix="edit_threshold_select"),
        )
    else:
        await state.clear()
        await callback.message.edit_text(
            f"Порог удалён. У тикера {data['symbol']} больше не осталось порогов.\n"
            f"Если он больше не нужен — удали его полностью через пункт меню «Удалить тикер».",
            reply_markup=main_menu_keyboard(),
        )
    await callback.answer()


@router.callback_query(EditTickerStates.choosing_field, F.data == "field:done")
async def finish_editing(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Готово! Главное меню:", reply_markup=main_menu_keyboard())
    await callback.answer()


# --- Вспомогательные функции ------------------------------------------------------------------------

def _format_threshold_summary(symbol: str, threshold) -> str:
    direction_text = "выше" if threshold["direction"] == "above" else "ниже"
    comment_line = f"\n💬 {threshold['comment']}" if threshold["comment"] else "\n💬 (без комментария)"
    return (
        f"Тикер: {symbol}\n"
        f"Условие: уведомить, когда {direction_text} ${threshold['target_price']}"
        f"{comment_line}\n\n"
        f"Что редактируем?"
    )


async def _field_choice_screen_text(state: FSMContext) -> str:
    data = await state.get_data()
    threshold = repository.get_threshold(data["threshold_id"])
    return _format_threshold_summary(data["symbol"], threshold)