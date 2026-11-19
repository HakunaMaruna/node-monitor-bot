import logging
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.models.node import Node, naive_utcnow
from app.services.cheburcheck import refresh_nodes_blocked
from app.services.monitor import check_node
from app.services.notifier import send_status_alert
from app.services.nodes import list_nodes
from app.utils.design import PARSE_MODE
from app.utils.formatting import format_summary

logger = logging.getLogger(__name__)


class MonitorScheduler:
    def __init__(
        self,
        bot: Bot,
        *,
        alert_chat_id: int,
        summary_chat_id: int,
        poll_tick_seconds: int = 1,
        summary_interval_hours: int = 1,
        cheburcheck_interval_hours: int = settings.CHEBURCHECK_INTERVAL_HOURS,
        cheburcheck_startup_delay_sec: int = settings.CHEBURCHECK_STARTUP_DELAY_SEC,
        cheburcheck_timeout_sec: int = settings.CHEBURCHECK_TIMEOUT_SEC,
        cheburcheck_delay_sec: float = settings.CHEBURCHECK_REQUEST_DELAY_SEC,
    ) -> None:
        self.bot = bot
        self.alert_chat_id = alert_chat_id
        self.summary_chat_id = summary_chat_id
        self.poll_tick_seconds = poll_tick_seconds
        self.summary_interval_hours = summary_interval_hours
        self.cheburcheck_interval_hours = cheburcheck_interval_hours
        self.cheburcheck_startup_delay_sec = cheburcheck_startup_delay_sec
        self.cheburcheck_timeout_sec = cheburcheck_timeout_sec
        self.cheburcheck_delay_sec = cheburcheck_delay_sec
        self.scheduler = AsyncIOScheduler()

    def start(self) -> None:
        self.scheduler.add_job(
            self.poll_nodes,
            trigger=IntervalTrigger(seconds=self.poll_tick_seconds),
            id="poll_nodes",
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
        self.scheduler.add_job(
            self.check_cheburcheck,
            trigger=IntervalTrigger(hours=self.cheburcheck_interval_hours),
            next_run_time=datetime.now(self.scheduler.timezone)
            + timedelta(seconds=self.cheburcheck_startup_delay_sec),
            id="cheburcheck",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self.scheduler.start()

    def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown()

    async def _check_node(self, node: Node) -> None:
        status, _, should_notify = await check_node(node)
        if should_notify:
            await send_status_alert(self.bot, node, status, self.alert_chat_id)

    async def poll_nodes(self) -> None:
        now = naive_utcnow()
        for node in await list_nodes(enabled_only=True):
            if node.last_check_time is None:
                await self._check_node(node)
                continue
            if (now - node.last_check_time).total_seconds() >= node.interval_seconds:
                await self._check_node(node)

    async def check_all(self) -> None:
        for node in await list_nodes(enabled_only=True):
            await self._check_node(node)

    async def check_cheburcheck(self, nodes: list[Node] | None = None) -> list[str]:
        targets = nodes if nodes is not None else await list_nodes(enabled_only=True)
        return await refresh_nodes_blocked(
            targets,
            bot=self.bot,
            alert_chat_id=self.alert_chat_id,
            timeout_sec=self.cheburcheck_timeout_sec,
            delay_sec=self.cheburcheck_delay_sec,
        )

    async def send_summary(self) -> None:
        nodes = await list_nodes()
        try:
            await self.bot.send_message(
                chat_id=self.summary_chat_id,
                text=format_summary(nodes),
                parse_mode=PARSE_MODE,
            )
        except TelegramAPIError:
            logger.exception("Не удалось отправить сводку")
