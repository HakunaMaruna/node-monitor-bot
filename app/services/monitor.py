from datetime import datetime, timezone

from app.models.node import Node
from app.services.nodes import record_check_result
from app.services.ping import PingService


async def check_node(node: Node) -> tuple[bool, bool, bool]:
    status = await PingService.check_node(node)
    checked_at = datetime.now(timezone.utc).replace(tzinfo=None)
    _, changed, should_notify = await record_check_result(node.id, status, checked_at)
    return status, changed, should_notify
