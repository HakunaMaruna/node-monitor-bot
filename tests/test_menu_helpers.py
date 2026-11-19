import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import AnswerCallbackQuery

from app.handlers.menu import answer_callback, edit_message


class FakeMessage:
    def __init__(self, error: str):
        self.error = error

    async def edit_text(self, text, reply_markup=None):
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


async def test_other_edit_errors_propagate():
    with pytest.raises(TelegramBadRequest):
        await edit_message(FakeCallback("other error"), "text", None)
