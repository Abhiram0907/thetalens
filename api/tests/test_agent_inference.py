"""Tests for agent direction inference from enriched context."""

from app.agents.thesis_agent import _infer_direction_from_context, _needs_direction_inference


class TestNeedsDirectionInference:
    def test_empty_needs_inference(self):
        assert _needs_direction_inference("") is True

    def test_infer_marker(self):
        assert _needs_direction_inference("infer") is True

    def test_explicit_direction(self):
        assert _needs_direction_inference("Bullish") is False


class TestInferDirectionFromContext:
    def test_bullish_sentiment(self):
        direction, reason = _infer_direction_from_context({
            "get_news_sentiment": {
                "overall_sentiment": "bullish",
                "sentiment_score": 0.4,
            },
        })
        assert direction == "bullish"
        assert "bullish" in reason.lower()

    def test_bearish_sentiment_score(self):
        direction, _ = _infer_direction_from_context({
            "get_news_sentiment": {"sentiment_score": -0.5},
        })
        assert direction == "bearish"

    def test_earnings_high_iv_neutral(self):
        direction, reason = _infer_direction_from_context({
            "get_news_sentiment": {"overall_sentiment": "neutral", "sentiment_score": 0},
            "get_upcoming_earnings": {"earnings_in_trade_window": True},
            "get_iv_rank": {"regime": "High"},
        })
        assert direction == "neutral"
        assert "earnings" in reason.lower()

    def test_mixed_evidence_defaults_neutral(self):
        direction, _ = _infer_direction_from_context({
            "get_news_sentiment": {"overall_sentiment": "neutral", "sentiment_score": 0},
            "get_iv_rank": {"regime": "Mid"},
        })
        assert direction == "neutral"
