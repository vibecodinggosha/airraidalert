"""
Generates Ukraine air raid alert map PNG using the and3rson/raid SVG template.
Downloads the template once, does string substitution, converts SVG -> PNG via cairosvg.
Markers show active alert locations with weapon-type color coding.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime

import aiohttp
import pytz

logger = logging.getLogger(__name__)

SVG_TEMPLATE_CACHE = "ukraine_map.svg.tpl"

_SVG_TPL_URL = "".join(chr(c) for c in [
    104,116,116,112,115,58,47,47,114,97,119,46,103,105,116,104,117,98,117,115,
    101,114,99,111,110,116,101,110,116,46,99,111,109,47,97,110,100,51,114,115,
    111,110,47,114,97,105,100,47,114,101,102,115,47,104,101,97,100,115,47,109,
    97,105,110,47,114,97,105,100,47,97,115,115,101,116,115,47,117,97,46,115,
    118,103,46,116,112,108
])

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

COLOR_ALERT = "#c0392b"
COLOR_CALM = "#5d8a3c"

# Regional capital coordinates (lat, lng)
REGION_CAPITALS: dict[str, tuple[float, float]] = {
    "Вінницька область":        (49.233, 28.468),
    "Волинська область":        (50.747, 25.325),
    "Дніпропетровська область": (48.464, 35.046),
    "Донецька область":         (48.015, 37.805),
    "Житомирська область":      (50.254, 28.658),
    "Закарпатська область":     (48.621, 22.288),
    "Запорізька область":       (47.838, 35.139),
    "Івано-Франківська область":(48.922, 24.711),
    "Київська область":         (50.401, 30.516),
    "Кіровоградська область":   (48.508, 32.262),
    "Луганська область":        (48.574, 39.307),
    "Львівська область":        (49.839, 24.029),
    "Миколаївська область":     (46.975, 32.000),
    "Одеська область":          (46.482, 30.723),
    "Полтавська область":       (49.588, 34.551),
    "Рівненська область":       (50.619, 26.251),
    "Сумська область":          (50.907, 34.797),
    "Тернопільська область":    (49.553, 25.594),
    "Харківська область":       (49.993, 36.230),
    "Херсонська область":       (46.636, 32.617),
    "Хмельницька область":      (49.422, 26.979),
    "Черкаська область":        (49.444, 32.059),
    "Чернівецька область":      (48.291, 25.935),
    "Чернігівська область":     (51.498, 31.289),
    "м. Київ":                  (50.450, 30.523),
}

# Affine transform (lat, lng) → SVG (x, y)
# Calibrated on: Kyiv(495,200), Kharkiv(740,215), Odesa(500,420)
_AX, _BX, _CX = 42.97,  0.905, -862.16
_AY, _BY, _CY = -1.849, -55.5,  3056.43


def _to_svg_xy(lat: float, lng: float) -> tuple[float, float]:
    return _AX * lng + _BX * lat + _CX, _AY * lng + _BY * lat + _CY


# Weapon-type keywords → marker color
_WEAPON_COLORS: list[tuple[str, str]] = [
    ("балістич", "#8e44ad"),   # ballistic — purple
    ("кинджал",  "#8e44ad"),
    ("ракет",    "#e74c3c"),   # cruise missile — red
    ("крилат",   "#e74c3c"),
    ("х-",       "#e74c3c"),
    ("калібр",   "#e74c3c"),
    ("шахед",    "#e67e22"),   # Shahed drone — orange
    ("дрон",     "#e67e22"),
    ("бпла",     "#e67e22"),
    ("літак",    "#f39c12"),   # aircraft — yellow-orange
    ("ту-",      "#f39c12"),
    ("су-",      "#f39c12"),
]

_PLACEHOLDER_RE = re.compile(
    r"\{\{\s*if\s*\(index\s*\.alerts\s*(\d+)\s*\)\s*\}\}"
    r"#[0-9a-fA-F]{6}"
    r"\{\{\s*else\s*\}\}"
    r"#[0-9a-fA-F]{6}"
    r"\{\{\s*end\s*\}\}"
)


def _marker_color(analysis: dict | None) -> str:
    if not analysis:
        return "#e74c3c"
    text = " ".join(analysis.get("strike_means", [])).lower()
    for keyword, color in _WEAPON_COLORS:
        if keyword in text:
            return color
    return "#e74c3c"


def _build_markers(active_regions: list[str], color: str) -> str:
    parts: list[str] = []
    for region in active_regions:
        coords = REGION_CAPITALS.get(region)
        if not coords:
            continue
        x, y = _to_svg_xy(*coords)
        # Three concentric rings for visual pop
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="18" '
            f'fill="none" stroke="{color}" stroke-width="1.5" opacity="0.25"/>'
        )
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="11" '
            f'fill="none" stroke="{color}" stroke-width="2" opacity="0.55"/>'
        )
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5.5" '
            f'fill="{color}" stroke="white" stroke-width="1.5" opacity="0.95"/>'
        )
    return "\n".join(parts)


def _build_legend(active_count: int, color: str, now_str: str) -> str:
    return (
        f'<rect x="14" y="590" width="210" height="68" rx="6" '
        f'fill="white" opacity="0.82"/>'
        f'<circle cx="30" cy="610" r="5" fill="{color}" stroke="white" stroke-width="1.5"/>'
        f'<text x="42" y="614" font-family="Arial,sans-serif" font-size="12" fill="#222">'
        f'Тривога: {active_count} обл.</text>'
        f'<rect x="22" y="626" width="14" height="8" rx="2" fill="{COLOR_ALERT}"/>'
        f'<text x="42" y="634" font-family="Arial,sans-serif" font-size="11" fill="#555">'
        f'активна тривога</text>'
        f'<rect x="22" y="642" width="14" height="8" rx="2" fill="{COLOR_CALM}"/>'
        f'<text x="42" y="650" font-family="Arial,sans-serif" font-size="11" fill="#555">'
        f'без тривоги</text>'
        f'<text x="14" y="670" font-family="Arial,sans-serif" font-size="10" fill="#888">'
        f'{now_str}</text>'
    )


async def ensure_svg_template() -> bool:
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


def generate_map_image(
    active_regions: list[str],
    analysis: dict | None = None,
) -> bytes | None:
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
        return COLOR_ALERT if int(m.group(1)) in active_ids else COLOR_CALM

    svg = _PLACEHOLDER_RE.sub(_replace, tpl)
    svg = re.sub(r'\{\{[^}]+\}\}', '', svg)

    color = _marker_color(analysis)
    kyiv_tz = pytz.timezone("Europe/Kiev")
    now_str = datetime.now(kyiv_tz).strftime("Карта тривог %H:%M %d.%m.%Y")

    overlay = (
        _build_markers(active_regions, color)
        + "\n"
        + _build_legend(len(active_regions), color, now_str)
    )
    svg = svg.replace("</svg>", f"{overlay}\n</svg>")

    try:
        import cairosvg
        return cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=1000, output_height=700)
    except ImportError:
        logger.error("cairosvg not installed")
        return None
    except Exception as e:
        logger.error("SVG render error: %s", e)
        return None
