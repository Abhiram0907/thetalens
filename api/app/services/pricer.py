"""Map strategy templates to live option contracts."""

from __future__ import annotations

from datetime import date

from app.schemas.analysis import Leg
from app.services.market_data import MarketSnapshot, OptionContract


def _dte(expiry: date, today: date | None = None) -> int:
    today = today or date.today()
    return max((expiry - today).days, 0)


def _leg_label(expiry: date, strike: float, opt_type: str = "P") -> str:
    return f"{expiry.strftime('%b %d')} {strike:g}{opt_type}"


def _pick_contract(
    contracts: list[OptionContract],
    expiry: date,
    target_strike: float,
    contract_type: str = "put",
) -> OptionContract | None:
    pool = [
        c
        for c in contracts
        if c.expiry == expiry and c.contract_type == contract_type
    ]
    if not pool:
        return None
    return min(pool, key=lambda c: abs(c.strike - target_strike))


def contract_to_leg(
    c: OptionContract,
    action: str,
    qty: int,
    *,
    back_month: bool = False,
) -> Leg:
    opt = "CALL" if c.contract_type == "call" else "PUT"
    suffix = "C" if opt == "CALL" else "P"
    return Leg(
        action=action,
        qty=qty,
        type=opt,
        strike=c.strike,
        dte=_dte(c.expiry),
        premium=round(c.mid, 2),
        label=_leg_label(c.expiry, c.strike, suffix),
        back_month=back_month,
    )


def round_strike(spot: float, ratio: float) -> float:
    """Round to sensible equity strike spacing."""
    raw = spot * ratio
    if spot > 200:
        step = 5
    elif spot > 50:
        step = 2.5 if raw < 100 else 5
    else:
        step = 1
    return round(raw / step) * step


def select_expiries(snapshot: MarketSnapshot, target_dte: int) -> tuple[date, date]:
    today = date.today()
    expiries = sorted({c.expiry for c in snapshot.contracts})

    def near(dte: int) -> date:
        return min(expiries, key=lambda e: abs((e - today).days - dte))

    back_target = target_dte + 90 if target_dte >= 60 else min(target_dte * 2, 42)
    front = snapshot.front_expiry or near(target_dte)
    back = snapshot.back_expiry or near(back_target)
    if back <= front and len(expiries) > 1:
        later = [e for e in expiries if e > front]
        back = later[0] if later else front
    return front, back
