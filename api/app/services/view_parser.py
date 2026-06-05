import re

from app.schemas.analysis import ParsedView
from app.services.field_parser import parse_magnitude_text, parse_risk_budget_text
from app.services.ticker_resolver import resolve_underlying_explicit

DEFAULT_VIEW = ParsedView(
    direction="Bearish",
    direction_icon="↓",
    magnitude="-5% to -10%",
    horizon="21 days",
    horizon_label="3 weeks",
    volatility_view="Neutral",
    risk_budget="$500",
    underlying="NVDA",
    underlying_price=0.0,
    realized_vol_rank=50,
    realized_vol_regime="—",
    realized_vol_label="—",
    iv_rank=50,
    iv_label="—",
)


def _labeled(q: str, label: str) -> str | None:
    m = re.search(rf"{label}\s*:\s*([^\n.;]+)", q, re.I)
    return m.group(1).strip() if m else None


def _extract_ticker(q: str) -> str:
    return resolve_underlying_explicit(q) or DEFAULT_VIEW.underlying


def _extract_direction(q: str) -> tuple[str, str]:
    labeled = _labeled(q, "direction")
    if labeled:
        low = labeled.lower()
        if "bear" in low:
            return "Bearish", "↓"
        if "bull" in low:
            return "Bullish", "↑"
        if "neutral" in low:
            return "Neutral", "→"

    if re.search(r"\bdirection\s*:\s*neutral\b", q, re.I) or re.search(
        r"\bneutral\b", q, re.I
    ):
        if not re.search(r"\b(bearish|bullish)\b", q, re.I):
            return "Neutral", "→"
    if re.search(r"\b(bearish|down|lower|bleed|drop|fall|crash|fade|short)\b", q, re.I):
        if not re.search(r"\bdirection\s*:\s*neutral\b", q, re.I):
            return "Bearish", "↓"
    if re.search(r"\b(bullish|up|higher|rally|long)\b", q, re.I):
        return "Bullish", "↑"
    if re.search(r"\bneutral|range|sideways\b", q, re.I):
        return "Neutral", "→"
    return "Bearish", "↓"


def _extract_magnitude(q: str) -> str:
    labeled = _labeled(q, "magnitude")
    if labeled:
        return parse_magnitude_text(labeled)
    return parse_magnitude_text(q, default="Small (<5%)" if re.search(r"\bneutral\b", q, re.I) else "-5% to -10%")


def _extract_horizon(q: str) -> tuple[str, str]:
    labeled = _labeled(q, "horizon")
    if labeled:
        if re.search(r"\bleap", labeled, re.I):
            months = re.search(r"(\d+)\s*month", labeled, re.I)
            if months:
                n = int(months.group(1))
                return f"{n * 30} days", f"{n} months"
            return "180 days", "LEAPS"
        months = re.search(r"(\d+)\s*month", labeled, re.I)
        if months:
            n = int(months.group(1))
            return f"{n * 30} days", f"{n} months"
        if re.search(r"2\s*[-–]\s*3\s*week", labeled, re.I):
            return "21 days", "2–3 weeks"
        weeks = re.search(r"(\d+)\s*week", labeled, re.I)
        if weeks:
            n = int(weeks.group(1))
            return f"{n * 7} days", f"{n} weeks" if n != 1 else "1 week"
        return labeled, labeled

    if re.search(r"\bleap", q, re.I):
        months = re.search(r"(\d+)\s*month", q, re.I)
        if months:
            n = int(months.group(1))
            return f"{n * 30} days", f"{n} months"
        return "180 days", "LEAPS"
    months = re.search(r"(\d+)\s*month", q, re.I)
    if months:
        n = int(months.group(1))
        return f"{n * 30} days", f"{n} months"
    if re.search(r"2\s*[-–]\s*3\s*week", q, re.I):
        return "21 days", "2–3 weeks"
    weeks = re.search(r"(\d+)\s*week", q, re.I)
    if weeks:
        n = int(weeks.group(1))
        days = n * 7
        label = f"{n} week" if n == 1 else f"{n} weeks"
        return f"{days} days", label
    days = re.search(r"(\d+)\s*day", q, re.I)
    if days:
        n = int(days.group(1))
        return f"{n} days", f"{n} days"
    return "21 days", "3 weeks"


def _extract_risk_budget(q: str) -> str:
    labeled = _labeled(q, "risk budget") or _labeled(q, "risk_budget")
    if labeled:
        return parse_risk_budget_text(labeled)
    return parse_risk_budget_text(q)


def _extract_vol_view(q: str) -> str:
    if re.search(r"\b(high iv|elevated vol|vol crush|sell vol)\b", q, re.I):
        return "Bearish vol"
    if re.search(r"\b(low iv|cheap vol|buy vol)\b", q, re.I):
        return "Bullish vol"
    return "Neutral"


def parse_view(query: str) -> ParsedView:
    q = query.strip()
    underlying = _extract_ticker(q)
    direction, icon = _extract_direction(q)
    magnitude = _extract_magnitude(q)
    horizon, horizon_label = _extract_horizon(q)
    risk_budget = _extract_risk_budget(q)
    vol_view = _extract_vol_view(q)

    return ParsedView(
        direction=direction,
        direction_icon=icon,
        magnitude=magnitude,
        horizon=horizon,
        horizon_label=horizon_label,
        volatility_view=vol_view,
        risk_budget=risk_budget,
        underlying=underlying,
        underlying_price=0.0,
        realized_vol_rank=50,
        realized_vol_regime="—",
        realized_vol_label="—",
        iv_rank=50,
        iv_label="—",
    )
