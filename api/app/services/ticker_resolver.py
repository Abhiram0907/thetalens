"""Resolve equity/ETF tickers from natural-language queries."""

from __future__ import annotations

import re

TICKER_RE = re.compile(r"\b([A-Z]{1,5})\b")
DOLLAR_TICKER_RE = re.compile(r"\$([A-Z]{1,5})\b")

_NOISE_WORDS = frozenset({
    "I", "A", "AN", "THE", "AND", "OR", "FOR", "NOT", "TO", "IN", "ON",
    "IS", "IT", "MY", "OF", "AT", "IF", "DO", "SO", "UP", "BY", "AM",
    "BE", "NO", "AS", "BUT", "ALL", "CAN", "HAD", "HAS", "HER", "HIS",
    "HOW", "ITS", "MAY", "NEW", "NOW", "OLD", "OUR", "OUT", "OWN",
    "SAY", "SHE", "TOO", "USE", "WAY", "WHO", "DAY", "GET", "HIM",
    "LET", "PUT", "RUN", "SET", "TRY", "TWO", "WIN", "MAX", "LOW",
    "HIGH", "OVER", "NEXT", "LIKE", "MOVE", "FIND", "WANT", "LOOK",
    "WEEK", "RISK", "SELL", "WITH", "THAT", "THIS", "WHAT", "WHEN",
    "WILL", "THAN", "FROM", "THEM", "SOME", "JUST", "VERY", "ABOUT",
    "DOWN", "LONG", "TERM", "BULL", "BEAR", "BULLISH", "BEARISH", "NEUTRAL",
})

_TRADING_CONTEXT_RE = re.compile(
    r"\b(bullish|bearish|neutral|calls?|puts?|options?|stocks?|earnings|"
    r"weeks?|months?|days?|years?|risk|budget|leaps?|trade|ticker|symbol|\$)\b",
    re.I,
)


def _labeled(q: str, label: str) -> str | None:
    m = re.search(rf"{label}\s*:\s*([^\n.;]+)", q, re.I)
    return m.group(1).strip() if m else None


def _from_dollar_or_caps(q: str) -> str | None:
    dollar_m = DOLLAR_TICKER_RE.search(q)
    if dollar_m:
        return dollar_m.group(1)
    for m in TICKER_RE.finditer(q):
        sym = m.group(1)
        if sym not in _NOISE_WORDS and len(sym) >= 2:
            return sym
    return None


def _from_short_words(q: str) -> str | None:
    """Pick a 2–5 letter token that looks like a ticker (after uppercasing)."""
    if not _TRADING_CONTEXT_RE.search(q):
        return None
    for word in q.upper().split():
        clean = word.strip(".,!?;:")
        if (
            2 <= len(clean) <= 5
            and clean.isalpha()
            and clean not in _NOISE_WORDS
        ):
            return clean
    return None


def resolve_underlying_explicit(query: str) -> str | None:
    """Fast deterministic resolution for labeled fields, $TICKER, and caps symbols."""
    q = query.strip()
    if not q:
        return None

    labeled = _labeled(q, "underlying")
    if labeled:
        sym = labeled.upper().split()[0].replace("$", "")
        if re.fullmatch(r"[A-Z]{1,5}", sym):
            return sym

    caps = _from_dollar_or_caps(q)
    if caps:
        return caps

    return _from_short_words(q)


def resolve_underlying(query: str) -> str | None:
    """Sync resolver (explicit patterns only). Use resolve_underlying_ai at inference."""
    return resolve_underlying_explicit(query)


async def resolve_underlying_ai(query: str) -> str | None:
    """Resolve ticker at inference: explicit symbols first, then focused LLM."""
    explicit = resolve_underlying_explicit(query)
    if explicit:
        return explicit

    try:
        from app.llm.runtime import resolve_ticker_llm

        return await resolve_ticker_llm(query)
    except Exception:
        return None


