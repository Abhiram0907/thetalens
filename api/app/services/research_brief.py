"""Parse and derive stored research brief from agent analysis (no export-time LLM)."""

from __future__ import annotations

import re

from app.schemas.market_intel import MarketIntel
from app.schemas.research_brief import ResearchBrief
from app.schemas.research_report import ResearchReport

_SECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("stock_doing", re.compile(r"1\.\s*WHAT'?S THE STOCK DOING\??", re.I)),
    ("mood", re.compile(r"2\.\s*WHAT'?S THE MOOD\??", re.I)),
    ("could_move", re.compile(r"3\.\s*WHAT COULD MOVE IT\??", re.I)),
    ("working_for", re.compile(r"4\.\s*WHAT'?S WORKING FOR THIS THESIS\??", re.I)),
    ("working_against", re.compile(r"5\.\s*WHAT'?S WORKING AGAINST IT\??", re.I)),
    ("bottom_line", re.compile(r"6\.\s*BOTTOM LINE", re.I)),
]

# Legacy agent headings → map into brief fields when numbered format missing
_LEGACY_SECTIONS: list[tuple[str, re.Pattern[str]]] = [
    ("stock_doing", re.compile(r"##\s*Executive summary", re.I)),
    ("mood", re.compile(r"##\s*News\s*&\s*directional alignment", re.I)),
    ("could_move", re.compile(r"##\s*Catalyst\s*&\s*earnings", re.I)),
    ("working_for", re.compile(r"##\s*Magnitude\s*&\s*expected move", re.I)),
    ("working_against", re.compile(r"##\s*Risks\s*&\s*caveats", re.I)),
]


def _extract_bullets(block: str) -> list[str]:
    items: list[str] = []
    for line in block.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^[-*•]\s+(.+)$", line)
        if m:
            items.append(m.group(1).strip())
        elif re.match(r"^\d+[.)]\s+", line):
            items.append(re.sub(r"^\d+[.)]\s+", "", line).strip())
    return items[:4]


def _parse_numbered_sections(text: str, patterns: list[tuple[str, re.Pattern[str]]]) -> dict[str, str]:
    sections: dict[str, str] = {}
    for i, (key, pattern) in enumerate(patterns):
        match = pattern.search(text)
        if not match:
            continue
        start = match.end()
        end = len(text)
        for j in range(i + 1, len(patterns)):
            nxt = patterns[j][1].search(text, start)
            if nxt:
                end = nxt.start()
                break
        sections[key] = text[start:end].strip()
    return sections


def parse_research_brief(text: str) -> ResearchBrief:
    """Parse agent final analysis into structured brief sections."""
    text = (text or "").strip()
    if not text:
        return ResearchBrief()

    sections = _parse_numbered_sections(text, _SECTION_PATTERNS)
    if not sections.get("stock_doing"):
        sections = _parse_numbered_sections(text, _LEGACY_SECTIONS)

    working_for = sections.get("working_for", "")
    working_against = sections.get("working_against", "")
    return ResearchBrief(
        stock_doing=sections.get("stock_doing", ""),
        mood=sections.get("mood", ""),
        could_move=sections.get("could_move", ""),
        working_for=_extract_bullets(working_for) if working_for else [],
        working_against=_extract_bullets(working_against) if working_against else [],
        bottom_line=sections.get("bottom_line", ""),
    )


def fallback_research_brief(
    report: ResearchReport,
    intel: MarketIntel | None,
) -> ResearchBrief:
    """Deterministic brief when agent text is missing or unparsed."""
    view = report.parsed_view
    sym = view.underlying.upper()
    stock = f"{sym} is at ${view.underlying_price:.2f}."
    if intel and intel.sector:
        stock += f" {intel.sector.narrative or ''}".strip()
    mood = "Recent headline coverage is limited."
    if report.sentiment_headlines:
        h = report.sentiment_headlines[0]
        mood = f'Headlines lean {h.tone or "mixed"}; top story: "{h.title}".'
    move = "Check the calendar for earnings and other scheduled events in your window."
    if intel and intel.catalysts:
        c = intel.catalysts[0]
        move = f"Recent item: {c.description} ({c.date})."
    pros = [f"You are {view.direction.lower()} over {view.horizon_label or view.horizon}."]
    cons: list[str] = []
    if report.thesis_risk_callout:
        cons.append(report.thesis_risk_callout)
    if intel and intel.macro:
        headwinds = [m for m in intel.macro if m.thesis_impact == "headwind"]
        if headwinds:
            cons.append(f"{headwinds[0].name} is a headwind: {headwinds[0].note}")
    bottom = (
        f"Your {view.direction.lower()} view on {sym} depends on whether recent tape "
        "and headlines keep cooperating through your horizon."
    )
    return ResearchBrief(
        stock_doing=stock,
        mood=mood,
        could_move=move,
        working_for=pros[:3],
        working_against=cons[:3] or ["Sentiment or macro could shift before your horizon ends."],
        bottom_line=bottom,
    )


def research_brief_from_agent_text(
    agent_text: str,
    report: ResearchReport,
    intel: MarketIntel | None = None,
) -> ResearchBrief:
    """Prefer parsed agent analysis; fall back to deterministic brief."""
    parsed = parse_research_brief(agent_text)
    if parsed.stock_doing or parsed.mood:
        if not parsed.bottom_line and parsed.working_against:
            parsed = parsed.model_copy(update={"bottom_line": parsed.working_against[-1]})
        return parsed
    return fallback_research_brief(report, intel)
