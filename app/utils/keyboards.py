import math

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.models.node import Node
from app.utils.design import ICON, NODES_PER_PAGE, button_text, protocol_icon, status_icon
from app.utils.formatting import format_interval


def reply_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Список нод")],
            [KeyboardButton(text="Добавить ноду")],
            [KeyboardButton(text="Проверить все")],
            [KeyboardButton(text="Помощь")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие или введите команду",
    )


def main_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{ICON['list']} Список нод", callback_data="list")],
            [InlineKeyboardButton(text=f"{ICON['add']} Добавить ноду", callback_data="add")],
            [
                InlineKeyboardButton(
                    text=f"{ICON['refresh']} Проверить все", callback_data="check_all"
                )
            ],
        ]
    )


def nodes_list(nodes: list[Node], page: int = 0) -> InlineKeyboardMarkup:
    pages = max(1, math.ceil(len(nodes) / NODES_PER_PAGE))
    page = max(0, min(page, pages - 1))
    visible = nodes[page * NODES_PER_PAGE : (page + 1) * NODES_PER_PAGE]
    rows = [
        [
            InlineKeyboardButton(
                text=(
                    f"{status_icon(node.last_status, node.enabled)} "
                    f"{protocol_icon(node.protocol)} {button_text(node.name)} · "
                    f"{format_interval(node.check_interval, node.check_interval_unit)}"
                ),
                callback_data=f"node:{node.id}",
            )
        ]
        for node in visible
    ]
    if pages > 1:
        nav = []
        if page > 0:
            nav.append(
                InlineKeyboardButton(text="◀ Назад", callback_data=f"page:{page - 1}")
            )
        nav.append(
            InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data=f"page:{page}")
        )
        if page < pages - 1:
            nav.append(
                InlineKeyboardButton(text="Вперёд ▶", callback_data=f"page:{page + 1}")
            )
        rows.append(nav)
    rows.extend(
        [
            [InlineKeyboardButton(text=f"{ICON['add']} Добавить ноду", callback_data="add")],
            [
                InlineKeyboardButton(
                    text=f"{ICON['refresh']} Проверить все", callback_data="check_all"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{ICON['home']} Главное меню", callback_data="main"
                )
            ],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def node_actions(node: Node) -> InlineKeyboardMarkup:
    toggle = (
        f"{ICON['paused']} Выключить" if node.enabled else f"{ICON['refresh']} Включить"
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{ICON['refresh']} Проверить", callback_data=f"check:{node.id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{ICON['shield']} Cheburcheck: проверить",
                    callback_data=f"blocked:{node.id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{ICON['shield']} Диагностика ТСПУ",
                    callback_data=f"tspu:{node.id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{ICON['shield']} Динамическая проверка",
                    callback_data=f"probe:{node.id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{ICON['search']} Расширенная диагностика",
                    callback_data=f"tspu_full:{node.id}",
                )
            ],
            [InlineKeyboardButton(text=toggle, callback_data=f"toggle:{node.id}")],
            [
                InlineKeyboardButton(
                    text=f"{ICON['clock']} Интервал", callback_data=f"interval:{node.id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{ICON['delete']} Удалить", callback_data=f"delete:{node.id}"
                )
            ],
            [InlineKeyboardButton(text=f"{ICON['back']} К списку", callback_data="list")],
            [
                InlineKeyboardButton(
                    text=f"{ICON['home']} Главное меню", callback_data="main"
                )
            ],
        ]
    )


def confirm_delete(node_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{ICON['delete']} Да, удалить",
                    callback_data=f"confirm_delete:{node_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{ICON['cancel']} Отмена", callback_data="list"
                )
            ],
        ]
    )


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{ICON['cancel']} Отмена", callback_data="cancel")]
        ]
    )


def protocol_choice() -> InlineKeyboardMarkup:
    icons = {"TCP": ICON["tcp"], "HTTP": ICON["http"], "HTTPS": ICON["https"]}
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{icons[protocol]} {protocol}",
                    callback_data=f"protocol:{protocol}",
                )
            ]
            for protocol in ("TCP", "HTTP", "HTTPS")
        ]
        + [
            [
                InlineKeyboardButton(
                    text=f"{ICON['cancel']} Отмена", callback_data="cancel"
                )
            ]
        ]
    )


def skip_choice(action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{ICON['skip']} Пропустить", callback_data=f"skip:{action}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{ICON['cancel']} Отмена", callback_data="cancel"
                )
            ],
        ]
    )
