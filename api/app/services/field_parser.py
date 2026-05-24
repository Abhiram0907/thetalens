"""Parse natural-language risk budget and magnitude from user text."""

from __future__ import annotations

import re

_WORD_ONES = {
    "a": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}
_WORD_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50}


def _words_to_number(text: str) -> int | None:
    t = text.lower().strip()
    if t in ("grand", "g"):
        return 1000
    if t == "half":
        return 500
    if t in _WORD_ONES:
        return _WORD_ONES[t]
    m = re.match(r"(twenty|thirty|forty|fifty)\s*(one|two|three|four|five|six|seven|eight|nine)?", t)
    if m:
        base = _WORD_TENS[m.group(1)]
        extra = _WORD_ONES.get(m.group(2), 0) if m.group(2) else 0
        return base + extra
    if t in _WORD_TENS:
        return _WORD_TENS[t]
    return None


def parse_risk_budget_text(text: str, *, default: str = "$500") -> str:
    """Normalize any NL risk-budget phrase to a $X,XXX string."""
    raw = text.strip()
    if not raw:
        return default

    labeled = re.search(
        r"(?:risk\s*budget|max(?:imum)?\s*(?:loss|risk)|capital\s*at\s*risk|willing\s*to\s*lose)"
        r"\s*:?\s*(.+)$",
        raw,
        re.I,
    )
    if labeled:
        raw = labeled.group(1).strip()

    m = re.search(
        r"(?:up\s*to|at\s*most|max(?:imum)?|no\s*more\s*than|willing\s*to\s*(?:lose|risk)?)\s*"
        r"\$?\s*([\d,]+(?:\.\d+)?)\s*(k|grand|g)?",
        raw,
        re.I,
    )
    if m:
        return _amount_from_match(m.group(1), m.group(2))

    m = re.search(r"\$\s*([\d,]+(?:\.\d+)?)\s*(k|grand|g)?", raw, re.I)
    if m:
        return _amount_from_match(m.group(1), m.group(2))

    m = re.search(r"\b([\d,]+(?:\.\d+)?)\s*(k|grand|g)\b", raw, re.I)
    if m:
        return _amount_from_match(m.group(1), m.group(2))

    m = re.search(r"\b([\d,]+)\s*(?:dollars?|bucks?|usd)\b", raw, re.I)
    if m:
        return _amount_from_match(m.group(1), None)

    m = re.search(r"\b([\d,]{2,})\b", raw)
    if m:
        val = int(m.group(1).replace(",", ""))
        if 50 <= val <= 500_000:
            return f"${val:,}"

    half = re.search(r"\bhalf\s*a?\s*grand\b", raw, re.I)
    if half:
        return "$500"

    for phrase, amount in (("grand", 1000), ("two fifty", 250)):
        if phrase in raw.lower():
            return f"${amount:,}"

    return raw if raw.startswith("$") else default


def _amount_from_match(num: str, suffix: str | None) -> str:
    val = float(num.replace(",", ""))
    if suffix and suffix.lower() in ("k", "grand", "g"):
        val *= 1000
    return f"${int(round(val)):,}"


def parse_magnitude_text(text: str, *, default: str = "-5% to -10%") -> str:
    """Preserve or normalize NL magnitude; do not force dropdown buckets only."""
    raw = text.strip()
    if not raw:
        return default

    labeled = re.search(
        r"magnitude\s*:?\s*(.+)$",
        raw,
        re.I,
    )
    if labeled:
        raw = labeled.group(1).strip()

    if re.search(r"small\s*[<(]?\s*5\s*%|small\s+move|slight\s+move", raw, re.I):
        return "Small (<5%)"

    bearish = bool(re.search(r"\b(down|drop|fall|lower|decline|pullback|bleed)\b", raw, re.I))
    bullish = bool(re.search(r"\b(up|rally|rise|higher|gain)\b", raw, re.I))

    pct_range = re.search(
        r"(-?\d+(?:\.\d+)?)\s*%?\s*[-–to]+\s*(-?\d+(?:\.\d+)?)\s*%",
        raw,
        re.I,
    )
    if pct_range:
        a, b = float(pct_range.group(1)), float(pct_range.group(2))
        if a > 0 and b > 0 and bearish and not bullish:
            return f"-{a:g}% to -{b:g}%"
        if a > 0 and b > 0 and bullish and not bearish:
            return f"+{a:g}% to +{b:g}%"
        return f"{pct_range.group(1)}% to {pct_range.group(2)}%"

    single = re.search(r"(-?\d+(?:\.\d+)?)\s*%", raw)
    if single:
        v = float(single.group(1))
        if v < 0 or (v > 0 and bearish and not bullish):
            base = abs(v)
            return f"-{base:g}% to -{base + 5:g}%"
        if v > 0 and bullish and not bearish:
            return f"+{v:g}% to +{v + 5:g}%"
        if v < 0:
            return f"{v:g}% to {v - 5:g}%"
        return f"+{v:g}% to +{v + 5:g}%"

    if re.search(r"\bmoderate\b", raw, re.I):
        return "-5% to -10%"
    if re.search(r"\bsharp|big|large|crash\b", raw, re.I):
        return "-10% to -20%"
    if re.search(r"\bneutral|range|sideways|pinning\b", raw, re.I):
        return "Small (<5%)"

    # Keep free-form NL phrasing (e.g. "about a 7% pullback")
    if len(raw) >= 3:
        return raw

    return default
