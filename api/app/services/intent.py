import re

from app.core.dependencies import get_intent_chain
from app.services.field_parser import parse_magnitude_text, parse_risk_budget_text
from app.services.strategy_builder import parse_horizon_days
from app.schemas.intent import IntentSlots
from app.schemas.analysis import (
    CapturedIntent,
    IntentResponse,
)

_NOISE_WORDS = {
    "I", "A", "AN", "THE", "AND", "OR", "FOR", "NOT", "TO", "IN", "ON",
    "IS", "IT", "MY", "OF", "AT", "IF", "DO", "SO", "UP", "BY", "AM",
    "BE", "NO", "AS", "BUT", "ALL", "CAN", "HAD", "HAS", "HER", "HIS",
    "HOW", "ITS", "MAY", "NEW", "NOW", "OLD", "OUR", "OUT", "OWN",
    "SAY", "SHE", "TOO", "USE", "WAY", "WHO", "DAY", "GET", "HIM",
    "LET", "PUT", "RUN", "SET", "TRY", "TWO", "WIN", "MAX", "LOW",
    "HIGH", "OVER", "NEXT", "LIKE", "MOVE", "FIND", "WANT", "LOOK",
    "WEEK", "RISK", "SELL", "WITH", "THAT", "THIS", "WHAT", "WHEN",
    "WILL", "THAN", "FROM", "THEM", "SOME", "JUST", "VERY", "ABOUT",
    "DOWN", "LONG", "TERM",
}

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


async def extract_intent_slots(query: str) -> IntentSlots:
    """Single LLM intent extraction (with regex fallback)."""
    q = query.strip()
    try:
        chain = get_intent_chain()
        return await chain.ainvoke({"query": q})
    except Exception:
        return _fallback_slots(q)


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
    labeled = _labeled(q, "underlying")
    if labeled:
        sym = labeled.upper().split()[0].replace("$", "")
        if re.fullmatch(r"[A-Z]{1,5}", sym):
            return sym
    company_map = {
        "nvidia": "NVDA",
        "apple": "AAPL",
        "tesla": "TSLA",
        "microsoft": "MSFT",
        "amazon": "AMZN",
        "meta": "META",
        "facebook": "META",
    }
    lower = q.lower()
    for name, sym in company_map.items():
        if name in lower:
            return sym
    for m in re.finditer(r"\$([A-Z]{1,5})\b", q):
        return m.group(1)
    for m in re.finditer(r"\b([A-Z]{1,5})\b", q):
        sym = m.group(1)
        if sym not in _NOISE_WORDS and len(sym) >= 2:
            return sym
    return None


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
    missing: list[str] = []
    confidence = max(slots.confidence, 70)
    summary = "Intent retrieved; the agent will infer direction and fill gaps from market data."

    return IntentResponse(
        is_clear=True,
        confidence=confidence,
        captured=captured,
        missing=missing,
        questions=[],
        summary=summary,
        clarify_reasoning_steps=[],
    )
