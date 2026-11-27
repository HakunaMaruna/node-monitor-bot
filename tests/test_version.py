import asyncio
from pathlib import Path

from app.handlers.admin import cmd_version
from app.version import VERSION


def test_version_matches_version_file():
    version_file = Path(__file__).resolve().parents[1] / "VERSION"
    assert VERSION == version_file.read_text(encoding="utf-8").strip()


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

    assert message.answers == [f"Node Monitor Bot ver. {VERSION}"]
