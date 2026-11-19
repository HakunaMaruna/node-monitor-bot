from app.models.node import Node


def status_label(status: bool) -> str:
    return "UP" if status else "DOWN"


def format_node(node: Node) -> str:
    checked = node.last_check_time.strftime("%Y-%m-%d %H:%M") if node.last_check_time else "-"
    return (
        f"#{node.id} {node.name} | {node.protocol}://{node.ip}:{node.port} | "
        f"{status_label(node.last_status)} | {checked}"
    )


def format_node_card(node: Node) -> str:
    checked = node.last_check_time.strftime("%Y-%m-%d %H:%M") if node.last_check_time else "-"
    return (
        f"Нода #{node.id}: {node.name}\n"
        f"Адрес: {node.protocol}://{node.ip}:{node.port}\n"
        f"Статус: {status_label(node.last_status)}\n"
        f"Проверка: {'включена' if node.enabled else 'выключена'}\n"
        f"Таймаут: {node.timeout_sec} с\n"
        f"Ожидаемый ответ: {node.expected_response or '-'}\n"
        f"Последняя проверка: {checked}"
    )


def format_status_change(node: Node, status: bool) -> str:
    marker = "OK" if status else "ALERT"
    return f"{marker}: {node.name} ({node.ip}:{node.port}) -> {status_label(status)}"


def format_summary(nodes: list[Node]) -> str:
    enabled = [node for node in nodes if node.enabled]
    down = [node for node in enabled if not node.last_status]
    lines = [
        "Сводка по нодам",
        f"Всего: {len(nodes)}, включено: {len(enabled)}",
        f"UP: {len(enabled) - len(down)}, DOWN: {len(down)}",
    ]
    if down:
        lines.append("Проблемы:")
        lines.extend(f"- {node.name} ({node.ip}:{node.port})" for node in down)
    return "\n".join(lines)
