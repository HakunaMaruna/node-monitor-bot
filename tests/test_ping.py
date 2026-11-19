import asyncio

import pytest
from aiohttp import web

from app.models.node import Node
from app.services.ping import PingService, build_check_url


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


async def test_check_tcp_tolerates_cancelled_lookup(monkeypatch):
    async def cancelled(*args, **kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr(asyncio, "open_connection", cancelled)
    assert await PingService.check_tcp("unresolvable.invalid", 80, 1) is False


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


def test_build_check_url_handles_ipv6_and_scheme():
    ipv6 = Node(name="v6", ip="::1", port=8080, protocol="HTTP", timeout_sec=1)
    with_scheme = Node(
        name="host",
        ip="https://example.com/path",
        port=443,
        protocol="HTTP",
        timeout_sec=1,
    )
    with_port = Node(
        name="with-port", ip="example.com:8080", port=80, protocol="HTTP", timeout_sec=1
    )
    bracketed_v6 = Node(
        name="v6-port", ip="[::1]:9090", port=80, protocol="HTTP", timeout_sec=1
    )

    assert build_check_url(ipv6) == "http://[::1]:8080"
    assert build_check_url(with_scheme) == "https://example.com"
    assert build_check_url(with_port) == "http://example.com:8080"
    assert build_check_url(bracketed_v6) == "http://[::1]:9090"


async def test_check_node_detailed_reports_latency_and_error(http_port):
    node = Node(
        name="http",
        ip="127.0.0.1",
        port=http_port,
        protocol="HTTP",
        timeout_sec=2,
        expected_response="missing",
    )

    result = await PingService.check_node_detailed(node)

    assert result.status is False
    assert result.error == "ожидаемый текст не найден"
    assert result.latency_ms is not None and result.latency_ms >= 0


async def test_check_node_detailed_success_has_no_error(http_port):
    node = Node(
        name="http", ip="127.0.0.1", port=http_port, protocol="HTTP", timeout_sec=2
    )

    result = await PingService.check_node_detailed(node)

    assert result.status is True
    assert result.error is None
    assert result.latency_ms is not None


async def test_check_node_dispatch(http_port):
    tcp_node = Node(name="tcp", ip="127.0.0.1", port=http_port, protocol="TCP", timeout_sec=1)
    http_node = Node(name="http", ip="127.0.0.1", port=http_port, protocol="HTTP", timeout_sec=2)
    unknown = Node(name="unknown", ip="127.0.0.1", port=http_port, protocol="UDP", timeout_sec=1)

    assert await PingService.check_node(tcp_node) is True
    assert await PingService.check_node(http_node) is True
    assert await PingService.check_node(unknown) is False
