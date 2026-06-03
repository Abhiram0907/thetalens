from typing import Literal

from pydantic import BaseModel, Field

from app.core.disclaimer import DISCLAIMER_STANDARD


class FollowUpOption(BaseModel):
    value: str
    label: str


class FollowUpQuestion(BaseModel):
    id: str
    label: str
    prompt: str
    type: Literal["select", "text"]
    options: list[FollowUpOption] | None = None
    placeholder: str | None = None


class CapturedIntent(BaseModel):
    underlying: str | None = None
    direction: str | None = None
    magnitude: str | None = None
    horizon: str | None = None
    risk_budget: str | None = None
    mode: str = "thesis"


class IntentRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)


class IntentResponse(BaseModel):
    is_clear: bool
    confidence: int
    captured: CapturedIntent
    missing: list[str]
    questions: list[FollowUpQuestion]
    summary: str
    clarify_reasoning_steps: list["ReasoningStep"]


class AnalyzeRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    captured: CapturedIntent | None = None


class DataProvenance(BaseModel):
    spot_source: Literal["yfinance", "polygon"]
    spot_as_of: str | None = None
    options_price_method: Literal["black_scholes_modeled"] = "black_scholes_modeled"
    vol_input: Literal["realized_30d", "implied", "default"]
    data_age_warning: str | None = None


class ParsedView(BaseModel):
    direction: str
    direction_icon: str
    magnitude: str
    horizon: str
    horizon_label: str
    volatility_view: str
    risk_budget: str
    underlying: str
    underlying_price: float
    realized_vol_rank: int
    realized_vol_regime: str
    realized_vol_label: str
    iv_rank: int
    iv_label: str


class ReasoningStep(BaseModel):
    node: str
    message: str
    delay: int


class Leg(BaseModel):
    action: Literal["BUY", "SELL"]
    qty: int
    type: Literal["PUT", "CALL"]
    strike: float
    dte: int
    premium: float
    label: str
    back_month: bool = False


class StrategyMetrics(BaseModel):
    max_gain: float | str
    max_loss: float | str
    breakevens: list[str]
    pop: int
    ev: float
    risk_reward: str


class StrategyGreeks(BaseModel):
    delta: float
    theta: float
    vega: float
    gamma: float


class LiquidityProfile(BaseModel):
    score: int
    label: str
    quote_quality: str
    spread_warnings: list[str] = []


class TradeQuality(BaseModel):
    verdict: Literal["Tradeable", "Caution", "Avoid"]
    score: int
    reasons: list[str]


class ScenarioPoint(BaseModel):
    label: str
    underlying_price: float
    pnl: float


class ManagementRule(BaseModel):
    label: str
    detail: str


class Strategy(BaseModel):
    rank: int
    name: str
    tag: str
    legs: list[Leg]
    metrics: StrategyMetrics
    greeks: StrategyGreeks
    score: int
    critique: str
    vs_next: str | None
    warning: str | None = None
    liquidity: LiquidityProfile | None = None
    trade_quality: TradeQuality | None = None
    scenarios: list[ScenarioPoint] = []
    management_rules: list[ManagementRule] = []
    education: list[str] = []


class AnalyzeResponse(BaseModel):
    parsed_view: ParsedView
    reasoning_steps: list[ReasoningStep]
    strategies: list[Strategy]
    underlying_price: float
    data_provenance: DataProvenance
    disclaimer: str = Field(default=DISCLAIMER_STANDARD)
