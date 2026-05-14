import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_API_ID = int(os.environ["TELEGRAM_API_ID"])
TELEGRAM_API_HASH = os.environ["TELEGRAM_API_HASH"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OUTPUT_CHANNEL_ID = os.environ["OUTPUT_CHANNEL_ID"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SESSION_NAME = os.getenv("SESSION_NAME", "airraidalert")

ANALYTICS_HOUR = int(os.getenv("ANALYTICS_HOUR", "23"))
ANALYTICS_MINUTE = int(os.getenv("ANALYTICS_MINUTE", "45"))

MORNING_HOUR = int(os.getenv("MORNING_HOUR", "11"))
MORNING_MINUTE = int(os.getenv("MORNING_MINUTE", "0"))

KYIV_TZ = "Europe/Kiev"

SOURCE_CHANNELS = [
    "DIUkraine",
    "kpszsu",
    "war_monitor",
    "bezpechniyregion",
    "vanek_nikolaev",
]

# How many hours back to collect messages for analysis
MESSAGES_LOOKBACK_HOURS = 20
