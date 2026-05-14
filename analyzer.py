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

ЗАДАЧА: перевірити чи справдився вчорашній прогноз обстрілу, на основі нічних повідомлень.

ПРАВИЛА:
- Перерахуй конкретні події: пуски, перехоплення — тип, кількість, регіони.
- НЕ згадуй загиблих, поранених, жертв або деталі влучань.
- Якщо обстрілу не було — скажи прямо і коротко.
- Оціни прогноз чесно: не виправдовуй помилки.
- Висновок — одне речення.
- Мова: тільки українська.

ФОРМАТ — суворо JSON, без markdown:
{
  "confirmed": true | false,
  "accuracy": "ТОЧНИЙ" | "ЧАСТКОВО" | "ХИБНИЙ",
  "what_happened": "<2-3 речення: конкретні факти ночі>",
  "key_events": ["<конкретна подія з джерела>", ...],
  "conclusion": "<одне речення>",
  "sources_used": <число>
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
    data = {
        "date": datetime.now(KYIV_TZ).strftime("%d.%m.%Y"),
        "risk_level": analysis.get("risk_level"),
        "risk_percent": analysis.get("risk_percent"),
        "summary": analysis.get("summary"),
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
        f"Дата перевірки (Київ): {now_kyiv.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"=== ВЧОРАШНІЙ ПРОГНОЗ ===\n"
        f"Рівень загрози: {forecast.get('risk_level')}\n"
        f"Ймовірність обстрілу: {forecast.get('risk_percent')}%\n"
        f"Висновок прогнозу: {forecast.get('summary')}\n\n"
        f"=== ПОВІДОМЛЕННЯ ЗА НІЧ ===\n{messages_block}\n\n"
        "Перевір чи справдився прогноз та надай JSON-звіт."
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
    logger.info("Morning verification done: accuracy=%s", result.get("accuracy"))
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
    accuracy = verification.get("accuracy", "НЕВІДОМО")
    confirmed = verification.get("confirmed", False)
    what_happened = verification.get("what_happened", "")
    events = verification.get("key_events", [])
    conclusion = verification.get("conclusion", "")
    sources = verification.get("sources_used", message_count)

    accuracy_emoji = {"ТОЧНИЙ": "✅", "ЧАСТКОВО": "🔶", "ХИБНИЙ": "❌"}.get(accuracy, "❓")
    forecast_level = forecast.get("risk_level", "?")
    forecast_percent = forecast.get("risk_percent", 0)

    events_text = ""
    if events:
        events_text = "\n\n📋 *Ключові події ночі:*\n" + "\n".join(f"  • {e}" for e in events[:6])

    now_kyiv = datetime.now(KYIV_TZ)
    return (
        f"☀️ *Ранковий розбір прогнозу — {now_kyiv.strftime('%d.%m.%Y')}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{accuracy_emoji} *Прогноз: {accuracy}*\n\n"
        f"🔮 *Вчорашній прогноз:* {forecast_level} ({forecast_percent}%)\n"
        f"{'✔️ Обстріл стався' if confirmed else '✔️ Обстрілу не було'}\n\n"
        f"🌙 *Що відбулось вночі:*\n{what_happened}"
        f"{events_text}\n\n"
        f"💬 *Висновок щодо прогнозу:*\n{conclusion}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📡 Джерела: @DIUkraine · @kpszsu · @war\\_monitor · @bezpechniyregion · @vanek\\_nikolaev\n"
        f"🔍 Проаналізовано повідомлень: {sources}\n"
        f"🕐 Станом на: {now_kyiv.strftime('%H:%M')} за Києвом\n\n"
        f"_Наступний прогноз сьогодні о 23:45._"
    )
