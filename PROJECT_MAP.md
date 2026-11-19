# Карта проекта Node Monitor Bot

Telegram-бот для периодической проверки нод (TCP/HTTP/HTTPS) и уведомлений об изменении статуса.

## Структура

```
/work
├── app/
│   ├── main.py                  точка входа: БД, диспетчер (admin → menu → fallback), scheduler, polling
│   ├── version.py               чтение версии из VERSION
│   ├── config.py                настройки из .env (pydantic-settings)
│   ├── database.py              async-движок SQLAlchemy, сессии, init_db()
│   ├── models/node.py           модель Node (адрес, протокол, таймаут, интервал, статус, вердикт Cheburcheck)
│   ├── handlers/admin.py        команды /start /help /add /list /remove /enable /disable /interval /check и fallback
│   ├── handlers/menu.py         inline/reply-меню, колбэки, FSM-мастера AddNode и SetInterval
│   ├── handlers/states.py       состояния FSM AddNode и SetInterval
│   ├── middlewares/admin.py     ограничение сообщений и колбэков по ADMIN_ID
│   ├── services/
│   │   ├── nodes.py             CRUD и атомарная запись результата проверки
│   │   ├── ping.py              TCP/HTTP(S) проверки, нормализация URL и ожидаемый текст ответа
│   │   ├── monitor.py           однократная проверка + запись результата в БД
│   │   ├── scheduler.py         APScheduler: опрос нод, Cheburcheck и сводки
│   │   ├── cheburcheck.py       запрос к API cheburcheck.ru, запись вердикта, троттлинг
│   │   └── notifier.py          отправка алертов с подавлением ошибок Telegram
│   ├── utils/formatting.py      форматирование статуса, карточки, алерта и сводки
│   ├── utils/intervals.py       разбор и форматирование интервалов s/m/h
│   └── utils/keyboards.py       reply/inline-клавиатуры меню, списка, карточки и мастеров
├── tests/                       pytest: ping, CRUD, monitor, cheburcheck, scheduler, updater, middleware, keyboards
├── conftest.py                  тестовые env-переменные и in-memory SQLite
├── .env.example                 шаблон переменных окружения
├── requirements.txt             зависимости (включая sqlalchemy[asyncio])
├── .dockerignore / Dockerfile / docker-compose.yml  контейнерный запуск
├── .github/workflows/docker-publish.yml  сборка и публикация образа в GHCR
├── updater.py                   host-updater: GitHub Release → бэкап → Telegram → update → rollback
├── deploy/                      примеры systemd unit/timer для updater
├── VERSION                      текущая версия бота (1.0)
├── DOCKER.md                    подробная инструкция по Docker
├── UPDATES.md                   автообновление, бэкапы и откат
└── README.md                    установка и команды бота
```

## Потоки данных

1. **Добавление ноды:** кнопка «Добавить ноду» или `/add` → FSM `AddNode` → `services/nodes.add_node()` → таблица `nodes`.
2. **Навигация:** reply-кнопки и inline-меню → `handlers/menu.py` → карточка ноды/список/подтверждение удаления; `/version` → `app/version.py`.
3. **Проверка:** `scheduler.poll_nodes()` по интервалу ноды, кнопка «Проверить» или `/check` → `monitor.check_node()` → `ping.PingService.check_node()` → `nodes.record_check_result()`.
4. **Алерт:** DOWN — после каждой проверки по интервалу, UP — один раз при восстановлении (`last_notified_status`) → `services/notifier.py` → `ALERT_CHAT_ID` (или `ADMIN_ID`).
5. **Cheburcheck:** раз в `CHEBURCHECK_INTERVAL_HOURS` (или кнопка в карточке) → `cheburcheck.refresh_nodes_blocked()` → `GET /api/v1/check?target=<host>` → `nodes.record_blocked_result()` → алерт при смене вердикта.
6. **Сводка:** по расписанию `send_summary()` → `utils.formatting.format_summary()` (включая счётчики Cheburcheck) → `SUMMARY_CHAT_ID` (или `ADMIN_ID`).
7. **Обновление:** `updater.py` на хосте → GitHub Release → архив кода/БД/`.env` → `sendDocument` в Telegram → `git checkout` + Docker Compose; при ошибке `rollback` из архива.

## Запуск и проверки

```bash
cp .env.example .env
pip install -r requirements.txt
python -m app.main
pytest -q
docker compose pull && docker compose up -d
```

Образ публикуется в `ghcr.io/hakunamaruna/node-monitor-bot:latest` через GitHub Actions.

Переменные: `BOT_TOKEN`, `ADMIN_ID`, `DB_URL`, `ALERT_CHAT_ID`, `SUMMARY_CHAT_ID`,
`POLL_TICK_SECONDS` (секунды), `SUMMARY_INTERVAL_HOURS`, `CHEBURCHECK_INTERVAL_HOURS`,
`CHEBURCHECK_STARTUP_DELAY_SEC`, `CHEBURCHECK_TIMEOUT_SEC`,
`CHEBURCHECK_REQUEST_DELAY_SEC`, `CHEBURCHECK_BASE_URL`.
