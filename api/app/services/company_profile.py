"""Company profile grounding for research and agent context."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from app.tools.providers import get_yfinance_client


class CompanyProfile(BaseModel):
    ticker: str
    sector: str = ""
    industry: str = ""
    business_blurb: str = ""
    market_cap: str = ""


def _trim_blurb(text: str, max_len: int = 280) -> str:
    text = text.strip()
    if len(text) <= max_len:
        return text
    cut = text[: max_len - 3].rsplit(" ", 1)[0]
    return cut + "..."


async def fetch_company_profile(ticker: str) -> CompanyProfile:
    sym = ticker.upper().strip()
    try:
        info = await get_yfinance_client().ticker_info(sym)
    except Exception:
        info = {}

    sector = (info.get("sector") or "").strip()
    industry = (info.get("industry") or "").strip()
    raw = (info.get("longBusinessSummary") or "").strip()
    blurb = _trim_blurb(raw) if raw else ""
    if not blurb and industry:
        blurb = f"{sym} operates in {industry}"
        if sector:
            blurb += f" ({sector})"

    cap = info.get("marketCap")
    market_cap = ""
    if isinstance(cap, (int, float)) and cap >= 1_000_000_000:
        market_cap = f"${cap / 1_000_000_000:.1f}B"
    elif isinstance(cap, (int, float)) and cap >= 1_000_000:
        market_cap = f"${cap / 1_000_000:.0f}M"

    return CompanyProfile(
        ticker=sym,
        sector=sector,
        industry=industry,
        business_blurb=blurb,
        market_cap=market_cap,
    )


def profile_from_dict(data: dict | None) -> CompanyProfile | None:
    if not data or not data.get("ticker"):
        return None
    return CompanyProfile.model_validate(data)


def headline_focus_label(ticker: str, headlines: list[str], industry: str = "") -> str:
    """Classify whether news is company-specific or sector-themed."""
    if not headlines:
        return "limited coverage"
    sym = ticker.upper()
    tokens = {sym.lower(), sym}
    if industry:
        for word in re.findall(r"[a-z]{4,}", industry.lower()):
            tokens.add(word)
    company_hits = 0
    for title in headlines:
        lower = title.lower()
        if sym.lower() in lower or any(t in lower for t in tokens if len(t) > 3):
            company_hits += 1
    ratio = company_hits / len(headlines)
    if ratio >= 0.5:
        return "mostly company-specific"
    if ratio >= 0.2:
        return "mix of company and sector headlines"
    return "mostly sector or thematic headlines"
