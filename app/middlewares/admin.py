from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware


class AdminOnlyMiddleware(BaseMiddleware):
    def __init__(self, admin_id: int) -> None:
        self.admin_id = admin_id

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None or user.id != self.admin_id:
            if hasattr(event, "answer"):
                await event.answer("Команда доступна только администратору.")
            return None
        return await handler(event, data)
