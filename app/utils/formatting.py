from app.models.node import Node
from app.utils.intervals import format_interval


def status_label(status: bool) -> str:
    return "UP" if status else "DOWN"


def blocked_label(blocked: bool | None) -> str:
    if blocked is None:
        return "не проверялась"
    return "заблокирована" if blocked else "не заблокирована"


def format_node(node: Node) -> str:
    checked = node.last_check_time.strftime("%Y-%m-%d %H:%M") if node.last_check_time else "-"
    return (
        f"#{node.id} {node.name} | {node.protocol}://{node.ip}:{node.port} | "
        f"{status_label(node.last_status)} | Cheburcheck: {blocked_label(node.blocked)} | {checked}"
    )


def format_node_card(node: Node) -> str:
    checked = node.last_check_time.strftime("%Y-%m-%d %H:%M") if node.last_check_time else "-"
    checked_block = (
        node.blocked_checked_at.strftime("%Y-%m-%d %H:%M") if node.blocked_checked_at else "-"
    )
    return (
        f"Нода #{node.id}: {node.name}\n"
        f"Адрес: {node.protocol}://{node.ip}:{node.port}\n"
        f"Статус: {status_label(node.last_status)}\n"
        f"Cheburcheck: {blocked_label(node.blocked).capitalize()} ({checked_block})\n"
        f"Проверка: {'включена' if node.enabled else 'выключена'}\n"
        f"Интервал опроса: {format_interval(node.check_interval, node.check_interval_unit)}\n"
        f"Таймаут: {node.timeout_sec} с\n"
        f"Ожидаемый ответ: {node.expected_response or '-'}\n"
        f"Последняя проверка: {checked}"
    )


def format_status_change(node: Node, status: bool) -> str:
    marker = "OK" if status else "ALERT"
    return f"{marker}: {node.name} ({node.ip}:{node.port}) -> {status_label(status)}"


def format_blocked_verdict(node: Node, blocked: bool | None) -> str:
    return f"Cheburcheck: {node.name} — {blocked_label(blocked)}"


def format_blocked_change(node: Node, blocked: bool) -> str:
    return (
        f"Cheburcheck: {node.name} ({node.ip}:{node.port}) -> "
        f"{blocked_label(blocked).upper()}"
    )


def format_summary(nodes: list[Node]) -> str:
    enabled = [node for node in nodes if node.enabled]
    down = [node for node in enabled if not node.last_status]
    blocked = [node for node in enabled if node.blocked is True]
    clean = [node for node in enabled if node.blocked is False]
    unchecked = len(enabled) - len(blocked) - len(clean)
    lines = [
        "Сводка по нодам",
        f"Всего: {len(nodes)}, включено: {len(enabled)}",
        f"UP: {len(enabled) - len(down)}, DOWN: {len(down)}",
        f"Cheburcheck: заблокировано {len(blocked)}, "
        f"не заблокировано {len(clean)}, не проверялось {unchecked}",
    ]
    if blocked:
        lines.append("Заблокированные:")
        lines.extend(f"- {node.name} ({node.ip}:{node.port})" for node in blocked)
    if down:
        lines.append("Проблемы:")
        lines.extend(f"- {node.name} ({node.ip}:{node.port})" for node in down)
    return "\n".join(lines)
