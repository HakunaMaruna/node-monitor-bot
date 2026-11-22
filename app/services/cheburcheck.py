import asyncio
import json
import logging
import re
from urllib.parse import quote

import aiohttp
from yarl import URL

from app.config import settings
from app.models.node import Node, naive_utcnow
from app.services.notifier import send_blocked_alert
from app.services.nodes import get_node, record_blocked_result
from app.services.ping import split_host_and_port
from app.utils.formatting import format_blocked_error, format_blocked_verdict

logger = logging.getLogger(__name__)

MAX_EVENT_LINE_BYTES = 64 * 1024
MAX_PROBE_RESULTS = 500
CONTEXT_ID_RE = re.compile(r"[A-Za-z0-9._-]{1,1024}")


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


async def probe_check(
    target: str,
    *,
    api_token: str | None = None,
    timeout_sec: int | None = None,
    base_url: str | None = None,
) -> dict:
    base = (base_url or settings.CHEBURCHECK_BASE_URL).rstrip("/")
    token = api_token if api_token is not None else settings.CHEBURCHECK_API_TOKEN
    token = (token or "").strip()
    if not token:
        raise CheburcheckError("API-токен Cheburcheck не настроен")

    timeout = settings.CHEBURCHECK_TIMEOUT_SEC if timeout_sec is None else timeout_sec
    client_timeout = aiohttp.ClientTimeout(total=max(timeout, 30))

    # Сначала получаем подписанный контекст проверки.
    try:
        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            async with session.get(
                base + "/check",
                params={"target": target},
                headers={"Accept": "application/json"},
            ) as response:
                if response.status == 429:
                    raise CheburcheckError("превышен лимит запросов Cheburcheck, попробуйте позже")
                if response.status >= 400:
                    raise CheburcheckError(f"Cheburcheck вернул HTTP {response.status}")
                payload = await response.json(content_type=None)
    except CheburcheckError:
        raise
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError) as exc:
        raise CheburcheckError(f"ошибка запроса к Cheburcheck: {exc}") from exc

    raw_context_id = payload.get("id") if isinstance(payload, dict) else None
    context_id = str(raw_context_id).strip() if raw_context_id else ""
    if not context_id:
        raise CheburcheckError("Cheburcheck не вернул контекст для динамической проверки")
    if ".." in context_id or context_id.startswith(".") or context_id.endswith("."):
        raise CheburcheckError("Cheburcheck вернул некорректный идентификатор контекста")
    if not CONTEXT_ID_RE.fullmatch(context_id):
        raise CheburcheckError("Cheburcheck вернул некорректный идентификатор контекста")

    url = f"{base}/probe/{quote(context_id, safe='')}"
    results: list[dict] = []
    started: dict | None = None
    done: dict | None = None
    event_name = "message"
    data_lines: list[str] = []

    def process_event() -> None:
        nonlocal started, done
        if not data_lines:
            return
        raw_data = "\n".join(data_lines)
        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError:
            return
        if event_name == "started" and isinstance(data, dict):
            started = data
        elif event_name == "result" and isinstance(data, dict):
            results.append(data)
        elif event_name == "done" and isinstance(data, dict):
            done = data

    for attempt in range(3):
        try:
            async with aiohttp.ClientSession(timeout=client_timeout) as session:
                async with session.get(
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "text/event-stream",
                    },
                ) as response:
                    if response.status == 429:
                        if attempt < 2:
                            await asyncio.sleep(3 * (attempt + 1))
                            continue
                        raise CheburcheckError("превышен лимит запросов Cheburcheck, попробуйте позже")
                    if response.status == 401:
                        raise CheburcheckError("неверный или просроченный API-токен Cheburcheck")
                    if response.status == 403:
                        raise CheburcheckError("нет доступа к динамическим сканерам Cheburcheck")
                    if response.status >= 400:
                        raise CheburcheckError(f"Cheburcheck probe вернул HTTP {response.status}")

                    while True:
                        raw = await response.content.readline()
                        if not raw:
                            break
                        if len(raw) > MAX_EVENT_LINE_BYTES:
                            raise CheburcheckError("слишком длинная строка в потоке Cheburcheck")
                        if len(results) > MAX_PROBE_RESULTS:
                            break
                        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                        if line == "":
                            process_event()
                            event_name = "message"
                            data_lines = []
                        elif line.startswith("event:"):
                            event_name = line[6:].strip() or "message"
                        elif line.startswith("data:"):
                            data_lines.append(line[5:].strip())
                    process_event()
            break
        except CheburcheckError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError) as exc:
            raise CheburcheckError(f"ошибка динамической проверки Cheburcheck: {exc}") from exc

    verdicts: set[str] = set()
    for result in results:
        for verdict in result.get("verdicts") or []:
            verdicts.add(str(verdict))

    return {
        "target": target,
        "context_id": context_id,
        "online_probes": (started or {}).get("online_probes"),
        "response_count": (done or {}).get("response_count"),
        "results": results,
        "verdicts": sorted(verdicts),
    }
