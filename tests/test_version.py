import asyncio
from pathlib import Path

from app.handlers.admin import cmd_version
from app.version import VERSION


def test_version_is_1_0():
    version_file = Path(__file__).resolve().parents[1] / "VERSION"
    assert version_file.read_text(encoding="utf-8").strip() == "1.8"
    assert VERSION == "1.8"


def test_version_command_answers_with_version():
    class Message:
        def __init__(self):
            self.answers = []

        async def answer(self, text, **kwargs):
            self.answers.append(text)

    class State:
        async def clear(self):
            return None

    message = Message()
    state = State()

    asyncio.run(cmd_version(message, state))

    assert message.answers == ["Node Monitor Bot ver. 1.8"]
