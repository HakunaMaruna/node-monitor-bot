from app.models.node import Node
from app.services.monitor import check_node
from app.services.nodes import get_node
from app.services.ping import PingService


async def test_check_node_persists_status_change(node_db, monkeypatch):
    node = await add_test_node()

    async def down(candidate):
        return False

    monkeypatch.setattr(PingService, "check_node", staticmethod(down))
    assert await check_node(node) == (False, True)

    updated = await get_node(node.id)
    assert updated.last_status is False
    assert updated.last_check_time is not None

    node = await get_node(node.id)
    assert await check_node(node) == (False, False)


async def add_test_node():
    from app.services.nodes import add_node

    return await add_node(
        name="test",
        ip="127.0.0.1",
        port=1234,
        protocol="TCP",
    )
