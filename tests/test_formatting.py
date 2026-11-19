from datetime import datetime, timedelta

from app.models.node import Node
from app.utils.history import append_check
from app.version import VERSION
from app.utils.formatting import (
    format_blocked_change,
    format_blocked_error,
    format_cheburcheck_report,
    format_check_result,
    format_list_header,
    format_main_menu,
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
    assert "🌐 Протокол: <b>HTTP</b>" in card
    assert "🔗 Адрес: <code>http://example.com:80</code>" in card
    assert "🟢 Статус: <b>Доступна</b>" in card
    assert "⏱️ Интервал: <b>5m</b>" in card
    assert "⏭️ Следующая проверка: <b>через 3 мин</b>" in card
    assert "🕒 Последняя проверка: <b>2 мин назад</b>" in card
    assert "📅 Точное время: <b>19.11 11:58 UTC</b>" in card
    assert "✅ Вердикт: <b>Не заблокирована</b>" in card
    assert "📅 Проверено: <b>19.11 11:30 UTC</b>" in card
    assert "🕒 Когда: <b>30 мин назад</b>" in card
    assert "🔎 Ожидаемый ответ: <code>OK</code>" in card
    assert "⚡ Задержка: <b>42 мс</b>" in card
    assert "📈 Uptime 24h: <b>нет данных</b>" in card
    assert "📉 Последние проверки: <b>—</b>" in card
    assert "<b>СОСТОЯНИЕ</b>" in card
    assert "<b>МЕТРИКИ</b>" in card
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
    assert "⏸️ Статус: <b>Отключена</b>" in card
    assert "🔌 Протокол: <b>TCP</b>" in card
    assert "🔗 Адрес: <code>tcp://example.com:80</code>" in card
    assert "🔎 Ожидаемый ответ: не используется" in card
    assert "⚪ Вердикт: <b>Не проверялась</b>" in card
    assert "📅 Проверено: <b>— UTC</b>" in card
    assert "🕒 Когда: <b>никогда</b>" in card


def test_node_card_escapes_html_from_names():
    card = format_node_card(make_node(name="<b>bad</b>", expected_response="<script>"), now=NOW)

    assert "&lt;b&gt;bad&lt;/b&gt;" in card
    assert "&lt;script&gt;" in card
    assert "<script>" not in card


def test_node_card_shows_status_duration():
    node = make_node(
        last_status=False,
        status_since=NOW - timedelta(minutes=45),
    )

    card = format_node_card(node, now=NOW)

    assert "📅 Недоступна с: <b>19.11 11:15 UTC</b>" in card
    assert "⏳ Длительность: <b>45 мин</b>" in card


def test_recovery_alert_shows_downtime():
    node = make_node(last_status=True, status_since=NOW)
    alert = format_status_change(node, True, downtime_seconds=125)

    assert "🟢 <b>НОДА ВОССТАНОВЛЕНА</b>" in alert
    assert "⏳ Была недоступна: <b>2 мин</b>" in alert


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
    assert "📈 Uptime 24h: <b>50.0%</b>" in card
    assert "📉 Последние проверки: <b>🟢🔴</b>" in card
    assert "⚠️ Причина: <code>таймаут</code>" in card
    assert "🔁 Ошибок подряд: <b>1</b>" in card


def test_check_result_and_alerts_use_russian_statuses():
    node = make_node(last_status=False)
    alert = format_status_change(node, False)

    assert "🔴 <b>#1 web</b>" in format_check_result(node, False)
    assert "📌 Статус: <b>Недоступна</b>" in format_check_result(node, False)
    assert "🔴 <b>НОДА НЕДОСТУПНА</b>" in alert
    assert "📌 Статус: <b>Недоступна</b>" in alert
    assert "⚡ Задержка: <b>42 мс</b>" in alert
    assert "🚫 <b>CHEBURCHECK: ЗАБЛОКИРОВАНА</b>" in format_blocked_change(node, True)
    assert "📌 Вердикт: <b>Заблокирована</b>" in format_blocked_change(node, True)


def test_down_alert_shows_error_and_failure_count():
    node = make_node(
        last_status=False,
        last_latency_ms=321,
        last_error="соединение <сброшено>",
        consecutive_failures=3,
    )
    alert = format_status_change(node, False)

    assert "⚡ Задержка: <b>321 мс</b>" in alert
    assert "⚠️ Причина: <code>соединение &lt;сброшено&gt;</code>" in alert
    assert "🔁 Ошибок подряд: <b>3</b>" in alert
    assert "<сброшено>" not in alert


def test_cheburcheck_report_escapes_errors():
    error = format_blocked_error(make_node(name="<b>bad</b>"), "ошибка <script>")

    assert "&lt;b&gt;bad&lt;/b&gt;" in error
    assert "&lt;script&gt;" in error
    assert "<script>" not in error

    report = format_cheburcheck_report([error])

    assert "<b>CHEBURCHECK: ОТЧЁТ</b>" in report
    assert "Проверено нод: <b>1</b>" in report
    assert "⚠️ Ошибок: <b>1</b>" in report
    assert "<b>1.</b> ⚠️ <b>CHEBURCHECK: ОШИБКА</b>" in report
    assert "Нет включённых нод" in format_cheburcheck_report([])


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
    assert "• <b>blocked</b>" in summary
    assert "🔗 <code>example.com:80</code>" in summary
    assert "off" not in summary


def test_main_menu_and_list_header_use_separate_lines():
    menu = format_main_menu(total=3, enabled=2, down=1)
    header = format_list_header(total=45, enabled=40, page=1, pages=3)

    assert f"📌 Версия: <b>{VERSION}</b>" in menu
    assert "🖥️ Всего нод: <b>3</b>" in menu
    assert "🟢 Активных: <b>2</b>" in menu
    assert "🔴 Проблем: <b>1</b>" in menu
    assert "📄 Страница: <b>2/3</b>" in header


def test_summary_includes_average_uptime():
    history = append_check(None, NOW - timedelta(minutes=10), True)
    history = append_check(history, NOW - timedelta(minutes=5), False)
    nodes = [make_node(id=1, check_history=history)]

    summary = format_summary(nodes)

    assert "Средний uptime 24h: <b>50.0%</b>" in summary
