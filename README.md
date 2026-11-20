# Node Monitor Bot

Мониторинг сетевых нод с уведомлениями в Telegram. Карта проекта: [PROJECT_MAP.md](PROJECT_MAP.md).

## Возможности

- Проверка нод по TCP, HTTP и HTTPS с таймаутом, ожидаемым текстом и своим интервалом опроса (секунды/минуты/часы).
- Периодическая проверка адресов через Cheburcheck (`заблокирована`/`не заблокирована`) раз в 6 ч, первая — через 10 с после старта; уведомление только при смене вердикта, сводка показывает счётчики.
- Периодические проверки и сводки по расписанию (APScheduler).
- Уведомления об изменении статуса в отдельный чат или администратору.
- Управление нодами через кнопки: главное меню, список нод, карточка ноды, мастер добавления.
- Информативный интерфейс с иконками: статус, протокол, Cheburcheck и время в карточке; пагинация списка от 20 нод; HTML-оформление заголовков и адресов.
- Сообщения разбиты на смысловые блоки: состояние, метрики, Cheburcheck; каждое поле — отдельной строкой. Результаты проверок и отчёты Cheburcheck выводятся отдельными блоками с адресами и вердиктами.
- Метрики проверок: задержка, причина ошибки, число неудач подряд, uptime за 24 часа и мини-график последних проверок в карточке; DOWN-алерты тоже показывают причину, задержку и счётчик неудач.
- Таймер статуса: карточка показывает, с какого времени нода в текущем состоянии и как долго она недоступна; DOWN-алерты, сводка и алерт восстановления сообщают длительность простоя.
- Устойчивость к устаревшим кнопкам и неизвестным сообщениям: бот отвечает подсказкой и обновляет меню.
- Автообновление на хосте (`updater.py`): бэкап кода и БД отправляется в Telegram перед обновлением, есть откат из архива. Updater не запускается при незакоммиченных изменениях и проверяет, что `VERSION` совпадает с тегом. Текущая версия — `ver. 1.8`.
- Повторные `DOWN`-алерты подавляются на `ALERT_REPEAT_MINUTES` минут; `0` отключает подавление. Восстановление всегда приходит сразу.
- Результаты периодической проверки Cheburcheck отправляются в `SUMMARY_CHAT_ID` (или `ADMIN_ID`) компактным отчётом.
- В карточке ноды доступны быстрая и расширенная диагностика ТСПУ: режим ТСПУ, порты, SNI, DNS, блокировки, NAT, split DNS и другие проверки без внешних утилит.

## Кнопки и команды бота

`/start` открывает меню с inline-кнопками и закрепляет быстрые кнопки внизу чата:
"Список нод", "Добавить ноду", "Проверить все", "Помощь". Мастер добавления спрашивает имя,
протокол, адрес, порт, таймаут и ожидаемый текст ответа; таймаут и текст можно пропустить.
В карточке ноды доступны кнопки проверки, `Cheburcheck: проверить`, `Диагностика ТСПУ`, `Расширенная диагностика`, изменения интервала опроса, включения/выключения и удаления с подтверждением. Карточка показывает иконку статуса, протокол, адрес, интервал и время следующей проверки, время последней проверки UTC с относительным временем, задержку, причину ошибки, uptime 24h со sparkline и отдельный блок Cheburcheck. Сводка дополнительно показывает средний uptime 24h. Список нод разбит на страницы по 20 записей.

Старые команды тоже работают:

- `/start`, `/help` — справка
- `/version` — текущая версия бота
- `/add` — мастер добавления (или `/add <name> <TCP|HTTP|HTTPS> <ip> <port> [timeout] [expected]` одной командой; чтобы задать ожидаемый текст, укажите timeout, например `5`)
- `/list` — список нод
- `/remove <id>` — удалить ноду
- `/enable <id>`, `/disable <id>` — включить/выключить проверку
- `/interval <id> <30s|5m|2h>` — интервал опроса ноды
- `/check [id]` — разовая проверка ноды или всех включённых нод
- `/blocked <id>` — проверить адрес ноды через Cheburcheck

Если нода недоступна, первое уведомление приходит сразу, последующие — не чаще одного раза в `ALERT_REPEAT_MINUTES` минут. После восстановления приходит одно уведомление, следующие появятся только при повторной недоступности.

## Установка через Docker

Подробная инструкция: [DOCKER.md](DOCKER.md). Коротко:

```bash
git clone https://github.com/HakunaMaruna/node-monitor-bot.git
cd node-monitor-bot
cp .env.example .env
nano .env
docker compose pull
docker compose up -d
```

Готовый образ: `ghcr.io/hakunamaruna/node-monitor-bot:latest`. Для сборки из исходников используйте `docker compose build`.

Cheburcheck использует публичный API `cheburcheck.ru/api/v1/check` без токена. Интервал (часы), таймаут и задержку между нодами можно задать переменными `CHEBURCHECK_INTERVAL_HOURS`, `CHEBURCHECK_TIMEOUT_SEC`, `CHEBURCHECK_REQUEST_DELAY_SEC`.

Настройка автообновления, бэкапов и отката: [UPDATES.md](UPDATES.md).

## Запуск локально
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

## Подробная установка

### Локально (без Docker)

1. Установите Python 3.11+ и зависимости:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Создайте `.env` на основе `.env.example`:
   ```bash
   cp .env.example .env
   ```
   Заполните минимум:
   - `BOT_TOKEN` — токен бота от @BotFather;
   - `ADMIN_ID` — ваш Telegram ID;
   - `DB_URL` — путь к SQLite, например `sqlite+aiosqlite:///./data/nodes.db`.
3. Создайте каталог данных, если он указан в `DB_URL`:
   ```bash
   mkdir -p data
   ```
4. Запустите бота:
   ```bash
   python -m app.main
   ```
   База данных создаётся автоматически при первом запуске.

### Docker Compose

```bash
cp .env.example .env
nano .env
docker compose up -d --build
```

Готовый образ:
```bash
docker pull ghcr.io/hakunamaruna/node-monitor-bot:latest
```

### Сервер (systemd, без Docker)

```bash
sudo mkdir -p /opt/node-monitor-bot
sudo chown -R $USER:$USER /opt/node-monitor-bot
git clone https://github.com/HakunaMaruna/node-monitor-bot.git /opt/node-monitor-bot
cd /opt/node-monitor-bot
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env
nano .env
sudo cp deploy/node-monitor-updater.service /etc/systemd/system/node-monitor-bot.service
sudo systemctl daemon-reload
sudo systemctl enable --now node-monitor-bot.service
```

Проверка:
```bash
systemctl status node-monitor-bot.service
journalctl -u node-monitor-bot.service -f
```

### Бэкап и обновление

Перед обновлением сохраните код и БД:
```bash
tar -czf node-monitor-bot-backup-$(date +%Y%m%d-%H%M%S).tar.gz /opt/node-monitor-bot
```

Обновление вручную:
```bash
cd /opt/node-monitor-bot
git pull
./venv/bin/pip install -r requirements.txt
sudo systemctl restart node-monitor-bot.service
```

## Тесты
```bash
pytest -q
```
