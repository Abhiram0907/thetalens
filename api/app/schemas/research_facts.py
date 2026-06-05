"""Structured facts assembled for research export (source of truth, not agent prose)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HeadlineFact(BaseModel):
    title: str
    tone: str = ""
    source: str = ""


class ResearchFacts(BaseModel):
    ticker: str
    direction: str = "Neutral"
    horizon: str = ""
    price: float = 0.0

    business_blurb: str = ""
    sector_name: str = ""
    industry: str = ""

    ytd_pct: float | None = None
    spy_ytd_pct: float | None = None
    sector_etf_label: str = ""
    sector_etf_ytd_pct: float | None = None
    sector_regime: str = ""

    sentiment_tone: str = ""
    sentiment_score: float | None = None
    headline_count: int = 0
    headlines: list[HeadlineFact] = Field(default_factory=list)
    headline_focus: str = ""
    coverage_note: str = ""

    next_earnings: str = ""
    earnings_in_window: bool | None = None
    earnings_note: str = ""

    catalysts: list[str] = Field(default_factory=list)
    macro_headwinds: list[str] = Field(default_factory=list)
    macro_tailwinds: list[str] = Field(default_factory=list)
    peer_symbols: list[str] = Field(default_factory=list)
    analyst_consensus: str = ""
    thesis_risk: str = ""
    expected_move_pct: float | None = None
