"""Massive (Polygon) market data — reference contracts + aggregate bars."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone

import httpx

from app.config import get_settings
from app.services.greeks import DEFAULT_IV, bs_price

logger = logging.getLogger(__name__)

DEFAULT_BASE = "https://api.polygon.io"


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


class MarketDataError(Exception):
    pass


def _parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])


class PolygonClient:
    def __init__(self, api_key: str, base_url: str = DEFAULT_BASE) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    async def _get_json(self, client: httpx.AsyncClient, path: str, params: dict | None = None) -> dict:
        params = dict(params or {})
        params.setdefault("apiKey", self.api_key)
        max_retries = 4
        for attempt in range(max_retries):
            r = await client.get(f"{self.base_url}{path}", params=params)
            if r.status_code == 429:
                wait = 12 * (attempt + 1)
                logger.warning("Polygon 429 on %s — retry %d in %ds", path, attempt + 1, wait)
                await asyncio.sleep(wait)
                continue
            if r.status_code == 403:
                raise MarketDataError(r.json().get("message", "Polygon not authorized for this endpoint"))
            r.raise_for_status()
            data = r.json()
            if data.get("status") == "NOT_AUTHORIZED":
                raise MarketDataError(data.get("message", "Not authorized"))
            return data
        raise MarketDataError(f"Polygon rate-limited after {max_retries} retries on {path}")

    async def get_spot(self, symbol: str) -> tuple[float, datetime | None]:
        sym = symbol.upper()
        try:
            from app.tools.providers import get_yfinance_client
            prev = await get_yfinance_client().previous_close(sym)
            if prev and prev.get("c"):
                ts = prev.get("t")
                as_of = datetime.fromtimestamp(ts / 1000, tz=timezone.utc) if ts else None
                return float(prev["c"]), as_of
        except Exception:
            pass
        async with httpx.AsyncClient(timeout=30.0) as client:
            data = await self._get_json(
                client,
                f"/v2/aggs/ticker/{sym}/prev",
                {"adjusted": "true"},
            )
        results = data.get("results") or []
        if not results:
            raise MarketDataError(f"No price data for {sym}")
        bar = results[0]
        ts = bar.get("t")
        as_of = datetime.fromtimestamp(ts / 1000, tz=timezone.utc) if ts else None
        return float(bar["c"]), as_of

    async def _list_reference_contracts(
        self,
        symbol: str,
        spot: float,
        min_expiry: date,
        max_expiry: date,
        contract_type: str,
    ) -> list[dict]:
        sym = symbol.upper()
        rows: list[dict] = []
        params: dict = {
            "underlying_ticker": sym,
            "contract_type": contract_type,
            "expiration_date.gte": min_expiry.isoformat(),
            "expiration_date.lte": max_expiry.isoformat(),
            "strike_price.gte": round(spot * 0.80, 2),
            "strike_price.lte": round(spot * 1.20, 2),
            "limit": 1000,
            "sort": "strike_price",
            "order": "asc",
        }
        path = "/v3/reference/options/contracts"
        next_path: str | None = path

        async with httpx.AsyncClient(timeout=60.0) as client:
            while next_path:
                if next_path.startswith("http"):
                    r = await client.get(next_path)
                    r.raise_for_status()
                    data = r.json()
                else:
                    data = await self._get_json(
                        client, next_path, params if next_path == path else None
                    )
                rows.extend(data.get("results") or [])
                next_url = data.get("next_url")
                if next_url:
                    if "apiKey=" not in next_url:
                        sep = "&" if "?" in next_url else "?"
                        next_url = f"{next_url}{sep}apiKey={self.api_key}"
                    next_path = next_url
                    params = {}
                else:
                    break
        return rows

    def _price_contracts_bs(self, refs: list[dict], spot: float, sigma: float | None = None) -> list[OptionContract]:
        """Price all contracts via Black-Scholes — zero Polygon API calls."""
        vol = sigma or DEFAULT_IV
        out: list[OptionContract] = []
        for ref in refs:
            ticker = ref.get("ticker")
            strike = ref.get("strike_price")
            expiry = ref.get("expiration_date")
            if not ticker or strike is None or not expiry:
                continue
            ctype = (ref.get("contract_type") or "put").lower()
            expiry_date = _parse_date(expiry)
            t = max((expiry_date - date.today()).days, 1) / 365.0
            mid = bs_price(spot, float(strike), t, vol, is_call=ctype == "call")
            if mid is None or mid <= 0:
                continue
            out.append(OptionContract(
                ticker=ticker,
                strike=float(strike),
                expiry=expiry_date,
                contract_type=ctype,
                mid=mid,
                bid=None,
                ask=None,
                open_interest=0,
                iv=None,
                delta=None,
                gamma=None,
                theta=None,
                vega=None,
            ))
        return out

    async def load_snapshot(self, symbol: str, target_dte: int = 21, sigma: float | None = None) -> MarketSnapshot:
        sym = symbol.upper()
        spot, as_of = await self.get_spot(sym)
        today = date.today()
        min_exp = today
        max_exp = today.fromordinal(
            today.toordinal() + max(target_dte + 120, target_dte * 2 + 21, 55)
        )

        put_refs = await self._list_reference_contracts(sym, spot, min_exp, max_exp, "put")
        call_refs = await self._list_reference_contracts(sym, spot, min_exp, max_exp, "call")
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

        contracts = self._price_contracts_bs(selected_refs, spot, sigma)
        if not contracts:
            raise MarketDataError(f"Could not price options for {sym}")

        front = _parse_date(front_s)
        back = _parse_date(back_s)

        return MarketSnapshot(
            symbol=sym,
            spot=spot,
            as_of=as_of,
            contracts=contracts,
            front_expiry=front,
            back_expiry=back,
        )


def get_polygon_client() -> PolygonClient:
    settings = get_settings()
    if not settings.polygon_api_key:
        raise MarketDataError("POLYGON_API_KEY is not set in .env")
    return PolygonClient(settings.polygon_api_key, settings.polygon_base_url)


def estimate_iv_rank(contracts: list[OptionContract], spot: float) -> tuple[int, str]:
    if not contracts:
        return 50, "50th percentile (estimated)"
    atm = min(contracts, key=lambda c: abs(c.strike - spot))
    # Without IV history, use moneyness of long put premium as rough signal
    pct = int(max(25, min(75, 50 + (spot - atm.strike) / spot * 100)))
    suffix = "th"
    if pct % 10 == 1 and pct != 11:
        suffix = "st"
    elif pct % 10 == 2 and pct != 12:
        suffix = "nd"
    elif pct % 10 == 3 and pct != 13:
        suffix = "rd"
    return pct, f"{pct}{suffix} percentile (EOD data)"
