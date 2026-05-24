from app.schemas.analysis import (
    Leg,
    ReasoningStep,
    Strategy,
    StrategyGreeks,
    StrategyMetrics,
)

CURRENT_PRICE = 135.42


def build_reasoning_steps(
    view,
    *,
    front_label: str = "",
    back_label: str = "",
    contract_count: int = 0,
    strategy_count: int = 5,
) -> list[ReasoningStep]:
    v = view
    return [
        ReasoningStep(node="View Parser", message="Parsing natural language view…", delay=200),
        ReasoningStep(
            node="View Parser",
            message=f"Extracted: {v.direction} · {v.magnitude} · {v.horizon} horizon",
            delay=900,
        ),
        ReasoningStep(
            node="View Parser",
            message=(
                f"Vol view: {v.volatility_view} · Budget: {v.risk_budget} · "
                f"Underlying: {v.underlying} @ ${v.underlying_price:.2f}"
            ),
            delay=1500,
        ),
        ReasoningStep(
            node="Strategy Planner",
            message=f"Generating candidate structures for {v.direction.lower()} view…",
            delay=2400,
        ),
        ReasoningStep(
            node="Strategy Planner",
            message=(
                f"IV Rank check: {v.underlying} IV30 at {v.iv_label} — "
                "short-vol structures permitted, not preferred"
            ),
            delay=3100,
        ),
        ReasoningStep(
            node="Strategy Planner",
            message=f"Emitting {strategy_count} candidates from live chain…",
            delay=3800,
        ),
        ReasoningStep(
            node="Pricer",
            message=f"Fetching {v.underlying} chain — {front_label or 'front'} / {back_label or 'back'} expiries (Massive)…",
            delay=4600,
        ),
        ReasoningStep(
            node="Pricer",
            message=f"Chain loaded: {contract_count or '—'} contracts · mids from snapshot quotes",
            delay=5200,
        ),
        ReasoningStep(
            node="Pricer",
            message=f"Greeks from chain snapshot · S = ${v.underlying_price:.2f} · {v.iv_label}",
            delay=5700,
        ),
        ReasoningStep(
            node="Pricer",
            message=f"Monte Carlo: 10 000 GBM paths, {v.horizon} horizon — simulating P&L distributions",
            delay=6200,
        ),
        ReasoningStep(
            node="Critic",
            message="Ranking on EV / MaxLoss, theta efficiency, probability of profit…",
            delay=7100,
        ),
        ReasoningStep(
            node="Critic",
            message=f"⚠ 1×2 Ratio Put: undefined max loss — violates {v.risk_budget} risk budget",
            delay=7700,
        ),
        ReasoningStep(
            node="Critic",
            message="Bear Put Spread ranked #1: best EV/risk ($42.50 EV on $490 risk)",
            delay=8300,
        ),
        ReasoningStep(
            node="Synthesizer",
            message="Playbook complete — 4 of 5 structures satisfy all constraints",
            delay=9000,
        ),
    ]


def get_strategies() -> list[Strategy]:
    return [
        Strategy(
            rank=1,
            name="Bear Put Spread",
            tag="vertical",
            legs=[
                Leg(action="BUY", qty=1, type="PUT", strike=135, dte=21, premium=6.4, label="Jun 01 135P"),
                Leg(action="SELL", qty=1, type="PUT", strike=125, dte=21, premium=1.5, label="Jun 01 125P"),
            ],
            metrics=StrategyMetrics(
                max_gain=510,
                max_loss=490,
                breakevens=["130.10"],
                pop=38,
                ev=42.5,
                risk_reward="1.04",
            ),
            greeks=StrategyGreeks(delta=-0.28, theta=-2.15, vega=0.18, gamma=0.012),
            score=87,
            critique=(
                "Optimal risk/reward for a -5% to -10% move. Defined risk fits $500 budget with $10 margin. "
                "Highest expected value among candidates at $42.50."
            ),
            vs_next=(
                "Beats Put Diagonal on expected value ($42.50 vs $38.20) and directional sensitivity "
                "(Δ -0.28 vs -0.22)."
            ),
        ),
        Strategy(
            rank=2,
            name="Put Diagonal",
            tag="diagonal",
            legs=[
                Leg(
                    action="BUY",
                    qty=1,
                    type="PUT",
                    strike=130,
                    dte=42,
                    premium=5.2,
                    label="Jun 22 130P",
                    back_month=True,
                ),
                Leg(action="SELL", qty=1, type="PUT", strike=125, dte=21, premium=1.0, label="Jun 01 125P"),
            ],
            metrics=StrategyMetrics(
                max_gain=680,
                max_loss=420,
                breakevens=["128.80"],
                pop=42,
                ev=38.2,
                risk_reward="1.62",
            ),
            greeks=StrategyGreeks(delta=-0.22, theta=1.4, vega=0.32, gamma=0.008),
            score=82,
            critique="Positive theta earns $1.40/day while position works. Higher PoP at 42%.",
            vs_next="Beats BWB on probability of profit (42% vs 35%) and theta profile.",
        ),
        Strategy(
            rank=3,
            name="Broken-Wing Butterfly",
            tag="butterfly",
            legs=[
                Leg(action="BUY", qty=1, type="PUT", strike=135, dte=21, premium=6.4, label="Jun 01 135P"),
                Leg(action="SELL", qty=2, type="PUT", strike=128, dte=21, premium=2.8, label="Jun 01 128P"),
                Leg(action="BUY", qty=1, type="PUT", strike=124, dte=21, premium=1.15, label="Jun 01 124P"),
            ],
            metrics=StrategyMetrics(
                max_gain=705,
                max_loss=195,
                breakevens=["134.05", "124.95"],
                pop=35,
                ev=31.6,
                risk_reward="3.62",
            ),
            greeks=StrategyGreeks(delta=-0.15, theta=0.85, vega=0.12, gamma=0.015),
            score=76,
            critique="Best risk/reward ratio (3.62) and lowest max loss ($195).",
            vs_next="Beats Put Calendar on max gain ($705 vs $340) and risk/reward.",
        ),
        Strategy(
            rank=4,
            name="Put Calendar Spread",
            tag="calendar",
            legs=[
                Leg(action="SELL", qty=1, type="PUT", strike=130, dte=21, premium=3.8, label="Jun 01 130P"),
                Leg(
                    action="BUY",
                    qty=1,
                    type="PUT",
                    strike=130,
                    dte=42,
                    premium=5.2,
                    label="Jun 22 130P",
                    back_month=True,
                ),
            ],
            metrics=StrategyMetrics(
                max_gain=340,
                max_loss=140,
                breakevens=["126.40", "133.80"],
                pop=48,
                ev=22.8,
                risk_reward="2.43",
            ),
            greeks=StrategyGreeks(delta=-0.08, theta=3.2, vega=0.45, gamma=0.003),
            score=68,
            critique="Highest PoP (48%) and best theta ($3.20/day). Conservative, income-oriented play.",
            vs_next="Beats Ratio Put on risk profile — defined max loss ($140) vs unlimited.",
        ),
        Strategy(
            rank=5,
            name="1×2 Ratio Put Spread",
            tag="ratio",
            legs=[
                Leg(action="BUY", qty=1, type="PUT", strike=135, dte=21, premium=6.4, label="Jun 01 135P"),
                Leg(action="SELL", qty=2, type="PUT", strike=125, dte=21, premium=1.5, label="Jun 01 125P"),
            ],
            metrics=StrategyMetrics(
                max_gain=660,
                max_loss="∞",
                breakevens=["134.60", "115.40"],
                pop=33,
                ev=28.4,
                risk_reward="N/A",
            ),
            greeks=StrategyGreeks(delta=-0.35, theta=0.5, vega=-0.08, gamma=0.018),
            score=52,
            warning="Undefined max loss below $115.40 violates $500 risk budget",
            critique="Near-zero cost entry with strong directional exposure. Included for comparison only.",
            vs_next=None,
        ),
    ]
