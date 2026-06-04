"""Export detail helpers."""

from app.services.export_detail import build_thesis_risk_callout
from tests.test_research_report import _sample_view


def test_thesis_risk_on_sentiment_divergence():
    view = _sample_view().model_copy(update={"direction": "Bearish"})
    msg = build_thesis_risk_callout(
        view,
        {"get_news_sentiment": {"overall_sentiment": "bullish"}},
    )
    assert msg
    assert "fading" in msg.lower() or "bearish" in msg.lower()
