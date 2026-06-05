"""Parse and derive stored research brief from agent analysis (no export-time LLM)."""

from __future__ import annotations

import re

from app.schemas.market_intel import MarketIntel
from app.schemas.research_brief import ResearchBrief
from app.schemas.research_report import ResearchReport

_STRUCTURE_CUTOFF = re.compile(
    r"\n\s*(?:\*{1,3}\s*)*(?:\*\*)?\s*"
    r"(?:Hypothetical|STRUCTURE\s+NOTES|Option\s+structure|"
    r"Recommended\s+Structures|Structures\s+to\s+Avoid|assess_structure_fit)",
    re.I,
)

_OPTIONS_JARGON = re.compile(
    r"\b(bull call spread|bear call|call diagonal|put diagonal|iron condor|"
    r"short premium|undefined.?risk|IV rank|implied vol|vol regime|theta|vega|"
    r"hypothetical structure)\b",
    re.I,
)

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


def sanitize_agent_brief_text(text: str) -> str:
    """Drop option-structure appendices the agent must not put in the export brief."""
    text = (text or "").strip()
    if not text:
        return ""
    cut = _STRUCTURE_CUTOFF.search(text)
    if cut:
        text = text[: cut.start()].strip()
    return text


def _truncate_sentences(text: str, max_sentences: int = 2) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    kept = [p.strip() for p in parts if p.strip()][:max_sentences]
    return " ".join(kept)


def _bottom_line_from_context(report: ResearchReport, intel: MarketIntel | None) -> str:
    view = report.parsed_view
    sym = view.underlying.upper()
    direction = (view.direction or "Neutral").lower()
    horizon = view.horizon_label or view.horizon

    business = ""
    sector_ctx = ""
    if intel and intel.sector:
        s = intel.sector
        if s.business_blurb:
            business = s.business_blurb
        elif s.industry:
            business = f"{sym} is in {s.industry}"
            if s.sector_name:
                business += f" ({s.sector_name})"
        if s.sector_name:
            sector_ctx = f"{s.sector_name} sector"

    if report.sentiment_headlines:
        tone = report.sentiment_headlines[0].tone or "mixed"
        sector_ctx = f"{sector_ctx} — headline tone {tone}".strip(" —")

    line1_bits = [b for b in [business, sector_ctx] if b]
    line1 = ". ".join(line1_bits) if line1_bits else f"{sym} is the focus for this thesis."
    if not line1.endswith("."):
        line1 += "."

    verdict = {
        "bullish": "supported",
        "bearish": "challenged",
        "neutral": "mixed",
    }.get(direction, "mixed")
    line2 = (
        f"A {direction} view over {horizon} looks {verdict} "
        f"based on tape and headlines — verify before acting."
    )
    return f"{line1} {line2}"


def _clean_bottom_line(
    line: str,
    report: ResearchReport,
    intel: MarketIntel | None,
) -> str:
    line = (line or "").strip()
    if not line or _OPTIONS_JARGON.search(line) or "hypothetical" in line.lower():
        return _bottom_line_from_context(report, intel)
    return _truncate_sentences(line, 2)


def parse_research_brief(text: str) -> ResearchBrief:
    """Parse agent final analysis into structured brief sections."""
    text = sanitize_agent_brief_text(text)
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
        s = intel.sector
        if s.business_blurb:
            stock = f"{s.business_blurb} {stock}"
        elif s.industry:
            stock = f"{sym} ({s.industry}) {stock}"
        if s.narrative:
            stock += f" {s.narrative}"
    mood = "Recent headline coverage is limited."
    if report.sentiment_headlines:
        h = report.sentiment_headlines[0]
        mood = f'Headlines lean {h.tone or "mixed"}; top story: "{h.title}".'
    if intel and intel.sector and intel.sector.sector_name:
        mood += f" Sector context: {intel.sector.sector_name}."
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
    bottom = _bottom_line_from_context(report, intel)
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
        bottom = _clean_bottom_line(parsed.bottom_line, report, intel)
        if not bottom and parsed.working_against:
            bottom = _clean_bottom_line(parsed.working_against[-1], report, intel)
        parsed = parsed.model_copy(update={"bottom_line": bottom})
        return parsed
    return fallback_research_brief(report, intel)
