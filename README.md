# «Дойма» — Telegram-бот для пар

Единый хаб пары: совместный календарь, идеи «куда сходить», поручения друг другу с мгновенными уведомлениями, список покупок, важные даты и личные списки желаний.

Документы: [CONCEPT.md](CONCEPT.md) · спека интервью `.omc/specs/deep-interview-couples-telegram-bot.md`

## Возможности

- 👩‍❤️‍👨 **Пара** — создаётся по одноразовой ссылке-приглашению (`t.me/<bot>?start=<код>`); один часовой пояс на пару
- 📅 **Календарь** — сетка месяца на inline-кнопках; напоминания за день и за 2 часа (или своё время)
- 💡 **Идеи** — общий вишлист «куда сходить»; кнопка «Запланировать» превращает идею в событие
- ✅ **Поручения** — полный цикл «Принять / Не могу / Готово», дедлайн, эскалация просрочки обоим
- 🛒 **Покупки** — общий список, отметка «куплено»
- 🎂 **Важные даты** — ежегодные, напоминание за неделю и в сам день (DST-корректно)
- 🎁 **Желания** — личный список; партнёр видит только на чтение, о просмотрах не сообщается
- Быстрые команды: `/todo купи хлеб`, `/buy молоко, яйца`, `/idea тот бар на крыше`

## Запуск (Linux)

Требуется Python 3.12+ и токен бота от [@BotFather](https://t.me/BotFather).

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
cp .env.example .env     # вписать BOT_TOKEN
.venv/bin/python -m bot.main
```

Работает через long polling — домен и HTTPS не нужны. БД — один файл SQLite (`doima.sqlite3`), бэкап = копия файла.

### Как сервис (systemd)

`/etc/systemd/system/doima-bot.service`:

```ini
[Unit]
Description=Doima Telegram bot
After=network-online.target
Wants=network-online.target

[Service]
User=doima
WorkingDirectory=/opt/doima-bot
ExecStart=/opt/doima-bot/.venv/bin/python -m bot.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now doima-bot
```

Рестарты безопасны: при старте бот отправляет все напоминания, созревшие за время простоя.

## Тесты

```bash
.venv/bin/pip install -e .[dev]
.venv/bin/python -m pytest
```

<details>
<summary>Разработка на Windows</summary>

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -e .[dev]
copy .env.example .env
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m bot.main
```

Пакет `tzdata` в зависимостях нужен именно для Windows (нет системной базы IANA-поясов); на Linux он не мешает — используется системная база.
</details>

Покрыто: создание/одноразовость пары, жизненный цикл поручений (включая гонки двух партнёров), правила напоминаний, DST для ежегодных дат, восстановление напоминаний после простоя любой длины, идемпотентность доставки.

## Архитектура (коротко)

- **aiogram 3** + **SQLAlchemy 2 (aiosqlite, WAL)**, один процесс
- Напоминания: таблица `Reminder` — единственный источник истины; минутный asyncio-цикл; первый тик после старта отправляет всё просроченное (простой не теряет напоминаний), отметка `sent` — optimistic UPDATE (нет двойных отправок)
- Время: в БД UTC; для ежегодных дат хранится локальное время, UTC пересчитывается на каждый год в поясе пары
- Полное обоснование решений — в ADR внутри плана консенсуса
