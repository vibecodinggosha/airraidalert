"""
Generates Ukraine air raid alert map image using matplotlib + GADM GeoJSON.
"""
import io
import json
import logging
import os

import aiohttp

logger = logging.getLogger(__name__)

GEOJSON_CACHE = "ukraine_regions.geojson"

# GADM 4.1 NAME_1 -> Ukrainian API region name
GADM_TO_API = {
    "Cherkasy": "Черкаська область",
    "Chernihiv": "Чернігівська область",
    "Chernivtsi": "Чернівецька область",
    "Dnipropetrovsk": "Дніпропетровська область",
    "Donetsk": "Донецька область",
    "Ivano-Frankivsk": "Івано-Франківська область",
    "Kharkiv": "Харківська область",
    "Kherson": "Херсонська область",
    "Khmelnytskyi": "Хмельницька область",
    "Kiev": "Київська область",
    "Kiev City": "м. Київ",
    "Kirovohrad": "Кіровоградська область",
    "Luhansk": "Луганська область",
    "Lviv": "Львівська область",
    "Mykolaiv": "Миколаївська область",
    "Odessa": "Одеська область",
    "Poltava": "Полтавська область",
    "Rivne": "Рівненська область",
    "Sumy": "Сумська область",
    "Ternopil": "Тернопільська область",
    "Vinnytsia": "Вінницька область",
    "Volyn": "Волинська область",
    "Zakarpattia": "Закарпатська область",
    "Zaporizhia": "Запорізька область",
    "Zhytomyr": "Житомирська область",
}

OCCUPIED = {"Crimea", "Sevastopol"}


async def ensure_geojson() -> bool:
    """Download and cache Ukraine regions GeoJSON (GADM 4.1, run once)."""
    if os.path.exists(GEOJSON_CACHE):
        return True
    # https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_UKR_1.json
    url = "".join(chr(c) for c in [
        104,116,116,112,115,58,47,47,103,101,111,100,97,116,97,46,117,99,100,
        97,118,105,115,46,101,100,117,47,103,97,100,109,47,103,97,100,109,52,
        46,49,47,106,115,111,110,47,103,97,100,109,52,49,95,85,75,82,95,49,
        46,106,115,111,110
    ])
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=120)) as r:
                if r.status == 200:
                    data = await r.read()
                    with open(GEOJSON_CACHE, "wb") as f:
                        f.write(data)
                    logger.info("Downloaded Ukraine GeoJSON (%d bytes)", len(data))
                    return True
                logger.warning("GeoJSON download HTTP %d", r.status)
    except Exception as e:
        logger.error("GeoJSON download failed: %s", e)
    return False


def generate_map_image(active_regions: list[str]) -> bytes | None:
    """Generate PNG map of Ukraine with alert regions highlighted. Returns bytes or None."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        logger.error("matplotlib not installed: pip install matplotlib")
        return None

    if not os.path.exists(GEOJSON_CACHE):
        logger.warning("GeoJSON not cached, map unavailable")
        return None

    try:
        with open(GEOJSON_CACHE, encoding="utf-8") as f:
            geojson = json.load(f)
    except Exception as e:
        logger.error("GeoJSON load error: %s", e)
        return None

    active_set = set(active_regions)

    fig, ax = plt.subplots(figsize=(14, 9), facecolor="#0d1117")
    ax.set_facecolor("#0d1117")
    ax.set_aspect("equal")
    ax.axis("off")

    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        name_en = props.get("NAME_1", props.get("name", ""))
        if name_en in OCCUPIED:
            color = "#4a4a5a"
        elif GADM_TO_API.get(name_en, "") in active_set:
            color = "#e53935"
        else:
            color = "#2e7d32"
        _draw_geom(ax, feature.get("geometry", {}), color)

    count = len(active_regions)
    title = f"Air Raid Alerts: {count} region{'s' if count != 1 else ''}" if count else "No active alerts"
    ax.set_title(title, color="white", fontsize=14, pad=8, fontweight="bold")

    legend = [
        mpatches.Patch(color="#e53935", label="Alert active"),
        mpatches.Patch(color="#2e7d32", label="Clear"),
        mpatches.Patch(color="#4a4a5a", label="Occupied"),
    ]
    ax.legend(handles=legend, loc="lower left", facecolor="#1a1a2e",
              edgecolor="#555", labelcolor="white", fontsize=11)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                facecolor="#0d1117", edgecolor="none")
    plt.close()
    buf.seek(0)
    return buf.getvalue()


def _draw_geom(ax, geom, color):
    t = geom.get("type", "")
    c = geom.get("coordinates", [])
    if t == "Polygon":
        _fill(ax, c[0], color)
    elif t == "MultiPolygon":
        for poly in c:
            _fill(ax, poly[0], color)


def _fill(ax, ring, color):
    try:
        xs = [p[0] for p in ring]
        ys = [p[1] for p in ring]
        ax.fill(xs, ys, color=color, alpha=0.88, linewidth=0)
        ax.plot(xs + [xs[0]], ys + [ys[0]], color="#cccccc", linewidth=0.25, alpha=0.4)
    except Exception:
        pass
