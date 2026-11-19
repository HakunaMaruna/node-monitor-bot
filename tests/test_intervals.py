import pytest

from app.utils.intervals import format_interval, interval_seconds, parse_interval


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("30s", (30, "s")),
        ("5 min", (5, "m")),
        ("2hours", (2, "h")),
        ("10", (10, "m")),
        ("0s", None),
        ("1.5h", None),
        ("abc", None),
    ],
)
def test_parse_interval(value, expected):
    assert parse_interval(value) == expected


def test_interval_seconds_and_format():
    assert interval_seconds(30, "s") == 30
    assert interval_seconds(5, "m") == 300
    assert interval_seconds(2, "h") == 7200
    assert format_interval(5, "m") == "5m"
