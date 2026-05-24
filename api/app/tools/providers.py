"""
Multi-source market data providers.

Routes data requests to the optimal free-tier API:
  - yfinance:  daily bars, previous close, spot price  (no key, no rate limit)
  - Finnhub:   company peers, news sentiment, earnings calendar  (60 req/min free)
  - Polygon:   options contracts only  (5 req/min free)
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from functools import lru_cache

import finnhub
import yfinance as yf

_executor = ThreadPoolExecutor(max_workers=8)


# ---------------------------------------------------------------------------
# yfinance — daily bars, previous close  (free, no key, no rate limit)
# ---------------------------------------------------------------------------

class YFinanceClient:
    """Wraps yfinance sync calls in async via a thread pool."""

    async def daily_bars(self, ticker: str, from_date: str, to_date: str) -> list[dict]:
        def _fetch():
            tk = yf.Ticker(ticker)
            df = tk.history(start=from_date, end=to_date, auto_adjust=True)
            if df.empty:
                return []
            rows = []
            for ts, row in df.iterrows():
                rows.append({
                    "c": float(row["Close"]),
                    "o": float(row["Open"]),
                    "h": float(row["High"]),
                    "l": float(row["Low"]),
                    "v": int(row["Volume"]),
                    "t": int(ts.timestamp() * 1000),
                })
            return rows

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, _fetch)

    async def previous_close(self, ticker: str) -> dict | None:
        def _fetch():
            tk = yf.Ticker(ticker)
            df = tk.history(period="2d", auto_adjust=True)
            if df.empty:
                return None
            last = df.iloc[-1]
            return {
                "c": float(last["Close"]),
                "o": float(last["Open"]),
                "h": float(last["High"]),
                "l": float(last["Low"]),
                "v": int(last["Volume"]),
                "t": int(df.index[-1].timestamp() * 1000),
            }

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, _fetch)

    async def ticker_info(self, ticker: str) -> dict:
        def _fetch():
            tk = yf.Ticker(ticker)
            return dict(tk.info) if tk.info else {}

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, _fetch)


# ---------------------------------------------------------------------------
# Finnhub — peers, news sentiment, earnings  (60 req/min free)
# ---------------------------------------------------------------------------

class FinnhubClient:
    """Wraps the finnhub-python sync client in async."""

    def __init__(self, api_key: str):
        self._client = finnhub.Client(api_key=api_key)

    async def company_peers(self, ticker: str) -> list[str]:
        def _fetch():
            peers = self._client.company_peers(ticker)
            return [p for p in peers if p != ticker]

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, _fetch)

    async def news_sentiment(self, ticker: str) -> dict:
        def _fetch():
            return self._client.news_sentiment(ticker)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, _fetch)

    async def company_news(self, ticker: str, days_back: int = 7) -> list[dict]:
        def _fetch():
            to_date = date.today().isoformat()
            from_date = (date.today() - timedelta(days=days_back)).isoformat()
            return self._client.company_news(ticker, _from=from_date, to=to_date)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, _fetch)

    async def earnings_calendar(
        self, ticker: str = "", from_date: str | None = None, to_date: str | None = None
    ) -> list[dict]:
        def _fetch():
            f = from_date or date.today().isoformat()
            t = to_date or (date.today() + timedelta(days=90)).isoformat()
            result = self._client.earnings_calendar(
                _from=f, to=t, symbol=ticker, international=False
            )
            return result.get("earningsCalendar", [])

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, _fetch)

    async def company_earnings(self, ticker: str, limit: int = 4) -> list[dict]:
        def _fetch():
            return self._client.company_earnings(ticker, limit=limit)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, _fetch)


# ---------------------------------------------------------------------------
# Singleton accessors
# ---------------------------------------------------------------------------

_yf_client: YFinanceClient | None = None
_fh_client: FinnhubClient | None = None


def get_yfinance_client() -> YFinanceClient:
    global _yf_client
    if _yf_client is None:
        _yf_client = YFinanceClient()
    return _yf_client


def get_finnhub_client(api_key: str | None = None) -> FinnhubClient | None:
    global _fh_client
    if _fh_client is None:
        if not api_key:
            return None
        _fh_client = FinnhubClient(api_key)
    return _fh_client
