from aiogram.fsm.state import State, StatesGroup


class AddNode(StatesGroup):
    name = State()
    protocol = State()
    ip = State()
    port = State()
    timeout = State()
    expected = State()


class SetInterval(StatesGroup):
    value = State()
