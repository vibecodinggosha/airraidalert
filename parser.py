import asyncio
import logging
from datetime import datetime, timezone, timedelta
import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

CHANNELS = ["DIUkraine", "kpszsu", "war_monitor", "bezpechniyregion", "vanek_nikolaev", "strategic_review"]

KEYWORDS = [
    "obstril", "raket", "udar", "atak", "dron", "shahed",
    "vybuh", "zahoza", "tryvoh", "pusk", "pvo", "perekhoplen",
    "missile", "attack", "drone", "alert", "explosion", "launch",
    "balistych", "krylat", "kindzhal", "kalibr", "iskander",
    "zenitn", "artiler", "naloт", "vidbii",
    "обстріл", "ракет", "удар", "атак", "дрон", "шахед",
    "вибух", "загроза", "тривог", "пуск", "пво", "перехоплен",
    "балістич", "крилат", "кінджал", "калібр", "іскандер",
    "повітряна тривога", "відбій", "налот", "зенітн", "артилер",
    # Reconnaissance drones — critical pre-attack signal near Kyiv/central regions
    "розвідувальн", "розвідник", "орлан", "supercam", "супервам",
    "бпла розвід", "розвідувальний бпла", "розвідувальний дрон",
]


def _is_relevant(text):
    if not text:
        return False
    t = text.lower()
    return any(kw in t for kw in KEYWORDS)


async def fetch_channel(session, channel, since):
    base = "https" + "://t.me/s/"
    url = base + channel
    headers = {"User-Agent": "Mozilla/5.0 (compatible; bot)"}
    results = []
    try:
        async with session.get(
            url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            html = await resp.text()
        soup = BeautifulSoup(html, "html.parser")
        for msg in soup.select(".tgme_widget_message"):
            time_tag = msg.select_one("time")
            text_tag = msg.select_one(".tgme_widget_message_text")
            if not time_tag or not text_tag:
                continue
            dt_str = time_tag.get("datetime", "").replace("Z", "+00:00")
            try:
                dt = datetime.fromisoformat(dt_str)
            except Exception:
                continue
            if dt < since:
                continue
            text = text_tag.get_text(" ", strip=True)
            if not _is_relevant(text):
                continue
            results.append({
                "channel": channel,
                "date": dt.isoformat(),
                "text": text[:2000],
            })
    except Exception as e:
        logger.warning("Failed %s: %s", channel, e)
    return results


async def collect_recent_messages(hours=20):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    all_messages = []
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_channel(session, ch, since) for ch in CHANNELS]
        results = await asyncio.gather(*tasks)
        for msgs in results:
            all_messages.extend(msgs)
    all_messages.sort(key=lambda m: m["date"])
    logger.info("Collected %d messages", len(all_messages))
    return all_messages
