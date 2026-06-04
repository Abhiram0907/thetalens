"""Export request schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.analysis import (
    CapturedIntent,
    DataProvenance,
    ParsedView,
    ReasoningStep,
    Strategy,
)
from app.schemas.research_report import ResearchReport


class ExportRequest(BaseModel):
    """Client sends the inference payload; server renders HTML or returns JSON report."""

    format: Literal["html", "json"] = "html"
    query: str | None = Field(None, max_length=4000)
    captured: CapturedIntent | None = None
    parsed_view: ParsedView
    reasoning_steps: list[ReasoningStep] = Field(default_factory=list)
    strategies: list[Strategy] = Field(default_factory=list)
    underlying_price: float
    data_provenance: DataProvenance
    enriched_context: dict | None = None
    research_report: ResearchReport | None = None
