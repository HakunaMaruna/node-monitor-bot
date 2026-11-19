from app.models.node import Node
from app.services import cheburcheck
from app.services.cheburcheck import (
    CheburcheckError,
    check_blocked,
    extract_target,
    refresh_node_blocked,
    refresh_nodes_blocked,
)
from app.services.nodes import add_node, get_node
from app.utils.formatting import format_summary


class FakeBot:
    def __init__(self):
        self.messages = []

    async def send_message(self, chat_id, text, **kwargs):
        self.messages.append((chat_id, text))


def fake_session(payload, status=200):
    seen = {}

    class FakeResponse:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def json(self, content_type=None):
            return payload

    class FakeSession:
        def __init__(self, timeout=None):
            seen["timeout"] = timeout

        def get(self, url, params=None, headers=None):
            seen.update(url=url, params=params, headers=headers)
            response = FakeResponse()
            response.status = status
            return response

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    return FakeSession, seen


def test_extract_target():
    assert extract_target(Node(ip="10.0.0.1:8080", port=80, protocol="TCP")) == "10.0.0.1"
    assert (
        extract_target(Node(ip="[2001:db8::1]:443", port=443, protocol="TCP"))
        == "2001:db8::1"
    )
    assert (
        extract_target(Node(ip="https://example.com:8443/path", port=443, protocol="HTTPS"))
        == "example.com"
    )
    assert extract_target(Node(ip="", port=80, protocol="TCP")) is None


async def test_refresh_blocked_escapes_invalid_target_error(node_db):
    node = await add_node(name="<b>x</b>", ip="", port=80, protocol="HTTP")

    blocked, changed, message = await refresh_node_blocked(node)

    assert (blocked, changed) == (None, False)
    assert "&lt;b&gt;x&lt;/b&gt;" in message
    assert "<b>x</b>" not in message


async def test_check_blocked_parses_api_response(monkeypatch):
    session, seen = fake_session({"blocked": True})
    monkeypatch.setattr(cheburcheck.aiohttp, "ClientSession", session)

    assert await check_blocked("example.com", timeout_sec=3, base_url="https://api.test/v1/") is True
    assert seen["url"] == "https://api.test/v1/check"
    assert seen["params"] == {"target": "example.com"}


async def test_check_blocked_rejects_bad_payload(monkeypatch):
    session, _ = fake_session({"blocked": "yes"})
    monkeypatch.setattr(cheburcheck.aiohttp, "ClientSession", session)

    try:
        await check_blocked("example.com")
    except CheburcheckError:
        pass
    else:
        raise AssertionError("expected CheburcheckError")


async def test_refresh_blocked_persists_and_notifies(node_db, monkeypatch):
    node = await add_node(name="site", ip="example.com", port=443, protocol="HTTPS")
    verdicts = iter([False, True, True])

    async def fake_check(target, timeout_sec=None):
        assert target == "example.com"
        return next(verdicts)

    monkeypatch.setattr(cheburcheck, "check_blocked", fake_check)
    bot = FakeBot()

    blocked, changed, message = await refresh_node_blocked(node, bot=bot, alert_chat_id=100)
    assert (blocked, changed) == (False, True)
    assert "Не заблокирована" in message
    assert len(bot.messages) == 1

    updated = await get_node(node.id)
    assert updated.blocked is False
    assert updated.blocked_checked_at is not None

    blocked, changed, message = await refresh_node_blocked(
        await get_node(node.id), bot=bot, alert_chat_id=100
    )
    assert (blocked, changed) == (True, True)
    assert "Заблокирована" in message
    assert len(bot.messages) == 2

    blocked, changed, _ = await refresh_node_blocked(
        await get_node(node.id), bot=bot, alert_chat_id=100
    )
    assert (blocked, changed) == (True, False)
    assert len(bot.messages) == 2


async def test_refresh_nodes_blocked_throttles(node_db, monkeypatch):
    first = await add_node(name="first", ip="one.example", port=80, protocol="HTTP")
    second = await add_node(name="second", ip="two.example", port=80, protocol="HTTP")
    targets = []

    async def fake_check(target, timeout_sec=None):
        targets.append(target)
        return False

    slept = []

    async def fake_sleep(value):
        slept.append(value)

    monkeypatch.setattr(cheburcheck, "check_blocked", fake_check)
    monkeypatch.setattr(cheburcheck.asyncio, "sleep", fake_sleep)

    messages = await refresh_nodes_blocked([first, second], delay_sec=2.1)

    assert targets == ["one.example", "two.example"]
    assert slept == [2.1]
    assert len(messages) == 2


def test_summary_includes_cheburcheck_counts():
    nodes = [
        Node(id=1, name="blocked", ip="one.example", port=80, protocol="HTTP", enabled=True, blocked=True),
        Node(id=2, name="clean", ip="two.example", port=80, protocol="HTTP", enabled=True, blocked=False),
        Node(id=3, name="unknown", ip="three.example", port=80, protocol="HTTP", enabled=True, blocked=None),
        Node(id=4, name="off", ip="four.example", port=80, protocol="HTTP", enabled=False, blocked=True),
    ]

    text = format_summary(nodes)

    assert "Не заблокировано: <b>1</b>" in text
    assert "Заблокировано: <b>1</b>" in text
    assert "Не проверялось: <b>1</b>" in text
    assert "• <b>blocked</b>" in text
    assert "🔗 <code>one.example:80</code>" in text
    assert "off" not in text
