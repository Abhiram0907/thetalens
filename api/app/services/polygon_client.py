"""Unified Polygon.io REST client (agent tools + strategy snapshots)."""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_BASE = "https://api.polygon.io"
_MAX_RETRIES = 4


class PolygonClient:
    def __init__(self, api_key: str, base_url: str = DEFAULT_BASE) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    async def _get_json(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float = 30.0,
    ) -> dict:
        params = dict(params or {})
        params.setdefault("apiKey", self.api_key)
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    if path.startswith("http"):
                        r = await client.get(path)
                    else:
                        r = await client.get(f"{self.base_url}{path}", params=params)
                    if r.status_code == 429:
                        wait = 12 * (attempt + 1)
                        logger.warning(
                            "Polygon 429 on %s — retry %d in %ds",
                            path[:80],
                            attempt + 1,
                            wait,
                        )
                        await asyncio.sleep(wait)
                        continue
                    if r.status_code == 403:
                        body = r.json() if r.content else {}
                        raise httpx.HTTPStatusError(
                            body.get("message", "Polygon not authorized"),
                            request=r.request,
                            response=r,
                        )
                    r.raise_for_status()
                    data = r.json()
                    if data.get("status") == "NOT_AUTHORIZED":
                        msg = data.get("message", "Not authorized")
                        raise httpx.HTTPStatusError(msg, request=r.request, response=r)
                    return data
            except httpx.HTTPStatusError:
                raise
            except Exception as exc:
                last_exc = exc
                if attempt + 1 >= _MAX_RETRIES:
                    raise
                await asyncio.sleep(2 * (attempt + 1))

        raise RuntimeError(f"Polygon rate-limited after retries on {path}") from last_exc

    async def daily_bars(self, ticker: str, from_date: str, to_date: str) -> list[dict]:
        sym = ticker.upper()
        data = await self._get_json(
            f"/v2/aggs/ticker/{sym}/range/1/day/{from_date}/{to_date}",
            {"adjusted": "true", "sort": "asc", "limit": "5000"},
        )
        return list(data.get("results") or [])

    async def previous_close(self, ticker: str) -> dict | None:
        sym = ticker.upper()
        data = await self._get_json(
            f"/v2/aggs/ticker/{sym}/prev",
            {"adjusted": "true"},
        )
        results = data.get("results") or []
        return results[0] if results else None

    async def ticker_news(self, ticker: str, limit: int = 10) -> list[dict]:
        data = await self._get_json(
            "/v2/reference/news",
            {
                "ticker": ticker.upper(),
                "limit": str(limit),
                "sort": "published_utc",
                "order": "desc",
            },
        )
        return list(data.get("results") or [])

    async def options_contracts(
        self,
        ticker: str,
        expiration_gte: str | None = None,
        expiration_lte: str | None = None,
        limit: int = 250,
    ) -> list[dict]:
        params: dict[str, str] = {
            "underlying_ticker": ticker.upper(),
            "limit": str(limit),
            "sort": "expiration_date",
            "order": "asc",
        }
        if expiration_gte:
            params["expiration_date.gte"] = expiration_gte
        if expiration_lte:
            params["expiration_date.lte"] = expiration_lte
        data = await self._get_json("/v3/reference/options/contracts", params)
        return list(data.get("results") or [])

    async def related_companies(self, ticker: str) -> list[str]:
        data = await self._get_json(f"/v1/related-companies/{ticker.upper()}")
        return [r["ticker"] for r in data.get("results") or [] if r.get("ticker")]

    async def list_options_reference_contracts(
        self,
        symbol: str,
        spot: float,
        min_expiry: date,
        max_expiry: date,
        contract_type: str,
    ) -> list[dict]:
        sym = symbol.upper()
        rows: list[dict] = []
        params: dict[str, Any] = {
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
                    if r.status_code == 429:
                        await asyncio.sleep(12)
                        continue
                    r.raise_for_status()
                    data = r.json()
                else:
                    data = await self._get_json(path, params, timeout=60.0)
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

    async def fetch_option_iv_map(self, underlying: str) -> dict[str, float]:
        """
        Option chain snapshot (one request). Returns OCC ticker -> IV (decimal).
        On free tier this may 403; caller should fall back to modeled vol.
        """
        sym = underlying.upper()
        try:
            data = await self._get_json(
                f"/v3/snapshot/options/{sym}",
                {"limit": 250},
                timeout=45.0,
            )
        except httpx.HTTPStatusError as exc:
            logger.info("Polygon option snapshot unavailable for %s: %s", sym, exc)
            return {}
        except Exception as exc:
            logger.warning("Polygon option snapshot failed for %s: %s", sym, exc)
            return {}

        out: dict[str, float] = {}
        for row in data.get("results") or []:
            details = row.get("details") or {}
            ticker = details.get("ticker")
            iv = row.get("implied_volatility")
            if ticker and iv is not None:
                try:
                    val = float(iv)
                    if val > 0:
                        out[str(ticker)] = val
                except (TypeError, ValueError):
                    pass
        return out


def get_polygon_client() -> PolygonClient:
    settings = get_settings()
    if not settings.polygon_api_key:
        raise ValueError("POLYGON_API_KEY is not set")
    return PolygonClient(settings.polygon_api_key, settings.polygon_base_url or DEFAULT_BASE)
