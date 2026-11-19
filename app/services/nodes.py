from datetime import datetime

from sqlalchemy import select, update

from app.config import settings
from app.database import async_session
from app.models.node import Node
from app.utils.history import append_check


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
    node_id: int,
    status: bool,
    checked_at: datetime,
    *,
    latency_ms: int | None = None,
    error: str | None = None,
    alert_repeat_seconds: int | None = None,
) -> tuple[bool, bool, bool]:
    repeat_seconds = (
        settings.ALERT_REPEAT_MINUTES * 60
        if alert_repeat_seconds is None
        else alert_repeat_seconds
    )
    async with async_session() as session:
        node = await session.get(Node, node_id)
        if node is None:
            return False, False, False

        changed = node.last_status != status
        if changed or node.status_since is None:
            node.status_since = checked_at
        if status:
            should_notify = node.last_notified_status is not True
            if should_notify:
                node.last_alert_time = None
        else:
            last_alert_time = node.last_alert_time
            repeat_due = (
                last_alert_time is None
                or (checked_at - last_alert_time).total_seconds() >= repeat_seconds
            )
            should_notify = changed or repeat_due
            if should_notify:
                node.last_alert_time = checked_at
        node.last_status = status
        node.last_check_time = checked_at
        node.last_notified_status = status
        node.last_latency_ms = latency_ms
        node.last_error = None if status else error
        node.consecutive_failures = 0 if status else (node.consecutive_failures or 0) + 1
        node.check_history = append_check(node.check_history, checked_at, status)

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
