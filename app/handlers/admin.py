from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.handlers import menu
from app.services.nodes import add_node, delete_node, get_node, list_nodes, set_enabled
from app.utils.formatting import format_node_card

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await menu.show_main(message)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await menu.show_help(message)


@router.message(Command("add"))
async def cmd_add(message: Message, command: CommandObject, state: FSMContext) -> None:
    if not command.args:
        await menu.start_add_flow(message, state)
        return

    parts = command.args.split()
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
    await message.answer(f"Нода #{node.id} добавлена.\n{format_node_card(node)}")


@router.message(Command("list"))
async def cmd_list(message: Message) -> None:
    await menu.show_list(message)


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

    await message.answer(await menu.perform_checks(nodes, bot))


def parse_id(args: str | None) -> int | None:
    try:
        return int((args or "").strip())
    except ValueError:
        return None


@router.message()
async def cmd_unknown(message: Message) -> None:
    await message.answer(
        "Не понял сообщение. Используйте кнопки или /help.",
        reply_markup=menu.main_inline(),
    )
