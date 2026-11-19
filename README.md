# Node Monitor Bot

Мониторинг сетевых нод с уведомлениями в Telegram. Карта проекта: [PROJECT_MAP.md](PROJECT_MAP.md).

## Возможности

- Проверка нод по TCP, HTTP и HTTPS с таймаутом и ожидаемым текстом ответа.
- Периодические проверки и сводки по расписанию (APScheduler).
- Уведомления об изменении статуса в отдельный чат или администратору.
- Управление нодами командами администратора.

## Команды бота

- `/start`, `/help` — справка
- `/add <name> <TCP|HTTP|HTTPS> <ip> <port> [timeout] [expected]` — добавить ноду
- `/list` — список нод
- `/remove <id>` — удалить ноду
- `/enable <id>`, `/disable <id>` — включить/выключить проверку
- `/check [id]` — разовая проверка ноды или всех включённых нод

## Установка
1. Клонируйте репозиторий.
2. Создайте `.env` на основе `.env.example`.
3. Запустите через `docker-compose up -d`.

## Запуск локально
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

## Тесты
```bash
pytest -q
```
