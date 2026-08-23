"""
bot/handlers/calendar_info.py — пункт меню "ближайшие выходные биржи".

Самый простой хендлер из всех: без диалога, без состояния FSM — по нажатию
кнопки сразу показывает список ближайших праздничных дат биржи и возвращает
главное меню, чтобы можно было сразу выбрать следующее действие.
"""

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.keyboards import main_menu_keyboard
from services import market_calendar

router = Router()

HOLIDAYS_TO_SHOW = 5

# date.strftime("%A") без установленной русской локали вернёт английское
# название дня недели — поэтому переводим вручную для пользовательского текста.
_WEEKDAY_NAMES_RU = {
    0: "понедельник",
    1: "вторник",
    2: "среда",
    3: "четверг",
    4: "пятница",
    5: "суббота",
    6: "воскресенье",
}


@router.callback_query(F.data == "menu:calendar")
async def show_calendar(callback: CallbackQuery) -> None:
    holidays = market_calendar.get_upcoming_holidays(count=HOLIDAYS_TO_SHOW)

    if not holidays:
        text = (
            "Не нашёл ближайших праздничных дат биржи — возможно, список "
            "праздников в не покрывает текущий период. Проверьте файл конфига."
        )
    else:
        lines = ["Ближайшие нерабочие дни биржи (кроме обычных выходных):", ""]
        for holiday in holidays:
            weekday_name = _WEEKDAY_NAMES_RU[holiday.weekday()]
            lines.append(f"• {holiday.strftime('%d.%m.%Y')} ({weekday_name})")
        text = "\n".join(lines)

    await callback.message.edit_text(text, reply_markup=main_menu_keyboard())
    await callback.answer()