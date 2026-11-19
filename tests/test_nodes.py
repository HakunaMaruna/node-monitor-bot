from datetime import datetime

from app.services.nodes import (
    add_node,
    delete_node,
    get_node,
    list_nodes,
    record_blocked_result,
    record_check_result,
    set_enabled,
    set_interval,
    update_node_status,
)


async def test_node_crud(node_db):
    node = await add_node(
        name="node-1",
        ip="127.0.0.1",
        port=8080,
        protocol="HTTP",
        timeout_sec=3,
        expected_response="ok",
    )
    assert node.id is not None
    assert node.enabled is True

    loaded = await get_node(node.id)
    assert loaded is not None
    assert loaded.name == "node-1"
    assert loaded.expected_response == "ok"

    assert [item.id for item in await list_nodes()] == [node.id]
    assert await set_enabled(node.id, False) is True
    assert await list_nodes(enabled_only=True) == []

    checked_at = datetime(2026, 1, 1, 12, 0)
    assert await update_node_status(node.id, False, checked_at) is True
    loaded = await get_node(node.id)
    assert loaded.last_status is False
    assert loaded.last_check_time == checked_at
    assert loaded.check_interval == 1
    assert loaded.check_interval_unit == "m"
    assert loaded.last_notified_status is None
    assert loaded.blocked is None
    assert loaded.blocked_checked_at is None
    assert loaded.last_latency_ms is None
    assert loaded.last_error is None
    assert loaded.consecutive_failures == 0
    assert loaded.check_history is None

    checked_block = datetime(2026, 1, 1, 13, 0)
    exists, changed = await record_blocked_result(node.id, True, checked_block)
    assert (exists, changed) == (True, True)
    loaded = await get_node(node.id)
    assert loaded.blocked is True
    assert loaded.blocked_checked_at == checked_block
    assert await record_blocked_result(node.id, True, checked_block) == (True, False)
    assert await record_blocked_result(999, True, checked_block) == (False, False)

    assert await set_interval(node.id, 2, "h") is True
    loaded = await get_node(node.id)
    assert loaded.check_interval == 2
    assert loaded.check_interval_unit == "h"
    assert loaded.interval_seconds == 7200
    assert await set_interval(node.id, 0, "h") is False

    assert await delete_node(node.id) is True
    assert await get_node(node.id) is None
    assert await delete_node(node.id) is False


async def test_record_check_result_stores_metrics(node_db):
    node = await add_node(name="metrics", ip="127.0.0.1", port=80, protocol="HTTP")
    checked_at = datetime(2026, 1, 1, 12, 0)

    result = await record_check_result(
        node.id, False, checked_at, latency_ms=321, error="таймаут"
    )
    assert result == (True, True, True)

    loaded = await get_node(node.id)
    assert loaded.last_latency_ms == 321
    assert loaded.last_error == "таймаут"
    assert loaded.consecutive_failures == 1
    assert "true" not in (loaded.check_history or "").lower()
    assert "false" in (loaded.check_history or "").lower()

    await record_check_result(node.id, True, checked_at, latency_ms=10, error=None)
    loaded = await get_node(node.id)
    assert loaded.last_latency_ms == 10
    assert loaded.last_error is None
    assert loaded.consecutive_failures == 0
