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


def format_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    if total < 60:
        return f"{total} с"
    minutes = total // 60
    if minutes < 60:
        return f"{minutes} мин"
    hours = minutes // 60
    if hours < 24:
        rest = minutes % 60
        return f"{hours} ч {rest} мин" if rest else f"{hours} ч"
    days = hours // 24
    rest = hours % 24
    return f"{days} дн {rest} ч" if rest else f"{days} дн"


def _node_address(node: Node, *, scheme: bool = False) -> str:
    if not node.ip:
        return "—"
    prefix = f"{(node.protocol or '').lower()}://" if scheme else ""
    return f"{prefix}{node.ip}:{node.port}"


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
    interval = format_interval(node.check_interval, node.check_interval_unit)
    latency = f"{node.last_latency_ms} мс" if node.last_latency_ms is not None else "—"
    uptime = uptime_24h(node.check_history, current)
    uptime_text = f"{uptime}%" if uptime is not None else "нет данных"

    lines = [
        f"{state_icon} <b>Нода #{node.id} · {esc(node.name)}</b>",
        f"{proto_icon} Протокол: <b>{esc(node.protocol)}</b>",
        f"{ICON['link']} Адрес: <code>{esc(_node_address(node, scheme=True))}</code>",
        "",
        f"{ICON['info']} <b>СОСТОЯНИЕ</b>",
        f"{state_icon} Статус: <b>{state_text}</b>",
        f"{ICON['clock']} Интервал: <b>{interval}</b>",
        f"{ICON['skip']} Следующая проверка: <b>{_next_check(node, current)}</b>",
        f"{ICON['history']} Последняя проверка: <b>{_relative(node.last_check_time, current)}</b>",
        f"{ICON['calendar']} Точное время: <b>{_absolute(node.last_check_time)} UTC</b>",
        f"{ICON['settings']} Таймаут: <b>{node.timeout_sec} с</b>",
    ]
    if node.status_since is not None:
        status_index = next(
            index for index, line in enumerate(lines) if "Статус:" in line
        )
        label = "Доступна с" if node.last_status else "Недоступна с"
        elapsed = format_duration((current - node.status_since).total_seconds())
        lines[status_index + 1 : status_index + 1] = [
            f"{ICON['calendar']} {label}: <b>{_absolute(node.status_since)} UTC</b>",
            f"{ICON['duration']} Длительность: <b>{elapsed}</b>",
        ]
    if protocol in {"http", "https"} and node.expected_response:
        lines.append(f"{ICON['search']} Ожидаемый ответ: <code>{esc(node.expected_response)}</code>")
    elif protocol == "tcp":
        lines.append(f"{ICON['search']} Ожидаемый ответ: не используется")
    else:
        lines.append(f"{ICON['search']} Ожидаемый ответ: не задан")

    lines.extend(
        [
            "",
            f"{ICON['trend']} <b>МЕТРИКИ</b>",
            f"{ICON['latency']} Задержка: <b>{latency}</b>",
            f"{ICON['trend']} Uptime 24h: <b>{uptime_text}</b>",
            f"{ICON['chart']} Последние проверки: <b>{format_sparkline(node.check_history)}</b>",
        ]
    )
    if node.last_error:
        lines.append(f"{ICON['warning']} Причина: <code>{esc(node.last_error)}</code>")
    if node.consecutive_failures:
        lines.append(f"{ICON['repeat']} Ошибок подряд: <b>{node.consecutive_failures}</b>")

    lines.extend(
        [
            "",
            f"{ICON['shield']} <b>CHEBURCHECK</b>",
            f"{blocked_icon(node.blocked)} Вердикт: <b>{BLOCKED_TEXT[node.blocked]}</b>",
            f"{ICON['shield']} ТСПУ: <b>{BLOCKED_TEXT[node.blocked]}</b>",
            f"{ICON['calendar']} Проверено: <b>{_absolute(node.blocked_checked_at)} UTC</b>",
            f"{ICON['history']} Когда: <b>{_relative(node.blocked_checked_at, current)}</b>",
            "",
            f"{ICON['settings']} <b>УПРАВЛЕНИЕ</b>",
        ]
    )
    return "\n".join(lines)


def format_check_result(node: Node, status: bool) -> str:
    lines = [
        f"{status_icon(status, node.enabled)} <b>#{node.id} {esc(node.name)}</b>",
        f"{ICON['pin']} Статус: <b>{STATUS_TEXT[status]}</b>",
        f"{protocol_icon(node.protocol)} Протокол: <b>{esc(node.protocol)}</b>",
        f"{ICON['link']} Адрес: <code>{esc(_node_address(node))}</code>",
    ]
    if node.last_latency_ms is not None:
        lines.append(f"{ICON['latency']} Задержка: <b>{node.last_latency_ms} мс</b>")
    if not status and node.last_error:
        lines.append(f"{ICON['warning']} Причина: <code>{esc(node.last_error)}</code>")
    if not status and node.consecutive_failures:
        lines.append(f"{ICON['repeat']} Ошибок подряд: <b>{node.consecutive_failures}</b>")
    return "\n".join(lines)


def format_status_change(
    node: Node,
    status: bool,
    *,
    downtime_seconds: float | None = None,
    now: datetime | None = None,
) -> str:
    current = now or naive_utcnow()
    title = "НОДА ВОССТАНОВЛЕНА" if status else "НОДА НЕДОСТУПНА"
    lines = [
        f"{status_icon(status)} <b>{title}</b>",
        f"{ICON['node']} Нода: <b>#{node.id} {esc(node.name)}</b>",
        f"{protocol_icon(node.protocol)} Протокол: <b>{esc(node.protocol)}</b>",
        f"{ICON['link']} Адрес: <code>{esc(_node_address(node))}</code>",
        f"{ICON['pin']} Статус: <b>{STATUS_TEXT[status]}</b>",
    ]
    if not status and node.status_since is not None:
        elapsed = format_duration((current - node.status_since).total_seconds())
        lines.extend(
            [
                f"{ICON['calendar']} Недоступна с: <b>{_absolute(node.status_since)} UTC</b>",
                f"{ICON['duration']} Длительность: <b>{elapsed}</b>",
            ]
        )
    if status and downtime_seconds is not None:
        lines.append(
            f"{ICON['duration']} Была недоступна: <b>{format_duration(downtime_seconds)}</b>"
        )
    if node.last_latency_ms is not None:
        lines.append(f"{ICON['latency']} Задержка: <b>{node.last_latency_ms} мс</b>")
    if not status and node.last_error:
        lines.append(f"{ICON['warning']} Причина: <code>{esc(node.last_error)}</code>")
    if not status and node.consecutive_failures:
        lines.append(f"{ICON['repeat']} Ошибок подряд: <b>{node.consecutive_failures}</b>")
    lines.append(f"{ICON['calendar']} Проверка: <b>{_absolute(current)} UTC</b>")
    return "\n".join(lines)


def format_blocked_error(node: Node, reason: str) -> str:
    return "\n".join(
        [
            f"{ICON['warning']} <b>CHEBURCHECK: ОШИБКА</b>",
            f"{ICON['node']} Нода: <b>#{node.id} {esc(node.name)}</b>",
            f"{ICON['link']} Адрес: <code>{esc(_node_address(node))}</code>",
            f"{ICON['pin']} Причина: <code>{esc(reason)}</code>",
        ]
    )


def format_blocked_verdict(node: Node, blocked: bool | None) -> str:
    current = naive_utcnow()
    return "\n".join(
        [
            f"{ICON['shield']} <b>CHEBURCHECK</b>",
            f"{ICON['node']} Нода: <b>#{node.id} {esc(node.name)}</b>",
            f"{ICON['link']} Адрес: <code>{esc(_node_address(node))}</code>",
            f"{blocked_icon(blocked)} Вердикт: <b>{BLOCKED_TEXT[blocked]}</b>",
            f"{ICON['calendar']} Проверено: <b>{_absolute(node.blocked_checked_at)} UTC</b>",
            f"{ICON['history']} Когда: <b>{_relative(node.blocked_checked_at, current)}</b>",
        ]
    )


def format_blocked_change(node: Node, blocked: bool) -> str:
    title = "ЗАБЛОКИРОВАНА" if blocked else "НЕ ЗАБЛОКИРОВАНА"
    current = naive_utcnow()
    return "\n".join(
        [
            f"{blocked_icon(blocked)} <b>CHEBURCHECK: {title}</b>",
            f"{ICON['node']} Нода: <b>#{node.id} {esc(node.name)}</b>",
            f"{ICON['link']} Адрес: <code>{esc(_node_address(node))}</code>",
            f"{ICON['pin']} Вердикт: <b>{BLOCKED_TEXT[blocked]}</b>",
            f"{ICON['calendar']} Проверено: <b>{_absolute(node.blocked_checked_at)} UTC</b>",
            f"{ICON['history']} Когда: <b>{_relative(node.blocked_checked_at, current)}</b>",
        ]
    )


def format_main_menu(total: int, enabled: int, down: int) -> str:
    return "\n".join(
        [
            f"{ICON['node']} <b>МОНИТОРИНГ НОД</b>",
            f"{ICON['pin']} Версия: <b>{VERSION}</b>",
            f"{ICON['node']} Всего нод: <b>{total}</b>",
            f"{ICON['up']} Активных: <b>{enabled}</b>",
            f"{ICON['down']} Проблем: <b>{down}</b>",
            "",
            "Выберите действие:",
        ]
    )


def format_list_header(total: int, enabled: int, page: int, pages: int) -> str:
    lines = [
        f"{ICON['list']} <b>СПИСОК НОД</b>",
        f"{ICON['node']} Всего нод: <b>{total}</b>",
        f"{ICON['up']} Активных: <b>{enabled}</b>",
    ]
    if pages > 1:
        lines.append(f"{ICON['page']} Страница: <b>{page + 1}/{pages}</b>")
    return "\n".join(lines)


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


def _node_block(node: Node, now: datetime | None = None) -> str:
    lines = [
        f"• <b>{esc(node.name)}</b>",
        f"  {ICON['link']} <code>{esc(_node_address(node))}</code>",
    ]
    if now is not None and not node.last_status and node.status_since is not None:
        elapsed = format_duration((now - node.status_since).total_seconds())
        lines.append(f"  {ICON['duration']} Недоступна: <b>{elapsed}</b>")
    return "\n".join(lines)


def format_cheburcheck_report(results: list[str]) -> str:
    lines = [f"{ICON['shield']} <b>CHEBURCHECK: ОТЧЁТ</b>"]
    if not results:
        lines.append(f"{ICON['info']} Нет включённых нод")
        return "\n".join(lines)

    blocked_count = sum(
        1 for item in results if f"Вердикт: <b>{BLOCKED_TEXT[True]}</b>" in item
    )
    error_count = sum(1 for item in results if "CHEBURCHECK: ОШИБКА" in item)
    clean_count = sum(
        1 for item in results if f"Вердикт: <b>{BLOCKED_TEXT[False]}</b>" in item
    )
    lines.extend(
        [
            f"{ICON['list']} Проверено нод: <b>{len(results)}</b>",
            f"{ICON['ok']} Чисто: <b>{clean_count}</b>",
            f"{ICON['blocked']} Заблокировано: <b>{blocked_count}</b>",
            f"{ICON['warning']} Ошибок: <b>{error_count}</b>",
            "",
        ]
    )
    for index, item in enumerate(_limited(results), 1):
        if item.startswith("…"):
            lines.append(item)
        else:
            lines.append(f"<b>{index}.</b> {item}")
        lines.append("")
    lines.pop()
    return "\n".join(lines)


def format_summary(nodes: list[Node], now: datetime | None = None) -> str:
    enabled = [node for node in nodes if node.enabled]
    up = [node for node in enabled if node.last_status]
    down = [node for node in enabled if not node.last_status]
    blocked = [node for node in enabled if node.blocked is True]
    clean = [node for node in enabled if node.blocked is False]
    unchecked = len(enabled) - len(blocked) - len(clean)
    lines = [
        f"{ICON['info']} <b>СВОДКА ПО НОДАМ</b>",
        f"{ICON['node']} Всего нод: <b>{len(nodes)}</b>",
        f"{ICON['up']} Активных: <b>{len(enabled)}</b>",
        "",
        f"{ICON['up']} <b>ДОСТУПНОСТЬ</b>",
        f"{ICON['up']} В сети: <b>{len(up)}</b>",
        f"{ICON['down']} Недоступно: <b>{len(down)}</b>",
        f"{ICON['paused']} Отключено: <b>{len(nodes) - len(enabled)}</b>",
    ]
    current = now or naive_utcnow()
    uptimes = [
        value
        for node in enabled
        if (value := uptime_24h(node.check_history, current)) is not None
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
        for item in _limited(blocked):
            if isinstance(item, str) and item.startswith("…"):
                lines.append(item)
            else:
                lines.append(_node_block(item, current))
    if down:
        lines.extend(["", f"{ICON['down']} <b>ПРОБЛЕМЫ</b>"])
        for item in _limited(down):
            if isinstance(item, str) and item.startswith("…"):
                lines.append(item)
            else:
                lines.append(_node_block(item, current))
    return "\n".join(lines)
