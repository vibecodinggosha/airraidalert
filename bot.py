"""
Main entry point: sets up the aiogram bot, APScheduler, and Telethon parser.
Runs a nightly analytics job at ANALYTICS_HOUR:ANALYTICS_MINUTE Kyiv time.
"""
import asyncio
import logging
import sys

import pytz
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from analyzer import analyze_shelling_risk, format_report
from parser import collect_recent_messages

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

bot = Bot(
    token=config.TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
)
dp = Dispatcher()


async def run_analytics_job() -> None:
    """Collect messages, analyse with Claude, post report to the output channel."""
    logger.info("Starting analytics job")
    try:
        messages = await collect_recent_messages(hours=config.MESSAGES_LOOKBACK_HOURS)
        analysis = await analyze_shelling_risk(messages)
        report = format_report(analysis, len(messages))
        await bot.send_message(
            chat_id=config.OUTPUT_CHANNEL_ID,
            text=report,
            parse_mode=ParseMode.MARKDOWN,
        )
        logger.info("Analytics report posted successfully")
    except Exception:
        logger.exception("Analytics job failed")


def setup_scheduler() -> AsyncIOScheduler:
    kyiv_tz = pytz.timezone(config.KYIV_TZ)
    scheduler = AsyncIOScheduler(timezone=kyiv_tz)
    scheduler.add_job(
        run_analytics_job,
        trigger="cron",
        hour=config.ANALYTICS_HOUR,
        minute=config.ANALYTICS_MINUTE,
        id="nightly_analytics",
        name="Nightly shelling analytics",
    )
    return scheduler


async def main() -> None:
    logger.info(
        "Bot starting. Analytics scheduled at %02d:%02d Kyiv time",
        config.ANALYTICS_HOUR,
        config.ANALYTICS_MINUTE,
    )

    scheduler = setup_scheduler()
    scheduler.start()

    # Run once immediately on startup if --now flag passed
    if "--now" in sys.argv:
        logger.info("--now flag detected, running analytics immediately")
        await run_analytics_job()

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
