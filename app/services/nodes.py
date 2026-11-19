from datetime import datetime

from sqlalchemy import select, update

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
    check_interval: int = 1,
    check_interval_unit: str = "m",
) -> Node:
    node = Node(
        name=name,
        ip=ip,
        port=port,
        protocol=protocol,
        timeout_sec=timeout_sec,
        expected_response=expected_response,
        check_interval=check_interval,
        check_interval_unit=check_interval_unit,
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


async def update_node_status(node_id: int, status: bool, checked_at: datetime) -> bool:
    async with async_session() as session:
        result = await session.execute(
            update(Node)
            .where(Node.id == node_id)
            .values(last_status=status, last_check_time=checked_at)
        )
        await session.commit()
        return result.rowcount > 0


async def record_check_result(
    node_id: int, status: bool, checked_at: datetime
) -> tuple[bool, bool, bool]:
    async with async_session() as session:
        result = await session.execute(
            update(Node)
            .where(Node.id == node_id, Node.last_status != status)
            .values(last_status=status, last_check_time=checked_at)
        )
        if result.rowcount > 0:
            exists, changed = True, True
        else:
            result = await session.execute(
                update(Node).where(Node.id == node_id).values(last_check_time=checked_at)
            )
            exists, changed = result.rowcount > 0, False

        if not exists:
            await session.commit()
            return False, False, False

        if status:
            result = await session.execute(
                update(Node)
                .where(Node.id == node_id, Node.last_notified_status.is_not(True))
                .values(last_notified_status=True)
            )
            should_notify = result.rowcount > 0
        else:
            await session.execute(
                update(Node).where(Node.id == node_id).values(last_notified_status=False)
            )
            should_notify = True

        await session.commit()
        return True, changed, should_notify


async def record_blocked_result(
    node_id: int, blocked: bool, checked_at: datetime
) -> tuple[bool, bool]:
    async with async_session() as session:
        row = (
            await session.execute(select(Node.id, Node.blocked).where(Node.id == node_id))
        ).one_or_none()
        if row is None:
            return False, False
        changed = row.blocked != blocked
        await session.execute(
            update(Node)
            .where(Node.id == node_id)
            .values(blocked=blocked, blocked_checked_at=checked_at)
        )
        await session.commit()
        return True, changed


async def set_interval(node_id: int, amount: int, unit: str) -> bool:
    if amount <= 0 or unit not in {"s", "m", "h"}:
        return False
    async with async_session() as session:
        result = await session.execute(
            update(Node)
            .where(Node.id == node_id)
            .values(check_interval=amount, check_interval_unit=unit)
        )
        await session.commit()
        return result.rowcount > 0
