from datetime import datetime, timezone

from app.models.node import Node
from app.services.nodes import update_node_status
from app.services.ping import PingService


async def check_node(node: Node) -> tuple[bool, bool]:
    status = await PingService.check_node(node)
    changed = status != node.last_status
    checked_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await update_node_status(node.id, status, checked_at)
    return status, changed
