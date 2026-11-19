import asyncio

import aiohttp

from app.models.node import Node


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
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
            return False

    @classmethod
    async def check_node(cls, node: Node) -> bool:
        if node.protocol == "TCP":
            return await cls.check_tcp(node.ip, node.port, node.timeout_sec)

        if node.protocol in {"HTTP", "HTTPS"}:
            url = f"{node.protocol.lower()}://{node.ip}:{node.port}"
            return await cls.check_http(
                url, node.timeout_sec, expected_response=node.expected_response
            )

        return False
