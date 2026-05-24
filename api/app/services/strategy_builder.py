"""Build ranked strategies from live chain data."""

from __future__ import annotations

import re
from datetime import date

from app.schemas.analysis import (
    Leg,
    LiquidityProfile,
    ManagementRule,
    ParsedView,
    ScenarioPoint,
    Strategy,
    StrategyGreeks,
    StrategyMetrics,
    TradeQuality,
)
from app.services.greeks import aggregate_strategy_greeks
from app.services.market_data import MarketSnapshot
from app.services.pricer import (
    contract_to_leg,
    round_strike,
    select_expiries,
    _pick_contract,
)


def parse_horizon_days(horizon: str) -> int:
    h = horizon.lower()
    m = re.search(r"(\d+)", h)
    n = int(m.group(1)) if m else None

    if "leap" in h:
        return n * 30 if n else 180
    if "month" in h or re.search(r"\bmo\b", h):
        return (n or 1) * 30
    if "week" in h or re.search(r"\bw\b", h):
        return (n or 1) * 7
    if "year" in h or re.search(r"\byr\b", h):
        return (n or 1) * 365
    return n if n else 21


def parse_risk_budget(risk_budget: str) -> float:
    if not risk_budget or risk_budget.lower() in ("not specified", "none", "n/a", "any", "—"):
        return 100_000.0
    from app.services.field_parser import parse_risk_budget_text

    normalized = parse_risk_budget_text(risk_budget)
    m = re.search(r"[\d,]+", normalized.replace(",", ""))
    return float(m.group(0)) if m else 100_000.0


def _payoff_at_expiry(legs: list[Leg], spot_price: float, at_front: bool = True) -> float:
    pnl = 0.0
    for leg in legs:
        sign = 1.0 if leg.action == "BUY" else -1.0
        if leg.type == "PUT":
            intrinsic = max(leg.strike - spot_price, 0.0)
        else:
            intrinsic = max(spot_price - leg.strike, 0.0)
        if leg.back_month and at_front:
            tv = leg.premium * 0.45
            value = intrinsic + tv
        else:
            value = intrinsic
        pnl += sign * leg.qty * (value - leg.premium) * 100
    return pnl


def _scan_payoff(
    legs: list[Leg], center: float, half: float = 0.22
) -> tuple[float, float, list[float]]:
    lo, hi = center * (1 - half), center * (1 + half)
    points: list[tuple[float, float]] = []
    for i in range(161):
        s = lo + (hi - lo) * (i / 160)
        points.append((s, _payoff_at_expiry(legs, s)))
    pnls = [p for _, p in points]
    max_gain = max(pnls)
    max_loss = min(pnls)
    breakevens: list[float] = []
    for i in range(1, len(points)):
        s0, p0 = points[i - 1]
        s1, p1 = points[i]
        if abs(p0) < 1:
            breakevens.append(s0)
        elif p0 * p1 < 0:
            breakevens.append(s0 + (s1 - s0) * (-p0) / (p1 - p0))
    return max_gain, max_loss, breakevens


def _net_debit(legs: list[Leg]) -> float:
    total = 0.0
    for leg in legs:
        sign = 1.0 if leg.action == "BUY" else -1.0
        total += sign * leg.qty * leg.premium * 100
    return total


def _is_single_long_call(legs: list[Leg], tag: str) -> bool:
    return (
        tag == "long-call"
        and len(legs) == 1
        and legs[0].action == "BUY"
        and legs[0].type == "CALL"
    )


def _is_single_long_put(legs: list[Leg], tag: str) -> bool:
    return (
        tag == "long-put"
        and len(legs) == 1
        and legs[0].action == "BUY"
        and legs[0].type == "PUT"
    )


def _has_unlimited_upside(legs: list[Leg], tag: str) -> bool:
    if _is_single_long_call(legs, tag):
        return True
    if tag == "strangle" and any(leg.action == "BUY" and leg.type == "CALL" for leg in legs):
        return True
    return False


def _metrics_from_legs(
    legs: list[Leg],
    spot: float,
    risk_cap: float,
    tag: str,
) -> tuple[float | str, float | str, list[str], int, float, str, str | None]:
    scanned_max_gain, max_loss, breakevens = _scan_payoff(legs, spot)
    max_gain = scanned_max_gain
    debit = _net_debit(legs)

    if tag == "vertical" and len(legs) == 2:
        strikes = sorted(l.strike for l in legs)
        low, high = strikes[0], strikes[-1]
        width = (high - low) * 100
        if width <= 0:
            return 0, 0, [], 0, 0, "N/A", "invalid_pricing"
        if debit > 0:
            max_loss_v = debit
            max_gain_v = max(width - debit, 0)
            max_gain, max_loss = max_gain_v, -max_loss_v
            if all(leg.type == "CALL" for leg in legs):
                breakevens = [low + debit / 100]
            else:
                breakevens = [high - debit / 100]
        else:
            credit = abs(debit)
            # Credit cannot exceed the spread width in a valid defined-risk
            # vertical. If it does, stale/modelled mids created an invalid quote.
            if credit >= width:
                return 0, 0, [], 0, 0, "N/A", "invalid_pricing"
            max_gain, max_loss = credit, -(width - credit)
            if all(leg.type == "CALL" for leg in legs):
                breakevens = [low + credit / 100]
            else:
                breakevens = [high - credit / 100]

    undefined_tail = tag == "ratio"
    if undefined_tail:
        max_loss_out: float | str = "∞"
        max_gain_out = round(max(max_gain, 0), 0)
    elif _has_unlimited_upside(legs, tag):
        max_loss_out = round(debit if debit > 0 else abs(min(max_loss, 0)), 0)
        max_gain_out = "∞"
    elif _is_single_long_put(legs, tag):
        max_loss_out = round(debit, 0)
        max_gain_out = round(max(legs[0].strike * 100 - debit, 0), 0)
    else:
        max_loss_out = round(max(abs(min(max_loss, 0)), debit if debit > 0 else 0), 0)
        max_gain_out = round(max(max_gain, 0), 0)

    risk_buffer_warning = None
    if isinstance(max_loss_out, (int, float)) and max_loss_out > risk_cap and tag != "ratio":
        buffer_limit = risk_cap * 1.15
        if max_loss_out > buffer_limit:
            return 0, 0, [], 0, 0, "N/A", "over_budget"
        over_by = max_loss_out - risk_cap
        over_pct = (over_by / risk_cap) * 100 if risk_cap else 0
        risk_buffer_warning = (
            f"Max loss exceeds stated risk budget by ${over_by:,.0f} "
            f"({over_pct:.0f}% over). Shown only because it is within the 15% tolerance buffer."
        )

    lo_b, hi_b = spot * 0.5, spot * 1.5
    be_str = [f"{b:.2f}" for b in breakevens[:2] if lo_b <= b <= hi_b]
    if not be_str:
        be_str = [f"{b:.2f}" for b in breakevens[:2]]

    rr = (
        "N/A"
        if max_loss_out == "∞"
        or (isinstance(max_loss_out, (int, float)) and max_loss_out < 1)
        else "∞"
        if max_gain_out == "∞"
        else f"{max_gain_out / max_loss_out:.2f}"
    )
    pop = max(22, min(58, int(48 - abs(legs[0].strike - spot) / spot * 60)))
    ev_gain = scanned_max_gain if max_gain_out == "∞" else max_gain_out
    ev = round(
        ev_gain * (pop / 100)
        - (max_loss_out if isinstance(max_loss_out, (int, float)) else risk_cap) * 0.35,
        1,
    )

    warning = risk_buffer_warning
    if undefined_tail:
        be_low = min(breakevens) if breakevens else spot * 0.85
        warning = f"Undefined max loss below ${be_low:.2f} violates risk budget"

    return max_gain_out, max_loss_out, be_str, pop, ev, rr, warning


def _contracts_iv_map(snapshot: MarketSnapshot) -> dict[tuple[float, int, str], float]:
    from datetime import date as d

    today = d.today()
    out: dict[tuple[float, int, str], float] = {}
    for c in snapshot.contracts:
        if not c.iv or c.iv <= 0:
            continue
        dte = max((c.expiry - today).days, 0)
        opt = "CALL" if c.contract_type == "call" else "PUT"
        out[(c.strike, dte, opt)] = c.iv
    return out


def _build_legs(
    snapshot: MarketSnapshot,
    spec: list[tuple[str, int, float, date, bool, str]],
) -> list[Leg] | None:
    legs: list[Leg] = []
    spot = snapshot.spot
    for action, qty, ratio, expiry, back, ctype in spec:
        c = _pick_contract(
            snapshot.contracts, expiry, round_strike(spot, ratio), ctype
        )
        if not c:
            return None
        legs.append(contract_to_leg(c, action, qty, back_month=back))
    return legs


def _templates_for_direction(direction: str) -> list[tuple[str, str, list, str]]:
    if direction == "Neutral":
        return [
            (
                "Iron Condor",
                "vertical",
                [
                    ("BUY", 1, 0.92, "front", False, "put"),
                    ("SELL", 1, 0.95, "front", False, "put"),
                    ("SELL", 1, 1.05, "front", False, "call"),
                    ("BUY", 1, 1.08, "front", False, "call"),
                ],
                "Neutral high-probability income trade that sells premium outside the expected range.",
            ),
            (
                "Long Strangle",
                "strangle",
                [
                    ("BUY", 1, 0.95, "front", False, "put"),
                    ("BUY", 1, 1.05, "front", False, "call"),
                ],
                "Long vol/range play — profits from a move in either direction.",
            ),
            (
                "Put Calendar Spread",
                "calendar",
                [
                    ("SELL", 1, 0.98, "front", False, "put"),
                    ("BUY", 1, 0.98, "back", True, "put"),
                ],
                "Neutral income — positive theta if price pins near the short strike.",
            ),
            (
                "Iron Butterfly (puts)",
                "butterfly",
                [
                    ("BUY", 1, 0.94, "front", False, "put"),
                    ("SELL", 2, 1.0, "front", False, "put"),
                    ("BUY", 1, 1.04, "front", False, "put"),
                ],
                "Defined-risk range trade centered near spot (put-wing variant).",
            ),
            (
                "Put Diagonal",
                "diagonal",
                [
                    ("BUY", 1, 0.98, "back", True, "put"),
                    ("SELL", 1, 0.98, "front", False, "put"),
                ],
                "Diagonal with limited debit — benefits from time decay near strike.",
            ),
        ]
    if direction == "Bullish":
        return [
            (
                "Bull Put Spread",
                "vertical",
                [
                    ("SELL", 1, 0.98, "front", False, "put"),
                    ("BUY", 1, 0.95, "front", False, "put"),
                ],
                "Defined-risk bullish credit spread — sells premium below spot with a tighter risk width.",
            ),
            (
                "Long LEAPS Call",
                "long-call",
                [
                    ("BUY", 1, 1.0, "front", False, "call"),
                ],
                "Long-dated bullish call with defined debit risk and upside convexity.",
            ),
            (
                "Bull Call Spread",
                "vertical",
                [
                    ("BUY", 1, 1.0, "front", False, "call"),
                    ("SELL", 1, 1.05, "front", False, "call"),
                ],
                "Defined-risk bullish call vertical targeting a measured upside move.",
            ),
            (
                "Call Diagonal",
                "diagonal",
                [
                    ("BUY", 1, 1.0, "front", False, "call"),
                    ("SELL", 1, 1.1, "back", True, "call"),
                ],
                "Bullish diagonal that finances part of the long-dated call with upside call sale.",
            ),
        ]
    return [
        (
            "Bear Call Spread",
            "vertical",
            [
                ("SELL", 1, 1.03, "front", False, "call"),
                ("BUY", 1, 1.1, "front", False, "call"),
            ],
            "Defined-risk bearish credit spread — sells premium above spot.",
        ),
        (
            "Long Put",
            "long-put",
            [
                ("BUY", 1, 1.0, "front", False, "put"),
            ],
            "Single-leg bearish put with defined debit risk and large downside convexity.",
        ),
        (
            "Bear Put Spread",
            "vertical",
            [
                ("BUY", 1, 1.0, "front", False, "put"),
                ("SELL", 1, 0.93, "front", False, "put"),
            ],
            "Defined-risk bearish put vertical.",
        ),
        (
            "Put Diagonal",
            "diagonal",
            [
                ("BUY", 1, 0.96, "back", True, "put"),
                ("SELL", 1, 0.93, "front", False, "put"),
            ],
            "Positive theta diagonal for a gradual decline.",
        ),
        (
            "Broken-Wing Butterfly",
            "butterfly",
            [
                ("BUY", 1, 1.0, "front", False, "put"),
                ("SELL", 2, 0.95, "front", False, "put"),
                ("BUY", 1, 0.91, "front", False, "put"),
            ],
            "Asymmetric butterfly for a bearish pin.",
        ),
    ]


def _structure_avoided(name: str, avoid_structures: list[str]) -> bool:
    name_lower = name.lower()
    for avoid in avoid_structures:
        avoid_lower = avoid.lower()
        if avoid_lower in name_lower or name_lower in avoid_lower:
            return True
        if "long call" in avoid_lower and name_lower.startswith("long call"):
            return True
        if "long put" in avoid_lower and name_lower.startswith("long put"):
            return True
        if ("straddle" in avoid_lower or "strangle" in avoid_lower) and (
            "straddle" in name_lower or "strangle" in name_lower
        ):
            return True
        if "iron condor" in avoid_lower and "condor" in name_lower:
            return True
        if "iron butterfly" in avoid_lower and "butterfly" in name_lower:
            return True
        if "calendar" in avoid_lower and "calendar" in name_lower:
            return True
        if "diagonal" in avoid_lower and "diagonal" in name_lower:
            return True
    return False


def _liquidity_profile(legs: list[Leg]) -> LiquidityProfile:
    # Current Polygon tier only provides prior aggregate mids in this app; flag that
    # quote confidence is estimated until live bid/ask/OI are wired in.
    warnings = [
        "Quote quality is estimated from prior aggregate mids; verify live bid/ask before entry."
    ]
    wide_premium = any(leg.premium <= 0.05 for leg in legs)
    if wide_premium:
        warnings.append("One or more legs has a very small premium; fills may be unreliable.")
    score = 55 if not wide_premium else 40
    label = "Estimated" if score >= 50 else "Weak"
    return LiquidityProfile(
        score=score,
        label=label,
        quote_quality="Prior close / modeled mids",
        spread_warnings=warnings,
    )


def _scenario_points(legs: list[Leg], spot: float) -> list[ScenarioPoint]:
    moves = [(-10, "Down 10%"), (-5, "Down 5%"), (0, "Unchanged"), (5, "Up 5%"), (10, "Up 10%")]
    return [
        ScenarioPoint(
            label=label,
            underlying_price=round(spot * (1 + pct / 100), 2),
            pnl=round(_payoff_at_expiry(legs, spot * (1 + pct / 100)), 0),
        )
        for pct, label in moves
    ]


def _management_rules(
    tag: str,
    metrics: StrategyMetrics,
    *,
    earnings_in_window: bool,
) -> list[ManagementRule]:
    rules = [
        ManagementRule(
            label="Profit target",
            detail="Consider taking profits around 40-60% of planned max profit or when thesis is realized early.",
        ),
        ManagementRule(
            label="Risk stop",
            detail="Predefine an exit if mark-to-market loss reaches roughly 40-50% of max loss.",
        ),
        ManagementRule(
            label="Time stop",
            detail="Avoid holding short-dated options into the final week unless the trade thesis requires it.",
        ),
    ]
    if metrics.max_gain == "∞":
        rules[0] = ManagementRule(
            label="Profit target",
            detail="Upside is theoretically open; use a trailing target or close partial profits after a strong move.",
        )
    if tag in ("diagonal", "calendar"):
        rules.append(
            ManagementRule(
                label="Adjustment trigger",
                detail="Reassess if spot moves through the short strike or IV collapses faster than expected.",
            )
        )
    if earnings_in_window:
        rules.append(
            ManagementRule(
                label="Earnings risk",
                detail="Exit or reduce before earnings unless this is explicitly an earnings-volatility trade.",
            )
        )
    return rules


def _education_points(name: str, tag: str, metrics: StrategyMetrics) -> list[str]:
    points = []
    if metrics.max_gain == "∞":
        points.append("The upside is theoretically unlimited, but the chart only shows a practical price range.")
    if tag == "vertical":
        points.append("Defined-risk spread: max loss and max gain are set by strike width and net debit/credit.")
    elif tag in ("calendar", "diagonal"):
        points.append("Multi-expiry trade: results depend on both price movement and time/volatility changes.")
    elif tag in ("long-call", "long-put"):
        points.append("Single-leg long option: risk is limited to debit paid, but theta decay works against you.")
    elif tag == "strangle":
        points.append("Long-vol trade: needs a large move or IV expansion to offset two option premiums.")
    if name:
        points.append("Validate live quotes before entry; stale or modeled mids can overstate expected value.")
    return points


def _trade_quality(
    *,
    tag: str,
    metrics: StrategyMetrics,
    liquidity: LiquidityProfile,
    iv_regime: str,
    earnings_in_window: bool,
    warning: str | None,
) -> TradeQuality:
    score = 70
    reasons: list[str] = []

    if liquidity.score < 60:
        score -= 12
        reasons.append("Quote confidence is estimated; verify live liquidity before entry.")
    if warning:
        score -= 18
        reasons.append(warning)
    if earnings_in_window:
        score -= 12
        reasons.append("Earnings appears inside the trade window; gap and IV-crush risk are elevated.")
    if iv_regime == "High" and tag in ("long-call", "long-put", "strangle"):
        score -= 10
        reasons.append("High IV makes long-premium structures vulnerable to volatility contraction.")
    if metrics.risk_reward == "N/A":
        score -= 10
        reasons.append("Risk/reward cannot be cleanly estimated for this payoff shape.")

    score = max(0, min(100, score))
    if score >= 72:
        verdict = "Tradeable"
    elif score >= 50:
        verdict = "Caution"
    else:
        verdict = "Avoid"
    if not reasons:
        reasons.append("Defined risk and payoff profile are consistent with the stated thesis.")
    return TradeQuality(verdict=verdict, score=score, reasons=reasons)


def build_strategies(
    view: ParsedView,
    snapshot: MarketSnapshot,
    *,
    iv_regime: str = "Mid",
    earnings_in_window: bool = False,
    avoid_structures: list[str] | None = None,
) -> list[Strategy]:
    target_dte = parse_horizon_days(view.horizon)
    risk_cap = parse_risk_budget(view.risk_budget)
    front, back = select_expiries(snapshot, target_dte)
    spot = snapshot.spot

    def resolve_expiry(token: str) -> date:
        return back if token == "back" else front

    raw_templates = _templates_for_direction(view.direction)
    avoid_structures = avoid_structures or []
    built: list[Strategy] = []
    iv_map = _contracts_iv_map(snapshot)

    for name, tag, spec, critique_base in raw_templates:
        if _structure_avoided(name, avoid_structures):
            continue
        resolved = [
            (a, q, r, resolve_expiry(e), b, c)
            for a, q, r, e, b, c in spec
        ]
        legs = _build_legs(snapshot, resolved)
        if not legs:
            continue

        max_gain, max_loss, be_str, pop, ev, rr, warning = _metrics_from_legs(
            legs, spot, risk_cap, tag
        )
        if warning in ("over_budget", "invalid_pricing"):
            continue

        score = max(40, min(95, int(58 + ev / 6 - (22 if warning else 0))))
        if iv_regime == "High" and tag in ("long-call", "strangle"):
            score -= 8
        elif iv_regime == "Low" and tag in ("vertical",) and "credit" not in critique_base.lower():
            score += 4
        if warning and "15% tolerance buffer" in warning and score < 78:
            continue

        greeks = aggregate_strategy_greeks(legs, spot, contracts_iv=iv_map)

        earnings_note = ""
        if earnings_in_window:
            earnings_note = " Earnings in trade window — size accordingly."

        metrics = StrategyMetrics(
            max_gain=max_gain,
            max_loss=max_loss,
            breakevens=be_str,
            pop=pop,
            ev=ev,
            risk_reward=rr,
        )
        liquidity = _liquidity_profile(legs)
        trade_quality = _trade_quality(
            tag=tag,
            metrics=metrics,
            liquidity=liquidity,
            iv_regime=iv_regime,
            earnings_in_window=earnings_in_window,
            warning=warning,
        )
        if trade_quality.verdict == "Avoid":
            continue

        built.append(
            Strategy(
                rank=0,
                name=name,
                tag=tag,
                legs=legs,
                metrics=metrics,
                greeks=greeks,
                score=max(0, min(100, int((score * 0.7) + (trade_quality.score * 0.3)))),
                critique=(
                    f"{critique_base} IV regime: {iv_regime}.{earnings_note} "
                    f"EOD mids ({front.strftime('%b %d')} / {back.strftime('%b %d')})."
                ),
                vs_next=None,
                warning=warning,
                liquidity=liquidity,
                trade_quality=trade_quality,
                scenarios=_scenario_points(legs, spot),
                management_rules=_management_rules(
                    tag, metrics, earnings_in_window=earnings_in_window
                ),
                education=_education_points(name, tag, metrics),
            )
        )

    built.sort(key=lambda s: s.score, reverse=True)
    ranked: list[Strategy] = []
    for i, s in enumerate(built, start=1):
        vs_next = (
            f"Ranked above {built[i].name} on risk-adjusted score ({s.score} vs {built[i].score})."
            if i < len(built)
            else None
        )
        ranked.append(s.model_copy(update={"rank": i, "vs_next": vs_next}))
    return ranked
