import asyncio

from app.services.nodes import add_node
from app.services.scheduler import MonitorScheduler


class FakeBot:
    def __init__(self):
        self.messages = []

    async def send_message(self, chat_id, text):
        self.messages.append((chat_id, text))


async def test_scheduler_sends_alerts_and_summaries(node_db, monkeypatch):
    await add_node(name="node", ip="10.0.0.1", port=80, protocol="HTTP")

    async def fake_check(candidate):
        return False, True

    monkeypatch.setattr("app.services.scheduler.check_node", fake_check)

    bot = FakeBot()
    scheduler = MonitorScheduler(bot, alert_chat_id=100, summary_chat_id=200)

    await scheduler.check_all()
    assert bot.messages[0][0] == 100
    assert "ALERT" in bot.messages[0][1]

    await scheduler.send_summary()
    assert bot.messages[-1][0] == 200
    assert "Сводка по нодам" in bot.messages[-1][1]
    assert "DOWN: 0" in bot.messages[-1][1]

    scheduler.start()
    assert scheduler.scheduler.get_job("check_nodes") is not None
    assert scheduler.scheduler.get_job("send_summary") is not None
    scheduler.stop()
    await asyncio.sleep(0)
    assert scheduler.scheduler.running is False
