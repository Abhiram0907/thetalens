"""
Tool registry for the Trade Thesis Agent.

Each tool is a thin wrapper around Polygon REST calls or local compute.
Tools are registered with JSON-schema descriptions so the LLM can select them.
"""

from __future__ import annotations

import inspect
import json
import math
import statistics
from datetime import date, datetime, timedelta
from typing import Any, Callable

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Tool metadata
# ---------------------------------------------------------------------------

class ToolSpec(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]
    fn: Callable = Field(exclude=True)

    class Config:
        arbitrary_types_allowed = True


_TOOL_REGISTRY: dict[str, ToolSpec] = {}


def tool(name: str, description: str):
    """Decorator that registers a function as an agent tool."""
    def decorator(fn: Callable):
        sig = inspect.signature(fn)
        params: dict[str, Any] = {
            "type": "object",
            "properties": {},
            "required": [],
        }
        for pname, p in sig.parameters.items():
            if pname in ("polygon_client",):
                continue
            ptype = "string"
            if p.annotation in (int, float):
                ptype = "number"
            elif p.annotation is bool:
                ptype = "boolean"
            params["properties"][pname] = {"type": ptype}
            if p.default is inspect.Parameter.empty:
                params["required"].append(pname)

        _TOOL_REGISTRY[name] = ToolSpec(
            name=name,
            description=description,
            parameters=params,
            fn=fn,
        )
        return fn
    return decorator


def get_tool(name: str) -> ToolSpec | None:
    return _TOOL_REGISTRY.get(name)


def tools_as_openai_schema() -> list[dict]:
    """Return tool specs in the OpenAI/Gemini function-calling schema."""
    out = []
    for t in _TOOL_REGISTRY.values():
        out.append({
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        })
    return out


from app.services.market_cache import TTL_DAILY_BARS, cached_async
from app.services.polygon_client import PolygonClient

# Re-export for agent routes and scanner
__all__ = ["PolygonClient"]


# ---------------------------------------------------------------------------
# Multi-source helpers
# ---------------------------------------------------------------------------

async def _get_daily_bars(ticker: str, from_date: str, to_date: str, polygon_client: PolygonClient) -> list[dict]:
    """Fetch daily bars from yfinance first, fallback to Polygon (cached)."""
    key = f"bars:{ticker.upper()}:{from_date}:{to_date}"

    async def _fetch() -> list[dict]:
        from app.tools.providers import get_yfinance_client

        try:
            bars = await get_yfinance_client().daily_bars(ticker, from_date, to_date)
            if bars and len(bars) > 5:
                return bars
        except Exception:
            pass
        return await polygon_client.daily_bars(ticker, from_date, to_date)

    return await cached_async(key, TTL_DAILY_BARS, _fetch)


async def _get_previous_close(ticker: str, polygon_client: PolygonClient) -> dict | None:
    """Fetch previous close from yfinance first, fallback to Polygon."""
    from app.tools.providers import get_yfinance_client
    try:
        prev = await get_yfinance_client().previous_close(ticker)
        if prev:
            return prev
    except Exception:
        pass
    return await polygon_client.previous_close(ticker)


# ---------------------------------------------------------------------------
# TOOL IMPLEMENTATIONS
# ---------------------------------------------------------------------------

@tool(
    name="get_iv_rank",
    description=(
        "Compute the implied-volatility rank for a ticker. Returns the current "
        "30-day realized vol, the 252-day high/low, IV rank (0-100), and a "
        "regime label (Low / Mid / High). Use this FIRST to decide whether to "
        "sell premium (high IV) or buy options (low IV)."
    ),
)
async def get_iv_rank(ticker: str, *, polygon_client: PolygonClient) -> dict:
    today = date.today()
    start = today - timedelta(days=380)
    bars = await _get_daily_bars(
        ticker, start.isoformat(), today.isoformat(), polygon_client
    )
    if len(bars) < 60:
        return {"error": f"Not enough price history for {ticker}", "bars": len(bars)}

    closes = [b["c"] for b in bars]

    # rolling 30-day realized vol (annualized)
    def _rv(prices: list[float]) -> float:
        log_rets = [math.log(prices[i] / prices[i - 1]) for i in range(1, len(prices))]
        return statistics.stdev(log_rets) * math.sqrt(252) * 100

    window = 30
    rv_series: list[float] = []
    for i in range(window, len(closes)):
        rv_series.append(_rv(closes[i - window : i + 1]))

    if not rv_series:
        return {"error": "Not enough data to compute rolling vol"}

    current_rv = rv_series[-1]
    rv_high = max(rv_series)
    rv_low = min(rv_series)
    denom = rv_high - rv_low
    iv_rank = round(((current_rv - rv_low) / denom) * 100, 1) if denom > 0 else 50.0

    if iv_rank < 30:
        regime = "Low"
    elif iv_rank < 70:
        regime = "Mid"
    else:
        regime = "High"

    return {
        "ticker": ticker,
        "current_rv_30d": round(current_rv, 2),
        "rv_252d_high": round(rv_high, 2),
        "rv_252d_low": round(rv_low, 2),
        "iv_rank": iv_rank,
        "regime": regime,
        "note": "IV rank is based on 30-day realized vol percentile over 252 trading days.",
    }


@tool(
    name="get_upcoming_earnings",
    description=(
        "Check whether the ticker has an upcoming earnings date within the "
        "trade horizon. Returns the next known earnings date, days until, and "
        "whether it falls inside the user's expiry window. Critical for "
        "deciding whether to structure around or avoid earnings IV crush."
    ),
)
async def get_upcoming_earnings(ticker: str, horizon_days: int = 90,
                                 *, polygon_client: PolygonClient) -> dict:
    horizon_days = int(horizon_days)
    today = date.today()

    # --- Try Finnhub first (actual earnings calendar) ---
    from app.tools.providers import get_finnhub_client
    import os
    fh = get_finnhub_client(os.environ.get("FINNHUB_API_KEY", ""))
    if fh:
        try:
            cal = await fh.earnings_calendar(
                ticker=ticker,
                from_date=today.isoformat(),
                to_date=(today + timedelta(days=horizon_days + 30)).isoformat(),
            )
            upcoming = [e for e in cal if e.get("date", "") >= today.isoformat()]
            if upcoming:
                next_date = upcoming[0]["date"]
                ed = datetime.strptime(next_date, "%Y-%m-%d").date()
                days_until = (ed - today).days
                return {
                    "ticker": ticker,
                    "estimated_next_earnings": next_date,
                    "days_until_earnings": days_until,
                    "earnings_in_trade_window": 0 < days_until <= horizon_days,
                    "recent_earnings_news": [],
                    "source": "finnhub",
                    "note": "Earnings date from Finnhub earnings calendar.",
                }
            past = await fh.company_earnings(ticker, limit=1)
            if past:
                last = past[0].get("period", "")
                if last:
                    last_dt = datetime.strptime(last, "%Y-%m-%d").date()
                    candidate = last_dt + timedelta(days=90)
                    while candidate < today:
                        candidate += timedelta(days=90)
                    days_until = (candidate - today).days
                    return {
                        "ticker": ticker,
                        "estimated_next_earnings": candidate.isoformat(),
                        "days_until_earnings": days_until,
                        "earnings_in_trade_window": 0 < days_until <= horizon_days,
                        "recent_earnings_news": [],
                        "source": "finnhub_estimated",
                        "note": "Next earnings estimated from last Finnhub earnings record + 90 days.",
                    }
        except Exception:
            pass

    # --- Fallback: Polygon news heuristic ---
    news = await polygon_client.ticker_news(ticker, limit=20)
    earnings_keywords = {"earnings", "quarterly results", "Q1", "Q2", "Q3", "Q4",
                         "revenue", "EPS", "beat", "miss", "guidance", "fiscal"}

    earnings_articles: list[dict] = []
    for article in news:
        title = (article.get("title") or "").lower()
        if any(kw.lower() in title for kw in earnings_keywords):
            earnings_articles.append({
                "title": article.get("title"),
                "published": article.get("published_utc", "")[:10],
                "source": article.get("publisher", {}).get("name", "unknown"),
            })

    estimated_next = None
    if earnings_articles:
        last_pub = earnings_articles[0].get("published", "")
        if last_pub:
            try:
                last_dt = datetime.strptime(last_pub[:10], "%Y-%m-%d").date()
                candidate = last_dt + timedelta(days=90)
                while candidate < today:
                    candidate += timedelta(days=90)
                estimated_next = candidate.isoformat()
            except ValueError:
                pass

    days_until = None
    in_window = False
    if estimated_next:
        try:
            ed = datetime.strptime(estimated_next, "%Y-%m-%d").date()
            days_until = (ed - today).days
            in_window = 0 < days_until <= horizon_days
        except ValueError:
            pass

    return {
        "ticker": ticker,
        "estimated_next_earnings": estimated_next,
        "days_until_earnings": days_until,
        "earnings_in_trade_window": in_window,
        "recent_earnings_news": earnings_articles[:5],
        "source": "polygon_news_heuristic",
        "note": (
            "Earnings date estimated from recent news cadence. "
            "Verify against the company's IR calendar for exact dates."
        ),
    }


@tool(
    name="get_historical_post_earnings_move",
    description=(
        "Get the historical post-earnings price move for the last N quarters. "
        "Returns the 1-day and 5-day percentage moves after each earnings date. "
        "Use to calibrate expected move magnitude and choose strike widths."
    ),
)
async def get_historical_post_earnings_move(
    ticker: str, quarters: int = 6, *, polygon_client: PolygonClient
) -> dict:
    quarters = int(quarters)
    today = date.today()
    lookback = today - timedelta(days=quarters * 100)
    bars = await _get_daily_bars(
        ticker, lookback.isoformat(), today.isoformat(), polygon_client
    )
    if len(bars) < 60:
        return {"error": "Not enough history", "bars_found": len(bars)}

    # Detect earnings-like gaps: days with >2% absolute gap from prev close
    moves: list[dict] = []
    for i in range(1, len(bars)):
        prev_close = bars[i - 1]["c"]
        open_price = bars[i]["o"]
        close_price = bars[i]["c"]
        gap_pct = ((open_price - prev_close) / prev_close) * 100

        if abs(gap_pct) >= 2.0:
            # Check 5-day forward return
            fwd_5d = None
            if i + 5 < len(bars):
                fwd_5d = round(((bars[i + 5]["c"] - prev_close) / prev_close) * 100, 2)

            ts = bars[i].get("t", 0)
            dt_str = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d") if ts else "unknown"

            moves.append({
                "date": dt_str,
                "gap_pct": round(gap_pct, 2),
                "day_move_pct": round(((close_price - prev_close) / prev_close) * 100, 2),
                "fwd_5d_pct": fwd_5d,
            })

    # Keep the largest gap per ~85-day window (approximate quarterly)
    filtered: list[dict] = []
    for m in sorted(moves, key=lambda x: abs(x["gap_pct"]), reverse=True):
        if not filtered or all(
            abs(
                (datetime.strptime(m["date"], "%Y-%m-%d") -
                 datetime.strptime(f["date"], "%Y-%m-%d")).days
            ) > 60
            for f in filtered
        ):
            filtered.append(m)
        if len(filtered) >= quarters:
            break

    filtered.sort(key=lambda x: x["date"], reverse=True)

    abs_moves = [abs(m["day_move_pct"]) for m in filtered]
    median_move = round(statistics.median(abs_moves), 2) if abs_moves else None

    return {
        "ticker": ticker,
        "post_earnings_moves": filtered,
        "median_absolute_move": median_move,
        "count": len(filtered),
        "note": "Moves detected via >2% opening gaps as earnings-date proxy.",
    }


@tool(
    name="get_news_sentiment",
    description=(
        "Fetch recent news headlines for the ticker and classify overall "
        "sentiment as bullish, bearish, or neutral. Returns headline summaries "
        "and a sentiment score. Use to cross-check the user's directional thesis."
    ),
)
async def get_news_sentiment(ticker: str, *, polygon_client: PolygonClient) -> dict:
    # --- Try Finnhub first (NLP-powered sentiment + company news) ---
    from app.tools.providers import get_finnhub_client
    import os
    fh = get_finnhub_client(os.environ.get("FINNHUB_API_KEY", ""))
    if fh:
        try:
            sentiment_data = await fh.news_sentiment(ticker)
            news_list = await fh.company_news(ticker, days_back=7)
            buzz = sentiment_data.get("buzz", {})
            sent = sentiment_data.get("sentiment", {})

            bull_pct = sent.get("bullishPercent", 0)
            bear_pct = sent.get("bearishPercent", 0)
            if bull_pct > bear_pct + 0.1:
                overall = "bullish"
            elif bear_pct > bull_pct + 0.1:
                overall = "bearish"
            else:
                overall = "neutral"

            score = round(bull_pct - bear_pct, 2)

            headlines = []
            for a in news_list[:7]:
                headlines.append({
                    "title": a.get("headline", ""),
                    "source": a.get("source", "unknown"),
                    "published": datetime.fromtimestamp(a.get("datetime", 0)).strftime("%Y-%m-%d") if a.get("datetime") else "",
                    "tone": "neutral",
                })

            return {
                "ticker": ticker,
                "overall_sentiment": overall,
                "sentiment_score": score,
                "headline_count": len(headlines),
                "headlines": headlines,
                "buzz_articles": buzz.get("articlesInLastWeek", 0),
                "source": "finnhub",
                "note": "Sentiment from Finnhub NLP analysis of recent news.",
            }
        except Exception:
            pass

    # --- Fallback: Polygon news + keyword matching ---
    articles = await polygon_client.ticker_news(ticker, limit=10)

    bullish_words = {"beat", "surge", "rally", "upgrade", "outperform", "record",
                     "growth", "strong", "jumps", "soars", "positive", "bullish",
                     "gains", "rises", "buy", "upside"}
    bearish_words = {"miss", "decline", "downgrade", "underperform", "weak",
                     "falls", "drops", "slump", "bearish", "cut", "risk",
                     "warns", "loss", "sell", "crash", "plunge", "concern"}

    headlines: list[dict] = []
    bull_score = 0
    bear_score = 0

    for a in articles:
        title = a.get("title", "")
        title_lower = title.lower()
        h_bull = sum(1 for w in bullish_words if w in title_lower)
        h_bear = sum(1 for w in bearish_words if w in title_lower)
        bull_score += h_bull
        bear_score += h_bear

        if h_bull > h_bear:
            tone = "bullish"
        elif h_bear > h_bull:
            tone = "bearish"
        else:
            tone = "neutral"

        headlines.append({
            "title": title,
            "source": a.get("publisher", {}).get("name", "unknown"),
            "published": (a.get("published_utc") or "")[:10],
            "tone": tone,
        })

    total = bull_score + bear_score
    if total == 0:
        overall = "neutral"
        score = 0.0
    else:
        score = round((bull_score - bear_score) / total, 2)
        if score > 0.2:
            overall = "bullish"
        elif score < -0.2:
            overall = "bearish"
        else:
            overall = "neutral"

    return {
        "ticker": ticker,
        "overall_sentiment": overall,
        "sentiment_score": score,
        "headline_count": len(headlines),
        "headlines": headlines[:7],
        "source": "polygon",
        "note": "Sentiment is keyword-based from recent Polygon news. Not a substitute for fundamental analysis.",
    }


@tool(
    name="get_expected_move",
    description=(
        "Calculate the market's expected move for the ticker over a given DTE "
        "based on current ATM straddle pricing. Returns the expected move in "
        "dollars and percent. Use to compare against the user's magnitude thesis."
    ),
)
async def get_expected_move(ticker: str, dte: int = 30,
                             *, polygon_client: PolygonClient) -> dict:
    dte = int(dte)
    prev = await _get_previous_close(ticker, polygon_client)
    if not prev:
        return {"error": f"No price data for {ticker}"}

    spot = prev["c"]

    # Fetch near-term options to estimate ATM straddle
    today = date.today()
    exp_min = today + timedelta(days=max(dte - 15, 7))
    exp_max = today + timedelta(days=dte + 15)

    contracts = await polygon_client.options_contracts(
        ticker,
        expiration_gte=exp_min.isoformat(),
        expiration_lte=exp_max.isoformat(),
        limit=100,
    )

    if not contracts:
        bars = await _get_daily_bars(
            ticker,
            (today - timedelta(days=60)).isoformat(),
            today.isoformat(),
            polygon_client,
        )
        if len(bars) < 20:
            return {"error": "Insufficient data for expected move estimate"}

        closes = [b["c"] for b in bars]
        log_rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
        daily_vol = statistics.stdev(log_rets)
        expected_pct = daily_vol * math.sqrt(dte) * 100
        expected_dollar = spot * expected_pct / 100

        return {
            "ticker": ticker,
            "spot": round(spot, 2),
            "dte": dte,
            "expected_move_pct": round(expected_pct, 2),
            "expected_move_dollar": round(expected_dollar, 2),
            "method": "realized_vol_estimate",
            "note": "Based on 30-day realized volatility, not options-implied.",
        }

    # Find ATM calls and puts
    atm_calls = [c for c in contracts if c.get("contract_type") == "call"]
    atm_puts = [c for c in contracts if c.get("contract_type") == "put"]

    atm_calls.sort(key=lambda c: abs(c.get("strike_price", 0) - spot))
    atm_puts.sort(key=lambda c: abs(c.get("strike_price", 0) - spot))

    atm_strike = atm_calls[0]["strike_price"] if atm_calls else spot

    bars = await _get_daily_bars(
        ticker,
        (today - timedelta(days=60)).isoformat(),
        today.isoformat(),
        polygon_client,
    )
    closes = [b["c"] for b in bars] if bars else [spot]
    if len(closes) > 1:
        log_rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
        daily_vol = statistics.stdev(log_rets)
    else:
        daily_vol = 0.015  # fallback ~24% annual

    expected_pct = daily_vol * math.sqrt(dte) * 100
    expected_dollar = spot * expected_pct / 100

    return {
        "ticker": ticker,
        "spot": round(spot, 2),
        "atm_strike": round(atm_strike, 2),
        "dte": dte,
        "expected_move_pct": round(expected_pct, 2),
        "expected_move_dollar": round(expected_dollar, 2),
        "method": "rv_proxy_with_contract_reference",
        "contracts_found": len(contracts),
    }


def _format_magnitude(direction: str, move_pct: float) -> str:
    d = direction.lower()
    pct = max(round(move_pct, 1), 1.0)
    if d in ("neutral", "range", "sideways"):
        return f"±{pct}% range"
    if d in ("bullish", "up"):
        lo = round(pct * 0.75, 1)
        hi = round(pct * 1.25, 1)
        return f"+{lo}% to +{hi}% rally"
    lo = round(pct * 0.75, 1)
    hi = round(pct * 1.25, 1)
    return f"-{lo}% to -{hi}% decline"


async def derive_magnitude(
    ticker: str,
    direction: str,
    horizon_days: int,
    *,
    polygon_client: PolygonClient,
) -> dict:
    """Compute magnitude from market expected move and historical gap data."""
    em = await get_expected_move(ticker, horizon_days, polygon_client=polygon_client)
    if em.get("error"):
        base = 5.0
        method = "default_fallback"
    else:
        base = float(em.get("expected_move_pct", 5.0))
        method = em.get("method", "expected_move")

    pem = await get_historical_post_earnings_move(
        ticker, quarters=4, polygon_client=polygon_client
    )
    median = pem.get("median_absolute_move")
    if isinstance(median, (int, float)) and median > base:
        base = (base + float(median)) / 2
        method = f"{method}_earnings_adjusted"

    magnitude = _format_magnitude(direction, base)
    return {
        "ticker": ticker,
        "magnitude": magnitude,
        "direction": direction,
        "horizon_days": horizon_days,
        "expected_move_pct": em.get("expected_move_pct"),
        "calibrated_move_pct": round(base, 2),
        "method": method,
        "note": "Calculated from market data — not user-specified.",
    }


@tool(
    name="calculate_magnitude",
    description=(
        "Calculate the expected price move magnitude for the trade thesis from market "
        "data (expected move, historical volatility, post-earnings moves). Call AFTER "
        "get_expected_move. The user does NOT provide magnitude — you must compute it."
    ),
)
async def calculate_magnitude(
    ticker: str,
    direction: str,
    horizon: str = "30 days",
    *,
    polygon_client: PolygonClient,
) -> dict:
    from app.services.strategy_builder import parse_horizon_days

    horizon_days = parse_horizon_days(horizon)
    return await derive_magnitude(
        ticker, direction, horizon_days, polygon_client=polygon_client
    )


@tool(
    name="assess_structure_fit",
    description=(
        "Given a vol regime, direction, and whether earnings falls in window, "
        "return which option structures are recommended and which are "
        "contraindicated. Use AFTER get_iv_rank and get_upcoming_earnings."
    ),
)
async def assess_structure_fit(
    direction: str,
    iv_regime: str,
    earnings_in_window: str,
    magnitude: str = "moderate",
    *,
    polygon_client: PolygonClient,
) -> dict:
    earnings_flag = earnings_in_window.lower() in ("true", "yes", "1")
    iv = iv_regime.lower()
    d = direction.lower()

    recommended: list[dict] = []
    avoid: list[dict] = []

    # --- BULLISH ---
    if d in ("bullish", "up"):
        if iv == "high":
            recommended.append({
                "structure": "Bull Put Spread (credit)",
                "reason": "Sells rich premium; defined risk; profits from theta and direction.",
            })
            recommended.append({
                "structure": "Short Put",
                "reason": "Maximum theta capture in high-IV; pair with defined risk if needed.",
            })
            avoid.append({
                "structure": "Long Call",
                "reason": "Overpaying for vega in high IV regime; vulnerable to IV crush.",
            })
            if earnings_flag:
                recommended.append({
                    "structure": "Call Diagonal (sell pre-earnings, buy post-earnings)",
                    "reason": "Captures IV crush on the short leg while keeping upside exposure.",
                })
        elif iv == "low":
            recommended.append({
                "structure": "Long Call / LEAPS Call",
                "reason": "Cheap premium; benefits from IV expansion and direction.",
            })
            recommended.append({
                "structure": "Call Debit Spread",
                "reason": "Defined risk; lower cost basis than naked call.",
            })
            avoid.append({
                "structure": "Bull Put Spread (credit)",
                "reason": "Low premium collected doesn't justify risk; poor reward/risk.",
            })
        else:  # mid
            recommended.append({
                "structure": "Bull Call Spread",
                "reason": "Balanced risk/reward in normal vol environment.",
            })
            recommended.append({
                "structure": "Call Diagonal",
                "reason": "Theta collection + directional exposure.",
            })

    # --- BEARISH ---
    elif d in ("bearish", "down"):
        if iv == "high":
            recommended.append({
                "structure": "Bear Call Spread (credit)",
                "reason": "Sells rich premium with defined risk.",
            })
            avoid.append({
                "structure": "Long Put",
                "reason": "Expensive vega exposure; IV crush will erode gains.",
            })
        elif iv == "low":
            recommended.append({
                "structure": "Long Put / Put Debit Spread",
                "reason": "Cheap premium; benefits from IV expansion on sell-off.",
            })
            recommended.append({
                "structure": "Put Calendar Spread",
                "reason": "Buy cheap long-dated vol, sell short-dated theta.",
            })
        else:
            recommended.append({
                "structure": "Bear Put Spread",
                "reason": "Defined risk directional play in normal environment.",
            })
            recommended.append({
                "structure": "Put Diagonal",
                "reason": "Theta offset + downside exposure.",
            })

    # --- NEUTRAL ---
    elif d in ("neutral", "range", "sideways"):
        if iv == "high":
            recommended.append({
                "structure": "Iron Condor",
                "reason": "Premium-rich environment ideal for range-bound selling.",
            })
            recommended.append({
                "structure": "Iron Butterfly",
                "reason": "Maximum premium collection at the money.",
            })
            avoid.append({
                "structure": "Long Straddle / Strangle",
                "reason": "Buying inflated vol in a neutral thesis is contradictory.",
            })
        elif iv == "low":
            recommended.append({
                "structure": "Long Straddle",
                "reason": "Cheap convexity; profits from any breakout.",
            })
            recommended.append({
                "structure": "Calendar Spread",
                "reason": "Buy cheap long-dated vol; theta collection from short leg.",
            })
        else:
            recommended.append({
                "structure": "Iron Condor",
                "reason": "Standard neutral income strategy.",
            })

    # Earnings overlay
    if earnings_flag:
        avoid.append({
            "structure": "Any undefined-risk short premium",
            "reason": "Earnings gap risk can exceed expected move significantly.",
        })

    return {
        "direction": direction,
        "iv_regime": iv_regime,
        "earnings_in_window": earnings_flag,
        "recommended_structures": recommended,
        "structures_to_avoid": avoid,
    }
