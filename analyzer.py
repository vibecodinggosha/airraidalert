"""
Analyzes collected messages with Claude and produces a shelling risk report.
"""
import json
import logging
import os
from datetime import datetime
from typing import Optional

import anthropic
import pytz

import config

logger = logging.getLogger(__name__)

KYIV_TZ = pytz.timezone(config.KYIV_TZ)
FORECAST_FILE = "last_forecast.json"

BACKGROUND_KNOWLEDGE = """
=== БАЗА ЗНАНЬ: ПАТЕРНИ УДАРІВ РФ ПО УКРАЇНІ (2025-2026) ===

ВИЗНАЧЕННЯ МАСОВАНОГО ОБСТРІЛУ (критично для оцінки прогнозу):
- Масований обстріл = 300+ БПЛА АБО 20+ ракет АБО комбінація 10+ ракет + значна кількість БПЛА
- Кілька ракет (5-10) + 100-150 БПЛА = звичайна нічна атака, НЕ масований обстріл
- 141 БПЛА + 5 ракет = середня атака, не масована
- Масована дронова атака = 300+ БПЛА за одну хвилю/добу

ТАКТИКА КОМБІНОВАНИХ АТАК:
- Спочатку хвилі дронів для виснаження ППО → потім ракети по цілях
- Використовують ракети-імітації для перевантаження ППО
- Типова схема: дрони вдень для виснаження + пік вночі без розмазування на кілька днів
- Атаки можуть тривати багато годин, кілька хвиль протягом доби

ТЕНДЕНЦІЯ СПРЕСУВАННЯ АТАК (нова, критична):
- Раніше багатоетапні атаки розтягувались на 4-5 днів, тепер вкладаються в 1 добу
- Атаки відбуваються хвилями в межах однієї доби
- Чергування засобів: дроново-балістична атака → стратегічна авіація + БПЛА

ГЕОГРАФІЯ АТАК (актуальний патерн):
- Захід країни: виключно БПЛА (ракети встигають збивати на довгому маршруті)
- Центр/Північ/Південь/Схід: всі засоби — ракети + БПЛА
- Київщина: БПЛА роблять кола і хаотично літають — експерименти з виснаженням та проходженням ППО, не реальна атака
- Розширилась на захід, удари ближче до кордонів НАТО

ДРОНИ:
- Ройовий формат: сотні дронів за ніч, окремі атаки 500-1000+ БПЛА
- 14.05.2026: 1560 БПЛА за 24 години — рекордний рівень
- Між великими ударами — менші щоденні хвилі для виснаження (~100-200 БПЛА)
- Мета: виснаження ППО + психологічний тиск + навантаження на енергетику

РАКЕТИ:
- Ракети морського базування: лише в кожній 2-3 атаці (не в кожній)
- Більше немає виключно балістично-дронових атак — усі масовані або чисто дронові, або мішані
- Нетипово велика кількість ракет в день накопичення = сигнал наближення масованого удару

ФАЗА НАКОПИЧЕННЯ vs АТАКА:
- Після масованого удару — фаза накопичення 5-9 днів
- Ознаки накопичення: ~200-300 БПЛА накопичено, 4-8 споряджених бортів стратегічної авіації
- Ознаки кінця накопичення: зліт стратегічної авіації, активність бойових частот, споряджені борти

ЦІЛІ:
- Акцент на ОПК (оборонно-промисловий комплекс)
- Енергетика, інфраструктура, логістика одночасно — все в одній атаці
- Точкові енергетичні удари: малі підстанції, локальні розподільчі вузли
- Залізничні вузли, порти, паливо, склади
- Попередження по цілях спрацьовують лише частково

РОЗВІДУВАЛЬНІ ДРОНИ:
- Розвідник поблизу Києва (НЕ в прифронтових зонах) = ознака підготовки удару по столиці
- Розвідники шукають позиції ППО перед атакою
- Це критичний сигнал загрози

ПЕРЕДУДАРНІ СИГНАЛИ (за пріоритетом):
- 50+ БПЛА у повітряному просторі з вектором на Київщину = суттєва ознака масованого удару
- Бойова активність стратегічної авіації + виліт авіагрупи = висока ймовірність масованого ракетного удару (але не 100%)
- Стратегічна авіація готова до кінця доби + накопичення БПЛА достатні = удар у наступні 3 доби
- Балістичні/аеробалістичні загрози ВДЕНЬ — нетипово, але можливо
- Київщина може бути транзитною (БПЛА летять крізь), уточнюється по ходу атаки
- Якщо масований ракетний удар підтверджено вранці — повторні пуски можливі ввечері

ЧАСТОТА:
- РФ намагається перейти до системної кампанії: до 7 масованих атак на місяць
- Після піку завжди приходить спад (за кількома видами озброєння по черзі)
"""

SYSTEM_PROMPT = """Ти — військовий аналітик загроз повітряних ударів по Україні. Пишеш як оперативний аналітик — тільки факти, цифри, конкретика. Нуль води.

Використовуй базу знань нижче для контексту та розуміння патернів. Але головне — аналізуй РЕАЛЬНІ повідомлення що надійшли.

""" + BACKGROUND_KNOWLEDGE + """

ЗАДАЧА: на основі повідомлень з каналів моніторингу скласти нічний аналітичний звіт.

СУВОРО ЗАБОРОНЕНО — НЕ ВКЛЮЧАТИ В ЖОДНЕ ПОЛЕ:
- кількість загиблих, поранених, жертв (навіть якщо є в повідомленнях — ігноруй)
- конкретні адреси, назви об'єктів або локацій влучань
- будь-які деталі про постраждалих цивільних або військових
- слова: загиблий, поранений, жертва, постраждалий, завал, руйнування будівель
Фокус ВИКЛЮЧНО на: засобах ураження, напрямках пусків, роботі ППО, прогнозі.

ФОРМАТ ТЕКСТУ:
- Кожен пункт — максимум 10 слів, тільки суть
- situation: максимум 4 пункти
- strike_means: максимум 4 пункти
- key_signals: максимум 4 пункти
- threats: одне коротке речення
- pattern: одне коротке речення

КРИТИЧНІ СИГНАЛИ (підвищують оцінку різко):
- Розвідувальний дрон поблизу Києва або центральних областей (не фронт) = підготовка удару
- Зліт Ту-95МС / Ту-160 з аеродромів Енгельс, Оленя, Рязань
- Активні бойові частоти стратегічної авіації
- Пуски з кораблів у Каспійському/Чорному морі
- Хвилі дронів, що вже перетнули кордон

СТРУКТУРА JSON-ВІДПОВІДІ (суворо, без markdown):
{
  "risk_level": "НИЗЬКИЙ" | "СЕРЕДНІЙ" | "ВИСОКИЙ" | "КРИТИЧНИЙ",
  "situation": ["<конкретний факт>", ...],
  "strike_means": ["<тип: дані>", ...],
  "pattern": "<фаза: накопичення/активна атака/після удару + скільки днів>",
  "threats": "<конкретні загрози або 'нових достовірних не надходило'>",
  "recon_alert": "<якщо є розвідники поблизу Києва/центру — опиши, інакше null>",
  "forecast_tonight": {
    "rocket_percent": 0,
    "drone_mass_percent": 0,
    "combined_percent": 0,
    "overall_percent": 0,
    "risk_level": "..."
  },
  "forecast_days": [
    {"night": "сьогодні-завтра", "percent": 0},
    {"night": "+1 ніч", "percent": 0},
    {"night": "+2 ночі", "percent": 0},
    {"night": "+3 ночі", "percent": 0}
  ],
  "key_signals": ["<факт>", ...]
}"""

MORNING_SYSTEM_PROMPT = """Ти — військовий аналітик. Пишеш стисло, тільки факти, без води.

ЗАДАЧА: на основі повідомлень за добу скласти ранковий аналітичний брифінг.

ПРАВИЛА:
- НЕ згадуй загиблих, поранених, жертв або деталі влучань.
- Тільки факти: кількість БПЛА/ракет, засоби, напрямки, стан накопичення.
- Кожен пункт — максимум 10 слів.
- Мова: тільки українська.

ВИЗНАЧЕННЯ МАСОВАНОГО ОБСТРІЛУ:
- Масований = 300+ БПЛА АБО 20+ ракет АБО 10+ ракет + велика кількість БПЛА
- 5-10 ракет + 100-150 БПЛА = звичайна атака, НЕ масована

ФОРМАТ — суворо JSON, без markdown:
{
  "daily_update": {"drones": 0, "rockets": 0},
  "attack_features": ["<коротко>", ...],
  "strike_means": ["<тип: дані>", ...],
  "threats": "<одне речення або 'нових достовірних не надходило'>",
  "pattern_update": ["<факт про фазу накопичення>", ...],
  "forecast_days": [
    {"night": "дд-дд.мм", "percent": 0},
    {"night": "дд-дд.мм", "percent": 0},
    {"night": "дд-дд.мм", "percent": 0},
    {"night": "дд-дд.мм", "percent": 0}
  ]
}"""


def _build_messages_block(messages: list[dict]) -> str:
    if not messages:
        return "Повідомлень за вказаний період не знайдено."
    lines = []
    for m in messages:
        dt = datetime.fromisoformat(m["date"])
        kyiv_time = dt.astimezone(KYIV_TZ).strftime("%H:%M")
        lines.append(f"[{m['channel']} | {kyiv_time}] {m['text']}")
    return "\n\n".join(lines)


def save_forecast(analysis: dict) -> None:
    fn = analysis.get("forecast_tonight", {})
    data = {
        "date": datetime.now(KYIV_TZ).strftime("%d.%m.%Y"),
        "risk_level": _overall_risk_level(fn.get("overall_percent", 0)),
        "risk_percent": fn.get("overall_percent", 0),
        "summary": analysis.get("threats", ""),
    }
    with open(FORECAST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def load_forecast() -> Optional[dict]:
    if not os.path.exists(FORECAST_FILE):
        return None
    with open(FORECAST_FILE, encoding="utf-8") as f:
        return json.load(f)


async def analyze_shelling_risk(messages: list[dict]) -> dict:
    client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
    now_kyiv = datetime.now(KYIV_TZ)
    messages_block = _build_messages_block(messages)
    user_content = (
        f"Дата та час аналізу (Київ): {now_kyiv.strftime('%d.%m.%Y %H:%M')}\n"
        f"Кількість зібраних повідомлень: {len(messages)}\n\n"
        f"=== ПОВІДОМЛЕННЯ З КАНАЛІВ ===\n{messages_block}\n\n"
        "Проведи аналіз та надай структурований JSON-звіт."
    )
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    result = json.loads(raw.strip())
    result = _filter_casualties(result)
    logger.info("Analysis done: risk=%s (%s%%)", result.get("risk_level"), result.get("risk_percent"))
    return result


async def analyze_morning_verification(messages: list[dict], forecast: dict) -> dict:
    client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
    now_kyiv = datetime.now(KYIV_TZ)
    messages_block = _build_messages_block(messages)
    user_content = (
        f"Дата брифінгу (Київ): {now_kyiv.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"=== ПОВІДОМЛЕННЯ ЗА ДОБУ ===\n{messages_block}\n\n"
        "Склади ранковий аналітичний брифінг у форматі JSON."
    )
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=MORNING_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    result = json.loads(raw.strip())
    result = _filter_casualties(result)
    logger.info("Morning briefing done")
    return result


_CASUALTY_WORDS = [
    "загибл", "поранен", "жертв", "постраждал", "завал",
    "загиблий", "поранений", "жертва", "вбит", "смерт",
]


def _filter_casualties(analysis: dict) -> dict:
    def is_clean(text: str) -> bool:
        t = text.lower()
        return not any(w in t for w in _CASUALTY_WORDS)

    for field in ("situation", "strike_means", "key_signals"):
        if isinstance(analysis.get(field), list):
            analysis[field] = [item for item in analysis[field] if is_clean(item)]

    for field in ("threats", "pattern"):
        if isinstance(analysis.get(field), str):
            val = analysis[field]
            for w in _CASUALTY_WORDS:
                # Remove sentences containing casualty words
                sentences = val.split(".")
                sentences = [s for s in sentences if w not in s.lower()]
                val = ".".join(sentences)
            analysis[field] = val.strip()

    return analysis


def _overall_risk_level(p: int) -> str:
    if p >= 70: return "КРИТИЧНИЙ"
    if p >= 50: return "ВИСОКИЙ"
    if p >= 30: return "СЕРЕДНІЙ"
    return "НИЗЬКИЙ"


def _risk_label(p: int) -> str:
    if p >= 80: return "висока"
    if p >= 56: return "підвищена"
    if p >= 31: return "помірна"
    return "низька"


def format_report(analysis: dict, message_count: int) -> str:
    now_kyiv = datetime.now(KYIV_TZ)
    tonight = now_kyiv.strftime("%d.%m")
    tomorrow = (now_kyiv.replace(hour=0, minute=0) + __import__("datetime").timedelta(days=1)).strftime("%d.%m")

    situation = analysis.get("situation", [])
    strike_means = analysis.get("strike_means", [])
    pattern = analysis.get("pattern", "")
    threats = analysis.get("threats", "")
    fn = analysis.get("forecast_tonight", {})
    forecast_days = analysis.get("forecast_days", [])
    signals = analysis.get("key_signals", [])

    rocket_p = fn.get("rocket_percent", 0)
    drone_p = fn.get("drone_mass_percent", 0)
    combined_p = fn.get("combined_percent", 0)
    overall_p = fn.get("overall_percent", 0)

    # Derive level from overall_percent so it's always consistent
    level = _overall_risk_level(overall_p)
    level_emoji = {"НИЗЬКИЙ": "🟢", "СЕРЕДНІЙ": "🟡", "ВИСОКИЙ": "🟠", "КРИТИЧНИЙ": "🔴"}.get(level, "⚪")

    sit_text = "\n".join(f"• {s}" for s in situation) if situation else "• даних недостатньо"
    means_text = "\n".join(f"• {s}" for s in strike_means) if strike_means else "• даних немає"

    days_text = ""
    if forecast_days:
        days_text = "*Імовірність масованої атаки по ночах:*\n"
        days_text += "\n".join(f"• {d.get('night', '?')} — {d.get('percent', 0)}%" for d in forecast_days)

    signals_text = ""
    if signals:
        signals_text = "*Ключові сигнали:*\n" + "\n".join(f"• {s}" for s in signals[:6])

    return (
        f"✈️ *Ніч {tonight}-{tomorrow}*\n\n"
        f"*На цей момент*\n{sit_text}\n\n"
        f"*Засоби ураження*\n{means_text}\n\n"
        f"*Загрози*\n{threats}\n\n"
        f"*Оновлення патерну*\n{pattern}\n\n"
        f"{signals_text}\n\n"
        f"*Виходячи з наявної інформації*\n"
        f"Вірогідність масованого ракетного удару — {_risk_label(rocket_p)} ({rocket_p}%)\n"
        f"Вірогідність масованого дронового удару — {_risk_label(drone_p)} ({drone_p}%)\n"
        f"Вірогідність комбінованої атаки — {_risk_label(combined_p)} ({combined_p}%)\n"
        f"{level_emoji} Загальна загроза цієї ночі — *{level} ({overall_p}%)*\n\n"
        f"{days_text}\n\n"
        f"——\n"
        f"*Застереження*\n"
        f"Висновки зроблені аналітично на базі відкритих даних. "
        f"Ворог у будь-який момент може змінити стратегію."
    )


def format_morning_report(verification: dict, forecast: dict, message_count: int) -> str:
    now_kyiv = datetime.now(KYIV_TZ)
    daily = verification.get("daily_update", {})
    drones = daily.get("drones", "?")
    rockets = daily.get("rockets", "?")
    features = verification.get("attack_features", [])
    means = verification.get("strike_means", [])
    threats = verification.get("threats", "нових достовірних не надходило")
    pattern = verification.get("pattern_update", [])
    forecast_days = verification.get("forecast_days", [])

    features_text = "\n".join(f"• {s}" for s in features) if features else "• даних немає"
    means_text = "\n".join(f"• {s}" for s in means) if means else "• даних немає"
    pattern_text = "\n".join(f"• {s}" for s in pattern) if pattern else "• даних немає"
    days_text = "\n".join(f"• {d.get('night', '?')} — {d.get('percent', 0)}%" for d in forecast_days)

    return (
        f"*Інформація на {now_kyiv.strftime('%d.%m')}*\n\n"
        f"*Оновлення за добу*\n"
        f"• застосовано {drones} БПЛА\n"
        f"• застосовано {rockets} ракет\n\n"
        f"*Особливості атаки*\n{features_text}\n\n"
        f"*Засоби ураження*\n{means_text}\n\n"
        f"*Загрози*\n• {threats}\n\n"
        f"*Оновлення патерну*\n{pattern_text}\n\n"
        f"*Ймовірності масованої атаки по днях*\n{days_text}\n\n"
        f"——\n"
        f"*Застереження*\n"
        f"Висновки зроблені виключно аналітично на базі існуючих даних. "
        f"100 щоденних шахедів також можуть нести загрозу. "
        f"Ворог в будь-який момент може змінити стратегію."
    )
