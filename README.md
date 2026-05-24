# AirRaid Alert Analytics Bot

Telegram-бот для моніторингу загрози авіаударів по Україні. Збирає повідомлення з 33 Telegram-каналів, дедуплікує їх, аналізує через Claude AI та публікує нічну аналітику з картою тривог.

## Можливості

- **Моніторинг 33 каналів** — офіційні (ГУР, ПС ЗСУ), спеціалізовані (радар, авіамоніторинг) та регіональні
- **Дедуплікація** — одна подія від багатьох каналів рахується один раз; перевага надається офіційним джерелам
- **AI-аналіз** — Claude оцінює ймовірність обстрілу на основі відфільтрованих сигналів
- **Карта тривог** — SVG-карта України з маркерами активних регіонів та кольорами за типом зброї
- **Нічна аналітика** — щоночі о 23:45 за Києвом
- **Ранкова верифікація** — о 11:00 порівнює прогноз з реальністю

## Як працює

```
Telegram-канали (33)
        ↓
  Збір повідомлень (aiohttp + t.me/s/)
        ↓
  Дедуплікація та пріоритизація
  (тир 3: офіційні → тир 2: спеціалізовані → тир 1: регіональні)
        ↓
  Аналіз Claude AI (max 120 повідомлень)
        ↓
  Публікація звіту + карта → Telegram-канал
```

## Канали за тирами

**Тир 3 — Офіційні:**
`DIUkraine`, `kpszsu`, `Ukrainian_Intelligence`

**Тир 2 — Спеціалізовані:**
`raketna_neb`, `kudy_letyt`, `avimonitor`, `eRadarrua`, `war_monitor`, `radar_raketaa`, `war_raketaua`, `mon1tor_ua`, `strategic_review`, `strategicontrol`, `vanek_nikolaev`, `bayraktarmedia`, `povitryanatrivogaaa`

**Тир 1 — Регіональні:**
`bezpechniyregion`, `kyiv_golovne`, `chernihiv_golovne`, `sumy_main`, `suspilnesumy`, `zp_golovne`, `odesa_golovne`, `kherson_monitoring`, `poltava_golovne`, `lviv_golovne`, `zahid_golovne_ua`, `rivne_golovne`, `volyn_golovne_ua`, `zhytomyr_glvn`, `vinnytsia_golovne`, `chernivtsi_main`

## Налаштування

### 1. Клонувати репозиторій

```bash
git clone https://github.com/vibecodinggosha/airraidalert.git
cd airraidalert
pip install -r requirements.txt
```

### 2. Отримати credentials

- **Telegram Bot Token** — напишіть [@BotFather](https://t.me/BotFather)
- **Anthropic API Key** — [console.anthropic.com](https://console.anthropic.com)
- **Output Channel ID** — ID вашого Telegram-каналу (з правами адміністратора для бота)

### 3. Створити .env

```bash
cp .env.example .env
```

```env
TELEGRAM_BOT_TOKEN=your_bot_token
OUTPUT_CHANNEL_ID=-100xxxxxxxxxx
ANTHROPIC_API_KEY=sk-ant-...
ANALYTICS_HOUR=23
ANALYTICS_MINUTE=45
MORNING_HOUR=11
MORNING_MINUTE=0
```

> `TELEGRAM_API_ID` та `TELEGRAM_API_HASH` не потрібні — бот збирає повідомлення через публічний веб-інтерфейс t.me/s/.

### 4. Запустити

```bash
python bot.py
```

Для негайного тесту аналітики:

```bash
python bot.py --now
```

## Змінні середовища

| Змінна | Опис | За замовчуванням |
|--------|------|-----------------|
| `TELEGRAM_BOT_TOKEN` | Токен бота від BotFather | — |
| `OUTPUT_CHANNEL_ID` | ID каналу для публікації | — |
| `ANTHROPIC_API_KEY` | Ключ Anthropic API | — |
| `ANALYTICS_HOUR` | Година нічної аналітики (Київ) | `23` |
| `ANALYTICS_MINUTE` | Хвилина нічної аналітики | `45` |
| `MORNING_HOUR` | Година ранкової верифікації | `11` |
| `MORNING_MINUTE` | Хвилина ранкової верифікації | `0` |
| `MESSAGES_LOOKBACK_HOURS` | Глибина збору повідомлень | `20` |
| `SESSION_NAME` | Ім'я сесії | `airraidalert` |

## CI/CD

- **Тести** — запускаються автоматично при push у будь-яку гілку крім `main`
- **Deploy** — при merge у `main` деплоїться на EC2 через self-hosted runner

```bash
pytest tests/ -v
```

## Приклад звіту

```
🛡 Нічна аналітика — 21.05.2026
━━━━━━━━━━━━━━━━━━━━

🟠 Рівень загрози: ВИСОКИЙ
📊 Ймовірність обстрілу: 72%
`███████░░░` 72%

📝 Висновок:
Зафіксовано активність стратегічної авіації над Каспієм,
підвищена активність ППО у східних областях.

📌 Ключові сигнали:
  • Зліт Ту-95МС о 21:30 (підтверджено ГУР)
  • Тривога у Харківській, Сумській обл.
  • Активізація РЕБ на сході

⚠️ Рекомендація:
Тримайте тривожну валізу напоготові.
Знайте розташування найближчого укриття.
```

## Структура проєкту

```
airraidalert/
├── bot.py              # Головний файл, планувальник задач
├── analyzer.py         # AI-аналіз, дедуплікація, препроцесинг
├── parser.py           # Збір повідомлень з Telegram-каналів
├── map_generator.py    # Генерація SVG-карти тривог
├── alerts.py           # API тривог alerts.in.ua (з кешем)
├── db.py               # SQLite зберігання повідомлень
├── config.py           # Конфігурація з .env
├── tests/              # Юніт-тести (pytest)
└── .github/workflows/  # CI/CD пайплайни
```
