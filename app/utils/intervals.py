import re

UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600}
_UNIT_ALIASES = {
    "s": "s",
    "sec": "s",
    "secs": "s",
    "second": "s",
    "seconds": "s",
    "m": "m",
    "min": "m",
    "mins": "m",
    "minute": "m",
    "minutes": "m",
    "h": "h",
    "hr": "h",
    "hrs": "h",
    "hour": "h",
    "hours": "h",
}


def interval_seconds(amount: int, unit: str) -> int:
    return max(1, amount) * UNIT_SECONDS.get(unit, UNIT_SECONDS["m"])


def parse_interval(value: str) -> tuple[int, str] | None:
    match = re.fullmatch(r"(\d+)\s*([a-zA-Z]*)", (value or "").strip())
    if match is None:
        return None

    amount = int(match.group(1))
    raw_unit = match.group(2).lower()
    unit = "m" if not raw_unit else _UNIT_ALIASES.get(raw_unit)
    if amount <= 0 or unit is None:
        return None
    return amount, unit


def format_interval(amount: int, unit: str) -> str:
    return f"{amount}{unit}"
