"""Structured market context for standalone research exports."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class YtdReturnBar(BaseModel):
    symbol: str
    label: str
    return_pct: float


class SectorPositioning(BaseModel):
    ticker_return_pct: float
    benchmark_return_pct: float
    benchmark_label: str = "SPY"
    sector_etfs: list[YtdReturnBar] = Field(default_factory=list)
    narrative: str = ""
    sector_name: str = ""
    industry: str = ""
    business_blurb: str = ""


class PeerRow(BaseModel):
    symbol: str
    ytd_return_pct: float | None = None
    iv_rank: float | None = None
    pe: str = "—"
    market_cap: str = "—"


class MacroIndicator(BaseModel):
    name: str
    value: str
    trend: str = ""
    thesis_impact: Literal["headwind", "tailwind", "neutral"] = "neutral"
    note: str = ""


class CatalystEvent(BaseModel):
    date: str
    description: str
    category: str = "news"


class FlowsSnapshot(BaseModel):
    lines: list[str] = Field(default_factory=list)


class SeasonalityNote(BaseModel):
    text: str


class VolTermPoint(BaseModel):
    label: str
    dte: int
    iv_pct: float


class VolTermStructure(BaseModel):
    points: list[VolTermPoint] = Field(default_factory=list)
    shape: str = "flat"
    narrative: str = ""


class AnalystConsensus(BaseModel):
    consensus_rating: str = "—"
    rating_score: float | None = None
    num_analysts: int | None = None
    target_mean: float | None = None
    target_high: float | None = None
    target_low: float | None = None
    current_price: float | None = None
    upside_to_mean_pct: float | None = None
    upside_to_high_pct: float | None = None
    downside_to_low_pct: float | None = None
    buy_count: int | None = None
    hold_count: int | None = None
    sell_count: int | None = None
    narrative: str = ""


class MarketIntel(BaseModel):
    sector: SectorPositioning | None = None
    peers: list[PeerRow] = Field(default_factory=list)
    macro: list[MacroIndicator] = Field(default_factory=list)
    catalysts: list[CatalystEvent] = Field(default_factory=list)
    catalysts_stale_note: str = ""
    flows: FlowsSnapshot | None = None
    seasonality: SeasonalityNote | None = None
    vol_term: VolTermStructure | None = None
    analyst: AnalystConsensus | None = None
