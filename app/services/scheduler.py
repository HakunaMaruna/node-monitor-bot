from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.services.monitor import check_node
from app.services.nodes import list_nodes
from app.utils.formatting import format_status_change, format_summary


class MonitorScheduler:
    def __init__(
        self,
        bot: Bot,
        *,
        alert_chat_id: int,
        summary_chat_id: int,
        check_interval_minutes: int = 5,
        summary_interval_hours: int = 1,
    ) -> None:
        self.bot = bot
        self.alert_chat_id = alert_chat_id
        self.summary_chat_id = summary_chat_id
        self.check_interval_minutes = check_interval_minutes
        self.summary_interval_hours = summary_interval_hours
        self.scheduler = AsyncIOScheduler()

    def start(self) -> None:
        self.scheduler.add_job(
            self.check_all,
            trigger=IntervalTrigger(minutes=self.check_interval_minutes),
            id="check_nodes",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self.scheduler.add_job(
            self.send_summary,
            trigger=IntervalTrigger(hours=self.summary_interval_hours),
            id="send_summary",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self.scheduler.start()

    def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown()

    async def check_all(self) -> None:
        for node in await list_nodes(enabled_only=True):
            status, changed = await check_node(node)
            if changed:
                await self.bot.send_message(
                    chat_id=self.alert_chat_id,
                    text=format_status_change(node, status),
                )

    async def send_summary(self) -> None:
        nodes = await list_nodes()
        await self.bot.send_message(
            chat_id=self.summary_chat_id,
            text=format_summary(nodes),
        )
