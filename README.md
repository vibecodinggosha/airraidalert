# AirRaid Alert Analytics Bot

Бот збирає повідомлення з Telegram-каналів моніторингу загроз, аналізує їх через Claude AI та щоночі публікує аналітику з оцінкою ймовірності обстрілу.

## Джерела

- [@DIUkraine](https://t.me/DIUkraine) — Головне управління розвідки
- [@kpszsu](https://t.me/kpszsu) — Командування Повітряних Сил ЗСУ
- [@war_monitor](https://t.me/war_monitor) — моніторинг бойових дій

## Як працює

1. О `ANALYTICS_HOUR:ANALYTICS_MINUTE` за Києвом бот збирає повідомлення за останні 20 годин
2. Фільтрує лише релевантні (ракети, дрони, обстріли, пуски, тривоги)
3. Відправляє їх до Claude для аналізу
4. Публікує структурований звіт з рівнем загрози та рекомендацією

## Налаштування

### 1. Отримати Telegram API credentials

Зайдіть на [my.telegram.org/apps](https://my.telegram.org/apps), створіть застосунок — отримаєте `API_ID` та `API_HASH`.

### 2. Створити бота

Напишіть [@BotFather](https://t.me/BotFather), створіть бота — отримаєте `BOT_TOKEN`.
Додайте бота як адміністратора у ваш канал.

### 3. Налаштувати .env

```bash
cp .env.example .env
# Заповніть всі змінні у .env
```

### 4. Авторизувати Telethon (перший запуск)

Telethon потребує інтерактивної авторизації через номер телефону:

```bash
pip install -r requirements.txt
mkdir sessions
python -c "
from telethon.sync import TelegramClient
import config
with TelegramClient('sessions/airraidalert', config.TELEGRAM_API_ID, config.TELEGRAM_API_HASH) as c:
    c.start()
    print('Authorized!')
"
```

### 5. Запустити

**Локально:**
```bash
python bot.py
# або для негайного тесту:
python bot.py --now
```

**Docker:**
```bash
docker-compose up -d
```

## Змінні середовища

| Змінна | Опис |
|--------|------|
| `TELEGRAM_API_ID` | API ID з my.telegram.org |
| `TELEGRAM_API_HASH` | API Hash з my.telegram.org |
| `TELEGRAM_BOT_TOKEN` | Токен бота від BotFather |
| `OUTPUT_CHANNEL_ID` | ID або username каналу для публікації |
| `ANTHROPIC_API_KEY` | Ключ Anthropic API |
| `ANALYTICS_HOUR` | Година публікації (Київ, за замовчуванням: 23) |
| `ANALYTICS_MINUTE` | Хвилина публікації (за замовчуванням: 45) |

## Приклад звіту

```
🛡 Нічна аналітика обстрілів — 13.05.2026
━━━━━━━━━━━━━━━━━━━━

🟠 Рівень загрози: ВИСОКИЙ
📊 Ймовірність обстрілу: 78%
`████████░░` 78%

📝 Висновок:
Зафіксовано зльоти стратегічних бомбардувальників з аеродрому Енгельс...

📌 Ключові сигнали:
  • Зліт 6 Ту-95МС о 20:14
  • Активізація ППО в Харківській обл.

⚠️ Рекомендація:
Тримайте тривожну валізу напоготові, знайте розташування найближчого укриття.
```
