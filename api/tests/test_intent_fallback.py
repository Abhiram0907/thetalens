"""Tests for regex-based intent fallback parsing (no LLM required)."""

from app.services.intent import (
    _fallback_direction,
    _fallback_horizon,
    _fallback_risk_budget,
    _fallback_slots,
    _fallback_underlying,
)


class TestFallbackUnderlying:
    def test_dollar_ticker(self):
        assert _fallback_underlying("I want to trade $NVDA") == "NVDA"

    def test_company_name_needs_ai_at_inference(self):
        assert _fallback_underlying("Apple looks weak") is None

    def test_labeled_field(self):
        assert _fallback_underlying("Underlying: TSLA") == "TSLA"

    def test_noise_words_excluded(self):
        assert _fallback_underlying("FIND stocks") is None


class TestFallbackDirection:
    def test_bullish(self):
        assert _fallback_direction("NVDA rally, long calls") == "Bullish"

    def test_bearish(self):
        assert _fallback_direction("TSLA drop, buy puts") == "Bearish"

    def test_neutral(self):
        assert _fallback_direction("SPY range-bound sideways") == "Neutral"

    def test_missing(self):
        assert _fallback_direction("What's the best play on AAPL?") is None


class TestFallbackHorizon:
    def test_weeks(self):
        assert _fallback_horizon("2 weeks out") == "2 weeks"

    def test_months(self):
        assert _fallback_horizon("hold for 3 months") == "3 months"

    def test_leap(self):
        assert _fallback_horizon("LEAP 6 months") == "6 months"


class TestFallbackRiskBudget:
    def test_dollar_amount(self):
        assert _fallback_risk_budget("risk budget $500 max") == "$500"

    def test_k_shorthand(self):
        result = _fallback_risk_budget("risk up to 1.5k")
        assert result == "$1,500"


class TestFallbackSlots:
    def test_full_thesis_query(self):
        slots = _fallback_slots(
            "NVDA bullish rally, 2 weeks, risk $1000"
        )
        assert slots.underlying == "NVDA"
        assert slots.direction == "Bullish"
        assert slots.horizon == "2 weeks"
        assert slots.risk_budget == "$1,000"
        assert slots.mode == "thesis"

    def test_agentic_no_direction(self):
        slots = _fallback_slots("Best options play on AAPL")
        assert slots.underlying == "AAPL"
        assert slots.direction is None
