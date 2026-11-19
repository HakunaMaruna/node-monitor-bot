import asyncio
import logging

from aiogram import Bot, Dispatcher

from app.config import settings
from app.database import init_db
from app.handlers.admin import router as admin_router
from app.handlers.menu import router as menu_router
from app.middlewares.admin import AdminOnlyMiddleware
from app.services.scheduler import MonitorScheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    await init_db()

    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()
    dp.message.middleware(AdminOnlyMiddleware(settings.ADMIN_ID))
    dp.callback_query.middleware(AdminOnlyMiddleware(settings.ADMIN_ID))
    dp.include_router(menu_router)
    dp.include_router(admin_router)

    scheduler = MonitorScheduler(
        bot,
        alert_chat_id=settings.ALERT_CHAT_ID or settings.ADMIN_ID,
        summary_chat_id=settings.SUMMARY_CHAT_ID or settings.ADMIN_ID,
        check_interval_minutes=settings.DEFAULT_CHECK_INTERVAL,
        summary_interval_hours=settings.SUMMARY_INTERVAL_HOURS,
    )
    scheduler.start()

    logger.info("Starting bot...")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.stop()
        logger.info("Bot stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
