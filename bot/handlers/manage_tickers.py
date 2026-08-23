"""
bot/handlers/manage_tickers.py — управление самим тикером (не порогами):
пауза/возобновление отслеживания и полное удаление тикера.

Оба сценария — чисто кнопочные, без ввода текста: выбрал тикер из списка →
либо статус переключился сразу, либо (для удаления) переспросили подтверждение.
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery

from bot.keyboards import confirm_delete_keyboard, main_menu_keyboard, ticker_selection_keyboard
from db import repository

router = Router()

TOGGLE_SCREEN_TEXT = "Нажмите на тикер, чтобы поставить или снять паузу:"


class ManageTickerStates(StatesGroup):
    choosing_ticker_to_toggle = State()
    choosing_ticker_to_delete = State()
    confirming_delete = State()


# --- Пауза / возобновление (переключатель) ----------------------------------------

@router.callback_query(F.data == "menu:pause_ticker")
async def start_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = repository.get_or_create_user(callback.message.chat.id)
    tickers = repository.list_tickers(user_id)

    if not tickers:
        await callback.message.edit_text(
            "У вас пока нет отслеживаемых тикеров.",
            reply_markup=main_menu_keyboard(),
        )
        await callback.answer()
        return

    await state.set_state(ManageTickerStates.choosing_ticker_to_toggle)
    await callback.message.edit_text(
        TOGGLE_SCREEN_TEXT,
        reply_markup=ticker_selection_keyboard(tickers, callback_prefix="toggle_select"),
    )
    await callback.answer()


@router.callback_query(ManageTickerStates.choosing_ticker_to_toggle, F.data.startswith("toggle_select:"))
async def handle_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    ticker_id = int(callback.data.split(":", 1)[1])
    ticker = repository.get_ticker(ticker_id)

    new_status = "active" if ticker["status"] == "paused" else "paused"
    repository.set_ticker_status(ticker_id, new_status)
    status_text = "возобновлено" if new_status == "active" else "приостановлено"

    # Остаёмся на этом же экране — список обновляем, чтобы можно было
    # переключить статус сразу у нескольких тикеров за один заход.
    user_id = repository.get_or_create_user(callback.message.chat.id)
    tickers = repository.list_tickers(user_id)

    await callback.message.edit_text(
        f"✅ Отслеживание {ticker['symbol']} {status_text}.\n\n{TOGGLE_SCREEN_TEXT}",
        reply_markup=ticker_selection_keyboard(tickers, callback_prefix="toggle_select"),
    )
    await callback.answer()


# --- Удаление тикера целиком (с подтверждением) ------------------------------------

@router.callback_query(F.data == "menu:delete_ticker")
async def start_delete(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = repository.get_or_create_user(callback.message.chat.id)
    tickers = repository.list_tickers(user_id)

    if not tickers:
        await callback.message.edit_text(
            "У вас пока нет отслеживаемых тикеров.",
            reply_markup=main_menu_keyboard(),
        )
        await callback.answer()
        return

    await state.set_state(ManageTickerStates.choosing_ticker_to_delete)
    await callback.message.edit_text(
        "Какой тикер удалить полностью (вместе со всеми его порогами)?",
        reply_markup=ticker_selection_keyboard(tickers, callback_prefix="delete_select"),
    )
    await callback.answer()


@router.callback_query(ManageTickerStates.choosing_ticker_to_delete, F.data.startswith("delete_select:"))
async def confirm_delete_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    ticker_id = int(callback.data.split(":", 1)[1])
    ticker = repository.get_ticker(ticker_id)
    thresholds = repository.list_thresholds_for_ticker(ticker_id)

    await state.update_data(ticker_id=ticker_id, symbol=ticker["symbol"])
    await state.set_state(ManageTickerStates.confirming_delete)

    thresholds_word = _pluralize_thresholds(len(thresholds))
    await callback.message.edit_text(
        f"Удалить {ticker['symbol']} и {len(thresholds)} {thresholds_word}? Это необратимо.",
        reply_markup=confirm_delete_keyboard(),
    )
    await callback.answer()


@router.callback_query(ManageTickerStates.confirming_delete, F.data == "confirm_delete")
async def execute_delete(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    repository.delete_ticker(data["ticker_id"])
    await state.clear()

    await callback.message.edit_text(
        f"🗑 Тикер {data['symbol']} и все его пороги удалены.",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


# --- Вспомогательные функции ------------------------------------------------------

def _pluralize_thresholds(count: int) -> str:
    """Склонение слова 'порог' под число: 1 порог, 2 порога, 5 порогов."""
    if count % 10 == 1 and count % 100 != 11:
        return "порог"
    if 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
        return "порога"
    return "порогов"