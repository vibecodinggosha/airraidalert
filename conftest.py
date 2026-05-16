import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

# Stub config so tests don't need real env vars
import types
config = types.ModuleType("config")
config.ANTHROPIC_API_KEY = "test-key"
config.KYIV_TZ = "Europe/Kiev"
config.MESSAGES_LOOKBACK_HOURS = 20
config.OUTPUT_CHANNEL_ID = "123"
sys.modules["config"] = config
