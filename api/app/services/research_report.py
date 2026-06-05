"""Build a structured research report at inference time (agent or direct analyze)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.schemas.analysis import (
    CapturedIntent,
    DataProvenance,
    ParsedView,
    ReasoningStep,
    Strategy,
)
from app.schemas.research_report import ReportSection, ResearchReport, ToolFinding
from app.services.export_detail import (
    build_export_shareable_line,
    build_thesis_risk_callout,
    build_vol_context_line,
    extract_sentiment_headlines,
    format_data_as_of_display,
)
from app.schemas.research_brief import ResearchBrief


def _fmt_money(value: float | str) -> str:
    if isinstance(value, (int, float)):
        return f"${value:,.0f}"
    return str(value)


def _extract_tool_findings(enriched: dict[str, Any]) -> list[ToolFinding]:
    findings: list[ToolFinding] = []

    iv = enriched.get("get_iv_rank") or {}
    if iv and not iv.get("error"):
        details = [
            f"IV rank: {iv.get('iv_rank', 'n/a')} ({iv.get('regime', 'n/a')} regime)",
            f"30-day realized vol: {iv.get('current_rv_30d', 'n/a')}%",
            f"252-day RV range: {iv.get('rv_252d_low', 'n/a')}% – {iv.get('rv_252d_high', 'n/a')}%",
        ]
        findings.append(
            ToolFinding(
                tool="get_iv_rank",
                summary=(
                    f"{iv.get('regime', 'Mid')} volatility — IV rank {iv.get('iv_rank', 'n/a')} "
                    f"with 30d RV near {iv.get('current_rv_30d', 'n/a')}%."
                ),
                details=[d for d in details if "n/a" not in d],
            )
        )

    earnings = enriched.get("get_upcoming_earnings") or {}
    if earnings.get("estimated_next_earnings") or earnings.get("note"):
        in_win = earnings.get("earnings_in_trade_window")
        findings.append(
            ToolFinding(
                tool="get_upcoming_earnings",
                summary=(
                    f"Next earnings ~{earnings.get('estimated_next_earnings', 'unknown')} "
                    f"({'inside' if in_win else 'outside'} the trade window)."
                ),
                details=[
                    earnings.get("note") or "",
                    f"Source: {earnings.get('source', 'unknown')}",
                ],
            )
        )

    news = enriched.get("get_news_sentiment") or {}
    if news.get("overall_sentiment"):
        headlines = news.get("sample_headlines") or news.get("headlines") or []
        detail_lines = [f"Sentiment score: {news.get('sentiment_score', 'n/a')}"]
        if isinstance(headlines, list):
            for h in headlines[:3]:
                if isinstance(h, dict):
                    detail_lines.append(f"• {h.get('headline', h.get('title', ''))}")
                elif isinstance(h, str):
                    detail_lines.append(f"• {h}")
        findings.append(
            ToolFinding(
                tool="get_news_sentiment",
                summary=(
                    f"Headline tone is {news.get('overall_sentiment')} "
                    f"({news.get('headline_count', 0)} articles reviewed)."
                ),
                details=[d for d in detail_lines if d],
            )
        )

    hist = enriched.get("get_historical_post_earnings_move") or {}
    if hist and not hist.get("error"):
        avg = hist.get("average_move_pct")
        if avg is not None:
            findings.append(
                ToolFinding(
                    tool="get_historical_post_earnings_move",
                    summary=f"Post-earnings moves averaged ±{avg}% over recent quarters.",
                    details=[
                        f"Quarters sampled: {hist.get('quarters_analyzed', 'n/a')}",
                        f"Max move: {hist.get('max_move_pct', 'n/a')}%",
                    ],
                )
            )

    em = enriched.get("get_expected_move") or {}
    if em.get("expected_move_pct") is not None:
        findings.append(
            ToolFinding(
                tool="get_expected_move",
                summary=(
                    f"Options-implied move ±{em.get('expected_move_pct')}% "
                    f"(±{_fmt_money(em.get('expected_move_dollar', 0))}) over {em.get('dte', '?')}d."
                ),
                details=[em.get("note") or "Derived from ATM straddle pricing on the chain."],
            )
        )

    mag = enriched.get("calculate_magnitude") or {}
    magnitude = enriched.get("magnitude") or mag.get("magnitude")
    if magnitude:
        findings.append(
            ToolFinding(
                tool="calculate_magnitude",
                summary=f"Thesis magnitude calibrated to {magnitude}.",
                details=[
                    mag.get("reasoning") or mag.get("note") or "",
                    f"Direction used: {mag.get('direction', enriched.get('direction', 'n/a'))}",
                ],
            )
        )

    fit = enriched.get("assess_structure_fit") or {}
    rec = fit.get("recommended_structures") or []
    avoid = fit.get("structures_to_avoid") or []
    if rec or avoid:
        rec_lines = [
            f"✓ {r.get('structure')}: {r.get('reason', '')}" for r in rec[:4]
        ]
        avoid_lines = [
            f"✗ {a.get('structure')}: {a.get('reason', '')}" for a in avoid[:4]
        ]
        findings.append(
            ToolFinding(
                tool="assess_structure_fit",
                summary=(
                    f"Regime favors {', '.join(r['structure'] for r in rec[:2]) or 'defined-risk structures'}."
                ),
                details=[ln for ln in rec_lines + avoid_lines if ln.strip()],
            )
        )

    inference = enriched.get("direction_inference") or {}
    if inference.get("inferred"):
        findings.append(
            ToolFinding(
                tool="direction_inference",
                summary=f"Direction set to {inference.get('direction')} from market signals.",
                details=[inference.get("reason") or ""],
            )
        )

    return findings


def _build_market_context(
    view: ParsedView,
    enriched: dict[str, Any],
    strategies: list[Strategy],
) -> list[ReportSection]:
    sections: list[ReportSection] = [
        ReportSection(
            title="Thesis framing",
            body=(
                f"{view.underlying} @ ${view.underlying_price:.2f} — {view.direction} "
                f"{view.magnitude} view over {view.horizon_label} ({view.horizon}). "
                f"Volatility lens: {view.volatility_view}. Capital at risk budget: {view.risk_budget}."
            ),
        ),
        ReportSection(
            title="Volatility & regime",
            body=(
                f"{view.realized_vol_label}. Realized-vol rank {view.realized_vol_rank} "
                f"({view.realized_vol_regime} regime). This shapes whether premium selling, "
                f"debit directional, or neutral structures are favored."
            ),
        ),
    ]

    earnings = enriched.get("get_upcoming_earnings") or {}
    if earnings.get("estimated_next_earnings"):
        sections.append(
            ReportSection(
                title="Catalyst calendar",
                body=(
                    f"Estimated next earnings: {earnings.get('estimated_next_earnings')}. "
                    f"{'Earnings fall inside the holding window — size and structure accordingly.' if earnings.get('earnings_in_trade_window') else 'Earnings are outside the primary window but may still affect sentiment.'}"
                ),
            )
        )

    if strategies:
        top = strategies[0]
        tq = top.trade_quality
        verdict = tq.verdict if tq else "n/a"
        sections.append(
            ReportSection(
                title="Structure landscape",
                body=(
                    f"The engine ranked {len(strategies)} template(s). Lead candidate: {top.name} "
                    f"(score {top.score}, execution {verdict}). "
                    f"{top.critique}"
                ),
            )
        )

    return sections


def _build_risks(
    view: ParsedView,
    enriched: dict[str, Any],
    strategies: list[Strategy],
    provenance: DataProvenance,
) -> list[str]:
    risks: list[str] = [
        "Options involve substantial risk; outcomes depend on price, volatility, and time.",
        "Leg premiums and greeks use modeled prices — verify live quotes with your broker before trading.",
    ]
    if provenance.data_age_warning:
        risks.append(provenance.data_age_warning)
    if provenance.spot_as_of:
        risks.append(f"Underlying spot as of {provenance.spot_as_of} ({provenance.spot_source}).")

    earnings = enriched.get("get_upcoming_earnings") or {}
    if earnings.get("earnings_in_trade_window"):
        risks.append("Earnings inside the trade window can gap price and crush IV — gamma/vega risk elevated.")

    news = enriched.get("get_news_sentiment") or {}
    if news.get("overall_sentiment") and view.direction:
        sent = str(news.get("overall_sentiment", "")).lower()
        dir_l = view.direction.lower()
        if (dir_l == "bullish" and sent == "bearish") or (dir_l == "bearish" and sent == "bullish"):
            risks.append(
                "Recent headline sentiment diverges from the stated directional bias — "
                "treat directional structures with extra skepticism."
            )

    for s in strategies[:3]:
        if s.warning:
            risks.append(f"{s.name}: {s.warning}")
        if s.trade_quality and s.trade_quality.verdict in ("Caution", "Avoid"):
            reasons = "; ".join(s.trade_quality.reasons[:2])
            if reasons:
                risks.append(f"{s.name} execution quality {s.trade_quality.verdict}: {reasons}")

    return risks


def _build_synthesis(view: ParsedView, strategies: list[Strategy], enriched: dict[str, Any]) -> str:
    if not strategies:
        return "No structures met liquidity, budget, and regime filters for this view."

    top = strategies[0]
    fit = enriched.get("assess_structure_fit") or {}
    rec_names = [r.get("structure") for r in fit.get("recommended_structures", [])[:2]]
    rec_phrase = f" Agent regime fit highlighted {', '.join(rec_names)}." if rec_names else ""

    loss = _fmt_money(top.metrics.max_loss)
    return (
        f"For a {view.direction.lower()} {view.magnitude} thesis on {view.underlying} "
        f"over {view.horizon_label}, {top.name} offers the best composite score "
        f"(EV ${top.metrics.ev:,.0f}, max loss {loss}, PoP {top.metrics.pop}%).{rec_phrase} "
        f"Review #{top.rank} execution quality and compare vs alternatives before sizing."
    )


def _build_executive_summary(
    view: ParsedView,
    strategies: list[Strategy],
    enriched: dict[str, Any],
    query: str | None,
) -> str:
    agent = (enriched.get("agent_analysis") or "").strip()
    if agent:
        first = agent.split("\n\n")[0].strip()
        if len(first) > 40:
            return first[:500] + ("…" if len(first) > 500 else "")

    if not strategies:
        sym = view.underlying
        return f"Research completed for {sym}; no ranked structures passed filters for the current view."

    top = strategies[0]
    inference = enriched.get("direction_inference") or {}
    dir_note = ""
    if inference.get("inferred"):
        dir_note = f" Direction inferred as {inference.get('direction')}."

    q = f' Query: "{query[:120]}…"' if query and len(query) > 120 else (f' Query: "{query}"' if query else "")
    return (
        f"{view.underlying} {view.direction} research — {top.name} leads {len(strategies)} "
        f"structure(s) for a {view.magnitude} move over {view.horizon_label}.{dir_note}{q}"
    )


def _build_thesis_interpretation(view: ParsedView, enriched: dict[str, Any], query: str | None) -> str:
    parts: list[str] = []
    if query:
        parts.append(f'User view: "{query.strip()}"')
    parts.append(
        f"Parsed thesis: {view.direction} on {view.underlying}, magnitude {view.magnitude}, "
        f"horizon {view.horizon_label}, risk budget {view.risk_budget}."
    )
    inference = enriched.get("direction_inference") or {}
    if inference.get("reason"):
        parts.append(f"Direction note: {inference['reason']}")
    mag = enriched.get("calculate_magnitude") or {}
    if mag.get("reasoning"):
        parts.append(f"Magnitude rationale: {mag['reasoning']}")
    return " ".join(parts)


def build_research_report(
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
    enriched = dict(enriched_context or {})
    enriched.setdefault("ticker", parsed_view.underlying)

    tool_findings = _extract_tool_findings(enriched)
    market_context = _build_market_context(parsed_view, enriched, strategies)
    risks = _build_risks(parsed_view, enriched, strategies, data_provenance)
    agent_narrative = (enriched.get("agent_analysis") or "").strip() or None
    em = enriched.get("get_expected_move") or {}

    draft = ResearchReport(
        generated_at=datetime.now(timezone.utc),
        query=query,
        captured=captured,
        executive_summary=_build_executive_summary(parsed_view, strategies, enriched, query),
        thesis_interpretation=_build_thesis_interpretation(parsed_view, enriched, query),
        market_context=market_context,
        tool_findings=tool_findings,
        agent_narrative=agent_narrative,
        risks_and_caveats=risks,
        synthesis=_build_synthesis(parsed_view, strategies, enriched),
        parsed_view=parsed_view,
        reasoning_steps=reasoning_steps,
        strategies=strategies,
        underlying_price=underlying_price,
        data_provenance=data_provenance,
        shareable_line="",
        thesis_risk_callout=build_thesis_risk_callout(parsed_view, enriched),
        vol_context_line=build_vol_context_line(enriched),
        data_as_of_display=format_data_as_of_display(data_provenance),
        expected_move_pct=em.get("expected_move_pct"),
        expected_move_dollars=em.get("expected_move_dollar"),
        sentiment_headlines=extract_sentiment_headlines(enriched),
    )
    return draft.model_copy(
        update={
            "research_brief": ResearchBrief(),
            "shareable_line": build_export_shareable_line(draft),
        }
    )
