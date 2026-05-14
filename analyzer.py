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

SYSTEM_PROMPT = """Ти — аналітик з безпеки, що спеціалізується на аналізі повітряних загроз та обстрілів в Україні.
Твоє завдання: на основі повідомлень з моніторингових Telegram-каналів скласти аналітичний звіт про ймовірність нічного обстрілу.

Правила аналізу:
1. Оцінюй реальну оперативну обстановку — активність ворога, пуски, переміщення, патерни атак.
2. Враховуй час доби, день тижня, попередні патерни атак.
3. Якщо є повідомлення про пуски, групи дронів або ракет — це критичні сигнали.
4. Якщо активність низька і немає ознак підготовки — знижуй оцінку ризику.
5. Відповідай виключно українською мовою.
6. Будь конкретним — посилайся на факти з повідомлень.

Формат відповіді — суворо JSON:
{
  "risk_level": "НИЗЬКИЙ" | "СЕРЕДНІЙ" | "ВИСОКИЙ" | "КРИТИЧНИЙ",
  "risk_percent": <ціле число 0-100>,
  "summary": "<3-5 речень: ключові факти та висновок>",
  "key_signals": ["<факт 1>", "<факт 2>", ...],
  "recommendation": "<порада для цивільного населення>",
  "sources_used": <кількість повідомлень що вплинули на аналіз>
}"""

MORNING_SYSTEM_PROMPT = """Ти — аналітик з безпеки, що спеціалізується на аналізі повітряних загроз та обстрілів в Україні.
Твоє завдання: перевірити чи справдився вчорашній нічний прогноз обстрілу, на основі повідомлень що надійшли вночі.

Правила:
1. Порівняй прогноз з реальними подіями — чи були обстріли, пуски, вибухи?
2. Оціни точність прогнозу об'єктивно.
3. Відповідай виключно українською мовою.
4. Будь конкретним — посилайся на факти з повідомлень.

Формат відповіді — суворо JSON:
{
  "confirmed": true | false,
  "accuracy": "ТОЧНИЙ" | "ЧАСТКОВО" | "ХИБНИЙ",
  "what_happened": "<3-5 речень: що реально відбулось вночі>",
  "key_events": ["<подія 1>", "<подія 2>", ...],
  "conclusion": "<висновок щодо якості прогнозу>",
  "sources_used": <кількість повідомлень>
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


def format_report(analysis: dict, message_count: int) -> str:
    level = analysis.get("risk_level", "НЕВІДОМО")
    percent = analysis.get("risk_percent", 0)
    summary = analysis.get("summary", "")
    signals = analysis.get("key_signals", [])
    recommendation = analysis.get("recommendation", "")
    sources = analysis.get("sources_used", message_count)

    level_emoji = {
        "НИЗЬКИЙ": "🟢", "СЕРЕДНІЙ": "🟡", "ВИСОКИЙ": "🟠", "КРИТИЧНИЙ": "🔴",
    }.get(level, "⚪")

    bar = "█" * round(percent / 10) + "░" * (10 - round(percent / 10))
    signals_text = ""
    if signals:
        signals_text = "\n\n📌 *Ключові сигнали:*\n" + "\n".join(f"  • {s}" for s in signals[:6])

    now_kyiv = datetime.now(KYIV_TZ)
    return (
        f"🛡 *Нічна аналітика обстрілів — {now_kyiv.strftime('%d.%m.%Y')}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{level_emoji} *Рівень загрози: {level}*\n"
        f"📊 Ймовірність обстрілу: *{percent}%*\n"
        f"`{bar}` {percent}%\n\n"
        f"📝 *Висновок:*\n{summary}"
        f"{signals_text}\n\n"
        f"⚠️ *Рекомендація:*\n{recommendation}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📡 Джерела: @DIUkraine · @kpszsu · @war\\_monitor\n"
        f"🔍 Проаналізовано повідомлень: {sources}\n"
        f"🕐 Станом на: {now_kyiv.strftime('%H:%M')} за Києвом\n\n"
        f"_Аналітика генерується автоматично на основі відкритих джерел. "
        f"Слідкуйте за офіційними повідомленнями ДСНС та місцевої влади._"
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
        f"📡 Джерела: @DIUkraine · @kpszsu · @war\\_monitor\n"
        f"🔍 Проаналізовано повідомлень: {sources}\n"
        f"🕐 Станом на: {now_kyiv.strftime('%H:%M')} за Києвом\n\n"
        f"_Наступний прогноз сьогодні о 23:45._"
    )
