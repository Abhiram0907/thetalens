"""Facts-first research brief composition."""

from datetime import datetime, timezone

import pytest

from app.schemas.analysis import DataProvenance
from app.schemas.market_intel import MarketIntel, SectorPositioning
from app.schemas.research_facts import HeadlineFact, ResearchFacts
from app.schemas.research_report import SentimentHeadline
from app.services.research_compose import compose_research_brief, compose_research_brief_enriched
from app.services.research_facts import gather_research_facts
from app.services.research_report import build_research_report
from app.services.research_report_build import _attach_stored_research
from tests.test_research_report import _sample_strategy, _sample_view


def _crwv_facts() -> ResearchFacts:
    return ResearchFacts(
        ticker="CRWV",
        direction="Bullish",
        horizon="6 months",
        price=42.5,
        business_blurb="CoreWeave provides GPU cloud infrastructure for AI and machine learning workloads.",
        sector_name="Technology",
        industry="Software—Infrastructure",
        ytd_pct=18.0,
        spy_ytd_pct=5.0,
        sector_etf_label="SMH",
        sector_etf_ytd_pct=12.0,
        sector_regime="leading",
        sentiment_tone="bullish",
        sentiment_score=0.35,
        headline_count=4,
        headlines=[
            HeadlineFact(
                title="CoreWeave expands data center capacity for AI clients",
                tone="bullish",
                source="Reuters",
            )
        ],
        headline_focus="mostly company-specific",
        coverage_note="About 4 recent headlines reviewed.",
        next_earnings="2026-08-15",
        earnings_in_window=True,
        peer_symbols=["NVDA", "AMD", "SMCI"],
    )


def test_compose_crwv_brief_has_business_context():
    brief = compose_research_brief(_crwv_facts())
    assert "GPU" in brief.stock_doing or "infrastructure" in brief.stock_doing.lower()
    assert "SMH" in brief.stock_doing or "YTD" in brief.stock_doing
    assert "company-specific" in brief.mood or "bullish" in brief.mood
    assert "earnings" in brief.could_move.lower()
    assert brief.working_for
    assert brief.working_against
    assert "Bull Call" not in brief.bottom_line
    assert "spread" not in brief.bottom_line.lower()


def test_gather_facts_from_report():
    enriched = {
        "company_profile": {
            "ticker": "CRWV",
            "sector": "Technology",
            "industry": "Software—Infrastructure",
            "business_blurb": "CoreWeave provides GPU cloud for AI.",
        },
        "get_news_sentiment": {
            "overall_sentiment": "bullish",
            "headline_count": 2,
            "headlines": [{"title": "CoreWeave wins new contract", "source": "Bloomberg"}],
        },
        "get_upcoming_earnings": {
            "estimated_next_earnings": "2026-08-15",
            "earnings_in_trade_window": True,
        },
    }
    report = build_research_report(
        parsed_view=_sample_view(),
        strategies=[_sample_strategy()],
        reasoning_steps=[],
        underlying_price=42.5,
        data_provenance=DataProvenance(spot_source="yfinance", vol_input="realized_30d"),
        enriched_context=enriched,
    )
    intel = MarketIntel(
        sector=SectorPositioning(
            ticker_return_pct=18.0,
            benchmark_return_pct=5.0,
            sector_etfs=[],
            sector_name="Technology",
            business_blurb="CoreWeave provides GPU cloud for AI.",
        )
    )
    facts = gather_research_facts(report, intel, enriched)
    assert facts.business_blurb
    assert facts.next_earnings == "2026-08-15"
    assert facts.headlines


@pytest.mark.asyncio
async def test_attach_stored_research_uses_facts_not_agent_prose():
    polluted_agent = """6. BOTTOM LINE
Use a Bull Call Spread in mid vol regime.
*** Hypothetical Structure Analysis ***
"""
    enriched = {
        "agent_analysis": polluted_agent,
        "company_profile": {
            "ticker": "NVDA",
            "business_blurb": "NVIDIA designs GPUs for AI and gaming.",
            "sector": "Technology",
            "industry": "Semiconductors",
        },
        "get_news_sentiment": {"overall_sentiment": "bullish", "headline_count": 5},
    }
    report = build_research_report(
        parsed_view=_sample_view(),
        strategies=[_sample_strategy()],
        reasoning_steps=[],
        underlying_price=120.5,
        data_provenance=DataProvenance(spot_source="yfinance", vol_input="realized_30d"),
        enriched_context=enriched,
    )
    report = report.model_copy(
        update={
            "market_intel": MarketIntel(
                sector=SectorPositioning(
                    ticker_return_pct=22.0,
                    benchmark_return_pct=12.0,
                    sector_etfs=[],
                    sector_name="Technology",
                    industry="Semiconductors",
                    business_blurb="NVIDIA designs GPUs for AI and gaming.",
                ),
            ),
            "generated_at": datetime(2026, 6, 3, tzinfo=timezone.utc),
        }
    )
    out = await _attach_stored_research(report, enriched)
    assert out.research_brief is not None
    assert "GPU" in out.research_brief.stock_doing or "NVIDIA" in out.research_brief.stock_doing
    assert "Bull Call" not in out.research_brief.bottom_line


@pytest.mark.asyncio
async def test_compose_with_mock_llm_bottom():
    from unittest.mock import AsyncMock, patch

    with patch(
        "app.llm.runtime.synthesize_bottom_line_llm",
        new_callable=AsyncMock,
        return_value=(
            "CoreWeave rides AI infra demand; sector tape is strong. "
            "A bullish six-month view looks supported but earnings add event risk."
        ),
    ) as mock:
        brief = await compose_research_brief_enriched(_crwv_facts())
        assert "CoreWeave" in brief.bottom_line or "bullish" in brief.bottom_line.lower()
        mock.assert_awaited_once()
