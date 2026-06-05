"""Stored research brief parsing and export layout."""

from datetime import datetime, timezone

import pytest

from app.schemas.analysis import DataProvenance
from app.schemas.market_intel import MarketIntel, SectorPositioning
from app.schemas.research_brief import ResearchBrief
from app.services.export_html import render_research_report_html
from app.services.research_brief import (
    parse_research_brief,
    research_brief_from_agent_text,
    sanitize_agent_brief_text,
)
from app.services.research_report import build_research_report
from tests.test_research_report import _sample_strategy, _sample_view

SAMPLE_AGENT_OUTPUT = """\
1. WHAT'S THE STOCK DOING?
NVDA is at $120 and up 22% YTD, beating SPY by about 10 points.

2. WHAT'S THE MOOD?
Headlines are mostly positive. Coverage is thin but the latest story hints at demand.

3. WHAT COULD MOVE IT?
Earnings on Aug 28 could move the stock. Nothing else big is scheduled this month.

4. WHAT'S WORKING FOR THIS THESIS?
- Sector momentum is strong at +18% YTD.
- News tone matches a bullish view.

5. WHAT'S WORKING AGAINST IT?
- Rising bond yields are a headwind for growth names.
- The stock has already run up a lot this year.

6. BOTTOM LINE
The bullish case holds if yields stay calm and earnings do not disappoint.
"""


def test_sanitize_strips_structure_appendix():
    raw = SAMPLE_AGENT_OUTPUT + """

*** **Hypothetical Structure Analysis:**
* **Bull Call Spread:** balanced risk/reward.
"""
    cleaned = sanitize_agent_brief_text(raw)
    assert "Bull Call Spread" not in cleaned
    assert "BOTTOM LINE" in cleaned
    brief = parse_research_brief(raw)
    assert "Bull Call Spread" not in brief.bottom_line


def test_polluted_bottom_line_replaced():
    polluted = SAMPLE_AGENT_OUTPUT.replace(
        "The bullish case holds if yields stay calm and earnings do not disappoint.",
        "The bullish thesis appears supported; use a Bull Call Spread in mid vol regime.",
    )
    report = build_research_report(
        parsed_view=_sample_view(),
        strategies=[_sample_strategy()],
        reasoning_steps=[],
        underlying_price=120.5,
        data_provenance=DataProvenance(spot_source="yfinance", vol_input="realized_30d"),
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
                    business_blurb="NVDA builds GPUs for AI data centers.",
                ),
            ),
        }
    )
    brief = research_brief_from_agent_text(polluted, report, report.market_intel)
    assert "Bull Call Spread" not in brief.bottom_line
    assert "GPU" in brief.bottom_line or "supported" in brief.bottom_line


def test_parse_research_brief():
    brief = parse_research_brief(SAMPLE_AGENT_OUTPUT)
    assert "NVDA" in brief.stock_doing
    assert brief.working_for
    assert "yields stay calm" in brief.bottom_line


@pytest.mark.asyncio
async def test_export_uses_stored_brief():
    enriched = {
        "get_news_sentiment": {"overall_sentiment": "bullish", "headline_count": 5},
        "company_profile": {
            "ticker": "NVDA",
            "business_blurb": "NVDA builds GPUs for AI data centers.",
            "sector": "Technology",
            "industry": "Semiconductors",
        },
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
                    business_blurb="NVDA builds GPUs for AI data centers.",
                ),
            ),
            "generated_at": datetime(2026, 6, 3, tzinfo=timezone.utc),
        }
    )
    from app.services.research_report_build import _attach_stored_research

    report = await _attach_stored_research(report, enriched)
    assert report.research_brief is not None
    assert report.research_brief.stock_doing
    html = render_research_report_html(report)
    assert "stock doing" in html
    assert "thesis-pros" in html
    assert "Bottom line" in html
    assert "Critical signals" not in html
