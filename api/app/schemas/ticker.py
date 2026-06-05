from pydantic import BaseModel, Field


class TickerResolution(BaseModel):
    underlying: str | None = Field(
        default=None,
        description="US-listed equity or ETF ticker (1–5 uppercase letters), or null if none mentioned",
    )
