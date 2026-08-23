"""
bot/handlers/start.py — команда /start и показ главного меню.

Также содержит общий обработчик кнопки "Отмена", которая встречается в
нескольких клавиатурах (bot/keyboards.py) — чтобы не дублировать этот код
в каждом хендлере с многошаговым диалогом (add_ticker, edit_ticker и т.д.).
"""

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards import main_menu_keyboard
from db import repository

router = Router()

WELCOME_TEXT = (
    "Привет! Я слежу за ценами акций на американском рынке и присылаю "
    "уведомление, когда цена достигает заданного значения.\n\n"
    "Выберите действие:"
)

MAIN_MENU_TEXT = "Главное меню. Выбери действие:"


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    """
    Регистрирует пользователя в БД (если это первое обращение — создаёт
    запись, иначе просто использует существующую) и показывает главное меню.
    """
    repository.get_or_create_user(message.chat.id)
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "cancel")
async def handle_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Общий обработчик кнопки "Отмена" — встречается в клавиатурах всех
    многошаговых диалогов. Сбрасывает текущее состояние FSM (если оно
    было) и возвращает пользователя в главное меню.
    """
    await state.clear()
    await callback.message.edit_text(MAIN_MENU_TEXT, reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "menu:main")
async def handle_back_to_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Возврат в главное меню с любого экрана. Другие хендлеры смогут
    предложить этот путь, просто добавив кнопку с callback_data="menu:main"
    (например, после успешного добавления тикера — "Готово, в меню").
    """
    await state.clear()
    await callback.message.edit_text(MAIN_MENU_TEXT, reply_markup=main_menu_keyboard())
    await callback.answer()