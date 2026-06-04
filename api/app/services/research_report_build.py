"""Async research report build with market intel enrichment."""

from __future__ import annotations

from typing import Any

from app.schemas.analysis import (
    CapturedIntent,
    DataProvenance,
    ParsedView,
    ReasoningStep,
    Strategy,
)
from app.schemas.research_report import ResearchReport
from app.services.export_detail import build_export_shareable_line
from app.services.market_intel import gather_market_intel
from app.services.research_brief import research_brief_from_agent_text
from app.services.research_report import build_research_report


def _agent_text(report: ResearchReport, enriched_context: dict[str, Any] | None) -> str:
    enriched = enriched_context or {}
    return (enriched.get("agent_analysis") or report.agent_narrative or "").strip()


def _attach_stored_research(
    report: ResearchReport,
    enriched_context: dict[str, Any] | None,
) -> ResearchReport:
    """Parse agent final analysis into export brief — no extra LLM calls."""
    agent_text = _agent_text(report, enriched_context)
    brief = report.research_brief
    if agent_text and (brief is None or not brief.stock_doing):
        brief = research_brief_from_agent_text(agent_text, report, report.market_intel)
    bottom = (brief.bottom_line if brief else "") or report.so_what_box or ""
    return report.model_copy(
        update={
            "research_brief": brief,
            "so_what_box": bottom or None,
            "shareable_line": build_export_shareable_line(report),
            "agent_narrative": agent_text or report.agent_narrative,
        }
    )


async def build_research_report_enriched(
    *,
    parsed_view: ParsedView,
    strategies: list[Strategy],
    reasoning_steps: list[ReasoningStep],
    underlying_price: float,
    data_provenance: DataProvenance,
    query: str | None = None,
    captured: CapturedIntent | None = None,
    enriched_context: dict[str, Any] | None = None,
) -> ResearchReport:
    report = build_research_report(
        parsed_view=parsed_view,
        strategies=strategies,
        reasoning_steps=reasoning_steps,
        underlying_price=underlying_price,
        data_provenance=data_provenance,
        query=query,
        captured=captured,
        enriched_context=enriched_context,
    )
    intel = await gather_market_intel(
        parsed_view.underlying,
        parsed_view,
        enriched_context,
    )
    report = report.model_copy(update={"market_intel": intel})
    return _attach_stored_research(report, enriched_context)


async def ensure_report_market_intel(
    report: ResearchReport,
    enriched_context: dict[str, Any] | None = None,
) -> ResearchReport:
    """Fill market intel on export when missing; reuse stored agent research."""
    if report.market_intel is not None:
        return _attach_stored_research(report, enriched_context)
    intel = await gather_market_intel(
        report.parsed_view.underlying,
        report.parsed_view,
        enriched_context,
    )
    return _attach_stored_research(
        report.model_copy(update={"market_intel": intel}),
        enriched_context,
    )
