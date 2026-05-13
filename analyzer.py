"""
Analyzes collected messages with Claude and produces a shelling risk report.
"""
import json
import logging
from datetime import datetime

import anthropic
import pytz

import config

logger = logging.getLogger(__name__)

KYIV_TZ = pytz.timezone(config.KYIV_TZ)

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


def _build_messages_block(messages: list[dict]) -> str:
    if not messages:
        return "Повідомлень за вказаний період не знайдено."
    lines = []
    for m in messages:
        dt = datetime.fromisoformat(m["date"])
        kyiv_time = dt.astimezone(KYIV_TZ).strftime("%H:%M")
        lines.append(f"[{m['channel']} | {kyiv_time}] {m['text']}")
    return "\n\n".join(lines)


async def analyze_shelling_risk(messages: list[dict]) -> dict:
    """
    Send messages to Claude and get back a structured risk assessment.
    Returns a dict with risk_level, risk_percent, summary, key_signals,
    recommendation, sources_used.
    """
    client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)

    now_kyiv = datetime.now(KYIV_TZ)
    date_str = now_kyiv.strftime("%d.%m.%Y %H:%M")

    messages_block = _build_messages_block(messages)
    user_content = (
        f"Дата та час аналізу (Київ): {date_str}\n"
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
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    result = json.loads(raw)
    logger.info(
        "Analysis done: risk=%s (%s%%)",
        result.get("risk_level"),
        result.get("risk_percent"),
    )
    return result


def format_report(analysis: dict, message_count: int) -> str:
    """Format the Claude analysis into a Telegram-ready message."""
    level = analysis.get("risk_level", "НЕВІДОМО")
    percent = analysis.get("risk_percent", 0)
    summary = analysis.get("summary", "")
    signals = analysis.get("key_signals", [])
    recommendation = analysis.get("recommendation", "")
    sources = analysis.get("sources_used", message_count)

    level_emoji = {
        "НИЗЬКИЙ": "🟢",
        "СЕРЕДНІЙ": "🟡",
        "ВИСОКИЙ": "🟠",
        "КРИТИЧНИЙ": "🔴",
    }.get(level, "⚪")

    bar_filled = round(percent / 10)
    bar = "█" * bar_filled + "░" * (10 - bar_filled)

    signals_text = ""
    if signals:
        signals_text = "\n".join(f"  • {s}" for s in signals[:6])
        signals_text = f"\n\n📌 *Ключові сигнали:*\n{signals_text}"

    now_kyiv = datetime.now(KYIV_TZ)
    date_str = now_kyiv.strftime("%d.%m.%Y")

    report = (
        f"🛡 *Нічна аналітика обстрілів — {date_str}*\n"
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
        f"🕐 Аналіз станом на: {now_kyiv.strftime('%H:%M')} за Києвом\n\n"
        f"_Аналітика генерується автоматично на основі відкритих джерел. "
        f"Слідкуйте за офіційними повідомленнями ДСНС та місцевої влади._"
    )
    return report
