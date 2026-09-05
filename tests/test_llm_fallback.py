from unittest.mock import AsyncMock

import pytest

from src.llm_client import ClassificationResult, LLMClassification, LLMClient
from src.models import RootCause


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    return LLMClient()


@pytest.mark.asyncio
async def test_gemini_success_does_not_call_groq(client, monkeypatch):
    gemini_mock = AsyncMock(
        return_value=LLMClassification(root_cause=RootCause.BANK_TIMEOUT, reasoning="timeout mentioned")
    )
    groq_mock = AsyncMock()
    monkeypatch.setattr(client, "_call_gemini", gemini_mock)
    monkeypatch.setattr(client, "_call_groq", groq_mock)

    result = await client.classify("Bank server timeout", "HDFC")

    assert isinstance(result, ClassificationResult)
    assert result.root_cause == RootCause.BANK_TIMEOUT
    assert result.provider_used == "gemini"
    groq_mock.assert_not_called()


@pytest.mark.asyncio
async def test_gemini_failure_falls_back_to_groq(client, monkeypatch):
    gemini_mock = AsyncMock(side_effect=TimeoutError("gemini timed out"))
    groq_mock = AsyncMock(
        return_value=LLMClassification(root_cause=RootCause.NETWORK_ERROR, reasoning="network mentioned")
    )
    monkeypatch.setattr(client, "_call_gemini", gemini_mock)
    monkeypatch.setattr(client, "_call_groq", groq_mock)

    result = await client.classify("Connection reset", "SBI")

    assert result.root_cause == RootCause.NETWORK_ERROR
    assert result.provider_used == "groq"
    groq_mock.assert_called_once()


@pytest.mark.asyncio
async def test_both_providers_fail_returns_unknown(client, monkeypatch):
    gemini_mock = AsyncMock(side_effect=TimeoutError("gemini timed out"))
    groq_mock = AsyncMock(side_effect=RuntimeError("groq 500"))
    monkeypatch.setattr(client, "_call_gemini", gemini_mock)
    monkeypatch.setattr(client, "_call_groq", groq_mock)

    result = await client.classify("Weird unexplained error", "AXIS")

    assert result.root_cause == RootCause.UNKNOWN
    assert result.provider_used is None
    assert "gemini timed out" in result.reasoning
    assert "groq 500" in result.reasoning
