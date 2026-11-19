# Автообновление Node Monitor Bot

Текущая версия бота — `ver. 1.1`, она зафиксирована в файле `VERSION` и git-теге `v1.1`.

Обновление выполняется отдельным скриптом на хосте: `updater.py`. Он не обновляет работающий контейнер изнутри, а управляет репозиторием и Docker Compose снаружи.

## Как это работает

1. `updater.py` раз в час запрашивает последний GitHub Release репозитория `HakunaMaruna/node-monitor-bot`.
2. Если тег релиза старше локальной версии из `VERSION`, создаётся архив `backups/node-monitor-backup-<version>-<timestamp>.tar.gz`.
3. Архив отправляется в Telegram документом в `ALERT_CHAT_ID` (или `ADMIN_ID`).
4. Отправляется уведомление о доступной версии и начале обновления.
5. Выполняется `git fetch`, проверка тега, `git checkout <tag>` и перезапуск через Docker Compose.
6. При успехе приходит уведомление об обновлении. При ошибке выполняется откат из только что созданного архива и отправляется уведомление с результатом.

Архив содержит код бота, `docker-compose.yml`, `Dockerfile`, `.env` и базу `nodes.db`. Директории `.git`, `backups`, `__pycache__` и `.pytest_cache` исключаются.

## Переменные окружения

Добавь их в `.env` на хосте:

```dotenv
DEPLOY_DIR=/opt/node-monitor-bot
BACKUP_DIR=/opt/node-monitor-bot/backups
GITHUB_REPO=HakunaMaruna/node-monitor-bot
GITHUB_TOKEN=                       # необязательно, только для лимитов GitHub API
INCLUDE_ENV=1                      # 0 — не класть .env в архив
CHECK_INTERVAL_SEC=3600
FETCH_COMMAND=git fetch --tags --force
UPDATE_COMMAND=docker compose pull && docker compose up -d --force-recreate --remove-orphans
STOP_COMMAND=docker compose down
ROLLBACK_START_COMMAND=docker compose build && docker compose up -d --force-recreate --remove-orphans
```

`BOT_TOKEN` и `ADMIN_ID`/`ALERT_CHAT_ID` уже используются ботом. Updater читает тот же `.env`.

Внимание: при `INCLUDE_ENV=1` архив с токеном бота отправляется в Telegram. Используйте приватный чат администратора. Если это неприемлемо, поставьте `INCLUDE_ENV=0` и храните `.env` отдельно.

## Команды

```bash
python3 updater.py check                         # локальная и последняя версия
python3 updater.py backup                        # создать архив и отправить в Telegram
python3 updater.py backup --no-send --no-env      # только локальный архив без .env
python3 updater.py update                        # проверить и применить обновление
python3 updater.py rollback /path/to/backup.tar.gz
python3 updater.py daemon                        # бесконечная проверка с CHECK_INTERVAL_SEC
```

## Установка на хосте через systemd

Клонируйте репозиторий в `/opt/node-monitor-bot`, заполните `.env` и установите unit-файлы:

```bash
sudo cp deploy/node-monitor-updater.service /etc/systemd/system/
sudo cp deploy/node-monitor-updater.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now node-monitor-updater.timer
systemctl status node-monitor-updater.timer
```

Проверить вручную:

```bash
sudo systemctl start node-monitor-updater.service
journalctl -u node-monitor-updater.service -f
```

Альтернатива с cron:

```cron
0 * * * * cd /opt/node-monitor-bot && /usr/bin/python3 updater.py update >> /var/log/node-updater.log 2>&1
```

## Откат

Каждый успешный autosave-архив можно использовать для отката:

```bash
cd /opt/node-monitor-bot
python3 updater.py rollback backups/node-monitor-backup-v1.1-20261119T120000Z.tar.gz
```

Команда останавливает контейнеры, восстанавливает файлы из архива, пересобирает образ из восстановленного кода и отправляет уведомление в Telegram.

## Проверка версии в боте

`/version` — показывает текущую версию, например `Node Monitor Bot ver. 1.1`.
