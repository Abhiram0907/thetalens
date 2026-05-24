"""Build agent reasoning steps from real pipeline outputs."""

from __future__ import annotations

from datetime import date

from app.schemas.analysis import CapturedIntent, ParsedView, ReasoningStep, Strategy
from app.services.market_data import MarketSnapshot
from app.services.strategy_builder import parse_risk_budget


def _step(node: str, message: str, delay: int) -> ReasoningStep:
    return ReasoningStep(node=node, message=message, delay=delay)


def _captured_summary(captured: CapturedIntent) -> str:
    parts: list[str] = []
    if captured.underlying:
        parts.append(captured.underlying)
    if captured.direction:
        parts.append(captured.direction)
    if captured.magnitude:
        parts.append(captured.magnitude)
    if captured.horizon:
        parts.append(captured.horizon)
    if captured.risk_budget:
        parts.append(captured.risk_budget)
    return " · ".join(parts) if parts else "partial view"


def build_clarify_reasoning_steps(
    captured: CapturedIntent,
    missing: list[str],
    *,
    question_templates: dict,
) -> list[ReasoningStep]:
    steps = [_step("View Parser", "Parsing natural language view…", 200)]

    summary = _captured_summary(captured)
    if summary != "partial view":
        steps.append(
            _step("View Parser", f"Extracted from query: {summary}", 750),
        )

    if missing:
        need = ", ".join(question_templates[f]["label"].lower() for f in missing)
        steps.append(
            _step(
                "View Parser",
                f"Intent extraction noted missing {need}; agent will infer or default downstream",
                1300,
            ),
        )
        steps.append(
            _step(
                "View Parser",
                "Proceeding without user clarification…",
                1800,
            ),
        )
    else:
        sym = captured.underlying or "symbol"
        steps.append(
            _step(
                "View Parser",
                f"Intent complete for {sym} — proceeding to structure",
                1200,
            ),
        )

    return steps


def _chain_summary(snapshot: MarketSnapshot) -> str:
    puts = [c for c in snapshot.contracts if c.contract_type == "put"]
    calls = [c for c in snapshot.contracts if c.contract_type == "call"]
    strikes = [c.strike for c in snapshot.contracts]
    if not strikes:
        return "no contracts priced"
    lo, hi = min(strikes), max(strikes)
    return (
        f"{len(snapshot.contracts)} contracts priced "
        f"({len(puts)}P / {len(calls)}C) · strikes ${lo:g}–${hi:g}"
    )


def _expiry_detail(snapshot: MarketSnapshot, target_dte: int) -> str:
    today = date.today()
    front = snapshot.front_expiry
    back = snapshot.back_expiry
    if not front:
        return f"target ~{target_dte} DTE"
    fd = (front - today).days
    if back and back != front:
        bd = (back - today).days
        return (
            f"{front.strftime('%b %d')} ({fd}d) / "
            f"{back.strftime('%b %d')} ({bd}d)"
        )
    return f"{front.strftime('%b %d')} ({fd}d)"


def build_analysis_reasoning_steps(
    view: ParsedView,
    snapshot: MarketSnapshot,
    strategies: list[Strategy],
    *,
    target_dte: int,
) -> list[ReasoningStep]:
    risk_cap = parse_risk_budget(view.risk_budget)
    names = [s.name for s in strategies]
    template_line = ", ".join(names[:4])
    if len(names) > 4:
        template_line += f", +{len(names) - 4} more"

    exp_detail = _expiry_detail(snapshot, target_dte)
    chain_line = _chain_summary(snapshot)

    steps: list[ReasoningStep] = [
        _step("View Parser", "Parsing natural language view…", 200),
        _step(
            "View Parser",
            (
                f"Extracted: {view.direction} {view.direction_icon} · "
                f"{view.magnitude} · {view.horizon_label} ({view.horizon})"
            ),
            850,
        ),
        _step(
            "View Parser",
            (
                f"Vol: {view.volatility_view} · Risk budget: {view.risk_budget} · "
                f"{view.underlying} @ ${view.underlying_price:.2f} (EOD)"
            ),
            1450,
        ),
        _step(
            "Strategy Planner",
            f"Planning {view.direction.lower()} structures for {view.horizon_label} horizon…",
            2200,
        ),
        _step(
            "Strategy Planner",
            f"IV context: {view.iv_label} on {view.underlying}",
            2900,
        ),
        _step(
            "Strategy Planner",
            f"Candidates: {template_line}",
            3600,
        ),
        _step(
            "Pricer",
            f"Loading {view.underlying} options via Massive — expiries {exp_detail}",
            4400,
        ),
        _step(
            "Pricer",
            f"Chain ready: {chain_line} · mids from prior-session aggregates",
            5100,
        ),
        _step(
            "Pricer",
            (
                f"Mapped legs to live strikes · spot ${snapshot.spot:.2f} · "
                f"budget ≤ ${risk_cap:,.0f} · greeks via BS (IV from mids)"
            ),
            5800,
        ),
        _step(
            "Critic",
            "Scoring on expected value, max loss vs budget, and payoff shape…",
            6600,
        ),
    ]

    delay = 7200
    for w in [s for s in strategies if s.warning][:2]:
        steps.append(_step("Critic", f"⚠ {w.name}: {w.warning}", delay))
        delay += 500

    rejected_note = ""
    if len(strategies) < 4:
        rejected_note = " (some templates dropped — illiquid strikes or over budget)"

    if strategies:
        top = strategies[0]
        loss = top.metrics.max_loss
        loss_s = (
            f"${loss:,.0f}"
            if isinstance(loss, (int, float))
            else str(loss)
        )
        delay += 400
        steps.append(
            _step(
                "Critic",
                (
                    f"#{top.rank} {top.name}: EV ${top.metrics.ev:.0f} · "
                    f"max loss {loss_s} · PoP {top.metrics.pop}% · "
                    f"score {top.score}"
                ),
                delay,
            ),
        )

    delay += 800
    steps.append(
        _step(
            "Synthesizer",
            (
                f"Playbook ready — {len(strategies)} structure(s) ranked"
                f"{rejected_note}"
            ),
            delay,
        ),
    )
    if strategies:
        steps.append(
            _step(
                "Synthesizer",
                f"Recommended: {strategies[0].name} for {view.direction.lower()} "
                f"{view.magnitude} view on {view.underlying}",
                delay + 600,
            ),
        )

    return steps


def build_agent_research_reasoning_steps(
    enriched: dict,
    view: ParsedView,
    snapshot: MarketSnapshot,
    strategies: list[Strategy],
    *,
    target_dte: int,
) -> list[ReasoningStep]:
    """Merge agent tool findings with the standard structuring pipeline steps."""
    steps: list[ReasoningStep] = [
        _step("Research Agent", f"Investigating {view.underlying} thesis before structuring…", 200),
    ]

    iv = enriched.get("get_iv_rank") or {}
    if iv and not iv.get("error"):
        steps.append(
            _step(
                "Research Agent",
                (
                    f"IV rank {iv.get('iv_rank')} — {iv.get('regime')} regime "
                    f"(30d RV {iv.get('current_rv_30d')}%)"
                ),
                900,
            ),
        )

    earnings = enriched.get("get_upcoming_earnings") or {}
    if earnings.get("estimated_next_earnings"):
        in_win = earnings.get("earnings_in_trade_window")
        steps.append(
            _step(
                "Research Agent",
                (
                    f"Earnings ~{earnings.get('estimated_next_earnings')} "
                    f"({'inside' if in_win else 'outside'} trade window)"
                ),
                1500,
            ),
        )

    news = enriched.get("get_news_sentiment") or {}
    if news.get("overall_sentiment"):
        steps.append(
            _step(
                "Research Agent",
                (
                    f"News sentiment: {news.get('overall_sentiment')} "
                    f"({news.get('headline_count', 0)} headlines)"
                ),
                2100,
            ),
        )

    inference = enriched.get("direction_inference") or {}
    if inference.get("inferred") and inference.get("direction"):
        reason = inference.get("reason") or "market data did not support a user-stated bias"
        steps.append(
            _step(
                "Research Agent",
                f"Inferred direction: {inference.get('direction')} — {reason}",
                2400,
            ),
        )

    em = enriched.get("get_expected_move") or {}
    if em.get("expected_move_pct") is not None:
        steps.append(
            _step(
                "Research Agent",
                (
                    f"Market expected move ±{em.get('expected_move_pct')}% "
                    f"(±${em.get('expected_move_dollar')}) over {em.get('dte', target_dte)}d"
                ),
                2700,
            ),
        )

    mag = enriched.get("calculate_magnitude") or {}
    calculated = enriched.get("magnitude") or mag.get("magnitude")
    if calculated:
        steps.append(
            _step(
                "Research Agent",
                f"Calculated magnitude: {calculated}",
                3300,
            ),
        )

    fit = enriched.get("assess_structure_fit") or {}
    rec = fit.get("recommended_structures") or []
    avoid = fit.get("structures_to_avoid") or []
    if rec:
        steps.append(
            _step(
                "Research Agent",
                f"Regime fit: {', '.join(r['structure'] for r in rec[:2])}",
                3900,
            ),
        )
    if avoid:
        steps.append(
            _step(
                "Research Agent",
                f"Filtered out: {', '.join(a['structure'] for a in avoid[:2])}",
                4500,
            ),
        )

    analysis = enriched.get("agent_analysis")
    if analysis:
        snippet = analysis.strip().split("\n")[0][:120]
        steps.append(_step("Research Agent", snippet, 5100))

    pipeline = build_analysis_reasoning_steps(
        view, snapshot, strategies, target_dte=target_dte
    )
    offset = 5800
    for s in pipeline[1:]:
        steps.append(_step(s.node, s.message, offset))
        offset += 650

    return steps
