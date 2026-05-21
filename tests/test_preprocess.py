import pytest
from datetime import datetime, timezone, timedelta
from analyzer import preprocess_messages, _fingerprint, _CHANNEL_TIER


def _msg(channel="test", minutes_ago=0, text="тривога ракет удар бпла шахед дрон"):
    dt = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return {"channel": channel, "date": dt.isoformat(), "text": text}


def test_fingerprint_extracts_keywords():
    fp = _fingerprint("Ракетна загроза, збито дрон над Харківщиною")
    assert "ракет" in fp
    assert "збито" in fp
    assert "харків" in fp


def test_fingerprint_empty():
    assert _fingerprint("Сьогодні гарна погода") == frozenset()


def test_dedup_removes_same_event_different_channels():
    msgs = [
        _msg("kpszsu",   minutes_ago=5,  text="збито шахед дрон бпла тривог удар над Харковом"),
        _msg("war_monitor", minutes_ago=3, text="збито шахед дрон бпла тривог удар над Харковом"),
        _msg("kyiv_golovne", minutes_ago=1, text="збито шахед дрон бпла тривог удар над Харковом"),
    ]
    result = preprocess_messages(msgs)
    assert len(result) == 1


def test_dedup_keeps_higher_tier():
    msgs = [
        _msg("kyiv_golovne", minutes_ago=5,  text="ракет дрон бпла шахед тривог удар атак збито"),
        _msg("kpszsu",       minutes_ago=3,  text="ракет дрон бпла шахед тривог удар атак збито"),
    ]
    result = preprocess_messages(msgs)
    assert len(result) == 1
    assert result[0]["channel"] == "kpszsu"


def test_dedup_keeps_different_events():
    msgs = [
        _msg("kpszsu",    minutes_ago=60, text="ракет дрон шахед тривог удар бпла збито Харків"),
        _msg("war_monitor", minutes_ago=5, text="ракет дрон шахед тривог удар бпла збито Київ"),
    ]
    result = preprocess_messages(msgs)
    assert len(result) == 2


def test_dedup_outside_window_not_deduped():
    msgs = [
        _msg("kpszsu",    minutes_ago=30, text="ракет дрон шахед тривог удар бпла перехоп збито"),
        _msg("war_monitor", minutes_ago=5,  text="ракет дрон шахед тривог удар бпла перехоп збито"),
    ]
    result = preprocess_messages(msgs)
    assert len(result) == 2


def test_cap_at_120_messages():
    msgs = [_msg("kyiv_golovne", minutes_ago=i, text=f"повідомлення {i}") for i in range(200)]
    result = preprocess_messages(msgs)
    assert len(result) <= 120


def test_high_tier_channels_preferred_when_capped():
    regional = [_msg("kyiv_golovne", minutes_ago=i, text=f"текст {i}") for i in range(100)]
    official = [_msg("kpszsu", minutes_ago=i+100, text=f"офіційне {i}") for i in range(100)]
    result = preprocess_messages(regional + official)
    channels = [m["channel"] for m in result]
    assert channels.count("kpszsu") > channels.count("kyiv_golovne")


def test_chronological_order_preserved():
    msgs = [_msg("kpszsu", minutes_ago=i, text=f"текст {i} різний без дублікатів номер {i}") for i in range(10)]
    result = preprocess_messages(msgs)
    dates = [m["date"] for m in result]
    assert dates == sorted(dates)


def test_empty_input():
    assert preprocess_messages([]) == []


def test_channel_tiers():
    assert _CHANNEL_TIER["kpszsu"] == 3
    assert _CHANNEL_TIER["DIUkraine"] == 3
    assert _CHANNEL_TIER["war_monitor"] == 2
    assert _CHANNEL_TIER.get("kyiv_golovne", 1) == 1
