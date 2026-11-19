from sqlalchemy import select

from app.database import async_session
from app.models.node import Node


async def list_nodes(*, enabled_only: bool = False) -> list[Node]:
    query = select(Node).order_by(Node.id)
    if enabled_only:
        query = query.where(Node.enabled.is_(True))
    async with async_session() as session:
        result = await session.execute(query)
        return list(result.scalars().all())


async def get_node(node_id: int) -> Node | None:
    async with async_session() as session:
        return await session.get(Node, node_id)


async def add_node(
    *,
    name: str,
    ip: str,
    port: int,
    protocol: str,
    timeout_sec: int = 5,
    expected_response: str | None = None,
) -> Node:
    node = Node(
        name=name,
        ip=ip,
        port=port,
        protocol=protocol,
        timeout_sec=timeout_sec,
        expected_response=expected_response,
    )
    async with async_session() as session:
        session.add(node)
        await session.commit()
        await session.refresh(node)
    return node


async def delete_node(node_id: int) -> bool:
    async with async_session() as session:
        node = await session.get(Node, node_id)
        if node is None:
            return False
        await session.delete(node)
        await session.commit()
    return True


async def set_enabled(node_id: int, enabled: bool) -> bool:
    async with async_session() as session:
        node = await session.get(Node, node_id)
        if node is None:
            return False
        node.enabled = enabled
        await session.commit()
    return True


async def update_node_status(node_id: int, status: bool, checked_at) -> bool:
    async with async_session() as session:
        node = await session.get(Node, node_id)
        if node is None:
            return False
        node.last_status = status
        node.last_check_time = checked_at
        await session.commit()
    return True
