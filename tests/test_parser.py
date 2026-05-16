import pytest
from parser import _is_relevant, CHANNELS, KEYWORDS


def test_relevant_ukrainian_keywords():
    assert _is_relevant("Повітряна тривога оголошена в Харківській області")
    assert _is_relevant("Збито шахед над Дніпром")
    assert _is_relevant("Ракетний удар по Запоріжжю")
    assert _is_relevant("Пуск балістичної ракети зафіксовано")
    assert _is_relevant("ППО збило 5 дронів")
    assert _is_relevant("Відбій тривоги")


def test_relevant_english_keywords():
    assert _is_relevant("missile attack detected")
    assert _is_relevant("drone spotted near border")
    assert _is_relevant("air alert issued")


def test_irrelevant_messages():
    assert not _is_relevant("Сьогодні гарна погода у Києві")
    assert not _is_relevant("Футбольний матч розпочнеться о 20:00")
    assert not _is_relevant("Нові ціни на проїзд у метро")
    assert not _is_relevant("")
    assert not _is_relevant(None)


def test_case_insensitive():
    assert _is_relevant("РАКЕТА летить у напрямку")
    assert _is_relevant("Шахед виявлено")
    assert _is_relevant("ДРОН над містом")


def test_channels_list_not_empty():
    assert len(CHANNELS) >= 30


def test_channels_are_strings():
    for ch in CHANNELS:
        assert isinstance(ch, str)
        assert len(ch) > 0
        assert not ch.startswith("@"), f"Channel {ch!r} should not have leading @"


def test_no_duplicate_channels():
    assert len(CHANNELS) == len(set(CHANNELS)), "Duplicate channels found"


def test_known_channels_present():
    assert "kpszsu" in CHANNELS
    assert "DIUkraine" in CHANNELS
    assert "war_monitor" in CHANNELS
    assert "kyiv_golovne" in CHANNELS


def test_keywords_not_empty():
    assert len(KEYWORDS) >= 20
