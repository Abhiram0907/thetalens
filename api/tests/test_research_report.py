"""Research report and export HTML."""

from datetime import datetime, timezone

from app.schemas.analysis import (
    DataProvenance,
    Leg,
    ParsedView,
    ReasoningStep,
    Strategy,
    StrategyGreeks,
    StrategyMetrics,
    TradeQuality,
)
from app.services.export_html import render_research_report_html
from app.services.research_report import build_research_report


def _sample_view() -> ParsedView:
    return ParsedView(
        direction="Bullish",
        direction_icon="↑",
        magnitude="±8%",
        horizon="30 days",
        horizon_label="30 days",
        volatility_view="Mid IV — balanced",
        risk_budget="$1,000",
        underlying="NVDA",
        underlying_price=120.5,
        realized_vol_rank=55,
        realized_vol_regime="Mid",
        realized_vol_label="Mid IV rank (55)",
        iv_rank=55,
        iv_label="Mid IV rank (55)",
    )


def _sample_strategy() -> Strategy:
    return Strategy(
        rank=1,
        name="Bull Put Spread",
        tag="Defined risk",
        legs=[
            Leg(
                action="SELL",
                qty=1,
                type="PUT",
                strike=115,
                dte=30,
                premium=2.5,
                label="Short put",
            ),
        ],
        metrics=StrategyMetrics(
            max_gain=250,
            max_loss=750,
            breakevens=["$112.50"],
            pop=68,
            ev=120,
            risk_reward="1:3",
        ),
        greeks=StrategyGreeks(delta=0.2, theta=-0.05, vega=0.1, gamma=0.01),
        score=82,
        critique="Fits bullish view with defined risk.",
        vs_next="Higher POP than #2",
        trade_quality=TradeQuality(
            verdict="Caution",
            score=70,
            reasons=["Modeled mids"],
        ),
    )


def test_build_research_report_from_enriched():
    enriched = {
        "get_iv_rank": {"iv_rank": 62, "regime": "Mid", "current_rv_30d": 45},
        "get_news_sentiment": {
            "overall_sentiment": "bullish",
            "headline_count": 5,
            "headlines": [
                {"title": "NVDA beats estimates", "published": "2026-06-01", "source": "Reuters"},
            ],
        },
        "get_expected_move": {"expected_move_pct": 10.5, "expected_move_dollar": 12.6, "dte": 30},
        "agent_analysis": "## Executive summary\nBullish setup.\n\n## Risks\nVerify quotes.",
        "calculate_magnitude": {"magnitude": "±8%"},
    }
    report = build_research_report(
        parsed_view=_sample_view(),
        strategies=[_sample_strategy()],
        reasoning_steps=[ReasoningStep(node="Research Agent", message="IV rank 62", delay=0)],
        underlying_price=120.5,
        data_provenance=DataProvenance(
            spot_source="yfinance",
            vol_input="realized_30d",
        ),
        query="NVDA bullish 30 days",
        enriched_context=enriched,
    )
    assert "NVDA" in report.executive_summary
    assert len(report.tool_findings) >= 2
    assert report.agent_narrative
    assert report.synthesis
    assert any("Modeled" in r for r in report.risks_and_caveats)
    assert report.shareable_line
    assert "NVDA" in report.shareable_line
    assert report.vol_context_line
    assert report.data_as_of_display
    assert len(report.sentiment_headlines) >= 1


def test_render_html_newsletter_poster_and_markdown():
    report = build_research_report(
        parsed_view=_sample_view(),
        strategies=[_sample_strategy()],
        reasoning_steps=[
            ReasoningStep(node="Research Agent", message="Skipped in export", delay=0),
        ],
        underlying_price=120.5,
        data_provenance=DataProvenance(
            spot_source="yfinance",
            vol_input="realized_30d",
        ),
        query="test",
        enriched_context={
            "get_iv_rank": {"iv_rank": 62, "regime": "Mid", "current_rv_30d": 45},
            "get_expected_move": {"expected_move_pct": 8.0, "expected_move_dollar": 9.6},
            "get_news_sentiment": {
                "overall_sentiment": "bullish",
                "headlines": [{"title": "Chip rally continues", "published": "2026-06-02"}],
            },
            "agent_analysis": (
                "1. WHAT'S THE STOCK DOING?\nNVDA at $120, up 22% YTD.\n\n"
                "2. WHAT'S THE MOOD?\nPositive headlines.\n\n"
                "3. WHAT COULD MOVE IT?\nEarnings next month.\n\n"
                "4. WHAT'S WORKING FOR THIS THESIS?\n- Strong sector.\n\n"
                "5. WHAT'S WORKING AGAINST IT?\n- Yields rising.\n\n"
                "6. BOTTOM LINE\nBull case needs calm macro."
            ),
        },
    )
    report.generated_at = datetime(2026, 6, 3, tzinfo=timezone.utc)
    html_out = render_research_report_html(report)
    assert "State of the Play" in html_out
    assert "logo-img" not in html_out
    assert "ticker-display" in html_out
    assert "--gold-bright" in html_out
    assert "shareable-line" in html_out
    assert "thesis-pros" in html_out or "stock doing" in html_out
    assert "Critical signals" not in html_out


def test_research_brief_from_agent_enriched():
    report = build_research_report(
        parsed_view=_sample_view(),
        strategies=[_sample_strategy()],
        reasoning_steps=[],
        underlying_price=120.5,
        data_provenance=DataProvenance(spot_source="yfinance", vol_input="realized_30d"),
        enriched_context={
            "agent_analysis": (
                "1. WHAT'S THE STOCK DOING?\nNVDA at $120.\n\n"
                "6. BOTTOM LINE\nBull case holds."
            ),
        },
    )
    assert report.research_brief is not None
    assert report.research_brief.stock_doing
    assert report.so_what_box == "Bull case holds."
