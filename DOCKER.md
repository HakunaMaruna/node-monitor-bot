# Установка Node Monitor Bot через Docker

Готовый образ собирается и публикуется в GitHub Container Registry при каждом push в `main`:

```
ghcr.io/hakunamaruna/node-monitor-bot:latest
```

## 1. Что понадобится

- Docker 24+ и Docker Compose Plugin (`docker compose version`).
- Токен Telegram-бота от [@BotFather](https://t.me/BotFather) и твой Telegram ID.
- Сервер с доступом в интернет (Telegram API и реестр образов).

Проверь установку:

```bash
docker --version
docker compose version
```

## 2. Подготовка

```bash
git clone https://github.com/HakunaMaruna/node-monitor-bot.git
cd node-monitor-bot
cp .env.example .env
nano .env
```

Заполни как минимум:

```dotenv
BOT_TOKEN=123456789:AA...        # токен от @BotFather
ADMIN_ID=123456789               # твой Telegram ID
ALERT_CHAT_ID=                   # оставь пустым, если алерты в ADMIN_ID
SUMMARY_CHAT_ID=                 # оставь пустым, если сводка в ADMIN_ID
ALERT_REPEAT_MINUTES=15          # 0 — без подавления повторных DOWN-алертов
POLL_TICK_SECONDS=1              # как часто проверять расписание нод
SUMMARY_INTERVAL_HOURS=1         # периодичность сводки
CHEBURCHECK_INTERVAL_HOURS=6     # периодичность проверки блокировок
CHEBURCHECK_STARTUP_DELAY_SEC=10 # первая проверка после старта бота
CHEBURCHECK_TIMEOUT_SEC=10       # таймаут запроса к Cheburcheck
CHEBURCHECK_REQUEST_DELAY_SEC=2.1 # пауза между нодами (лимит API ~30 req/min)
```

`DB_URL` в `.env` можно не трогать: `docker-compose.yml` сам задаёт путь
`sqlite+aiosqlite:////app/data/nodes.db` внутри контейнера.

Файл `.env` не должен попадать в git — он уже добавлен в `.gitignore` и `.dockerignore`.

## 3. Запуск из готового образа (рекомендуется)

```bash
docker compose pull
docker compose up -d
```

Compose сам создаст том `bot-data`, смонтирует его в `/app/data` и поднимет контейнер
с автоматическим перезапуском.

## 4. Сборка образа локально

Если нужно собрать образ из исходников на своём сервере:

```bash
docker compose build
docker compose up -d
```

Или через Docker напрямую:

```bash
docker build -t node-monitor-bot:local .
docker run -d --name node-monitor-bot --env-file .env \
  -v node-monitor-data:/app/data --restart unless-stopped node-monitor-bot:local
```

## 5. Управление

```bash
docker compose ps                 # статус контейнера
docker compose logs -f bot        # живые логи
docker compose restart bot        # перезапуск
docker compose down               # остановить и удалить контейнер
```

Обновление до последней версии образа:

```bash
docker compose pull
docker compose up -d
```

## 6. Данные и бэкап

База SQLite хранится в именованном томе `bot-data` (внутри контейнера `/app/data/nodes.db`).
Удаление контейнера через `docker compose down` не удаляет базу.

Бэкап в текущую папку:

```bash
docker compose run --rm -v "$PWD:/backup" bot \
  sh -c "cp /app/data/nodes.db /backup/nodes-backup.db"
```

## 7. Переменные окружения

| Переменная | Обязательна | По умолчанию | Назначение |
| --- | --- | --- | --- |
| `BOT_TOKEN` | да | — | токен Telegram-бота |
| `ADMIN_ID` | да | — | ID администратора, ему доступны команды |
| `ALERT_CHAT_ID` | нет | `ADMIN_ID` | чат для уведомлений о смене статуса |
| `SUMMARY_CHAT_ID` | нет | `ADMIN_ID` | чат для сводки и отчёта Cheburcheck |
| `ALERT_REPEAT_MINUTES` | нет | `15` | подавление повторных DOWN-алертов, `0` — отключить |
| `POLL_TICK_SECONDS` | нет | `1` | частота опроса расписания проверок |
| `SUMMARY_INTERVAL_HOURS` | нет | `1` | периодичность сводки |
| `CHEBURCHECK_INTERVAL_HOURS` | нет | `6` | периодичность проверки Cheburcheck |
| `CHEBURCHECK_STARTUP_DELAY_SEC` | нет | `10` | задержка первой проверки после старта |
| `CHEBURCHECK_TIMEOUT_SEC` | нет | `10` | таймаут запроса к API |
| `CHEBURCHECK_REQUEST_DELAY_SEC` | нет | `2.1` | пауза между нодами, чтобы не превысить лимит API |
| `CHEBURCHECK_BASE_URL` | нет | `https://cheburcheck.ru/api/v1` | базовый адрес API Cheburcheck |
| `DB_URL` | нет | `sqlite+aiosqlite:///./nodes.db` | URL базы (в Compose переопределён) |

## 8. Частые проблемы

- `401 Unauthorized` в логах — неверный `BOT_TOKEN`.
- Бот не отвечает на команды — проверь `ADMIN_ID` (это ID пользователя, не bots).
- База не сохраняется — убедись, что том `bot-data` смонтирован в `/app/data`.
- Образ не скачивается — проверь доступ к `ghcr.io` и выполни `docker login ghcr.io`.

## 9. Автообновление

Updater работает на хосте, а не внутри контейнера. Инструкция по GitHub Release, бэкапам, отправке архива в Telegram и откату: [UPDATES.md](UPDATES.md). Текущая версия бота — `ver. 1.3`, она доступна по команде `/version`.
