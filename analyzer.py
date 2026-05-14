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

SYSTEM_PROMPT = """Ти — військовий аналітик загроз повітряних ударів по Україні. Пишеш як оперативний аналітик — тільки факти, цифри, конкретика. Нуль води.

ЗАДАЧА: на основі повідомлень з каналів моніторингу скласти нічний аналітичний звіт про загрозу удару.

СТРУКТУРА АНАЛІЗУ:

1. "situation" — поточна ситуація. Витягни з повідомлень конкретні дані:
   - кількість точок пуску БПЛА (якщо є)
   - чи є підготовка на аеродромах (кількість споряджених бортів)
   - чи активні бойові частоти стратегічної авіації
   - час перших пусків або входження на територію (якщо відомо)
   - будь-які інші конкретні оперативні факти
   Якщо даних немає — пиши "даних немає" по кожному пункту.

2. "strike_means" — засоби ураження що виявлені/очікуються:
   - БПЛА: накопичено/задіяно скільки (або "даних немає")
   - Стратегічна авіація: скільки споряджених бортів (або "даних немає")
   - Ракети морського базування: активність (або "даних немає")
   - Балістика: ознаки підготовки (або "даних немає")

3. "pattern" — аналіз патерну:
   - скільки днів минуло з останнього масованого удару (якщо є дані)
   - тенденція: яка зараз фаза (накопичення/активна атака/після удару)
   - на які регіони спрямований удар (якщо є ознаки)

4. "threats" — конкретні загрози що надійшли за останні години (або "нових достовірних не надходило")

5. "forecast_tonight" — ймовірність удару ЦЮ НІЧ:
   - rocket_percent: масований ракетний удар (0-100)
   - drone_mass_percent: масований дроновий удар 50+ одиниць (0-100)
   - combined_percent: комбінована атака (0-100)
   - overall_percent: загальна ймовірність будь-якого удару (0-100)
   - risk_level: "НИЗЬКИЙ" | "СЕРЕДНІЙ" | "ВИСОКИЙ" | "КРИТИЧНИЙ"

6. "forecast_days" — прогноз по наступних 4 ночах, масштаб ймовірності від 0 до 100:
   [
     {"night": "сьогодні-завтра", "percent": X},
     {"night": "+1 ніч", "percent": X},
     {"night": "+2 ночі", "percent": X},
     {"night": "+3 ночі", "percent": X}
   ]

7. "key_signals" — список конкретних фактів що вплинули на оцінку (до 6 пунктів)

ФОРМАТ — суворо JSON, без markdown:
{
  "risk_level": "...",
  "situation": ["<факт 1>", "<факт 2>", ...],
  "strike_means": ["<засіб: дані>", ...],
  "pattern": "<1-2 речення про патерн>",
  "threats": "<факти або 'нових достовірних не надходило'>",
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
  "key_signals": ["...", ...]
}"""

MORNING_SYSTEM_PROMPT = """Ти — військовий аналітик. Пишеш стисло, тільки факти, без води.

ЗАДАЧА: перевірити чи справдився вчорашній прогноз обстрілу, на основі нічних повідомлень.

ПРАВИЛА:
- Перерахуй конкретні події: пуски, удари, перехоплення — тип, кількість, регіони.
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


def _risk_label(p: int) -> str:
    if p >= 80: return "висока"
    if p >= 56: return "підвищена"
    if p >= 31: return "помірна"
    return "низька"


def format_report(analysis: dict, message_count: int) -> str:
    now_kyiv = datetime.now(KYIV_TZ)
    tonight = now_kyiv.strftime("%d.%m")
    tomorrow = (now_kyiv.replace(hour=0, minute=0) + __import__("datetime").timedelta(days=1)).strftime("%d.%m")

    level = analysis.get("risk_level", "НЕВІДОМО")
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
        f"Ворог у будь-який момент може змінити стратегію.\n\n"
        f"📡 @DIUkraine · @kpszsu · @war\\_monitor · @bezpechniyregion · @vanek\\_nikolaev\n"
        f"🔍 {message_count} повідомлень · {now_kyiv.strftime('%H:%M')} Київ"
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
