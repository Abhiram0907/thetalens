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
from app.services.research_brief import sanitize_agent_brief_text
from app.services.research_compose import compose_research_brief_enriched
from app.services.research_facts import gather_research_facts
from app.services.research_report import build_research_report


def _agent_text(report: ResearchReport, enriched_context: dict[str, Any] | None) -> str:
    enriched = enriched_context or {}
    raw = (enriched.get("agent_analysis") or report.agent_narrative or "").strip()
    return sanitize_agent_brief_text(raw)


async def _attach_stored_research(
    report: ResearchReport,
    enriched_context: dict[str, Any] | None,
) -> ResearchReport:
    """Compose export brief from structured facts (primary path)."""
    facts = gather_research_facts(report, report.market_intel, enriched_context)
    brief = await compose_research_brief_enriched(facts)
    agent_text = _agent_text(report, enriched_context)
    bottom = brief.bottom_line or None
    return report.model_copy(
        update={
            "research_brief": brief,
            "so_what_box": bottom,
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
    return await _attach_stored_research(report, enriched_context)


async def ensure_report_market_intel(
    report: ResearchReport,
    enriched_context: dict[str, Any] | None = None,
) -> ResearchReport:
    """Fill market intel on export when missing; compose brief from facts."""
    if report.market_intel is not None:
        return await _attach_stored_research(report, enriched_context)
    intel = await gather_market_intel(
        report.parsed_view.underlying,
        report.parsed_view,
        enriched_context,
    )
    return await _attach_stored_research(
        report.model_copy(update={"market_intel": intel}),
        enriched_context,
    )
