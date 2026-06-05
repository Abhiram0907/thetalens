import re

from app.llm import parse_intent_slots
from app.services.field_parser import parse_magnitude_text, parse_risk_budget_text
from app.services.strategy_builder import parse_horizon_days
from app.services.ticker_resolver import resolve_underlying, resolve_underlying_ai
from app.schemas.intent import IntentSlots
from app.core.security import INTENT_UNRECOGNIZED
from app.schemas.analysis import (
    CapturedIntent,
    IntentResponse,
)

def slots_to_view_updates(slots: IntentSlots) -> dict:
    """Map intent slots to ParsedView fields (shared by analyze path)."""
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
    return updates


def slots_from_captured(captured: CapturedIntent) -> IntentSlots:
    direction = captured.direction
    if direction not in ("Bearish", "Bullish", "Neutral"):
        direction = None
    mode = captured.mode if captured.mode in ("thesis", "scanner") else "thesis"
    return IntentSlots(
        underlying=captured.underlying,
        direction=direction,
        magnitude=captured.magnitude,
        horizon=captured.horizon,
        risk_budget=captured.risk_budget,
        mode=mode,
        confidence=100,
        summary="",
    )


async def _fill_underlying(slots: IntentSlots, query: str) -> IntentSlots:
    if slots.underlying:
        return slots
    resolved = await resolve_underlying_ai(query)
    if resolved:
        return slots.model_copy(update={"underlying": resolved})
    return slots


async def extract_intent_slots(query: str) -> IntentSlots:
    """LLM intent extraction with AI ticker resolution and regex fallback."""
    q = query.strip()
    try:
        slots = await parse_intent_slots(q)
    except Exception:
        slots = _fallback_slots(q)
        return await _fill_underlying(slots, q)
    return await _fill_underlying(slots, q)


def _captured_from_slots(slots: IntentSlots) -> CapturedIntent:
    return CapturedIntent(
        underlying=slots.underlying,
        direction=slots.direction,
        magnitude=slots.magnitude,
        horizon=slots.horizon,
        risk_budget=slots.risk_budget,
        mode=slots.mode,
    )


def _labeled(q: str, label: str) -> str | None:
    m = re.search(rf"{label}\s*:\s*([^\n.;]+)", q, re.I)
    return m.group(1).strip() if m else None


def _fallback_underlying(q: str) -> str | None:
    return resolve_underlying(q)


def _fallback_direction(q: str) -> str | None:
    labeled = _labeled(q, "direction")
    target = labeled or q
    if re.search(r"\b(bearish|down|lower|drop|fall|pullback|bleed|short|puts?)\b", target, re.I):
        return "Bearish"
    if re.search(r"\b(bullish|up|higher|rally|gain|long|calls?)\b", target, re.I):
        return "Bullish"
    if re.search(r"\b(neutral|range|sideways|pin)\b", target, re.I):
        return "Neutral"
    return None


def _fallback_horizon(q: str) -> str | None:
    labeled = _labeled(q, "horizon")
    target = labeled or q
    if re.search(r"\bleap", target, re.I):
        m = re.search(r"(\d+)\s*months?", target, re.I)
        return f"{m.group(1)} months" if m else "6 months"
    m = re.search(r"(\d+)\s*[-–]\s*(\d+)\s*weeks?", target, re.I)
    if m:
        return f"{m.group(1)}–{m.group(2)} weeks"
    m = re.search(r"(\d+)\s*(days?|weeks?|months?|years?)", target, re.I)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return None


def _fallback_risk_budget(q: str) -> str | None:
    labeled = _labeled(q, "risk budget") or _labeled(q, "risk_budget")
    if labeled:
        return parse_risk_budget_text(labeled)
    if re.search(r"\bno\s+risk\b", q, re.I):
        return None
    if re.search(r"\b(risk|budget|lose|max loss|capital)\b|\$", q, re.I):
        parsed = parse_risk_budget_text(q, default="")
        return parsed or None
    return None


def _fallback_slots(query: str) -> IntentSlots:
    direction = _fallback_direction(query)
    slots = IntentSlots(
        underlying=_fallback_underlying(query),
        direction=direction,
        magnitude=None,
        horizon=_fallback_horizon(query),
        risk_budget=_fallback_risk_budget(query),
        confidence=0,
        summary="Parsed locally because the LLM is temporarily unavailable.",
    )
    slots.confidence = 100
    if not direction:
        slots.summary = "Intent retrieved; the agent will infer direction and fill gaps from market data."
    else:
        slots.summary = "Intent retrieved; ready for agent research."
    return slots




async def evaluate_intent(query: str) -> IntentResponse:
    slots = await extract_intent_slots(query)
    captured = _captured_from_slots(slots)

    if not captured.underlying:
        return IntentResponse(
            is_clear=False,
            confidence=0,
            captured=captured,
            missing=["underlying"],
            questions=[],
            summary=INTENT_UNRECOGNIZED,
            clarify_reasoning_steps=[],
        )

    confidence = max(slots.confidence, 70)
    summary = "Intent retrieved; the agent will infer direction and fill gaps from market data."

    return IntentResponse(
        is_clear=True,
        confidence=confidence,
        captured=captured,
        missing=[],
        questions=[],
        summary=summary,
        clarify_reasoning_steps=[],
    )
