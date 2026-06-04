"""Structured research report built at inference time."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.core.disclaimer import DISCLAIMER_STANDARD
from app.schemas.analysis import (
    CapturedIntent,
    DataProvenance,
    ParsedView,
    ReasoningStep,
    Strategy,
)
from app.schemas.market_intel import MarketIntel
from app.schemas.research_brief import ResearchBrief


class ReportSection(BaseModel):
    title: str
    body: str


class ToolFinding(BaseModel):
    tool: str
    summary: str
    details: list[str] = Field(default_factory=list)


class SentimentHeadline(BaseModel):
    title: str
    published: str = ""
    source: str = ""
    tone: str = ""


class ResearchReport(BaseModel):
    generated_at: datetime
    query: str | None = None
    captured: CapturedIntent | None = None
    executive_summary: str
    thesis_interpretation: str
    market_context: list[ReportSection] = Field(default_factory=list)
    tool_findings: list[ToolFinding] = Field(default_factory=list)
    agent_narrative: str | None = None
    risks_and_caveats: list[str] = Field(default_factory=list)
    synthesis: str = ""
    parsed_view: ParsedView
    reasoning_steps: list[ReasoningStep] = Field(default_factory=list)
    strategies: list[Strategy] = Field(default_factory=list)
    underlying_price: float
    data_provenance: DataProvenance
    disclaimer: str = Field(default=DISCLAIMER_STANDARD)
    shareable_line: str = ""
    thesis_risk_callout: str | None = None
    vol_context_line: str = ""
    data_as_of_display: str = ""
    expected_move_pct: float | None = None
    expected_move_dollars: float | None = None
    sentiment_headlines: list[SentimentHeadline] = Field(default_factory=list)
    market_intel: MarketIntel | None = None
    so_what_box: str | None = None
    research_brief: ResearchBrief | None = None

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_brief(cls, data: object) -> object:
        if isinstance(data, dict) and data.get("beginner_brief") and not data.get("research_brief"):
            data = dict(data)
            data["research_brief"] = data.pop("beginner_brief")
        return data
