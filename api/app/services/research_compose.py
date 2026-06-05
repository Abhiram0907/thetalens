"""Compose research brief from structured facts (deterministic + optional LLM bottom line)."""

from __future__ import annotations

import re

from app.schemas.research_brief import ResearchBrief
from app.schemas.research_facts import ResearchFacts

_OPTIONS_JARGON = re.compile(
    r"\b(bull call|bear call|spread|diagonal|condor|premium|IV rank|implied vol|theta|vega)\b",
    re.I,
)


def _fmt_pct(value: float | None, *, signed: bool = True) -> str:
    if value is None:
        return "n/a"
    if signed:
        return f"{value:+.1f}%"
    return f"{value:.1f}%"


def _compose_stock_doing(f: ResearchFacts) -> str:
    parts: list[str] = []
    if f.business_blurb:
        parts.append(f.business_blurb)
    elif f.industry:
        line = f"{f.ticker} operates in {f.industry}"
        if f.sector_name:
            line += f" ({f.sector_name})"
        parts.append(line + ".")
    else:
        parts.append(f"{f.ticker} is the focus name for this thesis.")

    price_bit = f"{f.ticker} trades near ${f.price:,.2f}" if f.price else f"{f.ticker} price data is limited"
    tape_bits = [price_bit]
    if f.ytd_pct is not None and f.spy_ytd_pct is not None:
        tape_bits.append(f"{_fmt_pct(f.ytd_pct)} YTD vs SPY {_fmt_pct(f.spy_ytd_pct)}")
    if f.sector_etf_label and f.sector_etf_ytd_pct is not None:
        tape_bits.append(f"{f.sector_etf_label} {_fmt_pct(f.sector_etf_ytd_pct)} YTD")
    if f.sector_regime:
        tape_bits.append(f"sector posture: {f.sector_regime}")
    parts.append("; ".join(tape_bits) + ".")
    return " ".join(parts)


def _compose_mood(f: ResearchFacts) -> str:
    parts = [f.coverage_note]
    parts.append(f"News reads as {f.headline_focus}.")
    if f.sentiment_tone:
        score_bit = ""
        if f.sentiment_score is not None:
            score_bit = f" (score {f.sentiment_score:+.2f})"
        parts.append(f"Overall tone is {f.sentiment_tone}{score_bit}.")
    if f.sector_name:
        parts.append(f"Sector backdrop: {f.sector_name}.")
    if f.headlines:
        top = f.headlines[0]
        src = f" ({top.source})" if top.source else ""
        parts.append(f'Notable headline: "{top.title}"{src}.')
    return " ".join(parts)


def _compose_could_move(f: ResearchFacts) -> str:
    if f.next_earnings:
        window = ""
        if f.earnings_in_window is True:
            window = " — inside your trade window"
        elif f.earnings_in_window is False:
            window = " — outside your trade window"
        line = f"Next earnings estimated {f.next_earnings}{window}."
        if f.earnings_note:
            line += f" {f.earnings_note}"
        return line.strip()
    if f.catalysts:
        return f"Next items on the calendar: {f.catalysts[0]}."
    return "No major dated catalysts were found inside the horizon; tape may be driven by sector flow."


def _sentiment_aligns(f: ResearchFacts) -> bool | None:
    tone = f.sentiment_tone.lower()
    direction = f.direction.lower()
    if not tone:
        return None
    if direction == "bullish":
        return tone in ("bullish", "positive")
    if direction == "bearish":
        return tone in ("bearish", "negative")
    return tone == "neutral"


def _compose_working_for(f: ResearchFacts) -> list[str]:
    bullets: list[str] = []
    if f.ytd_pct is not None and f.spy_ytd_pct is not None:
        if f.direction.lower() == "bullish" and f.ytd_pct > f.spy_ytd_pct:
            bullets.append(
                f"Momentum favors bulls: {f.ticker} {_fmt_pct(f.ytd_pct)} YTD vs SPY {_fmt_pct(f.spy_ytd_pct)}."
            )
        elif f.direction.lower() == "bearish" and f.ytd_pct < f.spy_ytd_pct:
            bullets.append(
                f"Relative weakness supports a bearish read: {f.ticker} {_fmt_pct(f.ytd_pct)} vs SPY {_fmt_pct(f.spy_ytd_pct)}."
            )
    if f.sector_regime == "leading" and f.direction.lower() == "bullish":
        bullets.append("Sector tape is leading the broad market — a tailwind for bullish sector names.")
    if f.sector_regime == "lagging" and f.direction.lower() == "bearish":
        bullets.append("Sector is lagging SPY — aligns with a cautious or bearish stance.")
    aligned = _sentiment_aligns(f)
    if aligned is True:
        bullets.append(f"Headline tone ({f.sentiment_tone}) aligns with your {f.direction.lower()} view.")
    if f.macro_tailwinds:
        bullets.append(f.macro_tailwinds[0])
    if f.analyst_consensus and f.direction.lower() == "bullish":
        bullets.append(f"Street view: {f.analyst_consensus}")
    if not bullets:
        bullets.append(f"Your {f.direction.lower()} view over {f.horizon} is the anchor — tape is mixed.")
    return bullets[:3]


def _compose_working_against(f: ResearchFacts) -> list[str]:
    bullets: list[str] = []
    if f.thesis_risk:
        bullets.append(f.thesis_risk)
    aligned = _sentiment_aligns(f)
    if aligned is False:
        bullets.append(
            f"Headline tone ({f.sentiment_tone}) pushes against a {f.direction.lower()} thesis."
        )
    if f.earnings_in_window:
        bullets.append(
            f"Earnings around {f.next_earnings} adds gap risk through the {f.horizon} window."
        )
    if f.macro_headwinds:
        bullets.append(f.macro_headwinds[0])
    if f.headline_count < 3:
        bullets.append("Thin news coverage makes the name harder to read — surprises can dominate.")
    if f.ytd_pct is not None and f.ytd_pct > 40 and f.direction.lower() == "bullish":
        bullets.append(f"A {_fmt_pct(f.ytd_pct)} YTD run leaves less room for easy upside.")
    if f.peer_symbols:
        bullets.append(f"Peers to watch: {', '.join(f.peer_symbols[:3])}.")
    if not bullets:
        bullets.append("Macro or sentiment could shift before the horizon ends.")
    return bullets[:3]


def _compose_bottom_line_deterministic(f: ResearchFacts) -> str:
    business = f.business_blurb or (
        f"{f.ticker} in {f.industry}" if f.industry else f.ticker
    )
    sector_bit = ""
    if f.sector_name:
        sector_bit = f"{f.sector_name} is {f.sector_regime or 'mixed'}"
        if f.sector_etf_label and f.sector_etf_ytd_pct is not None:
            sector_bit += f" ({f.sector_etf_label} {_fmt_pct(f.sector_etf_ytd_pct)} YTD)"

    mood_bit = f"headlines are {f.sentiment_tone}"
    if f.headline_focus != "limited coverage":
        mood_bit += f" with {f.headline_focus}"

    line1_parts = [p for p in [business.rstrip("."), sector_bit, mood_bit] if p]
    line1 = ". ".join(line1_parts)
    if not line1.endswith("."):
        line1 += "."

    verdict = "supported"
    if _sentiment_aligns(f) is False:
        verdict = "stretched"
    elif f.earnings_in_window and f.direction.lower() != "neutral":
        verdict = "event-driven"
    elif f.sector_regime == "lagging" and f.direction.lower() == "bullish":
        verdict = "contrarian"
    elif f.sector_regime == "leading" and f.direction.lower() == "bearish":
        verdict = "contrarian"

    line2 = (
        f"A {f.direction.lower()} view over {f.horizon} looks {verdict} "
        f"on business and sector context — verify before acting."
    )
    return f"{line1} {line2}"


def compose_research_brief(facts: ResearchFacts, *, bottom_line: str | None = None) -> ResearchBrief:
    """Deterministic brief from structured facts."""
    bottom = (bottom_line or "").strip() or _compose_bottom_line_deterministic(facts)
    return ResearchBrief(
        stock_doing=_compose_stock_doing(facts),
        mood=_compose_mood(facts),
        could_move=_compose_could_move(facts),
        working_for=_compose_working_for(facts),
        working_against=_compose_working_against(facts),
        bottom_line=bottom,
    )


async def compose_research_brief_enriched(
    facts: ResearchFacts,
    *,
    use_llm_bottom: bool = True,
) -> ResearchBrief:
    """Compose brief; optionally polish bottom line with a focused LLM call."""
    bottom_line: str | None = None
    if use_llm_bottom:
        try:
            from app.llm.runtime import synthesize_bottom_line_llm

            bottom_line = await synthesize_bottom_line_llm(facts)
            if bottom_line and _OPTIONS_JARGON.search(bottom_line):
                bottom_line = None
        except Exception:
            bottom_line = None
    return compose_research_brief(facts, bottom_line=bottom_line)
