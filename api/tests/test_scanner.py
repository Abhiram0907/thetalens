"""Tests for scanner quantitative helpers."""

import pytest

from app.services.scanner import (
    _beta,
    _correlation,
    _iv_rank_from_bars,
    _market_cap_label,
    _opportunity_score,
)


def _bars_from_closes(closes: list[float]) -> list[dict]:
    return [{"c": c} for c in closes]


class TestCorrelation:
    def test_perfect_positive(self):
        xs = [0.01, 0.02, -0.01, 0.015, 0.005]
        assert _correlation(xs, xs) == pytest.approx(1.0, abs=0.01)

    def test_insufficient_data(self):
        assert _correlation([0.01], [0.02]) == 0.0


class TestBeta:
    def test_beta_one_when_identical(self):
        rets = [0.01, -0.02, 0.015, -0.005, 0.02]
        assert _beta(rets, rets) == pytest.approx(1.0, abs=0.01)


class TestOpportunityScore:
    def test_high_iv_high_correlation_scores_higher(self):
        low = _opportunity_score(30, 0.3, 0.8, 25, False)
        high = _opportunity_score(80, 0.9, 1.5, 60, True)
        assert high > low

    def test_bounded_0_100(self):
        score = _opportunity_score(100, 1.0, 3.0, 100, True)
        assert 0 <= score <= 100


class TestIvRankFromBars:
    def test_returns_none_for_short_history(self):
        bars = _bars_from_closes([100 + i * 0.5 for i in range(40)])
        assert _iv_rank_from_bars(bars) is None

    def test_returns_percentile_for_long_history(self):
        import math
        import random

        random.seed(42)
        closes = [100.0]
        for _ in range(120):
            closes.append(closes[-1] * (1 + random.gauss(0, 0.02)))
        bars = _bars_from_closes(closes)
        ivr = _iv_rank_from_bars(bars)
        assert ivr is not None
        assert 0 <= ivr <= 100


class TestMarketCapLabel:
    def test_mega(self):
        assert _market_cap_label(500e9) == "Mega"

    def test_small(self):
        assert _market_cap_label(1e9) == "Small"
