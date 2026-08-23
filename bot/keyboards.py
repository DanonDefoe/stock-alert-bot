"""
bot/keyboards.py — вся разметка inline-кнопок бота.

Здесь только разметка (какие кнопки показать и что положить в callback_data),
без какой-либо обработки нажатий: обработчики callback_data живут в
bot/handlers/.
"""

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


# --- Главное меню -------------------------------------------------------------

def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить тикер", callback_data="menu:add_ticker")
    builder.button(text="✏️ Редактировать тикер", callback_data="menu:edit_ticker")
    builder.button(text="⏸ Пауза / возобновление", callback_data="menu:pause_ticker")
    builder.button(text="❌ Удалить тикер", callback_data="menu:delete_ticker")
    builder.button(text="📝 Список тикеров", callback_data="menu:list_tickers")
    builder.button(text="🏝 Ближайшие выходные биржи", callback_data="menu:calendar")
    builder.button(text="📊 Статистика запросов", callback_data="menu:stats")
    builder.adjust(1)  # по одной кнопке в ряд — надёжнее с длинным текстом
    return builder.as_markup()


# --- Выбор тикера из списка -----------------------------------------------------
# Переиспользуется для паузы/возобновления, удаления и редактирования —
# разные экраны просто передают свой callback_prefix.

def ticker_selection_keyboard(tickers, callback_prefix: str) -> InlineKeyboardMarkup:
    """
    tickers — список строк из repository.list_tickers() (объекты с
    доступом по имени колонки: ticker["id"], ticker["symbol"], ticker["status"]).

    callback_prefix — например "pause_select", "delete_select", "edit_select".
    Хендлер потом получает callback_data вида "pause_select:42" и парсит id
    тикера после двоеточия.
    """
    builder = InlineKeyboardBuilder()
    for ticker in tickers:
        status_icon = "⏸" if ticker["status"] == "paused" else "▶️"
        builder.button(
            text=f"{status_icon} {ticker['symbol']}",
            callback_data=f"{callback_prefix}:{ticker['id']}",
        )
    builder.button(text="⬅️ Отмена", callback_data="cancel")
    builder.adjust(2)  # тикеры по 2 в ряд — компактнее, чем по одному
    return builder.as_markup()


# --- Выбор конкретного порога у тикера (для редактирования/удаления) ------------
# У одного тикера может быть несколько порогов — эта клавиатура даёт выбрать,
# какой именно редактировать.

def threshold_selection_keyboard(thresholds, callback_prefix: str) -> InlineKeyboardMarkup:
    """
    thresholds — список строк из repository.list_thresholds_for_ticker()
    (доступ по имени колонки: threshold["id"], ["target_price"], ["direction"]).

    callback_prefix — например "edit_threshold_select".
    """
    builder = InlineKeyboardBuilder()
    for threshold in thresholds:
        icon = "📈" if threshold["direction"] == "above" else "📉"
        comparator = "≥" if threshold["direction"] == "above" else "≤"
        builder.button(
            text=f"{icon} {comparator}${threshold['target_price']}",
            callback_data=f"{callback_prefix}:{threshold['id']}",
        )
    builder.button(text="⬅️ Отмена", callback_data="cancel")
    builder.adjust(2)
    return builder.as_markup()


# --- Что редактировать у выбранного порога ---------------------------------------

def edit_field_choice_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Изменить цену", callback_data="field:price")
    builder.button(text="✏️ Изменить направление", callback_data="field:direction")
    builder.button(text="✏️ Изменить комментарий", callback_data="field:comment")
    builder.button(text="❌ Удалить этот порог", callback_data="field:delete")
    builder.button(text="✅ Готово", callback_data="field:done")
    builder.adjust(1)
    return builder.as_markup()


# --- Направление порога (above/below) -------------------------------------------

def direction_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📈 Уведомить, когда выше", callback_data="direction:above")
    builder.button(text="📉 Уведомить, когда ниже", callback_data="direction:below")
    builder.button(text="↩️ Отмена", callback_data="cancel")
    builder.adjust(1)
    return builder.as_markup()


# --- Шаг с комментарием (необязательное поле, до 200 символов) ------------------

def comment_step_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Пропустить", callback_data="comment:skip")
    builder.button(text="Отмена", callback_data="cancel")
    builder.adjust(1)
    return builder.as_markup()


# --- "Добавить ещё порог или закончить" (после ввода первого порога) -----------

def add_another_threshold_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить ещё порог", callback_data="threshold:add_another")
    builder.button(text="✅ Закончить", callback_data="threshold:done")
    builder.adjust(1)
    return builder.as_markup()


# --- Подтверждение удаления тикера (необратимое действие) -----------------------

def confirm_delete_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Да, удалить", callback_data="confirm_delete")
    builder.button(text="Отмена", callback_data="cancel")
    builder.adjust(1)
    return builder.as_markup()


# --- Пустой список тикеров -------------------------------------------------------

def empty_list_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить тикер", callback_data="menu:add_ticker")
    builder.button(text="⬅️ Вернуться в меню", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


# --- Универсальная кнопка отмены -------------------------------------------------
# Для шагов, где пользователь вводит текст (например, цену) и других кнопок
# не требуется — только выход из диалога.

def cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Отмена", callback_data="cancel")
    return builder.as_markup()