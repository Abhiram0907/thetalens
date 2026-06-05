"""Plain-language research brief sections (stored from agent analysis)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ResearchBrief(BaseModel):
    stock_doing: str = ""
    mood: str = ""
    could_move: str = ""
    working_for: list[str] = Field(default_factory=list)
    working_against: list[str] = Field(default_factory=list)
    bottom_line: str = ""


class BottomLineResult(BaseModel):
    bottom_line: str = ""
