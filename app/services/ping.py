import asyncio
import socket
import time
from dataclasses import dataclass
from ipaddress import ip_address, ip_network

import aiohttp
from yarl import URL

from app.config import settings
from app.models.node import Node

MAX_BODY_BYTES = 64 * 1024

# Запрещены всегда: адреса метаданных облака, широковещательные и служебные диапазоны.
ALWAYS_BLOCKED_NETS = (
    ip_network("0.0.0.0/8"),
    ip_network("169.254.0.0/16"),
    ip_network("224.0.0.0/4"),
    ip_network("240.0.0.0/4"),
    ip_network("::/128"),
    ip_network("fe80::/10"),
    ip_network("ff00::/8"),
)

# Внутренние сети: запрещаются при BLOCK_PRIVATE_TARGETS=1.
PRIVATE_NETS = (
    ip_network("10.0.0.0/8"),
    ip_network("100.64.0.0/10"),
    ip_network("127.0.0.0/8"),
    ip_network("172.16.0.0/12"),
    ip_network("192.168.0.0/16"),
    ip_network("fc00::/7"),
    ip_network("::1/128"),
)


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


def is_blocked_ip(host: str, *, block_private: bool | None = None) -> bool:
    try:
        ip = ip_address(str(host).strip().strip("[]"))
    except ValueError:
        return False
    if ip.version == 6 and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if block_private is None:
        block_private = settings.BLOCK_PRIVATE_TARGETS
    nets = ALWAYS_BLOCKED_NETS + PRIVATE_NETS if block_private else ALWAYS_BLOCKED_NETS
    return any(ip in net for net in nets if net.version == ip.version)


async def resolve_host(host: str) -> list[str]:
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    addresses: list[str] = []
    for info in infos:
        address = info[4][0]
        if address not in addresses:
            addresses.append(address)
    return addresses


async def target_allowed(host: str, *, block_private: bool | None = None) -> str | None:
    """None, если проверять цель можно; иначе текст причины отказа."""
    host = (host or "").strip().strip("[]")
    if not host:
        return "пустой адрес"
    if is_blocked_ip(host, block_private=block_private):
        return "адрес запрещён"
    try:
        ip_address(host)
        return None
    except ValueError:
        pass
    try:
        addresses = await resolve_host(host)
    except (OSError, UnicodeError):
        return None
    if any(is_blocked_ip(address, block_private=block_private) for address in addresses):
        return "адрес запрещён"
    return None


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


async def _read_body_limited(
    response: aiohttp.ClientResponse, limit: int = MAX_BODY_BYTES
) -> str | None:
    """Читает не больше limit байт; None, если ответ больше лимита."""
    if response.content_length is not None and response.content_length > limit:
        return None
    raw = await response.content.read(limit + 1)
    if len(raw) > limit:
        return None
    return raw.decode(response.charset or "utf-8", errors="replace")


class PingService:
    @staticmethod
    async def check_tcp_detailed(ip: str, port: int, timeout: int) -> tuple[bool, str | None]:
        forbidden = await target_allowed(ip)
        if forbidden is not None:
            return False, forbidden
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
            host = URL(url).host
        except ValueError:
            return False, "неверный адрес"
        if host is not None:
            forbidden = await target_allowed(host)
            if forbidden is not None:
                return False, forbidden
        try:
            client_timeout = aiohttp.ClientTimeout(total=timeout)
            async with aiohttp.ClientSession(timeout=client_timeout) as session:
                async with session.get(url, allow_redirects=False) as response:
                    if response.status != expected_code:
                        return False, f"HTTP {response.status}"
                    if expected_response is None:
                        return True, None
                    body = await _read_body_limited(response)
                    if body is None:
                        return False, "ответ больше 64 КБ"
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
