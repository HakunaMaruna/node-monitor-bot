from types import SimpleNamespace

from app.middlewares.admin import AdminOnlyMiddleware


class FakeEvent:
    def __init__(self):
        self.answers = []

    async def answer(self, text):
        self.answers.append(text)


async def test_admin_middleware_allows_admin():
    calls = []

    async def handler(event, data):
        calls.append(event)
        return "ok"

    middleware = AdminOnlyMiddleware(42)
    event = FakeEvent()
    result = await middleware(handler, event, {"event_from_user": SimpleNamespace(id=42)})
    assert result == "ok"
    assert calls == [event]
    assert event.answers == []


async def test_admin_middleware_blocks_other_users():
    async def handler(event, data):
        raise AssertionError("handler must not run")

    middleware = AdminOnlyMiddleware(42)
    event = FakeEvent()
    result = await middleware(handler, event, {"event_from_user": SimpleNamespace(id=7)})
    assert result is None
    assert len(event.answers) == 1
