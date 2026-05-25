"""SSE streaming endpoints for the Trade Thesis Agent."""

from __future__ import annotations

from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agents.thesis_agent import AgentEvent, EventType, ThesisAgent
from app.config import get_settings
from app.core.disclaimer import DISCLAIMER_STANDARD
from app.core.security import LLM_UNAVAILABLE, UPSTREAM_UNAVAILABLE, safe_client_message
from app.llm_config import get_llm_config
from app.middleware.rate_limit import limiter
from app.services.market_data import MarketDataError, get_polygon_client
from app.tools.registry import PolygonClient

router = APIRouter(prefix="/api/agent", tags=["agent"])


class ThesisRequest(BaseModel):
    query: str = Field(..., max_length=4000, description="The user's natural-language trade thesis")
    underlying: str | None = None
    direction: str | None = None
    magnitude: str | None = None
    horizon: str | None = None
    risk_budget: str | None = None
    confidence: float | None = None
    summary: str | None = None


class ThesisResult(BaseModel):
    enriched_context: dict
    events: list[dict]


def _get_polygon_client() -> PolygonClient:
    settings = get_settings()
    if not settings.polygon_api_key:
        raise HTTPException(503, "POLYGON_API_KEY not configured")
    return PolygonClient(api_key=settings.polygon_api_key, base_url=settings.polygon_base_url)


def _get_agent(polygon: PolygonClient) -> ThesisAgent:
    cfg = get_llm_config()
    api_key = cfg.google_api_key or get_settings().google_api_key
    if not api_key:
        raise HTTPException(503, "GOOGLE_API_KEY not configured")

    import os

    model = (
        os.environ.get("AGENT_MODEL")
        or os.environ.get("GOOGLE_MODEL")
        or cfg.resolve_model(provider="gemini", alias="gemma-26b")
    )
    return ThesisAgent(
        polygon_client=polygon,
        llm_provider="google",
        model=model,
        api_key=api_key,
        temperature=cfg.provider.temperature,
    )


def _build_intent(req: ThesisRequest) -> dict:
    return {
        "query": req.query,
        "underlying": req.underlying or _extract_ticker(req.query),
        "direction": req.direction or "infer",
        "horizon": req.horizon or "30 days",
        "risk_budget": req.risk_budget or "not specified",
        "summary": req.summary or req.query,
    }


_NOISE_WORDS = {
    "I", "A", "AN", "THE", "AND", "OR", "FOR", "NOT", "TO", "IN", "ON",
    "IS", "IT", "MY", "OF", "AT", "IF", "DO", "SO", "UP", "BY", "AM",
    "BE", "NO", "AS", "BUT", "ALL", "MAX", "LOW", "HIGH", "OVER", "NEXT",
    "LIKE", "MOVE", "FIND", "WANT", "LOOK", "WEEK", "RISK", "SELL",
    "WITH", "THAT", "THIS", "WHAT", "WHEN", "WILL", "THAN", "FROM",
    "DOWN", "LONG", "TERM",
}


def _extract_ticker(query: str) -> str:
    import re
    dollar_m = re.search(r"\$([A-Z]{1,5})\b", query)
    if dollar_m:
        return dollar_m.group(1)
    for m in re.finditer(r"\b([A-Z]{1,5})\b", query):
        sym = m.group(1)
        if sym not in _NOISE_WORDS and len(sym) >= 2:
            return sym
    words = query.upper().split()
    for word in words:
        clean = word.strip(".,!?;:")
        if 2 <= len(clean) <= 5 and clean.isalpha() and clean not in _NOISE_WORDS:
            return clean
    return "SPY"


@router.post("/stream")
@limiter.limit("8/minute")
async def stream_thesis(request: Request, req: ThesisRequest):
    polygon = _get_polygon_client()
    agent = _get_agent(polygon)
    intent = _build_intent(req)
    settings = get_settings()

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for event in agent.run(intent):
                yield event.to_sse()

                if event.type == EventType.CONTEXT:
                    try:
                        payload = await _build_strategies(event.data)
                        yield AgentEvent(
                            type=EventType.STRATEGIES,
                            data=payload,
                        ).to_sse()
                    except Exception as e:
                        yield AgentEvent(
                            type=EventType.ERROR,
                            data={
                                "message": safe_client_message(
                                    e,
                                    default=UPSTREAM_UNAVAILABLE,
                                    dev_detail=not settings.is_production,
                                )
                            },
                        ).to_sse()
        except Exception as e:
            yield AgentEvent(
                type=EventType.ERROR,
                data={
                    "message": safe_client_message(
                        e,
                        default=LLM_UNAVAILABLE,
                        dev_detail=not settings.is_production,
                    )
                },
            ).to_sse()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/run", response_model=ThesisResult)
@limiter.limit("4/minute")
async def run_thesis(request: Request, req: ThesisRequest):
    settings = get_settings()
    if settings.is_production:
        raise HTTPException(status_code=404, detail="Not found")

    polygon = _get_polygon_client()
    agent = _get_agent(polygon)
    intent = _build_intent(req)

    events: list[dict] = []
    enriched: dict = {}
    async for event in agent.run(intent):
        events.append({"type": event.type.value, "data": event.data})
        if event.type == EventType.CONTEXT:
            enriched = event.data

    if enriched:
        try:
            payload = await _build_strategies(enriched)
            events.append({"type": "strategies", "data": payload})
        except Exception:
            pass

    return ThesisResult(enriched_context=enriched, events=events)


async def _build_strategies(enriched_context: dict) -> dict:
    from app.schemas.analysis import ParsedView
    from app.services.market_data import estimate_iv_rank
    from app.services.reasoning import build_agent_research_reasoning_steps
    from app.services.strategy_builder import build_strategies, parse_horizon_days

    ticker = enriched_context.get("ticker", "SPY").upper()
    direction_raw = str(enriched_context.get("direction", "neutral")).lower()
    direction_map = {
        "bullish": ("Bullish", "↑"),
        "bearish": ("Bearish", "↓"),
        "neutral": ("Neutral", "→"),
    }
    direction, direction_icon = direction_map.get(direction_raw, ("Neutral", "→"))

    horizon = enriched_context.get("horizon", "30 days")
    target_dte = parse_horizon_days(horizon)

    iv_data = enriched_context.get("get_iv_rank", {}) or {}
    fit_data = enriched_context.get("assess_structure_fit", {}) or {}
    earnings_data = enriched_context.get("get_upcoming_earnings", {}) or {}
    avoid = [s["structure"] for s in fit_data.get("structures_to_avoid", [])]

    rv_pct = iv_data.get("current_rv_30d")
    sigma = rv_pct / 100.0 if rv_pct and rv_pct > 0 else None

    try:
        client = get_polygon_client()
        snapshot = await client.load_snapshot(ticker, target_dte, sigma=sigma)
    except MarketDataError as exc:
        raise HTTPException(
            status_code=503,
            detail=UPSTREAM_UNAVAILABLE,
        ) from exc

    iv_regime = iv_data.get("regime", "Mid")
    if iv_data.get("error"):
        iv_rank, iv_label = estimate_iv_rank(snapshot.contracts, snapshot.spot)
    else:
        iv_rank = int(round(float(iv_data.get("iv_rank", 50))))
        iv_label = iv_regime

    horizon_display = horizon if "day" in horizon.lower() else f"{target_dte} days"

    mag_data = enriched_context.get("calculate_magnitude") or {}
    magnitude = (
        enriched_context.get("magnitude")
        or mag_data.get("magnitude")
        or "±5% range"
    )

    view = ParsedView(
        direction=direction,
        direction_icon=direction_icon,
        magnitude=magnitude,
        horizon=horizon_display,
        horizon_label=horizon,
        volatility_view=iv_regime,
        risk_budget=enriched_context.get("risk_budget", "not specified"),
        underlying=ticker,
        underlying_price=round(snapshot.spot, 2),
        iv_rank=iv_rank,
        iv_label=iv_label,
    )

    strategies = build_strategies(
        view,
        snapshot,
        iv_regime=iv_regime,
        earnings_in_window=earnings_data.get("earnings_in_trade_window", False),
        avoid_structures=avoid,
    )
    if not strategies and avoid:
        strategies = build_strategies(
            view,
            snapshot,
            iv_regime=iv_regime,
            earnings_in_window=earnings_data.get("earnings_in_trade_window", False),
            avoid_structures=[],
        )
    if not strategies and direction != "Neutral":
        neutral_view = view.model_copy(
            update={
                "direction": "Neutral",
                "direction_icon": "→",
                "magnitude": "±5% range",
            }
        )
        strategies = build_strategies(
            neutral_view,
            snapshot,
            iv_regime=iv_regime,
            earnings_in_window=earnings_data.get("earnings_in_trade_window", False),
            avoid_structures=[],
        )
        if strategies:
            view = neutral_view

    if not strategies:
        raise HTTPException(
            status_code=503,
            detail=f"Could not build strategies for {ticker} from chain data.",
        )

    steps = build_agent_research_reasoning_steps(
        enriched_context, view, snapshot, strategies, target_dte=target_dte
    )

    return {
        "strategies": [s.model_dump() for s in strategies],
        "parsed_view": view.model_dump(),
        "reasoning_steps": [s.model_dump() for s in steps],
        "underlying_price": view.underlying_price,
        "disclaimer": DISCLAIMER_STANDARD,
    }
