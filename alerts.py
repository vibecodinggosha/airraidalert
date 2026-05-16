"""
Fetches air raid alert status from ubilling API.
Returns active alerts as messages for analysis.
"""
import asyncio
import logging
from datetime import datetime, timezone

import aiohttp

logger = logging.getLogger(__name__)

ALERTS_URL = "http" + "://ubilling.net.ua/aerialalerts/"

REGION_MAP = {
    "Вінницька область": "Vinnytsia",
    "Волинська область": "Volyn",
    "Дніпропетровська область": "Dnipro",
    "Донецька область": "Donetsk",
    "Житомирська область": "Zhytomyr",
    "Закарпатська область": "Zakarpattia",
    "Запорізька область": "Zaporizhzhia",
    "Івано-Франківська область": "Ivano-Frankivsk",
    "Київська область": "Kyiv region",
    "Кіровоградська область": "Kirovohrad",
    "Луганська область": "Luhansk",
    "Львівська область": "Lviv",
    "Миколаївська область": "Mykolaiv",
    "Одеська область": "Odesa",
    "Полтавська область": "Poltava",
    "Рівненська область": "Rivne",
    "Сумська область": "Sumy",
    "Тернопільська область": "Ternopil",
    "Харківська область": "Kharkiv",
    "Херсонська область": "Kherson",
    "Хмельницька область": "Khmelnytskyi",
    "Черкаська область": "Cherkasy",
    "Чернівецька область": "Chernivtsi",
    "Чернігівська область": "Chernihiv",
    "м. Київ": "Kyiv city",
}


async def fetch_alerts() -> list[dict]:
    """Fetch current air raid alerts. Returns list of message dicts."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                ALERTS_URL,
                headers={"User-Agent": "Mozilla/5.0 (compatible; bot)"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    logger.warning("Alerts API returned status %d", resp.status)
                    return []
                data = await resp.json(content_type=None)

        active = _parse_alerts(data)
        if not active:
            logger.info("Alerts API: no active alerts")
            return []

        now = datetime.now(timezone.utc).isoformat()
        region_list = ", ".join(active)
        text = f"ПОВІТРЯНА ТРИВОГА активна в {len(active)} областях: {region_list}"
        logger.info("Alerts API: %d active alerts", len(active))
        return [{"channel": "alerts_api", "date": now, "text": text}]

    except Exception as e:
        logger.warning("Alerts API fetch failed: %s", e)
        return []


def _parse_alerts(data) -> list[str]:
    """Parse API response, return list of region names with active alerts."""
    active = []

    if isinstance(data, dict):
        # Format: {"source": "...", "cachedat": "...", "states": {"Регіон": {"alertnow": bool}}}
        states = data.get("states", data)
        for region, info in states.items():
            if isinstance(info, dict) and info.get("alertnow"):
                active.append(region)

    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                name = item.get("name") or item.get("region") or item.get("oblast", "")
                if item.get("alertnow") and name:
                    active.append(name)

    return active
