import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from app.models.node import Node
from app.utils.formatting import format_status_change

logger = logging.getLogger(__name__)


async def send_status_alert(bot: Bot, node: Node, status: bool, chat_id: int) -> None:
    try:
        await bot.send_message(chat_id=chat_id, text=format_status_change(node, status))
    except TelegramAPIError:
        logger.exception("Не удалось отправить алерт для ноды #%s", node.id)
