from typing import Literal

from pydantic import BaseModel, Field

class IntentSlots(BaseModel):
    underlying: str | None = None
    direction: Literal["Bearish", "Bullish", "Neutral"] | None = None
    magnitude: str | None = None
    horizon: str | None = None
    risk_budget: str | None = None
    mode: Literal["thesis", "scanner"] = "thesis"
    confidence: int = Field(ge=0, le=100)
    summary: str