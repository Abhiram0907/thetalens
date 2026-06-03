"""
Scanner service: finds stocks with similar movement characteristics to a seed ticker.

Multi-source optimized:
  - Finnhub for company peers + earnings calendar  (60 req/min, no delay needed)
  - yfinance for daily bars, previous close, and company info  (no key, no rate limit)
  - Polygon as fallback only
"""

from __future__ import annotations

import asyncio
import math
import os
import statistics
from datetime import date, timedelta

from pydantic import BaseModel

from app.tools.providers import get_finnhub_client, get_yfinance_client
from app.services.market_cache import cached_yfinance_daily_bars
from app.services.polygon_client import PolygonClient


class ScannerStock(BaseModel):
    ticker: str
    name: str
    sector: str
    market_cap_label: str
    avg_volume: int
    price: float
    change_pct: float
    beta: float
    realized_vol_30d: float
    correlation: float
    iv_rank: float | None = None
    iv_rv_spread: float | None = None
    earnings_within_30d: bool = False
    earnings_date: str | None = None
    opportunity_score: float = 0.0


class SeedContext(BaseModel):
    ticker: str
    name: str
    sector: str
    market_cap_label: str
    price: float
    change_pct: float
    beta_spy: float
    realized_vol_30d: float
    iv_rank: float | None = None


# ---------------------------------------------------------------------------
# Pure math helpers
# ---------------------------------------------------------------------------

def _daily_returns(bars: list[dict]) -> list[float]:
    closes = [b["c"] for b in bars]
    if len(closes) < 2:
        return []
    return [
        (closes[i] - closes[i - 1]) / closes[i - 1]
        for i in range(1, len(closes))
    ]


def _correlation(xs: list[float], ys: list[float]) -> float:
    n = min(len(xs), len(ys))
    if n < 5:
        return 0.0
    xs, ys = xs[-n:], ys[-n:]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n)) / n
    std_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs) / n)
    std_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys) / n)
    if std_x == 0 or std_y == 0:
        return 0.0
    return cov / (std_x * std_y)


def _beta(stock_returns: list[float], benchmark_returns: list[float]) -> float:
    n = min(len(stock_returns), len(benchmark_returns))
    if n < 5:
        return 1.0
    xs, ys = benchmark_returns[-n:], stock_returns[-n:]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n)) / n
    var_x = sum((x - mean_x) ** 2 for x in xs) / n
    if var_x == 0:
        return 1.0
    return cov / var_x


def _realized_vol_30d(returns: list[float]) -> float:
    if len(returns) < 10:
        return 0.0
    recent = returns[-30:] if len(returns) >= 30 else returns
    return statistics.stdev(recent) * math.sqrt(252) * 100


def _iv_rank_from_bars(bars: list[dict]) -> float | None:
    """Compute IV rank (0-100) using rolling 30d realized vol percentile over available history."""
    closes = [b["c"] for b in bars]
    if len(closes) < 60:
        return None

    window = 30
    rv_series: list[float] = []
    for i in range(window, len(closes)):
        seg = closes[i - window: i + 1]
        log_rets = [math.log(seg[j] / seg[j - 1]) for j in range(1, len(seg))]
        if len(log_rets) < 2:
            continue
        rv_series.append(statistics.stdev(log_rets) * math.sqrt(252) * 100)

    if len(rv_series) < 5:
        return None

    current = rv_series[-1]
    rv_high = max(rv_series)
    rv_low = min(rv_series)
    denom = rv_high - rv_low
    return round(((current - rv_low) / denom) * 100, 1) if denom > 0 else 50.0


def _market_cap_label(cap: float | None) -> str:
    if not cap or cap <= 0:
        return "N/A"
    if cap >= 200e9:
        return "Mega"
    if cap >= 10e9:
        return "Large"
    if cap >= 2e9:
        return "Mid"
    if cap >= 300e6:
        return "Small"
    return "Micro"


def _opportunity_score(
    iv_rank: float | None,
    correlation: float,
    beta: float,
    rv: float,
    has_earnings: bool,
) -> float:
    """
    Composite score (0-100) weighting tradability factors:
      40% IV rank (higher = more premium-selling opportunity)
      25% abs(correlation) to seed
      15% beta magnitude
      10% realized vol (higher = wider expected moves)
      10% earnings proximity bonus
    """
    ivr = iv_rank if iv_rank is not None else 50.0
    score = (
        0.40 * ivr
        + 0.25 * abs(correlation) * 100
        + 0.15 * min(abs(beta), 3.0) / 3.0 * 100
        + 0.10 * min(rv, 100.0)
        + 0.10 * (80.0 if has_earnings else 30.0)
    )
    return round(min(score, 100.0), 1)


# ---------------------------------------------------------------------------
# Peer + earnings fetching
# ---------------------------------------------------------------------------

async def _get_peers(ticker: str, polygon: PolygonClient) -> list[str]:
    raw: list[str] = []
    fh = get_finnhub_client(os.environ.get("FINNHUB_API_KEY", ""))
    if fh:
        try:
            peers = await fh.company_peers(ticker)
            if peers:
                raw = peers
        except Exception:
            pass
    if not raw:
        raw = await polygon.related_companies(ticker)
    seen: set[str] = {ticker.upper()}
    unique: list[str] = []
    for p in raw:
        up = p.upper()
        if up not in seen:
            seen.add(up)
            unique.append(p)
    return unique


async def _get_earnings_date(ticker: str) -> str | None:
    fh = get_finnhub_client()
    if not fh:
        return None
    try:
        today = date.today()
        cal = await fh.earnings_calendar(
            ticker=ticker,
            from_date=today.isoformat(),
            to_date=(today + timedelta(days=60)).isoformat(),
        )
        for e in cal:
            if e.get("date", "") >= today.isoformat():
                return e["date"]
    except Exception:
        pass
    return None


async def _get_ticker_info(ticker: str) -> dict:
    """Get company name, sector, market cap from yfinance."""
    try:
        info = await get_yfinance_client().ticker_info(ticker)
        return {
            "name": info.get("shortName") or info.get("longName") or ticker,
            "sector": info.get("sector") or "—",
            "market_cap": info.get("marketCap"),
        }
    except Exception:
        return {"name": ticker, "sector": "—", "market_cap": None}


# ---------------------------------------------------------------------------
# Core scan
# ---------------------------------------------------------------------------

async def _build_stock(
    rel_ticker: str,
    seed_returns: list[float],
    bars: list[dict],
    full_year_bars: list[dict],
) -> ScannerStock | None:
    """Build a ScannerStock from pre-fetched bars."""
    rets = _daily_returns(bars)
    if len(rets) < 10:
        return None

    corr = _correlation(seed_returns, rets)
    b = _beta(rets, seed_returns)
    rv = _realized_vol_30d(rets)
    ivr = _iv_rank_from_bars(full_year_bars)
    iv_rv_spread = round(ivr - rv, 1) if ivr is not None else None

    prev = await get_yfinance_client().previous_close(rel_ticker)
    if not prev:
        return None

    price = prev["c"]
    prev_open = prev.get("o", price)
    change_pct = round(((price - prev_open) / prev_open) * 100, 2) if prev_open else 0.0

    avg_vol = 0
    if len(bars) >= 20:
        avg_vol = int(sum(b["v"] for b in bars[-20:]) / 20)

    info = await _get_ticker_info(rel_ticker)
    earnings_dt = await _get_earnings_date(rel_ticker)
    today = date.today()
    earnings_30d = False
    if earnings_dt:
        try:
            from datetime import datetime
            ed = datetime.strptime(earnings_dt, "%Y-%m-%d").date()
            earnings_30d = 0 < (ed - today).days <= 30
        except ValueError:
            pass

    opp = _opportunity_score(ivr, corr, b, rv, earnings_30d)

    return ScannerStock(
        ticker=rel_ticker,
        name=info["name"],
        sector=info["sector"],
        market_cap_label=_market_cap_label(info["market_cap"]),
        avg_volume=avg_vol,
        price=round(price, 2),
        change_pct=change_pct,
        beta=round(b, 2),
        realized_vol_30d=round(rv, 2),
        correlation=round(corr, 2),
        iv_rank=ivr,
        iv_rv_spread=iv_rv_spread,
        earnings_within_30d=earnings_30d,
        earnings_date=earnings_dt,
        opportunity_score=opp,
    )


async def build_seed_context(ticker: str) -> SeedContext:
    """Build the seed stock's own stats for the comparison header."""
    yf = get_yfinance_client()
    today = date.today()

    from_d90 = (today - timedelta(days=90)).isoformat()
    from_1y = (today - timedelta(days=380)).isoformat()
    to_date = today.isoformat()
    bars_90d = await cached_yfinance_daily_bars(ticker, from_d90, to_date)
    bars_1y = await cached_yfinance_daily_bars(ticker, from_1y, to_date)

    rv = _realized_vol_30d(_daily_returns(bars_90d))
    ivr = _iv_rank_from_bars(bars_1y)

    spy_bars = await cached_yfinance_daily_bars("SPY", from_d90, to_date)
    seed_rets = _daily_returns(bars_90d)
    spy_rets = _daily_returns(spy_bars)
    beta_spy = _beta(seed_rets, spy_rets) if len(spy_rets) > 10 else 1.0

    prev = await yf.previous_close(ticker)
    price = prev["c"] if prev else 0.0
    prev_open = prev.get("o", price) if prev else price
    change_pct = round(((price - prev_open) / prev_open) * 100, 2) if prev_open else 0.0

    info = await _get_ticker_info(ticker)

    return SeedContext(
        ticker=ticker,
        name=info["name"],
        sector=info["sector"],
        market_cap_label=_market_cap_label(info["market_cap"]),
        price=round(price, 2),
        change_pct=change_pct,
        beta_spy=round(beta_spy, 2),
        realized_vol_30d=round(rv, 2),
        iv_rank=ivr,
    )


_MIN_AVG_VOLUME = 200_000


async def scan_similar(ticker: str, polygon: PolygonClient, top_n: int = 5) -> tuple[SeedContext, list[ScannerStock]]:
    seed_ctx_task = asyncio.create_task(build_seed_context(ticker))

    related = await _get_peers(ticker, polygon)
    if not related:
        seed_ctx = await seed_ctx_task
        return seed_ctx, []

    today = date.today()
    from_90 = (today - timedelta(days=90)).isoformat()
    from_1y = (today - timedelta(days=380)).isoformat()
    to_date = today.isoformat()

    seed_bars = await cached_yfinance_daily_bars(ticker, from_90, to_date)
    seed_returns = _daily_returns(seed_bars)
    if len(seed_returns) < 10:
        seed_ctx = await seed_ctx_task
        return seed_ctx, []

    async def _process(rel_ticker: str) -> ScannerStock | None:
        try:
            bars_90 = await cached_yfinance_daily_bars(rel_ticker, from_90, to_date)
            if len(bars_90) < 20:
                return None
            bars_1y = await cached_yfinance_daily_bars(rel_ticker, from_1y, to_date)
            stock = await _build_stock(rel_ticker, seed_returns, bars_90, bars_1y)
            if stock and stock.avg_volume < _MIN_AVG_VOLUME:
                return None
            return stock
        except Exception:
            return None

    tasks = [_process(t) for t in related[:15]]
    results = await asyncio.gather(*tasks)
    candidates = [s for s in results if s is not None]

    candidates.sort(key=lambda s: s.opportunity_score, reverse=True)

    seed_ctx = await seed_ctx_task
    return seed_ctx, candidates[:top_n]
