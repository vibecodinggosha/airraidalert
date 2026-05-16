"""
Generates Ukraine air raid alert map PNG using the and3rson/raid SVG template.
Downloads the template once, does string substitution, converts SVG -> PNG via cairosvg.
"""
import logging
import os
import re

import aiohttp

logger = logging.getLogger(__name__)

SVG_TEMPLATE_CACHE = "ukraine_map.svg.tpl"

# and3rson/raid SVG template (IDs 1-25 match updater.go region list)
# https://raw.githubusercontent.com/and3rson/raid/main/raid/assets/ua.svg.tpl
_SVG_TPL_URL = "".join(chr(c) for c in [
    104,116,116,112,115,58,47,47,114,97,119,46,103,105,116,104,117,98,117,115,
    101,114,99,111,110,116,101,110,116,46,99,111,109,47,97,110,100,51,114,115,
    111,110,47,114,97,105,100,47,114,101,102,115,47,104,101,97,100,115,47,109,
    97,105,110,47,114,97,105,100,47,97,115,115,101,116,115,47,117,97,46,115,
    118,103,46,116,112,108
])

# Ukrainian API region name (ubilling) -> region ID in SVG template
API_TO_ID = {
    "Вінницька область": 1,
    "Волинська область": 2,
    "Дніпропетровська область": 3,
    "Донецька область": 4,
    "Житомирська область": 5,
    "Закарпатська область": 6,
    "Запорізька область": 7,
    "Івано-Франківська область": 8,
    "Київська область": 9,
    "Кіровоградська область": 10,
    "Луганська область": 11,
    "Львівська область": 12,
    "Миколаївська область": 13,
    "Одеська область": 14,
    "Полтавська область": 15,
    "Рівненська область": 16,
    "Сумська область": 17,
    "Тернопільська область": 18,
    "Харківська область": 19,
    "Херсонська область": 20,
    "Хмельницька область": 21,
    "Черкаська область": 22,
    "Чернівецька область": 23,
    "Чернігівська область": 24,
    "м. Київ": 25,
}

COLOR_ALERT = "#dd5522"
COLOR_CALM = "#77aa55"

_PLACEHOLDER_RE = re.compile(
    r"\{\{\s*if\s*\(index\s*\.alerts\s*(\d+)\s*\)\s*\}\}"
    r"#[0-9a-fA-F]{6}"
    r"\{\{\s*else\s*\}\}"
    r"#[0-9a-fA-F]{6}"
    r"\{\{\s*end\s*\}\}"
)


async def ensure_svg_template() -> bool:
    """Download and cache the SVG template from and3rson/raid (run once)."""
    if os.path.exists(SVG_TEMPLATE_CACHE):
        return True
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(_SVG_TPL_URL, timeout=aiohttp.ClientTimeout(total=30)) as r:
                if r.status == 200:
                    data = await r.read()
                    with open(SVG_TEMPLATE_CACHE, "wb") as f:
                        f.write(data)
                    logger.info("Downloaded SVG template (%d bytes)", len(data))
                    return True
                logger.warning("SVG template download HTTP %d", r.status)
    except Exception as e:
        logger.error("SVG template download failed: %s", e)
    return False


def generate_map_image(active_regions: list[str]) -> bytes | None:
    """Render Ukraine alert map PNG. Returns PNG bytes or None on error."""
    if not os.path.exists(SVG_TEMPLATE_CACHE):
        logger.warning("SVG template not cached, map unavailable")
        return None

    try:
        with open(SVG_TEMPLATE_CACHE, encoding="utf-8") as f:
            tpl = f.read()
    except Exception as e:
        logger.error("SVG template read error: %s", e)
        return None

    active_ids = {API_TO_ID[r] for r in active_regions if r in API_TO_ID}

    def _replace(m: re.Match) -> str:
        region_id = int(m.group(1))
        return COLOR_ALERT if region_id in active_ids else COLOR_CALM

    svg = _PLACEHOLDER_RE.sub(_replace, tpl)

    try:
        import cairosvg
        return cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=1000, output_height=670)
    except ImportError:
        logger.error("cairosvg not installed: pip install cairosvg")
        return None
    except Exception as e:
        logger.error("SVG render error: %s", e)
        return None
