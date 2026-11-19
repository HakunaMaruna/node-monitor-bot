import asyncio
import logging

import aiohttp
from yarl import URL

from app.config import settings
from app.models.node import Node, naive_utcnow
from app.services.notifier import send_blocked_alert
from app.services.nodes import get_node, record_blocked_result
from app.services.ping import split_host_and_port
from app.utils.formatting import format_blocked_error, format_blocked_verdict

logger = logging.getLogger(__name__)


class CheburcheckError(Exception):
    pass


def extract_target(node: Node) -> str | None:
    raw = (node.ip or "").strip()
    if not raw:
        return None

    if "://" in raw:
        try:
            parsed = URL(raw)
        except ValueError:
            return None
        host = parsed.host
    else:
        host, _ = split_host_and_port(raw.split("/", 1)[0])

    if not host:
        return None
    return host.strip("[]")


async def check_blocked(
    target: str, *, timeout_sec: int | None = None, base_url: str | None = None
) -> bool:
    timeout = settings.CHEBURCHECK_TIMEOUT_SEC if timeout_sec is None else timeout_sec
    url = (base_url or settings.CHEBURCHECK_BASE_URL).rstrip("/") + "/check"
    client_timeout = aiohttp.ClientTimeout(total=timeout)
    try:
        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            async with session.get(
                url,
                params={"target": target},
                headers={"Accept": "application/json"},
            ) as response:
                if response.status == 429:
                    raise CheburcheckError("превышен лимит запросов Cheburcheck")
                if response.status >= 400:
                    raise CheburcheckError(f"Cheburcheck вернул HTTP {response.status}")
                payload = await response.json(content_type=None)
    except CheburcheckError:
        raise
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError) as exc:
        raise CheburcheckError(f"ошибка запроса к Cheburcheck: {exc}") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("blocked"), bool):
        raise CheburcheckError("в ответе Cheburcheck нет поля blocked")
    return payload["blocked"]


async def refresh_node_blocked(
    node: Node,
    *,
    bot=None,
    alert_chat_id: int | None = None,
    timeout_sec: int | None = None,
) -> tuple[bool | None, bool, str]:
    target = extract_target(node)
    if target is None:
        return None, False, format_blocked_error(node, "не удалось определить цель")

    try:
        blocked = await check_blocked(target, timeout_sec=timeout_sec)
    except CheburcheckError as exc:
        logger.warning("Cheburcheck-проверка ноды #%s не удалась: %s", node.id, exc)
        return None, False, format_blocked_error(node, str(exc))

    exists, changed = await record_blocked_result(node.id, blocked, naive_utcnow())
    if not exists:
        return None, False, format_blocked_error(node, "нода не найдена")

    fresh = await get_node(node.id) or node
    if changed and bot is not None and alert_chat_id is not None:
        await send_blocked_alert(bot, fresh, blocked, alert_chat_id)

    return blocked, changed, format_blocked_verdict(fresh, blocked)


async def refresh_nodes_blocked(
    nodes: list[Node],
    *,
    bot=None,
    alert_chat_id: int | None = None,
    timeout_sec: int | None = None,
    delay_sec: float | None = None,
) -> list[str]:
    delay = settings.CHEBURCHECK_REQUEST_DELAY_SEC if delay_sec is None else delay_sec
    results: list[str] = []
    for index, node in enumerate(nodes):
        if index:
            await asyncio.sleep(delay)
        _, _, message = await refresh_node_blocked(
            node,
            bot=bot,
            alert_chat_id=alert_chat_id,
            timeout_sec=timeout_sec,
        )
        results.append(message)
    return results
