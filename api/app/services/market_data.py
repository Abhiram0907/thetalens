"""Market snapshots: reference contracts + Black–Scholes or implied-vol pricing."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from app.services.market_types import SpotSource, VolInput
from app.services.greeks import DEFAULT_IV, bs_price
from app.services.market_cache import (
    TTL_OPTION_IV_MAP,
    TTL_POLYGON_REFS,
    TTL_SNAPSHOT,
    cached_async,
)
from app.services.polygon_client import PolygonClient, get_polygon_client

logger = logging.getLogger(__name__)

class MarketDataError(Exception):
    pass


@dataclass(frozen=True)
class OptionContract:
    ticker: str
    strike: float
    expiry: date
    contract_type: str
    mid: float
    bid: float | None
    ask: float | None
    open_interest: int
    iv: float | None
    delta: float | None
    gamma: float | None
    theta: float | None
    vega: float | None


@dataclass
class MarketSnapshot:
    symbol: str
    spot: float
    as_of: datetime | None
    contracts: list[OptionContract]
    front_expiry: date | None
    back_expiry: date | None
    spot_source: SpotSource = "yfinance"
    pricing_vol_input: VolInput = "default"


def _parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def _implied_vol_from_reference(ref: dict) -> float | None:
    for key in ("implied_volatility", "iv"):
        raw = ref.get(key)
        if raw is None:
            continue
        try:
            val = float(raw)
            if val > 0:
                return val
        except (TypeError, ValueError):
            continue
    return None


def _resolve_contract_vol(
    ref: dict,
    *,
    iv_by_ticker: dict[str, float],
    fallback_sigma: float | None,
) -> tuple[float, bool]:
    """Return (sigma decimal, used_implied)."""
    ticker = ref.get("ticker")
    if ticker and ticker in iv_by_ticker:
        return iv_by_ticker[ticker], True
    ref_iv = _implied_vol_from_reference(ref)
    if ref_iv is not None:
        return ref_iv, True
    if fallback_sigma is not None and fallback_sigma > 0:
        return fallback_sigma, False
    return DEFAULT_IV, False


def _price_contracts_bs(
    refs: list[dict],
    spot: float,
    *,
    fallback_sigma: float | None = None,
    iv_by_ticker: dict[str, float] | None = None,
) -> tuple[list[OptionContract], VolInput]:
    iv_map = iv_by_ticker or {}
    out: list[OptionContract] = []
    used_implied = False
    used_realized = False

    for ref in refs:
        ticker = ref.get("ticker")
        strike = ref.get("strike_price")
        expiry = ref.get("expiration_date")
        if not ticker or strike is None or not expiry:
            continue
        ctype = (ref.get("contract_type") or "put").lower()
        expiry_date = _parse_date(expiry)
        t = max((expiry_date - date.today()).days, 1) / 365.0
        vol, from_implied = _resolve_contract_vol(
            ref, iv_by_ticker=iv_map, fallback_sigma=fallback_sigma
        )
        if from_implied:
            used_implied = True
        elif fallback_sigma is not None and fallback_sigma > 0:
            used_realized = True

        mid = bs_price(spot, float(strike), t, vol, is_call=ctype == "call")
        if mid is None or mid <= 0:
            continue
        out.append(
            OptionContract(
                ticker=ticker,
                strike=float(strike),
                expiry=expiry_date,
                contract_type=ctype,
                mid=mid,
                bid=None,
                ask=None,
                open_interest=0,
                iv=vol if from_implied else None,
                delta=None,
                gamma=None,
                theta=None,
                vega=None,
            )
        )

    if used_implied:
        vol_input: VolInput = "implied"
    elif used_realized:
        vol_input = "realized_30d"
    else:
        vol_input = "default"
    return out, vol_input


async def get_spot(symbol: str, client: PolygonClient) -> tuple[float, datetime | None, SpotSource]:
    sym = symbol.upper()
    try:
        from app.tools.providers import get_yfinance_client

        prev = await get_yfinance_client().previous_close(sym)
        if prev and prev.get("c"):
            ts = prev.get("t")
            as_of = datetime.fromtimestamp(ts / 1000, tz=timezone.utc) if ts else None
            return float(prev["c"]), as_of, "yfinance"
    except Exception:
        pass

    bar = await client.previous_close(sym)
    if not bar:
        raise MarketDataError(f"No price data for {sym}")
    ts = bar.get("t")
    as_of = datetime.fromtimestamp(ts / 1000, tz=timezone.utc) if ts else None
    return float(bar["c"]), as_of, "polygon"


async def _load_iv_map(client: PolygonClient, symbol: str) -> dict[str, float]:
    key = f"poly:ivmap:{symbol.upper()}"
    return await cached_async(
        key,
        TTL_OPTION_IV_MAP,
        lambda: client.fetch_option_iv_map(symbol),
    )


async def load_snapshot(
    symbol: str,
    target_dte: int = 21,
    sigma: float | None = None,
) -> MarketSnapshot:
    sym = symbol.upper()
    client = get_polygon_client()
    spot, as_of, spot_source = await get_spot(sym, client)
    today = date.today()
    min_exp = today
    max_exp = today.fromordinal(
        today.toordinal() + max(target_dte + 120, target_dte * 2 + 21, 55)
    )

    async def _puts() -> list[dict]:
        k = f"poly:refs:{sym}:put:{min_exp}:{max_exp}:{round(spot, 2)}"
        return await cached_async(
            k,
            TTL_POLYGON_REFS,
            lambda: client.list_options_reference_contracts(
                sym, spot, min_exp, max_exp, "put"
            ),
        )

    async def _calls() -> list[dict]:
        k = f"poly:refs:{sym}:call:{min_exp}:{max_exp}:{round(spot, 2)}"
        return await cached_async(
            k,
            TTL_POLYGON_REFS,
            lambda: client.list_options_reference_contracts(
                sym, spot, min_exp, max_exp, "call"
            ),
        )

    put_refs, call_refs = await _puts(), await _calls()
    refs = put_refs + call_refs
    if not put_refs:
        raise MarketDataError(
            f"No listed options for {sym}. Check the ticker is a US equity with an options market."
        )

    expiries = sorted({r["expiration_date"] for r in put_refs if r.get("expiration_date")})

    def near_dte(dte: int) -> str:
        return min(expiries, key=lambda e: abs((_parse_date(e) - today).days - dte))

    front_s = near_dte(target_dte)
    back_target = target_dte + 90 if target_dte >= 60 else min(target_dte * 2, 42)
    back_s = near_dte(back_target)
    if back_s == front_s and len(expiries) > 1:
        later = [e for e in expiries if e > front_s]
        back_s = later[0] if later else front_s

    ratios = [0.91, 0.93, 0.95, 0.96, 0.98, 1.0, 1.03, 1.05, 1.1, 1.2]
    targets: set[tuple[str, str, float]] = set()
    for exp in (front_s, back_s):
        for ratio in ratios:
            strike = round(spot * ratio, 2)
            targets.add((exp, "put", strike))
            targets.add((exp, "call", strike))

    def nearest_ref(exp: str, strike: float, ctype: str) -> dict | None:
        pool = [
            r
            for r in refs
            if r.get("expiration_date") == exp
            and (r.get("contract_type") or "put").lower() == ctype
        ]
        if not pool:
            return None
        return min(pool, key=lambda r: abs(float(r["strike_price"]) - strike))

    selected_refs: list[dict] = []
    seen: set[str] = set()
    for exp, ctype, strike in targets:
        ref = nearest_ref(exp, strike, ctype)
        if ref and ref["ticker"] not in seen:
            seen.add(ref["ticker"])
            selected_refs.append(ref)

    iv_by_ticker = await _load_iv_map(client, sym)
    if not iv_by_ticker:
        for ref in selected_refs:
            t = ref.get("ticker")
            ref_iv = _implied_vol_from_reference(ref)
            if t and ref_iv is not None:
                iv_by_ticker[t] = ref_iv

    contracts, vol_input = _price_contracts_bs(
        selected_refs,
        spot,
        fallback_sigma=sigma,
        iv_by_ticker=iv_by_ticker,
    )
    if not contracts:
        raise MarketDataError(f"Could not price options for {sym}")

    if vol_input == "default" and iv_by_ticker:
        front_ivs = [
            iv_by_ticker[r["ticker"]]
            for r in selected_refs
            if r.get("ticker") in iv_by_ticker
            and r.get("expiration_date") == front_s
        ]
        if front_ivs:
            logger.debug(
                "%s: chain IV available but not matched to selected strikes (n=%d)",
                sym,
                len(front_ivs),
            )

    front = _parse_date(front_s)
    back = _parse_date(back_s)

    return MarketSnapshot(
        symbol=sym,
        spot=spot,
        as_of=as_of,
        contracts=contracts,
        front_expiry=front,
        back_expiry=back,
        spot_source=spot_source,
        pricing_vol_input=vol_input,
    )


async def load_snapshot_cached(
    symbol: str,
    target_dte: int = 21,
    sigma: float | None = None,
) -> MarketSnapshot:
    sigma_key = f"{sigma:.5f}" if sigma is not None and sigma > 0 else "default"
    key = f"snap:{symbol.upper()}:{target_dte}:{sigma_key}"
    return await cached_async(
        key,
        TTL_SNAPSHOT,
        lambda: load_snapshot(symbol, target_dte, sigma=sigma),
    )


def estimate_iv_rank(contracts: list[OptionContract], spot: float) -> tuple[int, str]:
    if not contracts:
        return 50, "50th percentile (estimated)"
    atm = min(contracts, key=lambda c: abs(c.strike - spot))
    pct = int(max(25, min(75, 50 + (spot - atm.strike) / spot * 100)))
    suffix = "th"
    if pct % 10 == 1 and pct != 11:
        suffix = "st"
    elif pct % 10 == 2 and pct != 12:
        suffix = "nd"
    elif pct % 10 == 3 and pct != 13:
        suffix = "rd"
    return pct, f"{pct}{suffix} percentile (EOD data)"
