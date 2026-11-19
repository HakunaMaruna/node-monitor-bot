import asyncio

import pytest
from aiohttp import web

from app.models.node import Node
from app.services.ping import PingService


async def test_check_tcp_success():
    server = await asyncio.start_server(lambda reader, writer: writer.close(), "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    async with server:
        assert await PingService.check_tcp("127.0.0.1", port, 1) is True


async def test_check_tcp_failure():
    server = await asyncio.start_server(lambda reader, writer: writer.close(), "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    server.close()
    await server.wait_closed()
    assert await PingService.check_tcp("127.0.0.1", port, 1) is False


@pytest.fixture
async def http_port():
    async def handler(request):
        return web.Response(text="healthy node")

    async def bad_handler(request):
        return web.Response(status=500)

    application = web.Application()
    application.router.add_get("/", handler)
    application.router.add_get("/bad", bad_handler)
    runner = web.AppRunner(application)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    yield port
    await runner.cleanup()


async def test_check_http_status_and_body(http_port):
    base = f"http://127.0.0.1:{http_port}"
    assert await PingService.check_http(base, 2) is True
    assert await PingService.check_http(base, 2, expected_response="healthy") is True
    assert await PingService.check_http(base, 2, expected_response="missing") is False
    assert await PingService.check_http(f"{base}/bad", 2) is False


async def test_check_node_dispatch(http_port):
    tcp_node = Node(name="tcp", ip="127.0.0.1", port=http_port, protocol="TCP", timeout_sec=1)
    http_node = Node(name="http", ip="127.0.0.1", port=http_port, protocol="HTTP", timeout_sec=2)
    unknown = Node(name="unknown", ip="127.0.0.1", port=http_port, protocol="UDP", timeout_sec=1)

    assert await PingService.check_node(tcp_node) is True
    assert await PingService.check_node(http_node) is True
    assert await PingService.check_node(unknown) is False
