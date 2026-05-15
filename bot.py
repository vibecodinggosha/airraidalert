import asyncio
import logging
import sys

import pytz
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from analyzer import (
    analyze_morning_verification,
    analyze_shelling_risk,
    format_morning_report,
    format_report,
    load_forecast,
    save_forecast,
)
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
    """Nightly job: collect messages, analyse, post report, save forecast."""
    logger.info("Starting nightly analytics job")
    try:
        messages = await collect_recent_messages(hours=config.MESSAGES_LOOKBACK_HOURS)
        analysis = await analyze_shelling_risk(messages)
        save_forecast(analysis)
        report = format_report(analysis, len(messages))
        await bot.send_message(chat_id=config.OUTPUT_CHANNEL_ID, text=report)
        logger.info("Nightly report posted successfully")
    except Exception:
        logger.exception("Nightly analytics job failed")


async def run_morning_job() -> None:
    """Morning job: verify if last night's forecast was correct."""
    logger.info("Starting morning verification job")
    try:
        forecast = load_forecast()
        if not forecast:
            logger.warning("No forecast found, skipping morning verification")
            return
        # Collect last 24 hours for morning briefing
        messages = await collect_recent_messages(hours=24)
        verification = await analyze_morning_verification(messages, forecast)
        report = format_morning_report(verification, forecast, len(messages))
        await bot.send_message(chat_id=config.OUTPUT_CHANNEL_ID, text=report)
        logger.info("Morning verification posted successfully")
    except Exception:
        logger.exception("Morning verification job failed")


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
    scheduler.add_job(
        run_morning_job,
        trigger="cron",
        hour=config.MORNING_HOUR,
        minute=config.MORNING_MINUTE,
        id="morning_verification",
        name="Morning forecast verification",
    )
    return scheduler


async def main() -> None:
    logger.info(
        "Bot starting. Nightly at %02d:%02d, Morning check at %02d:%02d Kyiv time",
        config.ANALYTICS_HOUR,
        config.ANALYTICS_MINUTE,
        config.MORNING_HOUR,
        config.MORNING_MINUTE,
    )
    scheduler = setup_scheduler()
    scheduler.start()

    if "--now" in sys.argv:
        await run_analytics_job()
    if "--morning" in sys.argv:
        await run_morning_job()

    try:
        # No polling needed — bot only sends scheduled messages
        while True:
            await asyncio.sleep(60)
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
