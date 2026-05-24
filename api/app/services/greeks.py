"""Black–Scholes greeks and IV from market premiums."""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.schemas.analysis import Leg, StrategyGreeks

RISK_FREE = 0.0525
DEFAULT_IV = 0.48


@dataclass(frozen=True)
class LegGreeks:
    delta: float
    gamma: float
    theta: float  # $/day per contract (100 shares)
    vega: float  # $ per 1% IV move per contract


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _d1_d2(s: float, k: float, t: float, sigma: float, r: float) -> tuple[float, float]:
    if t <= 0 or sigma <= 0 or s <= 0 or k <= 0:
        return 0.0, 0.0
    vol_sqrt = sigma * math.sqrt(t)
    d1 = (math.log(s / k) + (r + 0.5 * sigma * sigma) * t) / vol_sqrt
    d2 = d1 - vol_sqrt
    return d1, d2


def bs_price(
    s: float,
    k: float,
    t: float,
    sigma: float,
    *,
    is_call: bool,
    r: float = RISK_FREE,
) -> float:
    if t <= 0:
        return max(0.0, s - k) if is_call else max(0.0, k - s)
    d1, d2 = _d1_d2(s, k, t, sigma, r)
    disc = math.exp(-r * t)
    if is_call:
        return s * _norm_cdf(d1) - k * disc * _norm_cdf(d2)
    return k * disc * _norm_cdf(-d2) - s * _norm_cdf(-d1)


def implied_vol(
    s: float,
    k: float,
    t: float,
    market_price: float,
    *,
    is_call: bool,
    r: float = RISK_FREE,
) -> float:
    if market_price <= 0 or t <= 0:
        return DEFAULT_IV
    intrinsic = max(0.0, s - k) if is_call else max(0.0, k - s)
    if market_price <= intrinsic + 0.01:
        return DEFAULT_IV

    lo, hi = 0.05, 2.5
    for _ in range(60):
        mid = (lo + hi) / 2
        p = bs_price(s, k, t, mid, is_call=is_call, r=r)
        if p > market_price:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def leg_greeks(
    spot: float,
    leg: Leg,
    *,
    iv: float | None = None,
) -> LegGreeks:
    t = max(leg.dte, 1) / 365.0
    is_call = leg.type == "CALL"
    sigma = iv if iv and iv > 0 else implied_vol(
        spot, leg.strike, t, leg.premium, is_call=is_call
    )

    if t <= 1 / 365:
        return LegGreeks(delta=0.0, gamma=0.0, theta=0.0, vega=0.0)

    d1, d2 = _d1_d2(spot, leg.strike, t, sigma, RISK_FREE)
    disc = math.exp(-RISK_FREE * t)
    pdf = _norm_pdf(d1)
    sqrt_t = math.sqrt(t)

    if is_call:
        delta = _norm_cdf(d1)
        theta_annual = (
            -(spot * pdf * sigma) / (2 * sqrt_t)
            - RISK_FREE * leg.strike * disc * _norm_cdf(d2)
        )
    else:
        delta = _norm_cdf(d1) - 1.0
        theta_annual = (
            -(spot * pdf * sigma) / (2 * sqrt_t)
            + RISK_FREE * leg.strike * disc * _norm_cdf(-d2)
        )

    gamma = pdf / (spot * sigma * sqrt_t) if spot > 0 else 0.0
    vega = spot * pdf * sqrt_t  # per 1.0 vol; scale to 1% below

    # Position conventions: theta $/day per contract, vega $ per 1% IV
    theta_daily = theta_annual / 365.0 * 100.0
    vega_1pct = vega / 100.0 * 100.0

    return LegGreeks(
        delta=delta,
        gamma=gamma,
        theta=theta_daily,
        vega=vega_1pct,
    )


def aggregate_strategy_greeks(
    legs: list[Leg],
    spot: float,
    contracts_iv: dict[tuple[float, int, str], float] | None = None,
) -> StrategyGreeks:
    """Net greeks for a multi-leg position."""
    contracts_iv = contracts_iv or {}
    d = g = t = v = 0.0

    for leg in legs:
        key = (leg.strike, leg.dte, leg.type)
        iv = contracts_iv.get(key)
        lg = leg_greeks(spot, leg, iv=iv)
        sign = 1.0 if leg.action == "BUY" else -1.0
        mult = sign * leg.qty
        d += lg.delta * mult
        g += lg.gamma * mult
        t += lg.theta * mult
        v += lg.vega * mult

    return StrategyGreeks(
        delta=round(d, 3),
        gamma=round(g, 4),
        theta=round(t, 2),
        vega=round(v, 2),
    )
