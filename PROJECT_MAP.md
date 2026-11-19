# Карта проекта Node Monitor Bot

Telegram-бот для периодической проверки нод (TCP/HTTP/HTTPS) и уведомлений об изменении статуса.

## Структура

```
/work
├── app/
│   ├── main.py                  точка входа: БД, диспетчер (admin → menu → fallback), scheduler, polling
│   ├── version.py               чтение версии из VERSION
│   ├── config.py                настройки из .env (pydantic-settings, ALERT_REPEAT_MINUTES)
│   ├── database.py              async-движок SQLAlchemy, сессии, init_db()
│   ├── models/node.py           модель Node (адрес, протокол, таймаут, интервал, статус, Cheburcheck, метрики, история, status_since, last_alert_time)
│   ├── handlers/admin.py        команды /start /help /add /list /remove /enable /disable /interval /check и fallback
│   ├── handlers/menu.py         inline/reply-меню, колбэки, FSM-мастера AddNode и SetInterval
│   ├── handlers/states.py       состояния FSM AddNode и SetInterval
│   ├── middlewares/admin.py     ограничение сообщений и колбэков по ADMIN_ID
│   ├── services/
│   │   ├── nodes.py             CRUD и запись результата с метриками в историю проверок
│   │   ├── ping.py              TCP/HTTP(S) проверки, задержка, причина ошибки, нормализация URL
│   │   ├── monitor.py           однократная проверка + запись результата в БД
│   │   ├── scheduler.py         APScheduler: опрос нод, Cheburcheck и сводки
│   │   ├── cheburcheck.py       запрос к API cheburcheck.ru, запись вердикта, троттлинг
│   │   └── notifier.py          отправка алертов с подавлением ошибок Telegram
│   ├── utils/design.py          иконки, HTML-экранирование, лимиты списков
│   ├── utils/history.py         история проверок: 24ч окно, uptime, сериализация JSON
│   ├── utils/formatting.py      блочное форматирование карточки, алертов, сводки, отчётов Cheburcheck, меню и справки
│   ├── utils/intervals.py       разбор и форматирование интервалов s/m/h
│   └── utils/keyboards.py       reply/inline-клавиатуры, иконки и пагинация списка
├── tests/                       pytest: ping, CRUD, monitor, cheburcheck, scheduler, updater, middleware, keyboards, formatting, history
├── conftest.py                  тестовые env-переменные и in-memory SQLite
├── .env.example                 шаблон переменных окружения
├── requirements.txt             зависимости (включая sqlalchemy[asyncio])
├── .dockerignore / Dockerfile / docker-compose.yml  контейнерный запуск
├── .github/workflows/docker-publish.yml  сборка и публикация образа в GHCR
├── updater.py                   host-updater: GitHub Release → проверка worktree/версии → бэкап → Telegram → update → rollback
├── deploy/                      примеры systemd unit/timer для updater
├── VERSION                      текущая версия бота (1.6)
├── DOCKER.md                    подробная инструкция по Docker
├── UPDATES.md                   автообновление, бэкапы и откат
└── README.md                    установка и команды бота
```

## Потоки данных

1. **Добавление ноды:** кнопка «Добавить ноду» или `/add` → FSM `AddNode` → `services/nodes.add_node()` → таблица `nodes`.
2. **Навигация:** reply-кнопки и inline-меню → `handlers/menu.py` → карточка ноды/список с пагинацией по 20 нод/подтверждение удаления; `/version` → `app/version.py`.
3. **Проверка:** `scheduler.poll_nodes()` по интервалу ноды, кнопка «Проверить» или `/check` → `monitor.check_node()` → `ping.PingService.check_node_detailed()` → `nodes.record_check_result()` (статус, `status_since`, задержка, ошибка, счётчик неудач, история, `last_alert_time`).
4. **Алерт:** DOWN — при смене статуса или не чаще одного раза в `ALERT_REPEAT_MINUTES`, UP — один раз при восстановлении (`last_notified_status`) с длительностью простоя → `services/notifier.py` → `ALERT_CHAT_ID` (или `ADMIN_ID`).
5. **Cheburcheck:** раз в `CHEBURCHECK_INTERVAL_HOURS` (или кнопка в карточке) → `cheburcheck.refresh_nodes_blocked()` → `GET /api/v1/check?target=<host>` → `nodes.record_blocked_result()` → алерт при смене вердикта; шедулярный прогон дополнительно отправляет отчёт в `SUMMARY_CHAT_ID` (или `ADMIN_ID`).
6. **Сводка:** по расписанию `send_summary()` → `utils.formatting.format_summary()` (счётчики Cheburcheck и средний uptime 24h) → `SUMMARY_CHAT_ID` (или `ADMIN_ID`).
7. **Обновление:** `updater.py` на хосте → GitHub Release → проверка чистого worktree → архив кода/БД/`.env` → `sendDocument` в Telegram → `git checkout` + проверка `VERSION` + Docker Compose; при ошибке `rollback` из архива.

## Запуск и проверки

```bash
cp .env.example .env
pip install -r requirements.txt
python -m app.main
pytest -q
docker compose pull && docker compose up -d
```

Образ публикуется в `ghcr.io/hakunamaruna/node-monitor-bot:latest` через GitHub Actions.

Переменные: `BOT_TOKEN`, `ADMIN_ID`, `DB_URL`, `ALERT_CHAT_ID`, `SUMMARY_CHAT_ID`, `ALERT_REPEAT_MINUTES`,
`POLL_TICK_SECONDS` (секунды), `SUMMARY_INTERVAL_HOURS`, `CHEBURCHECK_INTERVAL_HOURS`,
`CHEBURCHECK_STARTUP_DELAY_SEC`, `CHEBURCHECK_TIMEOUT_SEC`,
`CHEBURCHECK_REQUEST_DELAY_SEC`, `CHEBURCHECK_BASE_URL`.
