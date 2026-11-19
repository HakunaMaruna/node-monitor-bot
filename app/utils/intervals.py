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


def interval_seconds(amount: int | None, unit: str | None) -> int:
    value = 1 if amount is None else amount
    resolved = "m" if unit is None else unit
    return max(1, value) * UNIT_SECONDS.get(resolved, UNIT_SECONDS["m"])


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


def format_interval(amount: int | None, unit: str | None) -> str:
    return f"{1 if amount is None else amount}{'m' if unit is None else unit}"
