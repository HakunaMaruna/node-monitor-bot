import math
from datetime import datetime

from app.models.node import Node, naive_utcnow
from app.utils.design import (
    ICON,
    MAX_LIST_ITEMS,
    BLOCKED_TEXT,
    STATUS_TEXT,
    blocked_icon,
    esc,
    protocol_icon,
    status_icon,
)
from app.utils.history import decode_history, uptime_24h
from app.utils.intervals import format_interval
from app.version import VERSION


def _absolute(value: datetime | None) -> str:
    return value.strftime("%d.%m %H:%M") if value else "—"


def _relative(value: datetime | None, now: datetime) -> str:
    if value is None:
        return "никогда"
    seconds = max(0, int((now - value).total_seconds()))
    if seconds < 10:
        return "только что"
    if seconds < 60:
        return f"{seconds} с назад"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} мин назад"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} ч назад"
    return f"{hours // 24} дн назад"


def format_sparkline(raw: str | None, limit: int = 20) -> str:
    items = decode_history(raw)[-limit:]
    if not items:
        return "—"
    return "".join(ICON["up"] if status else ICON["down"] for _, status in items)


def _next_check(node: Node, now: datetime) -> str:
    if node.last_check_time is None:
        return "сразу"
    remaining = node.interval_seconds - (now - node.last_check_time).total_seconds()
    if remaining <= 0:
        return "сейчас"
    if remaining < 60:
        return f"через {math.ceil(remaining)} с"
    if remaining < 3600:
        return f"через {math.ceil(remaining / 60)} мин"
    return f"через {math.ceil(remaining / 3600)} ч"


def status_label(status: bool) -> str:
    return STATUS_TEXT[status].lower()


def blocked_label(blocked: bool | None) -> str:
    return BLOCKED_TEXT[blocked].lower()


def format_node_card(node: Node, now: datetime | None = None) -> str:
    current = now or naive_utcnow()
    state_icon = status_icon(node.last_status, node.enabled)
    if not node.enabled:
        state_text = "Отключена"
    else:
        state_text = STATUS_TEXT[node.last_status]
    proto_icon = protocol_icon(node.protocol)
    protocol = (node.protocol or "").lower()
    address = f"{protocol}://{node.ip}:{node.port}"
    interval = format_interval(node.check_interval, node.check_interval_unit)
    lines = [
        f"{state_icon} <b>Нода #{node.id} · {esc(node.name)}</b>",
        f"{proto_icon} {esc(node.protocol)} · <code>{esc(address)}</code>",
        "",
        f"{ICON['info']} <b>СОСТОЯНИЕ</b>",
        f"{state_icon} {state_text}",
        f"{ICON['clock']} Интервал: <b>{interval}</b> · следующая проверка {_next_check(node, current)}",
        f"{ICON['history']} Последняя проверка: {_absolute(node.last_check_time)} UTC · "
        f"{_relative(node.last_check_time, current)}",
        f"{ICON['settings']} Таймаут: <b>{node.timeout_sec} с</b>",
    ]
    if protocol in {"http", "https"} and node.expected_response:
        lines.append(f"{ICON['search']} Ожидаемый ответ: <code>{esc(node.expected_response)}</code>")
    elif protocol == "tcp":
        lines.append(f"{ICON['search']} Ожидаемый ответ: не используется")
    else:
        lines.append(f"{ICON['search']} Ожидаемый ответ: не задан")

    latency = f"{node.last_latency_ms} мс" if node.last_latency_ms is not None else "—"
    uptime = uptime_24h(node.check_history, current)
    uptime_text = f"{uptime}%" if uptime is not None else "нет данных"
    lines.append(f"{ICON['latency']} Задержка: <b>{latency}</b>")
    lines.append(
        f"{ICON['trend']} Uptime 24h: <b>{uptime_text}</b> · {format_sparkline(node.check_history)}"
    )
    if node.last_error:
        lines.append(f"{ICON['warning']} Причина: <code>{esc(node.last_error)}</code>")
    if node.consecutive_failures:
        lines.append(f"{ICON['repeat']} Ошибок подряд: <b>{node.consecutive_failures}</b>")

    lines.extend(
        [
            "",
            f"{ICON['shield']} <b>CHEBURCHECK</b>",
            f"{blocked_icon(node.blocked)} {BLOCKED_TEXT[node.blocked]}",
            f"{ICON['history']} Проверено: {_absolute(node.blocked_checked_at)} UTC · "
            f"{_relative(node.blocked_checked_at, current)}",
            "",
            f"{ICON['settings']} <b>УПРАВЛЕНИЕ</b>",
        ]
    )
    return "\n".join(lines)


def format_check_result(node: Node, status: bool) -> str:
    return (
        f"{status_icon(status, node.enabled)} <b>#{node.id} {esc(node.name)}</b> — "
        f"{STATUS_TEXT[status]}"
    )


def format_status_change(node: Node, status: bool) -> str:
    title = "ДОСТУПНА" if status else "НЕДОСТУПНА"
    return (
        f"{status_icon(status)} <b>{title}</b>\n"
        f"{protocol_icon(node.protocol)} <b>{esc(node.name)}</b> · "
        f"<code>{esc(node.ip)}:{node.port}</code>\n"
        f"{ICON['history']} Проверка: {_absolute(naive_utcnow())} UTC"
    )


def format_blocked_verdict(node: Node, blocked: bool | None) -> str:
    return (
        f"{ICON['shield']} Cheburcheck · <b>{esc(node.name)}</b> — "
        f"{blocked_icon(blocked)} {BLOCKED_TEXT[blocked]}"
    )


def format_blocked_change(node: Node, blocked: bool) -> str:
    title = "ЗАБЛОКИРОВАНА" if blocked else "НЕ ЗАБЛОКИРОВАНА"
    return (
        f"{blocked_icon(blocked)} <b>CHEBURCHECK: {title}</b>\n"
        f"<b>{esc(node.name)}</b> · <code>{esc(node.ip)}:{node.port}</code>"
    )


def format_main_menu(total: int, enabled: int, down: int) -> str:
    return (
        f"{ICON['node']} <b>МОНИТОРИНГ НОД</b> · ver. {VERSION}\n"
        f"{ICON['info']} Всего: <b>{total}</b> · активных: <b>{enabled}</b> · "
        f"проблем: <b>{down}</b>\n\n"
        "Выберите действие:"
    )


def format_list_header(total: int, enabled: int, page: int, pages: int) -> str:
    suffix = f" · стр. {page + 1}/{pages}" if pages > 1 else ""
    return (
        f"{ICON['list']} <b>СПИСОК НОД</b>\n"
        f"Всего: <b>{total}</b> · активных: <b>{enabled}</b>{suffix}"
    )


def format_help(poll_tick_seconds: int, summary_hours: int, cheburcheck_hours: int) -> str:
    return (
        f"{ICON['help']} <b>ПОМОЩЬ</b>\n\n"
        f"{ICON['list']} <b>МОНИТОРИНГ</b>\n"
        "• /start — главное меню\n"
        "• /list — список нод\n"
        "• /add — мастер добавления ноды\n"
        "• /check [id] — проверить ноду или все включённые\n"
        "• /enable <id>, /disable <id> — включить/выключить ноду\n"
        "• /interval <id> <30s|5m|2h> — интервал опроса\n"
        "• /remove <id> — удалить ноду\n\n"
        f"{ICON['shield']} <b>CHEBURCHECK</b>\n"
        "• /blocked <id> — проверить блокировку\n\n"
        f"{ICON['info']} <b>СИСТЕМА</b>\n"
        "• /version — версия бота\n"
        f"• Опрос каждые {poll_tick_seconds} с\n"
        f"• Сводка раз в {summary_hours} ч\n"
        f"• Cheburcheck раз в {cheburcheck_hours} ч"
    )


def _limited(items: list[str]) -> list[str]:
    if len(items) <= MAX_LIST_ITEMS:
        return items
    return items[:MAX_LIST_ITEMS] + [f"… и ещё {len(items) - MAX_LIST_ITEMS}"]


def format_summary(nodes: list[Node]) -> str:
    enabled = [node for node in nodes if node.enabled]
    up = [node for node in enabled if node.last_status]
    down = [node for node in enabled if not node.last_status]
    blocked = [node for node in enabled if node.blocked is True]
    clean = [node for node in enabled if node.blocked is False]
    unchecked = len(enabled) - len(blocked) - len(clean)
    lines = [
        f"{ICON['info']} <b>СВОДКА ПО НОДАМ</b>",
        f"Всего: <b>{len(nodes)}</b> · активных: <b>{len(enabled)}</b>",
        "",
        f"{ICON['up']} <b>ДОСТУПНОСТЬ</b>",
        f"{ICON['up']} В сети: <b>{len(up)}</b>",
        f"{ICON['down']} Недоступно: <b>{len(down)}</b>",
        f"{ICON['paused']} Отключено: <b>{len(nodes) - len(enabled)}</b>",
    ]
    now = naive_utcnow()
    uptimes = [
        value
        for node in enabled
        if (value := uptime_24h(node.check_history, now)) is not None
    ]
    if uptimes:
        average = round(sum(uptimes) / len(uptimes), 1)
        lines.append(f"{ICON['trend']} Средний uptime 24h: <b>{average}%</b>")
    lines.extend(
        [
            "",
            f"{ICON['shield']} <b>CHEBURCHECK</b>",
            f"{ICON['ok']} Не заблокировано: <b>{len(clean)}</b>",
            f"{ICON['blocked']} Заблокировано: <b>{len(blocked)}</b>",
            f"{ICON['unknown']} Не проверялось: <b>{unchecked}</b>",
        ]
    )
    if blocked:
        lines.extend(["", f"{ICON['blocked']} <b>ЗАБЛОКИРОВАННЫЕ</b>"])
        lines.extend(
            f"• {esc(node.name)} · <code>{esc(node.ip)}:{node.port}</code>"
            for node in _limited(blocked)
        )
    if down:
        lines.extend(["", f"{ICON['down']} <b>ПРОБЛЕМЫ</b>"])
        lines.extend(
            f"• {esc(node.name)} · <code>{esc(node.ip)}:{node.port}</code>"
            for node in _limited(down)
        )
    return "\n".join(lines)
