from datetime import datetime, timedelta

from app.utils.history import append_check, decode_history, uptime_24h

NOW = datetime(2026, 11, 19, 12, 0)


def test_append_and_decode_history():
    raw = append_check(None, NOW - timedelta(hours=3), True)
    raw = append_check(raw, NOW - timedelta(hours=2), False)
    raw = append_check(raw, NOW - timedelta(hours=1), True)

    items = decode_history(raw)

    assert [status for _, status in items] == [True, False, True]
    assert uptime_24h(raw, NOW) == 66.7


def test_history_drops_older_than_24_hours():
    raw = append_check(None, NOW - timedelta(hours=48), False)
    raw = append_check(raw, NOW, True)

    assert len(decode_history(raw)) == 1
    assert uptime_24h(raw, NOW) == 100.0


def test_uptime_without_history():
    assert decode_history(None) == []
    assert decode_history("not json") == []
    assert uptime_24h(None, NOW) is None
