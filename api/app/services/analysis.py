from fastapi import HTTPException

from app.core.security import INTENT_UNRECOGNIZED, UPSTREAM_UNAVAILABLE
from app.schemas.analysis import AnalyzeResponse, CapturedIntent, ParsedView
from app.services.data_provenance import build_data_provenance, build_vol_view_fields
from app.services.intent import (
    extract_intent_slots,
    slots_from_captured,
    slots_to_view_updates,
)
from app.services.market_data import (
    MarketDataError,
    estimate_iv_rank,
    load_snapshot_cached,
)
from app.services.reasoning import build_analysis_reasoning_steps
from app.services.research_report_build import build_research_report_enriched
from app.services.strategy_builder import build_strategies_resilient, parse_horizon_days
from app.services.view_parser import parse_view


async def _parse_view_from_query(
    query: str,
    *,
    captured: CapturedIntent | None = None,
) -> ParsedView:
    if captured is not None:
        slots = slots_from_captured(captured)
    else:
        slots = await extract_intent_slots(query)
    if not slots.underlying:
        raise HTTPException(status_code=422, detail=INTENT_UNRECOGNIZED)

    view = parse_view(query)
    updates = slots_to_view_updates(slots)
    if updates:
        view = view.model_copy(update=updates)
    return view


async def run_analysis(
    query: str,
    *,
    captured: CapturedIntent | None = None,
) -> AnalyzeResponse:
    view = await _parse_view_from_query(query, captured=captured)
    target_dte = parse_horizon_days(view.horizon)

    try:
        snapshot = await load_snapshot_cached(view.underlying, target_dte)
    except MarketDataError as exc:
        raise HTTPException(status_code=503, detail=UPSTREAM_UNAVAILABLE) from exc

    fallback_rank, fallback_label = estimate_iv_rank(snapshot.contracts, snapshot.spot)
    vol_fields = build_vol_view_fields(
        None,
        fallback_rank=fallback_rank,
        fallback_label=fallback_label,
    )
    view = view.model_copy(
        update={
            "underlying_price": round(snapshot.spot, 2),
            **vol_fields,
        }
    )
    data_provenance = build_data_provenance(snapshot, sigma=None)

    strategies, view, _build_notes = build_strategies_resilient(view, snapshot)
    if not strategies:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Could not build strategies for {view.underlying} from chain data. "
                "Try widening the horizon, relaxing risk budget, or a more liquid ticker."
            ),
        )

    steps = build_analysis_reasoning_steps(
        view, snapshot, strategies, target_dte=target_dte
    )

    report = await build_research_report_enriched(
        parsed_view=view,
        strategies=strategies,
        reasoning_steps=steps,
        underlying_price=view.underlying_price,
        data_provenance=data_provenance,
        query=query,
        captured=captured,
    )

    return AnalyzeResponse(
        parsed_view=view,
        reasoning_steps=steps,
        strategies=strategies,
        underlying_price=view.underlying_price,
        data_provenance=data_provenance,
        research_report=report,
    )
