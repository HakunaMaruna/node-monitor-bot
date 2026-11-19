from datetime import datetime

from app.services.nodes import (
    add_node,
    delete_node,
    get_node,
    list_nodes,
    set_enabled,
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

    assert await delete_node(node.id) is True
    assert await get_node(node.id) is None
    assert await delete_node(node.id) is False
