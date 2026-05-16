import asyncio
import pytest
import anthropic
from unittest.mock import AsyncMock, MagicMock, patch

import analyzer


def test_filter_casualties_removes_words():
    analysis = {
        "situation": ["вибухи в місті", "є загиблі серед мирних", "атака тривала годину"],
        "strike_means": ["ракета"],
        "key_signals": ["важливий сигнал", "є поранені"],
        "threats": "Є загроза. Можливі жертви серед цивільних. Атаки продовжуються.",
        "pattern": "Звичайний патерн.",
    }
    result = analyzer._filter_casualties(analysis)
    assert "є загиблі серед мирних" not in result["situation"]
    assert "атака тривала годину" in result["situation"]
    assert "є поранені" not in result["key_signals"]
    assert "важливий сигнал" in result["key_signals"]


def test_filter_casualties_preserves_clean():
    analysis = {
        "situation": ["обстріл інфраструктури", "дрони над містом"],
        "strike_means": ["шахед"],
        "key_signals": ["активність ППО"],
        "threats": "Загроза ракетного удару.",
        "pattern": "Нічна атака.",
    }
    result = analyzer._filter_casualties(analysis)
    assert result["situation"] == ["обстріл інфраструктури", "дрони над містом"]
    assert result["key_signals"] == ["активність ППО"]


@pytest.mark.asyncio
async def test_retry_succeeds_on_third_attempt():
    client = MagicMock()
    attempts = []

    async def fake_create(**kwargs):
        attempts.append(1)
        if len(attempts) < 3:
            raise anthropic.InternalServerError(
                response=MagicMock(status_code=500),
                body={"error": {"message": "Internal server error"}},
                message="Internal server error",
            )
        return MagicMock()

    client.messages.create = fake_create

    with patch("analyzer.asyncio.sleep", new_callable=AsyncMock):
        result = await analyzer._create_with_retry(client, model="test", max_tokens=10, messages=[])

    assert len(attempts) == 3


@pytest.mark.asyncio
async def test_retry_raises_after_max_attempts():
    client = MagicMock()

    async def always_fail(**kwargs):
        raise anthropic.InternalServerError(
            response=MagicMock(status_code=500),
            body={"error": {"message": "Internal server error"}},
            message="Internal server error",
        )

    client.messages.create = always_fail

    with patch("analyzer.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(anthropic.InternalServerError):
            await analyzer._create_with_retry(client, model="test", max_tokens=10, messages=[])


@pytest.mark.asyncio
async def test_retry_no_sleep_on_success():
    client = MagicMock()
    mock_response = MagicMock()

    async def succeed(**kwargs):
        return mock_response

    client.messages.create = succeed

    with patch("analyzer.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await analyzer._create_with_retry(client, model="test", max_tokens=10, messages=[])

    mock_sleep.assert_not_called()
    assert result is mock_response


def test_max_retries_constant():
    assert analyzer._MAX_RETRIES == 4


def test_retry_base_delay():
    assert analyzer._RETRY_BASE_DELAY == 2.0
