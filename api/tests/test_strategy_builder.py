"""Tests for strategy builder parsing and ranking."""

from datetime import date

from app.schemas.analysis import LiquidityProfile, ParsedView, StrategyMetrics
from app.services.strategy_builder import (
    _trade_quality,
    build_strategies,
    build_strategies_resilient,
    parse_horizon_days,
    parse_risk_budget,
)


class TestParseHorizonDays:
    def test_weeks(self):
        assert parse_horizon_days("2 weeks") == 14

    def test_months(self):
        assert parse_horizon_days("3 months") == 90

    def test_days_default(self):
        assert parse_horizon_days("45 days") == 45

    def test_bare_number(self):
        assert parse_horizon_days("21") == 21


class TestParseRiskBudget:
    def test_not_specified(self):
        assert parse_risk_budget("not specified") == 100_000.0

    def test_dollar_amount(self):
        assert parse_risk_budget("$500") == 500.0

    def test_none_like(self):
        assert parse_risk_budget("none") == 100_000.0


class TestTradeQuality:
    def test_tradeable_baseline(self):
        tq = _trade_quality(
            tag="vertical",
            metrics=StrategyMetrics(
                max_gain=500,
                max_loss=200,
                breakevens=["$98"],
                pop=65,
                ev=120,
                risk_reward="2.5:1",
            ),
            liquidity=LiquidityProfile(
                score=80,
                label="Good",
                quote_quality="estimated",
                spread_warnings=[],
            ),
            iv_regime="Mid",
            earnings_in_window=False,
            warning=None,
        )
        assert tq.verdict in ("Tradeable", "Caution")
        assert tq.score >= 70

    def test_avoid_on_earnings_and_warning(self):
        tq = _trade_quality(
            tag="long-call",
            metrics=StrategyMetrics(
                max_gain="∞",
                max_loss=500,
                breakevens=["$105"],
                pop=35,
                ev=-50,
                risk_reward="N/A",
            ),
            liquidity=LiquidityProfile(
                score=40,
                label="Thin",
                quote_quality="estimated",
                spread_warnings=["wide spread"],
            ),
            iv_regime="High",
            earnings_in_window=True,
            warning="over budget",
        )
        assert tq.verdict == "Avoid"


class TestBuildStrategies:
    def test_returns_ranked_strategies(self, sample_snapshot):
        view = ParsedView(
            direction="Neutral",
            direction_icon="→",
            magnitude="±5% range",
            horizon="30 days",
            horizon_label="30 days",
            volatility_view="Mid",
            risk_budget="$500",
            underlying="TEST",
            underlying_price=100.0,
            iv_rank=50,
            iv_label="Mid",
        )
        strategies = build_strategies(
            view, sample_snapshot, iv_regime="Mid", earnings_in_window=False
        )
        assert len(strategies) >= 1
        assert strategies[0].rank == 1
        scores = [s.score for s in strategies]
        assert scores == sorted(scores, reverse=True)

    def test_respects_avoid_structures(self, sample_snapshot):
        view = ParsedView(
            direction="Bullish",
            direction_icon="↑",
            magnitude="moderate",
            horizon="30 days",
            horizon_label="30 days",
            volatility_view="Mid",
            risk_budget="$1000",
            underlying="TEST",
            underlying_price=100.0,
            iv_rank=50,
            iv_label="Mid",
        )
        all_strats = build_strategies(view, sample_snapshot)
        filtered = build_strategies(
            view, sample_snapshot, avoid_structures=["Bull Put Spread"]
        )
        names_all = {s.name for s in all_strats}
        names_filtered = {s.name for s in filtered}
        if "Bull Put Spread" in names_all:
            assert "Bull Put Spread" not in names_filtered

    def test_resilient_recovers_from_tight_risk_budget(self, sample_snapshot):
        view = ParsedView(
            direction="Bullish",
            direction_icon="↑",
            magnitude="±10%",
            horizon="60 days",
            horizon_label="60 days",
            volatility_view="Mid",
            risk_budget="$50",
            underlying="MU",
            underlying_price=sample_snapshot.spot,
            iv_rank=50,
            iv_label="Mid",
        )
        strict = build_strategies(view, sample_snapshot)
        assert strict == []
        strategies, adjusted, notes = build_strategies_resilient(view, sample_snapshot)
        assert len(strategies) >= 1
        assert adjusted.risk_budget == "not specified"
        assert notes
