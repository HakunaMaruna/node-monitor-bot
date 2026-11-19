from datetime import datetime, timedelta

from app.models.node import Node
from app.utils.history import append_check
from app.utils.formatting import (
    format_blocked_change,
    format_check_result,
    format_node_card,
    format_status_change,
    format_summary,
)

NOW = datetime(2026, 11, 19, 12, 0)


def make_node(**kwargs) -> Node:
    values = {
        "id": 1,
        "name": "web",
        "ip": "example.com",
        "port": 80,
        "protocol": "HTTP",
        "enabled": True,
        "last_status": True,
        "check_interval": 5,
        "check_interval_unit": "m",
        "last_check_time": NOW - timedelta(minutes=2),
        "blocked": False,
        "blocked_checked_at": NOW - timedelta(minutes=30),
        "timeout_sec": 7,
        "expected_response": "OK",
        "last_latency_ms": 42,
        "last_error": None,
        "consecutive_failures": 0,
        "check_history": None,
    }
    values.update(kwargs)
    return Node(**values)


def test_node_card_has_icons_sections_and_relative_time():
    card = format_node_card(make_node(), now=NOW)

    assert "🟢 <b>Нода #1 · web</b>" in card
    assert "🌐 HTTP · <code>http://example.com:80</code>" in card
    assert "🟢 Доступна" in card
    assert "⏱️ Интервал: <b>5m</b> · следующая проверка через 3 мин" in card
    assert "🕒 Последняя проверка: 19.11 11:58 UTC · 2 мин назад" in card
    assert "✅ Не заблокирована" in card
    assert "🔎 Ожидаемый ответ: <code>OK</code>" in card
    assert "⚡ Задержка: <b>42 мс</b>" in card
    assert "📈 Uptime 24h: <b>нет данных</b> · —" in card
    assert "<b>СОСТОЯНИЕ</b>" in card
    assert "<b>CHEBURCHECK</b>" in card
    assert "<b>УПРАВЛЕНИЕ</b>" in card


def test_node_card_marks_disabled_and_hides_tcp_expected_response():
    card = format_node_card(
        make_node(
            protocol="TCP",
            enabled=False,
            last_status=True,
            expected_response="unused",
            blocked=None,
            blocked_checked_at=None,
        ),
        now=NOW,
    )

    assert "⏸️ <b>Нода #1 · web</b>" in card
    assert "⏸️ Отключена" in card
    assert "🔌 TCP" in card
    assert "🔎 Ожидаемый ответ: не используется" in card
    assert "⚪ Не проверялась" in card
    assert "🕒 Проверено: — UTC · никогда" in card


def test_node_card_escapes_html_from_names():
    card = format_node_card(make_node(name="<b>bad</b>", expected_response="<script>"), now=NOW)

    assert "&lt;b&gt;bad&lt;/b&gt;" in card
    assert "&lt;script&gt;" in card
    assert "<script>" not in card


def test_node_card_shows_error_uptime_and_sparkline():
    history = append_check(None, NOW - timedelta(minutes=10), True)
    history = append_check(history, NOW - timedelta(minutes=5), False)
    node = make_node(
        last_status=False,
        last_latency_ms=137,
        last_error="таймаут",
        consecutive_failures=1,
        check_history=history,
    )

    card = format_node_card(node, now=NOW)

    assert "⚡ Задержка: <b>137 мс</b>" in card
    assert "📈 Uptime 24h: <b>50.0%</b> · 🟢🔴" in card
    assert "⚠️ Причина: <code>таймаут</code>" in card
    assert "🔁 Ошибок подряд: <b>1</b>" in card


def test_check_result_and_alerts_use_russian_statuses():
    node = make_node(last_status=False)

    assert "🔴 <b>#1 web</b> — Недоступна" in format_check_result(node, False)
    assert "🔴 <b>НЕДОСТУПНА</b>" in format_status_change(node, False)
    assert "🚫 <b>CHEBURCHECK: ЗАБЛОКИРОВАНА</b>" in format_blocked_change(node, True)


def test_summary_has_sections_and_no_disabled_nodes_in_lists():
    nodes = [
        make_node(id=1, name="blocked", blocked=True),
        make_node(id=2, name="clean", blocked=False),
        make_node(id=3, name="unknown", blocked=None),
        make_node(id=4, name="off", enabled=False, blocked=True),
    ]

    summary = format_summary(nodes)

    assert "<b>СВОДКА ПО НОДАМ</b>" in summary
    assert "<b>ДОСТУПНОСТЬ</b>" in summary
    assert "<b>CHEBURCHECK</b>" in summary
    assert "Не заблокировано: <b>1</b>" in summary
    assert "Заблокировано: <b>1</b>" in summary
    assert "Не проверялось: <b>1</b>" in summary
    assert "blocked · <code>example.com:80</code>" in summary
    assert "off" not in summary


def test_summary_includes_average_uptime():
    history = append_check(None, NOW - timedelta(minutes=10), True)
    history = append_check(history, NOW - timedelta(minutes=5), False)
    nodes = [make_node(id=1, check_history=history)]

    summary = format_summary(nodes)

    assert "Средний uptime 24h: <b>50.0%</b>" in summary
