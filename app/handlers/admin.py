from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from app.config import settings
from app.services.monitor import check_node
from app.services.nodes import (
    add_node,
    delete_node,
    get_node,
    list_nodes,
    set_enabled,
)
from app.utils.formatting import format_node, format_status_change

router = Router()


@router.message(Command("start"))
@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Мониторинг нод.\n"
        "/add <name> <TCP|HTTP|HTTPS> <ip> <port> [timeout] [expected] - добавить ноду\n"
        "/list - список нод\n"
        "/remove <id> - удалить ноду\n"
        "/enable <id> /disable <id> - включить или выключить проверку\n"
        "/check [id] - проверить ноду или все включённые ноды\n"
        f"Периодичность проверки: {settings.DEFAULT_CHECK_INTERVAL} мин, "
        f"сводка: {settings.SUMMARY_INTERVAL_HOURS} ч"
    )


@router.message(Command("add"))
async def cmd_add(message: Message, command: CommandObject) -> None:
    parts = (command.args or "").split()
    if len(parts) < 4:
        await message.answer("Формат: /add <name> <TCP|HTTP|HTTPS> <ip> <port> [timeout] [expected]")
        return

    name, protocol, ip, port_value = parts[:4]
    protocol = protocol.upper()
    if protocol not in {"TCP", "HTTP", "HTTPS"}:
        await message.answer("Протокол должен быть TCP, HTTP или HTTPS.")
        return
    try:
        port = int(port_value)
        timeout = int(parts[4]) if len(parts) > 4 else 5
    except ValueError:
        await message.answer("Порт и timeout должны быть числами.")
        return
    if not 1 <= port <= 65535 or timeout <= 0:
        await message.answer("Некорректный порт или timeout.")
        return

    node = await add_node(
        name=name,
        ip=ip,
        port=port,
        protocol=protocol,
        timeout_sec=timeout,
        expected_response=" ".join(parts[5:]) or None,
    )
    await message.answer(f"Нода #{node.id} добавлена.\n{format_node(node)}")


@router.message(Command("list"))
async def cmd_list(message: Message) -> None:
    nodes = await list_nodes()
    if not nodes:
        await message.answer("Ноды не добавлены.")
        return
    await message.answer("\n".join(format_node(node) for node in nodes))


@router.message(Command("remove"))
async def cmd_remove(message: Message, command: CommandObject) -> None:
    node_id = parse_id(command.args)
    if node_id is None:
        await message.answer("Формат: /remove <id>")
        return
    if await delete_node(node_id):
        await message.answer(f"Нода #{node_id} удалена.")
    else:
        await message.answer(f"Нода #{node_id} не найдена.")


@router.message(Command("enable"))
@router.message(Command("disable"))
async def cmd_set_enabled(message: Message, command: CommandObject) -> None:
    node_id = parse_id(command.args)
    if node_id is None:
        await message.answer("Формат: /enable <id> или /disable <id>")
        return
    enabled = message.text is not None and message.text.startswith("/enable")
    if await set_enabled(node_id, enabled):
        await message.answer(f"Нода #{node_id}: {'включена' if enabled else 'выключена'}.")
    else:
        await message.answer(f"Нода #{node_id} не найдена.")


@router.message(Command("check"))
async def cmd_check(message: Message, command: CommandObject, bot: Bot) -> None:
    node_id = parse_id(command.args)
    if command.args and node_id is None:
        await message.answer("Формат: /check [id]")
        return

    if node_id is not None:
        node = await get_node(node_id)
        nodes = [node] if node else []
        if not nodes:
            await message.answer(f"Нода #{node_id} не найдена.")
            return
    else:
        nodes = await list_nodes(enabled_only=True)
        if not nodes:
            await message.answer("Нет включённых нод.")
            return

    results = []
    for node in nodes:
        status, changed = await check_node(node)
        if changed:
            await bot.send_message(
                chat_id=settings.ALERT_CHAT_ID or settings.ADMIN_ID,
                text=format_status_change(node, status),
            )
        results.append(f"#{node.id} {node.name}: {'UP' if status else 'DOWN'}")
    await message.answer("\n".join(results))


def parse_id(args: str | None) -> int | None:
    try:
        return int((args or "").strip())
    except ValueError:
        return None
