# Карта проекта Node Monitor Bot

Telegram-бот для периодической проверки нод (TCP/HTTP/HTTPS) и уведомлений об изменении статуса.

## Структура

```
/work
├── app/
│   ├── main.py                  точка входа: БД, диспетчер, middleware, scheduler, polling
│   ├── config.py                настройки из .env (pydantic-settings)
│   ├── database.py              async-движок SQLAlchemy, сессии, init_db()
│   ├── models/node.py           модель Node (адрес, протокол, таймаут, ожидаемый ответ, статус)
│   ├── handlers/admin.py        команды /start /help /add /list /remove /enable /disable /check
│   ├── middlewares/admin.py     ограничение команд по ADMIN_ID
│   ├── services/
│   │   ├── nodes.py             CRUD и обновление статуса нод
│   │   ├── ping.py              TCP/HTTP(S) проверки и ожидаемый текст ответа
│   │   ├── monitor.py           однократная проверка + запись результата в БД
│   │   └── scheduler.py         APScheduler: проверки и сводки, отправка алертов в Telegram
│   └── utils/formatting.py      форматирование статуса, алерта и сводки
├── tests/                       pytest: ping, CRUD, monitor, scheduler, middleware
├── conftest.py                  тестовые env-переменные и in-memory SQLite
├── .env.example                 шаблон переменных окружения
├── requirements.txt             зависимости (включая sqlalchemy[asyncio])
├── Dockerfile / docker-compose.yml  контейнерный запуск
└── README.md                    установка и команды бота
```

## Потоки данных

1. **Добавление ноды:** команда `/add` → `services/nodes.add_node()` → таблица `nodes`.
2. **Проверка:** `scheduler.check_all()` или `/check` → `monitor.check_node()` → `ping.PingService.check_node()` → `nodes.update_node_status()`.
3. **Алерт:** при изменении `last_status` scheduler/handler отправляет сообщение в `ALERT_CHAT_ID` (или `ADMIN_ID`).
4. **Сводка:** по расписанию `send_summary()` → `utils.formatting.format_summary()` → `SUMMARY_CHAT_ID` (или `ADMIN_ID`).

## Запуск и проверки

```bash
cp .env.example .env
pip install -r requirements.txt
python -m app.main
pytest -q
docker-compose up -d
```

Переменные: `BOT_TOKEN`, `ADMIN_ID`, `DB_URL`, `ALERT_CHAT_ID`, `SUMMARY_CHAT_ID`,
`DEFAULT_CHECK_INTERVAL` (минуты), `SUMMARY_INTERVAL_HOURS`.
