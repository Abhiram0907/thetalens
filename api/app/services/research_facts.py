"""Assemble structured ResearchFacts from report, market intel, and agent tools."""

from __future__ import annotations

from typing import Any

from app.schemas.market_intel import MarketIntel
from app.schemas.research_facts import HeadlineFact, ResearchFacts
from app.schemas.research_report import ResearchReport, SentimentHeadline
from app.services.company_profile import headline_focus_label, profile_from_dict


def _headlines_from_report(report: ResearchReport, enriched: dict[str, Any]) -> list[HeadlineFact]:
    out: list[HeadlineFact] = []
    for h in report.sentiment_headlines:
        out.append(HeadlineFact(title=h.title, tone=h.tone, source=h.source))
    if out:
        return out

    news = enriched.get("get_news_sentiment") or {}
    raw = news.get("headlines") or news.get("sample_headlines") or []
    for h in raw[:5]:
        if isinstance(h, str):
            out.append(HeadlineFact(title=h))
        elif isinstance(h, dict):
            out.append(
                HeadlineFact(
                    title=h.get("title") or h.get("headline") or "",
                    tone=h.get("tone") or "",
                    source=h.get("source") or "",
                )
            )
    return [x for x in out if x.title.strip()]


def gather_research_facts(
    report: ResearchReport,
    intel: MarketIntel | None,
    enriched: dict[str, Any] | None = None,
) -> ResearchFacts:
    enriched = enriched or {}
    view = report.parsed_view
    sym = view.underlying.upper()
    profile = profile_from_dict(enriched.get("company_profile"))

    business_blurb = ""
    sector_name = ""
    industry = ""
    if profile:
        business_blurb = profile.business_blurb
        sector_name = profile.sector
        industry = profile.industry
    if intel and intel.sector:
        s = intel.sector
        business_blurb = business_blurb or s.business_blurb
        sector_name = sector_name or s.sector_name
        industry = industry or s.industry

    ytd_pct = spy_ytd = sector_etf_ytd_pct = None
    sector_etf_label = ""
    sector_regime = ""
    if intel and intel.sector:
        s = intel.sector
        ytd_pct = s.ticker_return_pct
        spy_ytd = s.benchmark_return_pct
        if s.sector_etfs:
            best = max(s.sector_etfs, key=lambda b: b.return_pct)
            sector_etf_label = best.label
            sector_etf_ytd_pct = best.return_pct
        if "leading" in s.narrative:
            sector_regime = "leading"
        elif "lagging" in s.narrative:
            sector_regime = "lagging"
        else:
            sector_regime = "in line with the market"

    news = enriched.get("get_news_sentiment") or {}
    headlines = _headlines_from_report(report, enriched)
    headline_titles = [h.title for h in headlines]
    count = news.get("headline_count") or len(headlines)
    tone = str(news.get("overall_sentiment") or "").strip()
    if not tone and headlines:
        tone = headlines[0].tone or "mixed"
    score = news.get("sentiment_score")
    sentiment_score = float(score) if isinstance(score, (int, float)) else None

    if count == 0:
        coverage = "Headline coverage is very limited."
    elif count < 3:
        coverage = "Headline coverage is thin."
    else:
        coverage = f"About {int(count)} recent headlines reviewed."

    earnings = enriched.get("get_upcoming_earnings") or {}
    next_earnings = str(earnings.get("estimated_next_earnings") or "").strip()
    in_window = earnings.get("earnings_in_trade_window")
    earnings_note = str(earnings.get("note") or "").strip()

    catalysts: list[str] = []
    if intel:
        for c in intel.catalysts[:3]:
            catalysts.append(f"{c.description} ({c.date})")
        if intel.catalysts_stale_note:
            catalysts.append(intel.catalysts_stale_note)

    macro_headwinds = [
        f"{m.name}: {m.note}" for m in (intel.macro if intel else []) if m.thesis_impact == "headwind"
    ]
    macro_tailwinds = [
        f"{m.name}: {m.note}" for m in (intel.macro if intel else []) if m.thesis_impact == "tailwind"
    ]

    peers = [p.symbol for p in (intel.peers if intel else [])[:5] if p.symbol != sym]
    analyst = ""
    if intel and intel.analyst and intel.analyst.consensus_rating != "—":
        analyst = intel.analyst.narrative or intel.analyst.consensus_rating

    em = enriched.get("get_expected_move") or {}
    expected_move = em.get("expected_move_pct")
    if isinstance(expected_move, (int, float)):
        expected_move = float(expected_move)
    else:
        expected_move = report.expected_move_pct

    return ResearchFacts(
        ticker=sym,
        direction=view.direction or "Neutral",
        horizon=view.horizon_label or view.horizon or "",
        price=report.underlying_price,
        business_blurb=business_blurb,
        sector_name=sector_name,
        industry=industry,
        ytd_pct=ytd_pct,
        spy_ytd_pct=spy_ytd,
        sector_etf_label=sector_etf_label,
        sector_etf_ytd_pct=sector_etf_ytd_pct,
        sector_regime=sector_regime,
        sentiment_tone=tone or "mixed",
        sentiment_score=sentiment_score,
        headline_count=int(count) if count else len(headlines),
        headlines=headlines,
        headline_focus=headline_focus_label(sym, headline_titles, industry),
        coverage_note=coverage,
        next_earnings=next_earnings,
        earnings_in_window=in_window if isinstance(in_window, bool) else None,
        earnings_note=earnings_note,
        catalysts=catalysts,
        macro_headwinds=macro_headwinds[:3],
        macro_tailwinds=macro_tailwinds[:3],
        peer_symbols=peers,
        analyst_consensus=analyst,
        thesis_risk=report.thesis_risk_callout or "",
        expected_move_pct=expected_move,
    )
