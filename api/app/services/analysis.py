from fastapi import HTTPException

from app.core.dependencies import get_intent_chain
from app.core.security import UPSTREAM_UNAVAILABLE
from app.schemas.analysis import AnalyzeResponse
from app.services.field_parser import parse_magnitude_text, parse_risk_budget_text
from app.services.data_provenance import build_data_provenance, build_vol_view_fields
from app.services.market_data import (
    MarketDataError,
    estimate_iv_rank,
    load_snapshot_cached,
)
from app.services.reasoning import build_analysis_reasoning_steps
from app.services.strategy_builder import build_strategies_resilient, parse_horizon_days
from app.services.view_parser import parse_view


async def _parse_view_from_query(query: str):
    view = parse_view(query)
    try:
        slots = await get_intent_chain().ainvoke({"query": query.strip()})
        updates: dict = {}
        if slots.underlying:
            updates["underlying"] = slots.underlying.upper()
        if slots.direction:
            icons = {"Bearish": "↓", "Bullish": "↑", "Neutral": "→"}
            updates["direction"] = slots.direction
            updates["direction_icon"] = icons.get(slots.direction, "→")
        if slots.magnitude:
            updates["magnitude"] = parse_magnitude_text(slots.magnitude)
        if slots.horizon:
            updates["horizon_label"] = slots.horizon
            days = parse_horizon_days(slots.horizon)
            updates["horizon"] = f"{days} days"
        if slots.risk_budget:
            updates["risk_budget"] = parse_risk_budget_text(slots.risk_budget)
        if updates:
            view = view.model_copy(update=updates)
    except Exception:
        pass
    return view


async def run_analysis(query: str) -> AnalyzeResponse:
    view = await _parse_view_from_query(query)
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

    return AnalyzeResponse(
        parsed_view=view,
        reasoning_steps=steps,
        strategies=strategies,
        underlying_price=view.underlying_price,
        data_provenance=data_provenance,
    )
