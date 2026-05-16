from __future__ import annotations

import asyncio
import logging
import sys

import pytz
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BufferedInputFile
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
import db
from analyzer import (
    analyze_morning_verification,
    analyze_shelling_risk,
    format_morning_report,
    format_report,
    load_forecast,
    save_forecast,
)
from alerts import fetch_alerts, fetch_alerts_map, fetch_active_regions
from map_generator import ensure_svg_template, generate_map_image
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


async def _fetch_alerts_with_regions() -> tuple[list[str], str]:
    """Returns (active_regions, map_text) for use in reports."""
    active_regions = await fetch_active_regions()
    alerts_map = await fetch_alerts_map()
    return active_regions, alerts_map


async def _send_map_photo(active_regions: list[str], analysis: dict | None = None) -> None:
    """Generate and send Ukraine alert map as a photo."""
    try:
        img_bytes = await asyncio.to_thread(generate_map_image, active_regions, analysis)
        if img_bytes:
            photo = BufferedInputFile(img_bytes, filename="alerts_map.png")
            await bot.send_photo(chat_id=config.OUTPUT_CHANNEL_ID, photo=photo)
        else:
            logger.warning("Map image generation returned None")
    except Exception:
        logger.exception("Failed to send map photo")


async def collect_job() -> None:
    """Runs every 30 min — fetches recent messages and alert status, saves to DB."""
    try:
        messages = await collect_recent_messages(hours=2)
        alert_msgs = await fetch_alerts()
        all_msgs = messages + alert_msgs
        saved = db.save_messages(all_msgs)
        total = db.count_messages()
        logger.info("Collector: +%d new messages (total in DB: %d)", saved, total)
    except Exception:
        logger.exception("Message collection job failed")


async def run_analytics_job() -> None:
    """Nightly job: read from DB, analyse, post report, save forecast."""
    logger.info("Starting nightly analytics job")
    try:
        messages = db.get_messages_since(hours=config.MESSAGES_LOOKBACK_HOURS)
        if not messages:
            # Fallback: fetch live if DB is empty
            messages = await collect_recent_messages(hours=config.MESSAGES_LOOKBACK_HOURS)
            db.save_messages(messages)
        analysis = await analyze_shelling_risk(messages)
        save_forecast(analysis)
        active_regions, alerts_map = await _fetch_alerts_with_regions()
        report = format_report(analysis, len(messages), alerts_map)
        await bot.send_message(chat_id=config.OUTPUT_CHANNEL_ID, text=report)
        await _send_map_photo(active_regions, analysis)
        logger.info("Nightly report posted successfully (%d messages)", len(messages))
    except Exception:
        logger.exception("Nightly analytics job failed")


async def run_morning_job() -> None:
    """Morning job: read from DB for last 24h, post daily briefing."""
    logger.info("Starting morning briefing job")
    try:
        forecast = load_forecast()
        if not forecast:
            logger.warning("No forecast found, skipping morning briefing")
            return
        messages = db.get_messages_since(hours=24)
        if not messages:
            messages = await collect_recent_messages(hours=24)
        verification = await analyze_morning_verification(messages, forecast)
        active_regions, alerts_map = await _fetch_alerts_with_regions()
        report = format_morning_report(verification, forecast, len(messages), alerts_map)
        await bot.send_message(chat_id=config.OUTPUT_CHANNEL_ID, text=report)
        await _send_map_photo(active_regions)
        logger.info("Morning briefing posted successfully (%d messages)", len(messages))
    except Exception:
        logger.exception("Morning briefing job failed")


def setup_scheduler() -> AsyncIOScheduler:
    kyiv_tz = pytz.timezone(config.KYIV_TZ)
    scheduler = AsyncIOScheduler(timezone=kyiv_tz)
    scheduler.add_job(
        collect_job,
        trigger="interval",
        minutes=30,
        id="message_collector",
        name="Message collector (every 30 min)",
    )
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
    db.init_db()
    await ensure_svg_template()
    logger.info(
        "Bot starting. Collector every 30min. Nightly at %02d:%02d, Morning at %02d:%02d Kyiv time",
        config.ANALYTICS_HOUR,
        config.ANALYTICS_MINUTE,
        config.MORNING_HOUR,
        config.MORNING_MINUTE,
    )
    scheduler = setup_scheduler()
    scheduler.start()

    # Run initial collection on startup with wider window to populate DB
    try:
        messages = await collect_recent_messages(hours=20)
        saved = db.save_messages(messages)
        logger.info("Initial collection: +%d new messages (total in DB: %d)", saved, db.count_messages())
    except Exception:
        logger.exception("Initial collection failed")

    if "--now" in sys.argv:
        await run_analytics_job()
    if "--morning" in sys.argv:
        await run_morning_job()

    try:
        while True:
            await asyncio.sleep(60)
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
