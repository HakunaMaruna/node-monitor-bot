import asyncio
from ipaddress import ip_address

import aiohttp
from yarl import URL

from app.models.node import Node


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
    scheme = node.protocol.lower()
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
    async def check_tcp(ip: str, port: int, timeout: int) -> bool:
        writer = None
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port), timeout=timeout
            )
            return True
        except (OSError, asyncio.TimeoutError):
            return False
        finally:
            if writer is not None:
                writer.close()
                try:
                    await writer.wait_closed()
                except (OSError, ConnectionError):
                    pass

    @staticmethod
    async def check_http(
        url: str,
        timeout: int,
        expected_code: int = 200,
        expected_response: str | None = None,
    ) -> bool:
        try:
            client_timeout = aiohttp.ClientTimeout(total=timeout)
            async with aiohttp.ClientSession(timeout=client_timeout) as session:
                async with session.get(url) as response:
                    if response.status != expected_code:
                        return False
                    if expected_response is None:
                        return True
                    body = await response.text()
                    return expected_response in body
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, UnicodeError):
            return False

    @classmethod
    async def check_node(cls, node: Node) -> bool:
        if node.protocol == "TCP":
            return await cls.check_tcp(node.ip, node.port, node.timeout_sec)

        if node.protocol in {"HTTP", "HTTPS"}:
            url = build_check_url(node)
            if url is None:
                return False
            return await cls.check_http(
                url, node.timeout_sec, expected_response=node.expected_response
            )

        return False
