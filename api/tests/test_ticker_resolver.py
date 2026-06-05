"""Tests for NL ticker resolution (explicit patterns + AI inference)."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.intent import _fallback_risk_budget, _fallback_slots
from app.services.ticker_resolver import (
    resolve_underlying_ai,
    resolve_underlying_explicit,
)


class TestResolveUnderlyingExplicit:
    def test_dollar_ticker(self):
        assert resolve_underlying_explicit("I want to trade $NVDA") == "NVDA"

    def test_caps_ticker(self):
        assert resolve_underlying_explicit("NVDA bullish rally") == "NVDA"

    def test_company_name_needs_ai(self):
        q = "Bullish coreweave next 6 months. No risk"
        assert resolve_underlying_explicit(q) is None

    def test_bullish_not_ticker(self):
        assert resolve_underlying_explicit("Bullish on markets") is None

    def test_unrecognized_returns_none(self):
        assert resolve_underlying_explicit("tell me something interesting") is None


class TestResolveUnderlyingAi:
    @pytest.mark.asyncio
    async def test_uses_llm_for_company_names(self):
        with patch(
            "app.llm.runtime.resolve_ticker_llm",
            new_callable=AsyncMock,
            return_value="CRWV",
        ):
            q = "Bullish coreweave next 6 months. No risk"
            assert await resolve_underlying_ai(q) == "CRWV"

    @pytest.mark.asyncio
    async def test_skips_llm_when_explicit(self):
        with patch(
            "app.llm.runtime.resolve_ticker_llm",
            new_callable=AsyncMock,
        ) as mock_llm:
            assert await resolve_underlying_ai("NVDA bullish rally") == "NVDA"
            mock_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_failure_returns_none(self):
        with patch(
            "app.llm.runtime.resolve_ticker_llm",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM down"),
        ):
            assert await resolve_underlying_ai("Bullish coreweave next 6 months") is None


class TestIntentFallback:
    def test_no_risk_not_budget(self):
        assert _fallback_risk_budget("Bullish coreweave. No risk") is None

    def test_explicit_ticker_slots(self):
        slots = _fallback_slots("NVDA bullish rally, 2 weeks, risk $1000")
        assert slots.underlying == "NVDA"
        assert slots.direction == "Bullish"
