"""Market intel SVG in HTML export."""

from datetime import datetime, timezone

from app.schemas.analysis import DataProvenance, ReasoningStep
from app.schemas.research_brief import ResearchBrief
from app.schemas.market_intel import MarketIntel, SectorPositioning
from app.services.export_context_html import sector_ytd_bars_svg
from app.services.export_html import render_research_report_html
from app.services.research_report import build_research_report
from tests.test_research_report import _sample_strategy, _sample_view


def test_sector_bars_red_for_negative():
    svg = sector_ytd_bars_svg([], 11.0, -5.0)
    assert "#ff6b6b" in svg
    assert "#8a8478" in svg
    assert "#f4f0e6" in svg


def test_trimmed_export_layout():
    report = build_research_report(
        parsed_view=_sample_view(),
        strategies=[_sample_strategy()],
        reasoning_steps=[ReasoningStep(node="X", message="y", delay=0)],
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
                ),
            ),
            "research_brief": ResearchBrief(
                stock_doing="TEST narrative.",
                mood="Quiet headlines.",
                could_move="No scheduled catalysts.",
                working_for=["Sector leading."],
                working_against=["Macro headwind."],
                bottom_line="Weigh both sides.",
            ),
            "so_what_box": "Weigh both sides.",
            "shareable_line": "NVDA bull 30 days | Spot $120.50 | SMH +18.0% YTD",
            "generated_at": datetime(2026, 6, 3, tzinfo=timezone.utc),
        }
    )
    out = render_research_report_html(report)
    assert "Bottom line" in out
    assert "thesis-pros" in out
    assert "Critical signals" not in out
    assert "Top plays" not in out
    assert "shareable-line" in out
    assert "sector-bars-svg" in out
