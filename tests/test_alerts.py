import time
import pytest
import alerts


def test_parse_dict_format():
    data = {
        "states": {
            "Київська область": {"alertnow": True},
            "Львівська область": {"alertnow": False},
            "Харківська область": {"alertnow": True},
        }
    }
    result = alerts._parse_alerts(data)
    assert "Київська область" in result
    assert "Харківська область" in result
    assert "Львівська область" not in result


def test_parse_list_format():
    data = [
        {"name": "Сумська область", "alertnow": True},
        {"name": "Одеська область", "alertnow": False},
    ]
    result = alerts._parse_alerts(data)
    assert "Сумська область" in result
    assert "Одеська область" not in result


def test_parse_empty_data():
    assert alerts._parse_alerts({}) == []
    assert alerts._parse_alerts([]) == []


def test_cache_variables_exist():
    assert hasattr(alerts, "_cache_data")
    assert hasattr(alerts, "_cache_ts")
    assert hasattr(alerts, "_CACHE_TTL")
    assert alerts._CACHE_TTL == 60.0


def test_cache_ttl_not_expired(monkeypatch):
    alerts._cache_data = {"states": {}}
    alerts._cache_ts = time.monotonic()

    called = []

    async def fake_get(*a, **kw):
        called.append(1)

    # If cache is fresh, _get_raw_data should return cached value without HTTP call
    import asyncio

    async def run():
        import aiohttp
        monkeypatch.setattr(aiohttp, "ClientSession", lambda: None)
        result = await alerts._get_raw_data()
        return result

    result = asyncio.get_event_loop().run_until_complete(run())
    assert result == {"states": {}}
    assert called == []


def test_short_names_coverage():
    for region in alerts._parse_alerts({
        "states": {r: {"alertnow": True} for r in alerts.SHORT_NAMES}
    }):
        assert region in alerts.SHORT_NAMES
