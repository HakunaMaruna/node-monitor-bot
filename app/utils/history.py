import json
from datetime import datetime, timedelta

HISTORY_LIMIT = 200
UPTIME_WINDOW_HOURS = 24


def decode_history(raw: str | None) -> list[tuple[datetime, bool]]:
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return []
    result = []
    for item in payload:
        if not isinstance(item, list) or len(item) != 2:
            continue
        try:
            checked_at = datetime.fromisoformat(str(item[0]))
        except ValueError:
            continue
        result.append((checked_at, bool(item[1])))
    return result


def encode_history(items: list[tuple[datetime, bool]]) -> str:
    return json.dumps([[checked_at.isoformat(), status] for checked_at, status in items])


def append_check(raw: str | None, checked_at: datetime, status: bool) -> str:
    cutoff = checked_at - timedelta(hours=UPTIME_WINDOW_HOURS)
    items = [
        item for item in decode_history(raw) if item[0] >= cutoff and item[0] <= checked_at
    ]
    items.append((checked_at, status))
    return encode_history(items[-HISTORY_LIMIT:])


def uptime_24h(raw: str | None, now: datetime) -> float | None:
    cutoff = now - timedelta(hours=UPTIME_WINDOW_HOURS)
    items = [item for item in decode_history(raw) if item[0] >= cutoff]
    if not items:
        return None
    up = sum(1 for _, status in items if status)
    return round(up * 100 / len(items), 1)
