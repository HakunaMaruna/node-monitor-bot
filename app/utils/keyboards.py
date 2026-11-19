from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.models.node import Node


def reply_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Список нод")],
            [KeyboardButton(text="Добавить ноду")],
            [KeyboardButton(text="Проверить все")],
            [KeyboardButton(text="Помощь")],
        ],
        resize_keyboard=True,
    )


def main_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Список нод", callback_data="list")],
            [InlineKeyboardButton(text="Добавить ноду", callback_data="add")],
            [InlineKeyboardButton(text="Проверить все", callback_data="check_all")],
        ]
    )


def nodes_list(nodes: list[Node]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"#{node.id} {node.name}\n{'UP' if node.last_status else 'DOWN'}",
                callback_data=f"node:{node.id}",
            )
        ]
        for node in nodes
    ]
    rows.extend(
        [
            [InlineKeyboardButton(text="Добавить ноду", callback_data="add")],
            [InlineKeyboardButton(text="Проверить все", callback_data="check_all")],
            [InlineKeyboardButton(text="Главное меню", callback_data="main")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def node_actions(node: Node) -> InlineKeyboardMarkup:
    toggle = "Выключить" if node.enabled else "Включить"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Проверить", callback_data=f"check:{node.id}")],
            [InlineKeyboardButton(text=toggle, callback_data=f"toggle:{node.id}")],
            [InlineKeyboardButton(text="Интервал", callback_data=f"interval:{node.id}")],
            [InlineKeyboardButton(text="Удалить", callback_data=f"delete:{node.id}")],
            [InlineKeyboardButton(text="К списку", callback_data="list")],
            [InlineKeyboardButton(text="Главное меню", callback_data="main")],
        ]
    )


def confirm_delete(node_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Да, удалить", callback_data=f"confirm_delete:{node_id}")],
            [InlineKeyboardButton(text="Отмена", callback_data="list")],
        ]
    )


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="cancel")]]
    )


def protocol_choice() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=protocol, callback_data=f"protocol:{protocol}")]
            for protocol in ("TCP", "HTTP", "HTTPS")
        ]
        + [[InlineKeyboardButton(text="Отмена", callback_data="cancel")]]
    )


def skip_choice(action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data=f"skip:{action}")],
            [InlineKeyboardButton(text="Отмена", callback_data="cancel")],
        ]
    )
