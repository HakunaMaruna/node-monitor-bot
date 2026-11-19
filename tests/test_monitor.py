from app.models.node import Node
from app.services.monitor import check_node
from app.services.nodes import get_node
from app.services.ping import CheckResult, PingService


async def test_check_node_persists_status_change(node_db, monkeypatch):
    node = await add_test_node()

    async def down(candidate):
        return CheckResult(False, 12, "соединение отклонено")

    monkeypatch.setattr(PingService, "check_node_detailed", staticmethod(down))
    assert await check_node(node) == (False, True, True)

    updated = await get_node(node.id)
    assert updated.last_status is False
    assert updated.last_check_time is not None
    assert updated.last_latency_ms == 12
    assert updated.last_error == "соединение отклонено"
    assert updated.consecutive_failures == 1
    assert updated.check_history is not None

    node = await get_node(node.id)
    assert await check_node(node) == (False, False, True)
    updated = await get_node(node.id)
    assert updated.consecutive_failures == 2


async def test_check_node_ignores_stale_object_status(node_db, monkeypatch):
    node = await add_test_node()
    fresh = await get_node(node.id)
    stale = await get_node(node.id)

    async def down(candidate):
        return CheckResult(False, 12, "соединение отклонено")

    monkeypatch.setattr(PingService, "check_node_detailed", staticmethod(down))
    assert await check_node(fresh) == (False, True, True)
    assert await check_node(stale) == (False, False, True)


async def test_notification_rules(node_db, monkeypatch):
    node = await add_test_node()
    statuses = iter([False, True, True])

    async def next_status(candidate):
        return CheckResult(next(statuses), 20, None)

    monkeypatch.setattr(PingService, "check_node_detailed", staticmethod(next_status))
    assert await check_node(node) == (False, True, True)
    assert await check_node(node) == (True, True, True)
    assert await check_node(node) == (True, False, False)


async def add_test_node():
    from app.services.nodes import add_node

    return await add_node(
        name="test",
        ip="127.0.0.1",
        port=1234,
        protocol="TCP",
    )
