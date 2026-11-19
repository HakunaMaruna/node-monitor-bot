from datetime import datetime, timezone

from app.models.node import Node
from app.services.nodes import record_check_result
from app.services.ping import PingService


async def check_node(node: Node) -> tuple[bool, bool, bool]:
    result = await PingService.check_node_detailed(node)
    checked_at = datetime.now(timezone.utc).replace(tzinfo=None)
    _, changed, should_notify = await record_check_result(
        node.id,
        result.status,
        checked_at,
        latency_ms=result.latency_ms,
        error=result.error,
    )
    return result.status, changed, should_notify
