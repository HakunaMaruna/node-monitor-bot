import asyncio
import time
from dataclasses import dataclass
from ipaddress import ip_address

import aiohttp
from yarl import URL

from app.models.node import Node


@dataclass(frozen=True)
class CheckResult:
    status: bool
    latency_ms: int | None
    error: str | None


def _error_text(exc: BaseException) -> str:
    if isinstance(exc, asyncio.TimeoutError):
        return "таймаут"
    if isinstance(exc, asyncio.CancelledError):
        return "проверка отменена"
    if isinstance(exc, ConnectionRefusedError):
        return "соединение отклонено"
    text = " ".join(str(exc).split()) or exc.__class__.__name__
    return text[:120]


def split_host_and_port(raw: str) -> tuple[str, int | None]:
    if raw.startswith("["):
        closing = raw.find("]")
        if closing == -1:
            return raw, None
        host = raw[1:closing]
        rest = raw[closing + 1 :]
        if rest.startswith(":"):
            suffix = rest[1:]
            return host, int(suffix) if suffix.isdigit() else None
        return host, None

    try:
        ip_address(raw)
    except ValueError:
        if raw.count(":") == 1:
            host, _, suffix = raw.rpartition(":")
            if host and suffix.isdigit():
                return host, int(suffix)

    return raw, None


def build_check_url(node: Node) -> str | None:
    raw = (node.ip or "").strip()
    scheme = (node.protocol or "").lower()
    port = node.port

    if "://" in raw:
        try:
            parsed = URL(raw)
        except ValueError:
            return None
        if parsed.scheme in {"http", "https"}:
            scheme = parsed.scheme
        host = parsed.host or raw
        port = parsed.port or port
    else:
        host, embedded_port = split_host_and_port(raw.split("/", 1)[0])
        if embedded_port is not None:
            port = embedded_port

    try:
        return str(URL.build(scheme=scheme, host=host, port=port))
    except ValueError:
        return None


class PingService:
    @staticmethod
    async def check_tcp_detailed(ip: str, port: int, timeout: int) -> tuple[bool, str | None]:
        writer = None
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port), timeout=timeout
            )
            return True, None
        except (OSError, asyncio.TimeoutError, asyncio.CancelledError) as exc:
            return False, _error_text(exc)
        finally:
            if writer is not None:
                writer.close()
                try:
                    await writer.wait_closed()
                except (OSError, ConnectionError):
                    pass

    @staticmethod
    async def check_tcp(ip: str, port: int, timeout: int) -> bool:
        status, _ = await PingService.check_tcp_detailed(ip, port, timeout)
        return status

    @staticmethod
    async def check_http_detailed(
        url: str,
        timeout: int,
        expected_code: int = 200,
        expected_response: str | None = None,
    ) -> tuple[bool, str | None]:
        try:
            client_timeout = aiohttp.ClientTimeout(total=timeout)
            async with aiohttp.ClientSession(timeout=client_timeout) as session:
                async with session.get(url) as response:
                    if response.status != expected_code:
                        return False, f"HTTP {response.status}"
                    if expected_response is None:
                        return True, None
                    body = await response.text()
                    if expected_response in body:
                        return True, None
                    return False, "ожидаемый текст не найден"
        except (
            aiohttp.ClientError,
            asyncio.TimeoutError,
            asyncio.CancelledError,
            OSError,
            UnicodeError,
        ) as exc:
            return False, _error_text(exc)

    @staticmethod
    async def check_http(
        url: str,
        timeout: int,
        expected_code: int = 200,
        expected_response: str | None = None,
    ) -> bool:
        status, _ = await PingService.check_http_detailed(
            url, timeout, expected_code, expected_response
        )
        return status

    @classmethod
    async def check_node_detailed(cls, node: Node) -> CheckResult:
        started = time.perf_counter()
        try:
            if node.protocol == "TCP":
                status, error = await cls.check_tcp_detailed(
                    node.ip, node.port, node.timeout_sec
                )
            elif node.protocol in {"HTTP", "HTTPS"}:
                url = build_check_url(node)
                if url is None:
                    status, error = False, "неверный адрес"
                else:
                    status, error = await cls.check_http_detailed(
                        url, node.timeout_sec, expected_response=node.expected_response
                    )
            else:
                status, error = False, f"неподдерживаемый протокол {node.protocol}"
        except Exception as exc:
            status, error = False, _error_text(exc)
        latency_ms = max(0, round((time.perf_counter() - started) * 1000))
        return CheckResult(status, latency_ms, None if status else error)

    @classmethod
    async def check_node(cls, node: Node) -> bool:
        result = await cls.check_node_detailed(node)
        return result.status
