"""
Проверка рабочих/нерабочих дней биржи NYSE/Nasdaq.

Учитывает и обычные выходные (суббота/воскресенье), и официальные праздники
биржи из config.EXCHANGE_HOLIDAYS_2026. На этом этапе список праздников —
просто список дат, вписанный руками в config.py; в будущем можно будет
получать его через отдельный API вместо хардкода.
"""

from datetime import date, datetime, timezone

from config import EXCHANGE_HOLIDAYS_2026

# Праздники сгруппированы по году — так проще добавлять следующие годы
# в будущем, не трогая логику этого модуля, а просто дописав в config.py
# EXCHANGE_HOLIDAYS_2027 и одну строку сюда.
_HOLIDAYS_BY_YEAR: dict[int, set[str]] = {
    2026: set(EXCHANGE_HOLIDAYS_2026),
}


def is_trading_day(check_date: date) -> bool:
    """
    Возвращает True, если в этот день биржа работает — то есть это не
    выходной и не праздник. Ничего не знает про конкретные часы сессии,
    только про сам день целиком.
    """
    # date.weekday(): понедельник = 0, ..., суббота = 5, воскресенье = 6
    if check_date.weekday() >= 5:
        return False

    year_holidays = _HOLIDAYS_BY_YEAR.get(check_date.year)
    if year_holidays is None:
        print(
            f"[market_calendar] Внимание: список праздников биржи для "
            f"{check_date.year} года не задан в config.py — проверяется "
            f"только выходной/будний день, без учёта праздников."
        )
        return True

    return check_date.isoformat() not in year_holidays


def get_upcoming_holidays(count: int = 5, from_date: date | None = None) -> list[date]:
    """
    Возвращает ближайшие `count` праздничных дат биржи, начиная от from_date
    (по умолчанию — сегодня по UTC). Обычные выходные сюда не попадают —
    в списке праздников их и так нет.

    Используется в пункте меню "показать ближайшие даты выходного на бирже".
    """
    if from_date is None:
        from_date = datetime.now(timezone.utc).date()

    all_holidays = [
        date.fromisoformat(holiday_str)
        for year_holidays in _HOLIDAYS_BY_YEAR.values()
        for holiday_str in year_holidays
    ]

    upcoming = sorted(holiday for holiday in all_holidays if holiday >= from_date)

    if len(upcoming) < count:
        print(
            f"[market_calendar] Внимание: в config.py заданы праздники "
            f"только на {sorted(_HOLIDAYS_BY_YEAR.keys())} — возвращаю "
            f"{len(upcoming)} из запрошенных {count}, дальше список пуст."
        )

    return upcoming[:count]


if __name__ == "__main__":
    today = datetime.now(timezone.utc).date()
    print(f"Сегодня (UTC): {today} ({today.strftime('%A')})")
    print(f"Рабочий день биржи: {is_trading_day(today)}\n")

    print("Ближайшие праздники биржи:")
    for holiday in get_upcoming_holidays():
        print(f"  {holiday} ({holiday.strftime('%A')})")