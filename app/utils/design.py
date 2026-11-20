from html import escape

PARSE_MODE = "HTML"
NODES_PER_PAGE = 20
MAX_LIST_ITEMS = 15

ICON = {
    "up": "🟢",
    "down": "🔴",
    "paused": "⏸️",
    "tcp": "🔌",
    "http": "🌐",
    "https": "🔒",
    "shield": "🛡️",
    "clock": "⏱️",
    "duration": "⏳",
    "history": "🕒",
    "settings": "⚙️",
    "refresh": "🔄",
    "list": "📋",
    "home": "🏠",
    "add": "➕",
    "delete": "🗑️",
    "alert": "🚨",
    "ok": "✅",
    "blocked": "🚫",
    "unknown": "⚪",
    "info": "ℹ️",
    "help": "❔",
    "node": "🖥️",
    "search": "🔎",
    "latency": "⚡",
    "trend": "📈",
    "chart": "📉",
    "warning": "⚠️",
    "repeat": "🔁",
    "link": "🔗",
    "calendar": "📅",
    "pin": "📌",
    "page": "📄",
    "back": "«",
    "cancel": "↩️",
    "skip": "⏭️",
}

STATUS_TEXT = {True: "Доступна", False: "Недоступна"}
BLOCKED_TEXT = {None: "Не проверялась", True: "Заблокирована", False: "Не заблокирована"}


def esc(value: object) -> str:
    return escape(str(value), quote=True)


def protocol_icon(protocol: str) -> str:
    return ICON.get((protocol or "").lower(), ICON["node"])


def status_icon(status: bool, enabled: bool = True) -> str:
    if not enabled:
        return ICON["paused"]
    return ICON["up"] if status else ICON["down"]


def blocked_icon(blocked: bool | None) -> str:
    if blocked is None:
        return ICON["unknown"]
    return ICON["blocked"] if blocked else ICON["ok"]


def button_text(value: object, limit: int | None = None) -> str:
    text = " ".join(str(value).split())
    if limit is not None:
        text = text[:limit]
    return text
