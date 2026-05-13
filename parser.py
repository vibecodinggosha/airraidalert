"""
Parses recent messages from Telegram channels using Telethon.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from telethon import TelegramClient
from telethon.tl.types import Message

import config

logger = logging.getLogger(__name__)


def _is_shelling_related(text: str) -> bool:
    """Quick pre-filter: keep only messages related to air threats or shelling."""
    if not text:
        return False
    keywords = [
        "обстріл", "ракет", "удар", "атак", "дрон", "шахед", "shahed",
        "вибух", "загроза", "тривог", "пуск", "пво", "перехоплен",
        "missile", "attack", "drone", "alert", "explosion", "launch",
        "балістич", "крилат", "кінджал", "калібр", "іскандер",
        "повітряна тривога", "відбій", "налот", "бомбардув",
        "зенітн", "мінометн", "артилер", "обстрілян",
    ]
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


async def fetch_channel_messages(
    client: TelegramClient,
    channel: str,
    since: datetime,
    limit: int = 200,
) -> list[dict]:
    """Fetch messages from a single channel since the given UTC datetime."""
    results = []
    try:
        entity = await client.get_entity(channel)
        async for msg in client.iter_messages(entity, limit=limit):
            if not isinstance(msg, Message):
                continue
            if msg.date < since:
                break
            text = msg.text or msg.message or ""
            if not _is_shelling_related(text):
                continue
            results.append({
                "channel": channel,
                "id": msg.id,
                "date": msg.date.isoformat(),
                "text": text[:2000],
            })
    except Exception as exc:
        logger.warning("Failed to fetch from %s: %s", channel, exc)
    return results


async def collect_recent_messages(hours: int = 20) -> list[dict]:
    """
    Connect to Telegram, scrape SOURCE_CHANNELS for the last `hours` hours,
    return filtered list of shelling-related messages sorted oldest-first.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    client = TelegramClient(
        config.SESSION_NAME,
        config.TELEGRAM_API_ID,
        config.TELEGRAM_API_HASH,
    )
    all_messages: list[dict] = []
    try:
        await client.start()
        tasks = [
            fetch_channel_messages(client, ch, since)
            for ch in config.SOURCE_CHANNELS
        ]
        results = await asyncio.gather(*tasks)
        for msgs in results:
            all_messages.extend(msgs)
    finally:
        await client.disconnect()

    all_messages.sort(key=lambda m: m["date"])
    logger.info("Collected %d shelling-related messages", len(all_messages))
    return all_messages
