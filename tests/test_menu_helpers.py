import pytest
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.methods import AnswerCallbackQuery

from app.handlers.menu import answer_callback, edit_message, perform_checks
from app.models.node import Node


class FakeMessage:
    def __init__(self, error: str):
        self.error = error

    async def edit_text(self, text, reply_markup=None, **kwargs):
        raise TelegramBadRequest(AnswerCallbackQuery(callback_query_id="stale"),self.error)


class FakeCallback:
    def __init__(self, error: str):
        self.message = FakeMessage(error)

    async def answer(self, text=None, **kwargs):
        raise TelegramBadRequest(AnswerCallbackQuery(callback_query_id="stale"),"query is too old")


async def test_stale_callback_answer_is_ignored():
    await answer_callback(FakeCallback("message is not modified"))


async def test_message_not_modified_is_ignored():
    await edit_message(FakeCallback("message is not modified"), "text", None)


async def test_message_to_edit_not_found_is_ignored():
    await edit_message(FakeCallback("message to edit not found"), "text", None)


async def test_other_edit_errors_propagate():
    with pytest.raises(TelegramBadRequest):
        await edit_message(FakeCallback("other error"), "text", None)


async def test_perform_checks_continues_after_alert_error(monkeypatch):
    nodes = [
        Node(id=1, name="first", ip="10.0.0.1", port=80, protocol="HTTP"),
        Node(id=2, name="second", ip="10.0.0.2", port=80, protocol="HTTP"),
    ]

    async def fake_check(candidate):
        return False, True, True

    monkeypatch.setattr("app.handlers.menu.check_node", fake_check)

    async def fake_get_node(node_id):
        return next(node for node in nodes if node.id == node_id)

    monkeypatch.setattr("app.handlers.menu.get_node", fake_get_node)

    class FailingBot:
        def __init__(self):
            self.messages = []
            self.attempts = 0

        async def send_message(self, chat_id, text, **kwargs):
            self.attempts += 1
            if self.attempts == 1:
                raise TelegramAPIError(AnswerCallbackQuery(callback_query_id="stale"), "boom")
            self.messages.append((chat_id, text))

    bot = FailingBot()
    result = await perform_checks(nodes, bot)

    assert "first" in result
    assert "second" in result
    assert len(bot.messages) == 1
