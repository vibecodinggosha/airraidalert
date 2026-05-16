"""
Fetches air raid alert status from ubilling API.
Returns active alerts as messages for analysis.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import aiohttp
import pytz

logger = logging.getLogger(__name__)

ALERTS_URL = "http" + "://ubilling.net.ua/aerialalerts/"

_cache_data: dict | None = None
_cache_ts: float = 0.0
_CACHE_TTL = 60.0

SHORT_NAMES = {
    "Вінницька область": "Вінниця",
    "Волинська область": "Волинь",
    "Дніпропетровська область": "Дніпро",
    "Донецька область": "Донецьк",
    "Житомирська область": "Житомир",
    "Закарпатська область": "Закарпаття",
    "Запорізька область": "Запоріжжя",
    "Івано-Франківська область": "Івано-Фр.",
    "Київська область": "Київська",
    "Кіровоградська область": "Кіровоград",
    "Луганська область": "Луганськ",
    "Львівська область": "Львів",
    "Миколаївська область": "Миколаїв",
    "Одеська область": "Одеса",
    "Полтавська область": "Полтава",
    "Рівненська область": "Рівне",
    "Сумська область": "Суми",
    "Тернопільська область": "Тернопіль",
    "Харківська область": "Харків",
    "Херсонська область": "Херсон",
    "Хмельницька область": "Хмельницький",
    "Черкаська область": "Черкаси",
    "Чернівецька область": "Чернівці",
    "Чернігівська область": "Чернігів",
    "м. Київ": "Київ",
}


async def _get_raw_data() -> dict | None:
    global _cache_data, _cache_ts
    if time.monotonic() - _cache_ts < _CACHE_TTL:
        return _cache_data
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                ALERTS_URL,
                headers={"User-Agent": "Mozilla/5.0 (compatible; bot)"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    logger.warning("Alerts API returned status %d", resp.status)
                    return None
                _cache_data = await resp.json(content_type=None)
                _cache_ts = time.monotonic()
                return _cache_data
    except Exception as e:
        logger.warning("Alerts API fetch failed: %s", e)
        return None


def _parse_alerts(data) -> list[str]:
    """Parse API response, return list of region names with active alerts."""
    active = []
    if isinstance(data, dict):
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


async def fetch_alerts() -> list[dict]:
    """Fetch current air raid alerts. Returns list of message dicts for DB."""
    data = await _get_raw_data()
    if not data:
        return []
    active = _parse_alerts(data)
    if not active:
        logger.info("Alerts API: no active alerts")
        return []
    now = datetime.now(timezone.utc).isoformat()
    region_list = ", ".join(active)
    text = f"ПОВІТРЯНА ТРИВОГА активна в {len(active)} областях: {region_list}"
    logger.info("Alerts API: %d active alerts", len(active))
    return [{"channel": "alerts_api", "date": now, "text": text}]


async def fetch_alerts_map() -> str:
    """Returns formatted alert map string for inclusion in reports."""
    kyiv_tz = pytz.timezone("Europe/Kiev")
    now_str = datetime.now(kyiv_tz).strftime("%H:%M")

    data = await _get_raw_data()
    if not data:
        return f"🗺 *Карта тривог ({now_str})* — дані недоступні"

    active = _parse_alerts(data)

    if not active:
        return f"🗺 *Карта тривог ({now_str})*\n✅ Тривог немає"

    short = [SHORT_NAMES.get(r, r) for r in active]
    regions_str = " · ".join(short)
    return f"🗺 *Карта тривог ({now_str})* — {len(active)} обл.\n🔴 {regions_str}"


async def fetch_active_regions() -> list[str]:
    """Returns list of region names (Ukrainian) with active alerts."""
    data = await _get_raw_data()
    if not data:
        return []
    return _parse_alerts(data)
