from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.config import settings
from app.handlers.states import AddNode, SetInterval
from app.services.monitor import check_node
from app.services.notifier import send_status_alert
from app.services.nodes import add_node, delete_node, get_node, list_nodes, set_enabled, set_interval
from app.utils.formatting import format_node_card
from app.utils.intervals import format_interval, parse_interval
from app.utils.keyboards import (
    cancel_keyboard,
    confirm_delete,
    main_inline,
    node_actions,
    nodes_list,
    protocol_choice,
    reply_menu,
    skip_choice,
)

router = Router()
STALE_MESSAGE_ERRORS = ("message is not modified", "message to edit not found")

HELP_TEXT = (
    "Управление кнопками или командами:\n"
    "/start - меню\n"
    "/list - список нод\n"
    "/add - мастер добавления ноды\n"
    "/check [id] - проверить ноду или все включённые\n"
    "/remove <id> - удалить ноду\n"
    "/enable <id>, /disable <id> - переключатель проверки\n"
    "/interval <id> <30s|5m|2h> - интервал опроса ноды\n"
    f"Опрос запускается каждые {settings.POLL_TICK_SECONDS} с, "
    f"сводка раз в {settings.SUMMARY_INTERVAL_HOURS} ч"
)


async def show_main(message: Message) -> None:
    await message.answer("Мониторинг нод. Выберите действие:", reply_markup=main_inline())
    await message.answer("Быстрые кнопки:", reply_markup=reply_menu())


async def show_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_inline())


async def show_list(event: Message | CallbackQuery) -> None:
    nodes = await list_nodes()
    text = "Список нод:" if nodes else "Ноды не добавлены."
    await render(event, text, nodes_list(nodes))


async def answer_callback(callback: CallbackQuery, text: str | None = None, **kwargs) -> None:
    try:
        await callback.answer(text=text, **kwargs)
    except TelegramBadRequest:
        pass


async def edit_message(callback: CallbackQuery, text: str, markup) -> None:
    try:
        await callback.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as exc:
        if not any(phrase in str(exc).lower() for phrase in STALE_MESSAGE_ERRORS):
            raise


async def render(event: Message | CallbackQuery, text: str, markup) -> None:
    if isinstance(event, CallbackQuery):
        await answer_callback(event)
        await edit_message(event, text, markup)
    else:
        await event.answer(text, reply_markup=markup)


async def render_node(callback: CallbackQuery, node) -> None:
    await answer_callback(callback)
    await edit_message(callback, format_node_card(node), node_actions(node))


def parse_id(data: str, prefix: str) -> int | None:
    expected = f"{prefix}:"
    if not data.startswith(expected):
        return None
    try:
        return int(data[len(expected):])
    except ValueError:
        return None


async def perform_checks(nodes, bot: Bot) -> str:
    results = []
    for node in nodes:
        status, _, should_notify = await check_node(node)
        if should_notify:
            await send_status_alert(bot, node, status, settings.ALERT_CHAT_ID or settings.ADMIN_ID)
        results.append(f"#{node.id} {node.name}: {'UP' if status else 'DOWN'}")
    return "\n".join(results)


async def start_add_flow(event: Message | CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AddNode.name)
    await render(event, "Введите имя ноды:", cancel_keyboard())


@router.message(F.text == "Список нод")
async def button_list(message: Message, state: FSMContext) -> None:
    await state.clear()
    await show_list(message)


@router.message(F.text == "Добавить ноду")
async def button_add(message: Message, state: FSMContext) -> None:
    await start_add_flow(message, state)


@router.message(F.text == "Проверить все")
async def button_check_all(message: Message, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    nodes = await list_nodes(enabled_only=True)
    text = await perform_checks(nodes, bot) if nodes else "Нет включённых нод."
    await message.answer(text, reply_markup=main_inline())


@router.message(F.text == "Помощь")
async def button_help(message: Message, state: FSMContext) -> None:
    await state.clear()
    await show_help(message)


@router.callback_query(F.data == "cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await answer_callback(callback)
    await edit_message(callback, "Действие отменено.", main_inline())


@router.callback_query(F.data == "main")
async def cb_main(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await answer_callback(callback)
    await edit_message(callback, "Мониторинг нод. Выберите действие:", main_inline())


@router.callback_query(F.data == "list")
async def cb_list(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await show_list(callback)


@router.callback_query(F.data == "add")
async def cb_add(callback: CallbackQuery, state: FSMContext) -> None:
    await start_add_flow(callback, state)


@router.callback_query(F.data == "check_all")
async def cb_check_all(callback: CallbackQuery, bot: Bot) -> None:
    await answer_callback(callback)
    nodes = await list_nodes(enabled_only=True)
    text = await perform_checks(nodes, bot) if nodes else "Нет включённых нод."
    await edit_message(callback, text, main_inline())


@router.callback_query(F.data.startswith("node:"))
async def cb_node(callback: CallbackQuery) -> None:
    node_id = parse_id(callback.data, "node")
    node = await get_node(node_id) if node_id is not None else None
    if node is None:
        await answer_callback(callback, "Нода не найдена", show_alert=True)
        return
    await render_node(callback, node)


@router.callback_query(F.data.startswith("interval:"))
async def cb_interval(callback: CallbackQuery, state: FSMContext) -> None:
    node_id = parse_id(callback.data, "interval")
    node = await get_node(node_id) if node_id is not None else None
    if node is None:
        await answer_callback(callback, "Нода не найдена", show_alert=True)
        return
    await state.update_data(interval_node_id=node.id)
    await state.set_state(SetInterval.value)
    await answer_callback(callback)
    await edit_message(
        callback,
        f"Интервал опроса ноды {node.name}.\nВведите, например, 30s, 5m или 2h:",
        cancel_keyboard(),
    )


@router.callback_query(F.data.startswith("check:"))
async def cb_check_node(callback: CallbackQuery, bot: Bot) -> None:
    await answer_callback(callback)
    node_id = parse_id(callback.data, "check")
    node = await get_node(node_id) if node_id is not None else None
    if node is None:
        return
    text = await perform_checks([node], bot)
    updated = await get_node(node.id)
    if updated is None:
        await edit_message(callback, "Нода не найдена.", main_inline())
        return
    await edit_message(callback, f"{text}\n\n{format_node_card(updated)}", node_actions(updated))


@router.callback_query(F.data.startswith("toggle:"))
async def cb_toggle(callback: CallbackQuery) -> None:
    node_id = parse_id(callback.data, "toggle")
    node = await get_node(node_id) if node_id is not None else None
    if node is None:
        await answer_callback(callback, "Нода не найдена", show_alert=True)
        return
    await set_enabled(node.id, not node.enabled)
    updated = await get_node(node.id)
    if updated is None:
        await answer_callback(callback, "Нода не найдена", show_alert=True)
        await edit_message(callback, "Нода не найдена.", main_inline())
        return
    await render_node(callback, updated)


@router.callback_query(F.data.startswith("delete:"))
async def cb_delete(callback: CallbackQuery) -> None:
    node_id = parse_id(callback.data, "delete")
    node = await get_node(node_id) if node_id is not None else None
    if node is None:
        await answer_callback(callback, "Нода не найдена", show_alert=True)
        return
    await answer_callback(callback)
    await edit_message(callback, f"Удалить ноду {node.name}?", confirm_delete(node.id))


@router.callback_query(F.data.startswith("confirm_delete:"))
async def cb_confirm_delete(callback: CallbackQuery) -> None:
    node_id = parse_id(callback.data, "confirm_delete")
    if node_id is not None:
        await delete_node(node_id)
    await show_list(callback)


@router.message(AddNode.name)
async def add_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer("Введите имя ноды:", reply_markup=cancel_keyboard())
        return
    await state.update_data(name=name)
    await state.set_state(AddNode.protocol)
    await message.answer("Выберите протокол:", reply_markup=protocol_choice())


@router.callback_query(AddNode.protocol, F.data.startswith("protocol:"))
async def add_protocol(callback: CallbackQuery, state: FSMContext) -> None:
    protocol = callback.data.split(":", 1)[1]
    await state.update_data(protocol=protocol)
    await state.set_state(AddNode.ip)
    await answer_callback(callback)
    await edit_message(callback, "Введите IP или хост:", cancel_keyboard())


@router.message(AddNode.ip)
async def add_ip(message: Message, state: FSMContext) -> None:
    ip = (message.text or "").strip()
    if not ip:
        await message.answer("Введите IP или хост:", reply_markup=cancel_keyboard())
        return
    await state.update_data(ip=ip)
    await state.set_state(AddNode.port)
    await message.answer("Введите порт:", reply_markup=cancel_keyboard())


@router.message(AddNode.port)
async def add_port(message: Message, state: FSMContext) -> None:
    try:
        port = int((message.text or "").strip())
    except ValueError:
        await message.answer("Порт должен быть числом от 1 до 65535.", reply_markup=cancel_keyboard())
        return
    if not 1 <= port <= 65535:
        await message.answer("Порт должен быть от 1 до 65535.", reply_markup=cancel_keyboard())
        return
    await state.update_data(port=port)
    await state.set_state(AddNode.timeout)
    await message.answer("Таймаут в секундах:", reply_markup=skip_choice("timeout"))


@router.callback_query(AddNode.timeout, F.data == "skip:timeout")
async def skip_timeout(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(timeout_sec=5)
    await ask_expected(callback, state)


@router.message(AddNode.timeout)
async def add_timeout(message: Message, state: FSMContext) -> None:
    try:
        timeout = int((message.text or "").strip())
    except ValueError:
        await message.answer("Таймаут должен быть положительным числом.", reply_markup=skip_choice("timeout"))
        return
    if timeout <= 0:
        await message.answer("Таймаут должен быть положительным числом.", reply_markup=skip_choice("timeout"))
        return
    await state.update_data(timeout_sec=timeout)
    await ask_expected(message, state)


async def ask_expected(event: Message | CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddNode.expected)
    await render(event, "Ожидаемый текст ответа или пропустите:", skip_choice("expected"))


@router.callback_query(AddNode.expected, F.data == "skip:expected")
async def skip_expected(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(expected_response=None)
    await finish_add(callback, state)


@router.message(AddNode.expected)
async def add_expected(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    await state.update_data(expected_response=text or None)
    await finish_add(message, state)


async def finish_add(event: Message | CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    node = await add_node(
        name=data["name"],
        ip=data["ip"],
        port=int(data["port"]),
        protocol=data["protocol"],
        timeout_sec=int(data.get("timeout_sec", 5)),
        expected_response=data.get("expected_response"),
    )
    await state.clear()
    text = f"Нода #{node.id} добавлена.\n{format_node_card(node)}"
    await render(event, text, node_actions(node))


@router.message(SetInterval.value)
async def save_interval(message: Message, state: FSMContext) -> None:
    parsed = parse_interval(message.text or "")
    if parsed is None:
        await message.answer("Формат: 30s, 5m или 2h.", reply_markup=cancel_keyboard())
        return

    data = await state.get_data()
    node_id = data.get("interval_node_id")
    amount, unit = parsed
    await state.clear()
    if not isinstance(node_id, int) or not await set_interval(node_id, amount, unit):
        await message.answer("Нода не найдена.", reply_markup=main_inline())
        return

    node = await get_node(node_id)
    await message.answer(
        f"Интервал опроса: {format_interval(amount, unit)}.\n{format_node_card(node)}",
        reply_markup=node_actions(node),
    )


@router.callback_query()
async def cb_unknown(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await answer_callback(callback)
    await edit_message(callback, "Кнопка устарела. Откройте меню заново.", main_inline())
