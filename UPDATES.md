# Автообновление Node Monitor Bot

Текущая версия бота — `ver. 1.10`, она зафиксирована в файле `VERSION` и git-теге `v1.10`.

Обновление выполняется отдельным скриптом на хосте: `updater.py`. Он не обновляет работающий контейнер изнутри, а управляет репозиторием и Docker Compose снаружи.

## Как это работает

1. `updater.py` раз в час запрашивает последний GitHub Release репозитория `HakunaMaruna/node-monitor-bot`.
2. Проверяется, что в каталоге обновления нет незакоммиченных изменений, а `origin` указывает на ожидаемый репозиторий. Если нет — обновление не запускается, бэкап не создаётся, а в Telegram приходит причина.
3. Если тег релиза старше локальной версии из `VERSION`, создаётся архив `backups/node-monitor-backup-<version>-<timestamp>.tar.gz`.
4. Архив сохраняется локально с правами `0600` (каталог `0700`). В Telegram он отправляется только при `SEND_BACKUP=1`.
5. Отправляется уведомление о доступной версии и начале обновления.
6. Выполняется `git fetch`, проверка тега (и его подписи, если настроена), `git checkout --detach <tag>` и перезапуск через Docker Compose. После checkout updater сверяет `VERSION` с тегом и не запускает контейнеры при расхождении.
7. При успехе приходит уведомление об обновлении. При ошибке выполняется откат из только что созданного архива и отправляется уведомление с результатом.

Архив содержит код бота, `docker-compose.yml`, `Dockerfile` и базу `nodes.db`. `.env` попадает в архив только при `INCLUDE_ENV=1`. Директории `.git`, `backups`, `__pycache__`, `.pytest_cache`, `venv` и `.venv` исключаются.

## Переменные окружения

Добавь их в `.env` на хосте:

```dotenv
DEPLOY_DIR=/opt/node-monitor-bot
BACKUP_DIR=/opt/node-monitor-bot/backups
GITHUB_REPO=HakunaMaruna/node-monitor-bot
GITHUB_TOKEN=                       # необязательно, только для лимитов GitHub API
INCLUDE_ENV=0                      # 1 — класть .env в архив (не рекомендуется)
SEND_BACKUP=0                      # 1 — отправлять архив в Telegram (не рекомендуется)
REQUIRE_SIGNED_TAGS=0              # 1 — требовать подписанный тег
CHECK_INTERVAL_SEC=3600
FETCH_COMMAND=git fetch --tags origin
UPDATE_COMMAND=docker compose pull && docker compose up -d --force-recreate --remove-orphans
STOP_COMMAND=docker compose down
ROLLBACK_START_COMMAND=docker compose build && docker compose up -d --force-recreate --remove-orphans
```

`BOT_TOKEN` и `ADMIN_ID`/`ALERT_CHAT_ID` уже используются ботом. Updater читает тот же `.env`.

Внимание: при `INCLUDE_ENV=1` в архив попадает `.env` с `BOT_TOKEN` и `GITHUB_TOKEN`, а при `SEND_BACKUP=1` он ещё и уходит в Telegram. По умолчанию обе опции выключены: архив остаётся на хосте с правами `0600`.

Команды из `*_COMMAND` больше не запускаются через shell: строка разбивается на аргументы, цепочки `&&` разворачиваются в отдельные вызовы, а символы `|`, `;`, `$`, `>` и обратные кавычки отклоняются.

## Команды

```bash
python3 updater.py check                         # локальная и последняя версия
python3 updater.py backup --no-send --no-env      # локальный архив без .env
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
python3 updater.py rollback backups/node-monitor-backup-v1.9-20261120T120000Z.tar.gz
```

Команда останавливает контейнеры, восстанавливает файлы из архива, пересобирает образ из восстановленного кода и отправляет уведомление в Telegram.

## Проверка версии в боте

`/version` — показывает текущую версию, например `Node Monitor Bot ver. 1.10`.

## Подпись тегов (рекомендуется)

Updater умеет проверять подпись тега перед checkout. Если в каталоге деплоя есть файл
`.allowed_signers`, вызывается `git verify-tag` с этим файлом; если файла нет и
`REQUIRE_SIGNED_TAGS=1`, обновление останавливается.

```bash
# на машине, которой доверяет сервер
ssh-keygen -t ed25519 -C "releases" -f ~/.ssh/release_signing
git config user.signingkey ~/.ssh/release_signing.pub
git tag -s v1.11 -m "v1.11"

# на сервере в /opt/node-monitor-bot/.allowed_signers
releases@example.com ssh-ed25519 AAAAC3...   # публичный ключ
```

Затем `REQUIRE_SIGNED_TAGS=1` в `.env`. Без этой настройки обновление продолжает работать,
но апдейтер печатает предупреждение: подпись не проверяется.

Важно: обновление всё равно выполняется из GitHub-релиза, поэтому защита аккаунта
(2FA, правила доступа к ветке `main`) остаётся главной мерой.

## Права на файлы

```bash
sudo chown root:root /opt/node-monitor-bot/.env
sudo chmod 600 /opt/node-monitor-bot/.env
sudo chmod 700 /opt/node-monitor-bot/backups
```
