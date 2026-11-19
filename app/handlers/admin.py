from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.config import settings
from app.handlers import menu
from app.services.cheburcheck import refresh_node_blocked
from app.services.nodes import add_node, delete_node, get_node, list_nodes, set_enabled, set_interval
from app.utils.formatting import format_node_card
from app.version import VERSION
from app.utils.intervals import format_interval, parse_interval

router = Router()
fallback_router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await menu.show_main(message)


@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext) -> None:
    await state.clear()
    await menu.show_help(message)


@router.message(Command("version"))
async def cmd_version(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(f"Node Monitor Bot ver. {VERSION}")


@router.message(Command("add"))
async def cmd_add(message: Message, command: CommandObject, state: FSMContext) -> None:
    await state.clear()
    if not command.args:
        await menu.start_add_flow(message, state)
        return

    parts = command.args.split()
    if len(parts) < 4:
        await message.answer(
            "Формат: /add <name> <TCP|HTTP|HTTPS> <ip> <port> [timeout] [expected]"
        )
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
async def cmd_list(message: Message, state: FSMContext) -> None:
    await state.clear()
    await menu.show_list(message)


@router.message(Command("remove"))
async def cmd_remove(message: Message, command: CommandObject, state: FSMContext) -> None:
    await state.clear()
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
async def cmd_set_enabled(message: Message, command: CommandObject, state: FSMContext) -> None:
    await state.clear()
    node_id = parse_id(command.args)
    if node_id is None:
        await message.answer("Формат: /enable <id> или /disable <id>")
        return
    enabled = (command.command or "").lower() == "enable"
    if await set_enabled(node_id, enabled):
        await message.answer(f"Нода #{node_id}: {'включена' if enabled else 'выключена'}.")
    else:
        await message.answer(f"Нода #{node_id} не найдена.")


@router.message(Command("check"))
async def cmd_check(message: Message, command: CommandObject, state: FSMContext, bot: Bot) -> None:
    await state.clear()
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


@router.message(Command("blocked"))
async def cmd_check_blocked(
    message: Message, command: CommandObject, state: FSMContext, bot: Bot
) -> None:
    await state.clear()
    node_id = parse_id(command.args)
    if node_id is None:
        await message.answer("Формат: /blocked <id>")
        return
    node = await get_node(node_id)
    if node is None:
        await message.answer(f"Нода #{node_id} не найдена.")
        return
    _, _, verdict = await refresh_node_blocked(
        node,
        bot=bot,
        alert_chat_id=settings.ALERT_CHAT_ID or settings.ADMIN_ID,
    )
    updated = await get_node(node_id)
    await message.answer(f"{verdict}\n\n{format_node_card(updated)}", reply_markup=menu.node_actions(updated))


@router.message(Command("interval"))
async def cmd_interval(message: Message, command: CommandObject, state: FSMContext) -> None:
    await state.clear()
    parts = (command.args or "").split()
    parsed = parse_interval(" ".join(parts[1:])) if len(parts) >= 2 else None
    node_id = parse_id(parts[0]) if parts else None
    if node_id is None or parsed is None:
        await message.answer("Формат: /interval <id> <30s|5m|2h>")
        return

    amount, unit = parsed
    if not await set_interval(node_id, amount, unit):
        await message.answer(f"Нода #{node_id} не найдена.")
        return

    node = await get_node(node_id)
    await message.answer(
        f"Интервал опроса: {format_interval(amount, unit)}.\n{format_node_card(node)}"
    )


def parse_id(args: str | None) -> int | None:
    try:
        return int((args or "").strip())
    except ValueError:
        return None


@fallback_router.message()
async def cmd_unknown(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Не понял сообщение. Используйте кнопки или /help.",
        reply_markup=menu.main_inline(),
    )
