# 📈 Stock Alert Bot

Телеграм-бот для отслеживания цен акций на американском рынке.
A Telegram bot that tracks US stock prices and notifies you on target hits.

[🇷🇺 Русский](#русский) · [🇬🇧 English](#english)

---

## Русский

Телеграм-бот, который следит за ценами акций на американском рынке (NYSE/Nasdaq)
через [Finnhub API](https://finnhub.io/) и присылает уведомление, когда цена
достигает заданного порога.

### Возможности

- Добавление тикеров с произвольным числом ценовых порогов на каждый
- Уведомление срабатывает и при росте цены **выше** порога, и при падении **ниже**
- Необязательный комментарий к уведомлению (до 200 символов)
- Редактирование существующих порогов: цена, направление, комментарий
- Пауза / возобновление отслеживания тикера
- Полное удаление тикера вместе со всеми его порогами
- Список отслеживаемых тикеров с текущими и целевыми ценами
- Ближайшие нерабочие дни биржи (кроме обычных выходных)
- Статистика по количеству запросов к Finnhub за сутки
- Проверка цен по расписанию (2 раза в день, время задаётся в UTC), с пропуском
  выходных и праздников биржи
- Уведомление разовое — после срабатывания порог автоматически удаляется

### Стек технологий

- **Python** 3.12 / 3.13
- **[aiogram](https://docs.aiogram.dev/) 3.x** — Telegram Bot API
- **SQLite** — хранение тикеров, порогов и статистики запросов
- **[Finnhub API](https://finnhub.io/)** — котировки акций

### Структура проекта

```
stock-alert-bot/
├── .env                     # секреты (не в git)
├── .env.example
├── .gitignore
├── requirements.txt
├── main.py                  # точка входа
├── config.py                # все константы: расписание, праздники, пути
│
├── bot/
│   ├── keyboards.py          # разметка inline-клавиатур
│   ├── notifier.py           # отправка сообщений в Telegram
│   └── handlers/
│       ├── start.py           # /start и главное меню
│       ├── add_ticker.py      # добавление тикера и порогов
│       ├── edit_ticker.py     # редактирование порогов
│       ├── manage_tickers.py  # пауза/возобновление, удаление тикера
│       ├── calendar_info.py   # ближайшие выходные биржи
│       └── stats.py           # статистика запросов к API
│
├── db/
│   ├── database.py            # подключение к SQLite, создание таблиц
│   └── repository.py          # все операции чтения/записи в БД
│
├── services/
│   ├── finnhub_client.py      # обёртка над Finnhub API
│   ├── market_calendar.py     # рабочие/нерабочие дни биржи
│   ├── price_checker.py       # сравнение цены с порогами
│   └── scheduler.py           # фоновый цикл проверки по расписанию
│
└── data/
    └── bot.db                 # файл SQLite (создаётся автоматически)
```

### Установка и запуск

1. **Клонировать репозиторий и перейти в папку проекта:**
   ```bash
   git clone <repo-url>
   cd stock-alert-bot
   ```

2. **Создать виртуальное окружение и установить зависимости:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Получить необходимые ключи:**
   - Токен бота — через [@BotFather](https://t.me/BotFather) в Telegram (`/newbot`)
   - API-ключ Finnhub — бесплатная регистрация на [finnhub.io](https://finnhub.io/)

4. **Настроить переменные окружения** — скопировать `.env.example` в `.env`
   и вписать реальные значения:
   ```
   BOT_TOKEN=...
   FINNHUB_API_KEY=...
   ```

5. **Запустить бота:**
   ```bash
   python main.py
   ```

### Конфигурация

Все настраиваемые константы собраны в `config.py`:

| Константа | Назначение |
|---|---|
| `PRICE_CHECK_TIMES_UTC` | Время проверки цен (2 значения в UTC) |
| `EXCHANGE_HOLIDAYS_2026` | Нерабочие дни биржи NYSE/Nasdaq |
| `DB_PATH` | Путь к файлу SQLite |
| `DAILY_API_CALL_SOFT_LIMIT` | Собственный ориентир по числу запросов к Finnhub в сутки |

### Ограничения текущей версии

- Однопользовательский режим (задел на мультиюзер в схеме БД уже есть)
- Список праздников биржи задаётся вручную в коде, только на 2026 год
- Проверка цен — фиксированное расписание для всех тикеров (2 раза в день)

### Планы на будущее

- Поддержка нескольких пользователей
- Настраиваемая частота проверки для отдельных тикеров (3/4/6 раз в день или
  ежечасно в торговые часы)
- Графики истории цены
- Автоматическое получение календаря нерабочих дней биржи через API
- Отслеживание тикеров других стран


---


## English

A Telegram bot that tracks US stock prices (NYSE/Nasdaq) via the
[Finnhub API](https://finnhub.io/) and notifies you when a price hits a
target you've set.

### Features

- Add tickers with any number of price thresholds each
- Notifies both when price rises **above** and falls **below** a target
- Optional comment attached to each notification (up to 200 characters)
- Edit existing thresholds: price, direction, comment
- Pause / resume tracking for a ticker
- Fully delete a ticker along with all of its thresholds
- List of tracked tickers with current and target prices
- Upcoming exchange holidays (excluding regular weekends)
- Daily Finnhub API call statistics
- Scheduled price checks (twice a day, UTC times configurable), skipping
  weekends and exchange holidays
- One-shot notifications — a threshold is removed automatically once it fires

### Tech stack

- **Python** 3.12 / 3.13
- **[aiogram](https://docs.aiogram.dev/) 3.x** — Telegram Bot API
- **SQLite** — stores tickers, thresholds, and API usage stats
- **[Finnhub API](https://finnhub.io/)** — stock quotes

### Project structure

```
stock-alert-bot/
├── .env                     # secrets (not committed)
├── .env.example
├── .gitignore
├── requirements.txt
├── main.py                  # entry point
├── config.py                # all constants: schedule, holidays, paths
│
├── bot/
│   ├── keyboards.py          # inline keyboard layouts
│   ├── notifier.py           # sending Telegram messages
│   └── handlers/
│       ├── start.py           # /start and main menu
│       ├── add_ticker.py      # adding a ticker and thresholds
│       ├── edit_ticker.py     # editing thresholds
│       ├── manage_tickers.py  # pause/resume, delete ticker
│       ├── calendar_info.py   # upcoming exchange holidays
│       └── stats.py           # API usage stats
│
├── db/
│   ├── database.py            # SQLite connection, table creation
│   └── repository.py          # all read/write DB operations
│
├── services/
│   ├── finnhub_client.py      # Finnhub API wrapper
│   ├── market_calendar.py     # trading/non-trading day checks
│   ├── price_checker.py       # comparing price against thresholds
│   └── scheduler.py           # background scheduled-check loop
│
└── data/
    └── bot.db                 # SQLite file (created automatically)
```

### Setup

1. **Clone the repository and move into the project folder:**
   ```bash
   git clone <repo-url>
   cd stock-alert-bot
   ```

2. **Create a virtual environment and install dependencies:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Get the required keys:**
   - Bot token — via [@BotFather](https://t.me/BotFather) on Telegram (`/newbot`)
   - Finnhub API key — free sign-up at [finnhub.io](https://finnhub.io/)

4. **Set up environment variables** — copy `.env.example` to `.env` and fill
   in real values:
   ```
   BOT_TOKEN=...
   FINNHUB_API_KEY=...
   ```

5. **Run the bot:**
   ```bash
   python main.py
   ```

### Configuration

All configurable constants live in `config.py`:

| Constant | Purpose |
|---|---|
| `PRICE_CHECK_TIMES_UTC` | Price check times (2 UTC values) |
| `EXCHANGE_HOLIDAYS_2026` | NYSE/Nasdaq exchange holidays |
| `DB_PATH` | Path to the SQLite file |
| `DAILY_API_CALL_SOFT_LIMIT` | Self-imposed daily Finnhub call reference limit |

### Current limitations

- Single-user only (the DB schema already has multi-user support built in)
- Exchange holidays are hardcoded, currently only for 2026
- Price checks run on one fixed schedule shared by all tickers (twice a day)

### Roadmap

- Multi-user support
- Per-ticker configurable check frequency (3/4/6 times a day, or hourly during
  trading hours)
- Price history charts
- Fetching the exchange holiday calendar automatically via an API
- Tracking tickers from other countries' markets