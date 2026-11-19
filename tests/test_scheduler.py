import asyncio
from datetime import datetime

from aiogram.exceptions import TelegramAPIError
from aiogram.methods import AnswerCallbackQuery

from app.services.nodes import add_node, update_node_status
from app.services.scheduler import MonitorScheduler


class FakeBot:
    def __init__(self):
        self.messages = []

    async def send_message(self, chat_id, text, **kwargs):
        self.messages.append((chat_id, text))


async def test_scheduler_sends_alerts_and_summaries(node_db, monkeypatch):
    await add_node(name="node", ip="10.0.0.1", port=80, protocol="HTTP")

    async def fake_check(candidate):
        await update_node_status(candidate.id, False, datetime(2026, 1, 1, 12, 0))
        return False, True, True

    monkeypatch.setattr("app.services.scheduler.check_node", fake_check)

    bot = FakeBot()
    scheduler = MonitorScheduler(bot, alert_chat_id=100, summary_chat_id=200)

    await scheduler.check_all()
    assert bot.messages[0][0] == 100
    assert "НЕДОСТУПНА" in bot.messages[0][1]

    await scheduler.send_summary()
    assert bot.messages[-1][0] == 200
    assert "СВОДКА ПО НОДАМ" in bot.messages[-1][1]
    assert "Недоступно: <b>1</b>" in bot.messages[-1][1]

    scheduler.start()
    assert scheduler.scheduler.get_job("poll_nodes") is not None
    assert scheduler.scheduler.get_job("send_summary") is not None
    cheburcheck_job = scheduler.scheduler.get_job("cheburcheck")
    assert cheburcheck_job is not None
    assert cheburcheck_job.next_run_time is not None
    scheduler.stop()
    await asyncio.sleep(0)
    assert scheduler.scheduler.running is False


async def test_scheduler_continues_after_alert_error(node_db, monkeypatch):
    await add_node(name="first", ip="10.0.0.1", port=80, protocol="HTTP")
    await add_node(name="second", ip="10.0.0.2", port=80, protocol="HTTP")

    async def fake_check(candidate):
        return False, True, True

    monkeypatch.setattr("app.services.scheduler.check_node", fake_check)

    class FailingBot(FakeBot):
        def __init__(self):
            super().__init__()
            self.attempts = 0

        async def send_message(self, chat_id, text, **kwargs):
            self.attempts += 1
            if self.attempts == 1:
                raise TelegramAPIError(AnswerCallbackQuery(callback_query_id="stale"), "boom")
            await super().send_message(chat_id, text)

    bot = FailingBot()
    scheduler = MonitorScheduler(bot, alert_chat_id=100, summary_chat_id=200)

    await scheduler.check_all()

    assert bot.attempts == 2
    assert len(bot.messages) == 1


async def test_poll_nodes_respects_node_interval(node_db, monkeypatch):
    slow = await add_node(
        name="slow", ip="10.0.0.1", port=80, protocol="HTTP",
        check_interval=1, check_interval_unit="h",
    )
    due = await add_node(
        name="due", ip="10.0.0.2", port=80, protocol="HTTP",
        check_interval=1, check_interval_unit="s",
    )
    await update_node_status(due.id, True, datetime(2026, 1, 1, 12, 0))

    checked = []

    async def fake_check(candidate):
        checked.append(candidate.id)
        return True, False, False

    monkeypatch.setattr("app.services.scheduler.check_node", fake_check)

    scheduler = MonitorScheduler(FakeBot(), alert_chat_id=100, summary_chat_id=200)
    await scheduler.poll_nodes()

    assert checked == [due.id]
    assert slow.id not in checked


async def test_scheduler_runs_cheburcheck_for_enabled_nodes(node_db, monkeypatch):
    node = await add_node(name="site", ip="example.com", port=443, protocol="HTTPS")
    seen = {}

    async def fake_refresh(nodes, **kwargs):
        seen["ids"] = [candidate.id for candidate in nodes]
        seen["kwargs"] = kwargs
        return ["ok"]

    monkeypatch.setattr("app.services.scheduler.refresh_nodes_blocked", fake_refresh)

    bot = FakeBot()
    scheduler = MonitorScheduler(
        bot,
        alert_chat_id=100,
        summary_chat_id=200,
        cheburcheck_delay_sec=0,
    )
    assert await scheduler.check_cheburcheck() == ["ok"]
    assert bot.messages[-1][0] == 200
    assert "CHEBURCHECK: ОТЧЁТ" in bot.messages[-1][1]
    assert "• ok" in bot.messages[-1][1]
    assert seen["ids"] == [node.id]
    assert seen["kwargs"]["alert_chat_id"] == 100
    assert seen["kwargs"]["delay_sec"] == 0
