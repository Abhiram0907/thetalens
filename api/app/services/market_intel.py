"""Gather sector, peer, macro, catalyst, flow, seasonality, and vol-term context."""

from __future__ import annotations

import asyncio
import logging
import os
import statistics
from datetime import date, datetime, timedelta
from typing import Any

from app.schemas.analysis import ParsedView
from app.schemas.market_intel import (
    AnalystConsensus,
    CatalystEvent,
    FlowsSnapshot,
    MacroIndicator,
    MarketIntel,
    PeerRow,
    SeasonalityNote,
    SectorPositioning,
    VolTermPoint,
    VolTermStructure,
    YtdReturnBar,
)
from app.tools.providers import get_finnhub_client, get_yfinance_client

logger = logging.getLogger(__name__)

BENCHMARK = "SPY"
DEFAULT_SECTOR_ETFS = ("SMH", "SOXX", "XLK")
SECTOR_ETF_MAP: dict[str, tuple[str, ...]] = {
    "Technology": ("SMH", "SOXX", "XLK"),
    "Semiconductors": ("SMH", "SOXX"),
    "Communication Services": ("XLC", "XLK"),
    "Consumer Cyclical": ("XLY", "SPY"),
    "Financial Services": ("XLF", "SPY"),
    "Healthcare": ("XLV", "SPY"),
    "Energy": ("XLE", "SPY"),
}

FALLBACK_PEERS: dict[str, list[str]] = {
    "NVDA": ["AMD", "AVGO", "INTC", "QCOM", "TSM"],
    "AMD": ["NVDA", "INTC", "AVGO", "QCOM", "TSM"],
    "AAPL": ["MSFT", "GOOGL", "META", "AMZN", "AVGO"],
    "TSLA": ["F", "GM", "RIVN", "LCID", "NIO"],
    "MSFT": ["AAPL", "GOOGL", "AMZN", "META", "ORCL"],
    "CRWV": ["NVDA", "AMD", "SMCI", "DELL", "ORCL"],
}

MACRO_TICKERS = {
    "10Y Treasury": "^TNX",
    "US Dollar (DXY)": "DX-Y.NYB",
    "VIX": "^VIX",
}

# Fed meeting dates (update quarterly). Used for macro context on 30+ DTE trades.
_FOMC_DATES_2026 = [
    date(2026, 1, 28),
    date(2026, 3, 18),
    date(2026, 4, 29),
    date(2026, 6, 17),
    date(2026, 7, 29),
    date(2026, 9, 16),
    date(2026, 10, 28),
    date(2026, 12, 9),
]


def _next_fomc_note() -> str:
    today = date.today()
    for d in _FOMC_DATES_2026:
        if d >= today:
            days = (d - today).days
            return f"Next FOMC: {d.strftime('%b %d, %Y')} ({days}d) — event risk for holds through the decision."
    return ""


def _parse_event_date(raw: str) -> date | None:
    if not raw:
        return None
    raw = raw.strip()[:10]
    for fmt in ("%Y-%m-%d", "%Y-%m", "%b %Y", "%B %Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    if len(raw) >= 4 and raw[:4].isdigit():
        try:
            return date(int(raw[:4]), 1, 1)
        except ValueError:
            pass
    return None


def _catalysts_stale_note(events: list[CatalystEvent]) -> str:
    dates = [_parse_event_date(ev.date) for ev in events]
    valid = [d for d in dates if d]
    if not valid:
        return "No dated headlines in the window — catalyst list may be incomplete."
    latest = max(valid)
    age_days = (date.today() - latest).days
    if age_days > 120:
        return (
            f"Most recent dated item: {latest.strftime('%b %Y')} — "
            f"limited recent coverage; stale headlines are a data gap, not a quiet tape."
        )
    return ""


def _year_start() -> str:
    return date.today().replace(month=1, day=1).isoformat()


def _today() -> str:
    return date.today().isoformat()


async def _ytd_return_pct(symbol: str) -> float | None:
    yf = get_yfinance_client()
    bars = await yf.daily_bars(symbol, _year_start(), _today())
    if len(bars) < 2:
        return None
    start, end = bars[0]["c"], bars[-1]["c"]
    if start <= 0:
        return None
    return round((end / start - 1) * 100, 2)


def _rv_rank_from_closes(closes: list[float]) -> float | None:
    if len(closes) < 60:
        return None
    import math

    def _rv(prices: list[float]) -> float:
        log_rets = [math.log(prices[i] / prices[i - 1]) for i in range(1, len(prices))]
        return statistics.stdev(log_rets) * math.sqrt(252) * 100

    window = 30
    rv_series: list[float] = []
    for i in range(window, len(closes)):
        rv_series.append(_rv(closes[i - window : i + 1]))
    if not rv_series:
        return None
    current = rv_series[-1]
    lo, hi = min(rv_series), max(rv_series)
    if hi <= lo:
        return 50.0
    return round(((current - lo) / (hi - lo)) * 100, 1)


async def _iv_rank_for_symbol(symbol: str) -> float | None:
    yf = get_yfinance_client()
    start = (date.today() - timedelta(days=380)).isoformat()
    bars = await yf.daily_bars(symbol, start, _today())
    if len(bars) < 60:
        return None
    return _rv_rank_from_closes([b["c"] for b in bars])


def _fmt_cap(val: float | None) -> str:
    if val is None or val <= 0:
        return "—"
    if val >= 1e12:
        return f"${val / 1e12:.2f}T"
    if val >= 1e9:
        return f"${val / 1e9:.1f}B"
    if val >= 1e6:
        return f"${val / 1e6:.0f}M"
    return f"${val:,.0f}"


def _fmt_pe(info: dict) -> str:
    fwd = info.get("forwardPE")
    trail = info.get("trailingPE")
    if fwd and fwd > 0:
        return f"{fwd:.1f} fwd"
    if trail and trail > 0:
        return f"{trail:.1f}"
    return "—"


async def _resolve_peers(ticker: str, info: dict | None = None) -> list[str]:
    sym = ticker.upper()
    info = info or {}
    fh = get_finnhub_client(os.environ.get("FINNHUB_API_KEY", ""))
    peers: list[str] = []
    if fh:
        try:
            peers = (await fh.company_peers(sym))[:8]
        except Exception:
            logger.debug("Finnhub peers failed for %s", sym, exc_info=True)
    if not peers:
        peers = list(FALLBACK_PEERS.get(sym, []))
    sector = (info.get("sector") or "").strip()
    if len(peers) < 3:
        for etf in SECTOR_ETF_MAP.get(sector, DEFAULT_SECTOR_ETFS):
            if etf not in peers and etf != sym:
                peers.append(etf)
    out = [sym] + [p for p in peers if p != sym]
    return out[:6]


def _business_blurb(ticker: str, info: dict) -> tuple[str, str, str]:
    sector = (info.get("sector") or "").strip()
    industry = (info.get("industry") or "").strip()
    raw = (info.get("longBusinessSummary") or "").strip()
    if raw:
        blurb = raw if len(raw) <= 280 else raw[:277].rsplit(" ", 1)[0] + "..."
    elif industry and sector:
        blurb = f"{ticker.upper()} operates in {industry} ({sector})."
    elif industry:
        blurb = f"{ticker.upper()} operates in {industry}."
    else:
        blurb = ""
    return sector, industry, blurb


async def _build_sector(ticker: str, info: dict) -> SectorPositioning | None:
    sector_name, industry, business_blurb = _business_blurb(ticker, info)
    etfs = SECTOR_ETF_MAP.get(sector_name, DEFAULT_SECTOR_ETFS)
    symbols = [ticker.upper(), BENCHMARK, *etfs]
    returns = await asyncio.gather(*[_ytd_return_pct(s) for s in symbols])
    by_sym = dict(zip(symbols, returns, strict=True))
    ticker_ret = by_sym.get(ticker.upper())
    bench_ret = by_sym.get(BENCHMARK)
    if ticker_ret is None or bench_ret is None:
        return None

    bars: list[YtdReturnBar] = []
    for etf in etfs:
        r = by_sym.get(etf)
        if r is not None:
            bars.append(YtdReturnBar(symbol=etf, label=etf, return_pct=r))

    best = max(bars, key=lambda b: b.return_pct) if bars else None
    if best and best.return_pct > bench_ret + 3:
        regime = "leading"
        lead = f"{best.label} +{best.return_pct:.1f}% YTD vs {BENCHMARK} +{bench_ret:.1f}% — sector tide is strong"
    elif best and best.return_pct < bench_ret - 3:
        regime = "lagging"
        lead = f"{best.label} +{best.return_pct:.1f}% YTD vs {BENCHMARK} +{bench_ret:.1f}% — sector lagging the market"
    else:
        regime = "in line"
        lead = f"{ticker.upper()} {ticker_ret:+.1f}% YTD vs {BENCHMARK} {bench_ret:+.1f}% — near market pace"

    narrative = (
        f"{ticker.upper()} {ticker_ret:+.1f}% YTD vs {BENCHMARK} (SPX proxy) {bench_ret:+.1f}%. "
        f"Sector posture: {regime}. {lead}."
    )
    return SectorPositioning(
        ticker_return_pct=ticker_ret,
        benchmark_return_pct=bench_ret,
        benchmark_label="SPX (SPY)",
        sector_etfs=bars,
        narrative=narrative,
        sector_name=sector_name,
        industry=industry,
        business_blurb=business_blurb,
    )


async def _build_peers(ticker: str, info: dict | None = None) -> list[PeerRow]:
    symbols = await _resolve_peers(ticker, info)
    yf = get_yfinance_client()

    async def _row(sym: str) -> PeerRow:
        ytd, iv = await asyncio.gather(_ytd_return_pct(sym), _iv_rank_for_symbol(sym))
        try:
            info = await yf.ticker_info(sym)
        except Exception:
            info = {}
        return PeerRow(
            symbol=sym,
            ytd_return_pct=ytd,
            iv_rank=iv,
            pe=_fmt_pe(info),
            market_cap=_fmt_cap(info.get("marketCap")),
        )

    return await asyncio.gather(*[_row(s) for s in symbols])


async def _month_change_pct(symbol: str, days: int = 30) -> float | None:
    yf = get_yfinance_client()
    start = (date.today() - timedelta(days=days + 5)).isoformat()
    bars = await yf.daily_bars(symbol, start, _today())
    if len(bars) < 2:
        return None
    old = bars[0]["c"]
    new = bars[-1]["c"]
    if old <= 0:
        return None
    return round((new / old - 1) * 100, 2)


async def _build_macro(view: ParsedView) -> list[MacroIndicator]:
    dir_l = view.direction.lower()
    growth_sensitive = dir_l in ("bullish", "bearish") and view.magnitude

    out: list[MacroIndicator] = []
    for name, sym in MACRO_TICKERS.items():
        yf = get_yfinance_client()
        try:
            bars = await yf.daily_bars(sym, (date.today() - timedelta(days=35)).isoformat(), _today())
            if not bars:
                continue
            level = bars[-1]["c"]
            chg = await _month_change_pct(sym)
        except Exception:
            continue

        if "TNX" in sym:
            val = f"{level:.2f}%"
            trend = f"{chg:+.1f}% over 30d" if chg is not None else ""
            if chg and chg > 0.5:
                impact, note = "headwind", (
                    "Rising yields compress high-multiple growth valuations."
                )
            elif chg and chg < -0.5:
                impact, note = "tailwind", "Falling yields support duration-sensitive growth."
            else:
                impact, note = "neutral", "Rates stable — less macro drag on multiples."
        elif "VIX" in sym:
            val = f"{level:.1f}"
            trend = f"{chg:+.1f}% over 30d" if chg is not None else ""
            if level >= 22:
                impact, note = "headwind", "Elevated fear — wider spreads and gap risk."
            elif level <= 14:
                impact, note = "neutral", "Complacent vol — cheap hedges, smaller premiums."
            else:
                impact, note = "neutral", "Mid-range vol — balanced premium environment."
        else:
            val = f"{level:.2f}"
            trend = f"{chg:+.1f}% over 30d" if chg is not None else ""
            if chg and chg > 1:
                impact, note = "headwind", "Stronger dollar can pressure multinational earnings."
            elif chg and chg < -1:
                impact, note = "tailwind", "Weaker dollar supports risk assets."
            else:
                impact, note = "neutral", "Dollar range-bound."

        if growth_sensitive and "TNX" in sym and dir_l == "bullish" and impact == "headwind":
            note += f" Caution for {view.underlying} long-vol/debit structures."

        out.append(
            MacroIndicator(
                name=name,
                value=val,
                trend=trend,
                thesis_impact=impact,
                note=note,
            )
        )

    fomc = _next_fomc_note()
    if fomc:
        out.append(
            MacroIndicator(
                name="Fed calendar",
                value="FOMC",
                trend="",
                thesis_impact="neutral",
                note=fomc,
            )
        )
    return out


def _classify_headline(title: str) -> str:
    t = title.lower()
    if any(w in t for w in ("earnings", "eps", "revenue", "guidance", "beat", "miss")):
        return "earnings"
    if any(w in t for w in ("upgrade", "downgrade", "price target", "analyst", "rating")):
        return "analyst"
    if any(w in t for w in ("launch", "product", "chip", "partnership", "contract", "deal")):
        return "product"
    if any(w in t for w in ("sec", "regulat", "antitrust", "ban", "probe")):
        return "regulatory"
    if any(w in t for w in ("ceo", "cfo", "executive", "resign", "appoint")):
        return "management"
    return "news"


async def _build_catalysts(ticker: str, enriched: dict[str, Any]) -> list[CatalystEvent]:
    events: list[CatalystEvent] = []
    news = enriched.get("get_news_sentiment") or {}
    for h in (news.get("headlines") or news.get("sample_headlines") or [])[:8]:
        if not isinstance(h, dict):
            continue
        title = h.get("title") or h.get("headline") or ""
        if not title:
            continue
        events.append(
            CatalystEvent(
                date=h.get("published") or h.get("date") or "",
                description=title[:200],
                category=_classify_headline(title),
            )
        )

    fh = get_finnhub_client(os.environ.get("FINNHUB_API_KEY", ""))
    if fh:
        try:
            for e in (await fh.company_earnings(ticker, limit=4))[:3]:
                period = e.get("period", "")
                actual = e.get("actual")
                estimate = e.get("estimate")
                if actual is None:
                    continue
                surprise = ""
                if estimate:
                    surprise = f" (est {estimate})"
                events.append(
                    CatalystEvent(
                        date=period,
                        description=f"EPS {actual}{surprise}",
                        category="earnings",
                    )
                )
        except Exception:
            pass

    earnings = enriched.get("get_upcoming_earnings") or {}
    if earnings.get("estimated_next_earnings"):
        events.insert(
            0,
            CatalystEvent(
                date=str(earnings.get("estimated_next_earnings", "")),
                description=(
                    f"Next earnings ~{earnings.get('days_until', '?')}d "
                    f"({'in' if earnings.get('earnings_in_trade_window') else 'outside'} trade window)"
                ),
                category="earnings",
            ),
        )

    seen: set[str] = set()
    deduped: list[CatalystEvent] = []
    for ev in events:
        key = f"{ev.date}:{ev.description[:40]}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ev)
    return deduped[:5]


async def _build_flows(ticker: str) -> FlowsSnapshot | None:
    try:
        info = await get_yfinance_client().ticker_info(ticker)
    except Exception:
        return None
    lines: list[str] = []
    short_pct = info.get("shortPercentOfFloat")
    if short_pct is not None:
        lines.append(f"Short interest: {short_pct * 100:.1f}% of float")
    shares_short = info.get("sharesShort")
    prior = info.get("sharesShortPriorMonth")
    if shares_short and prior and prior > 0:
        chg = (shares_short - prior) / prior * 100
        lines.append(
            f"Shares short: {shares_short:,.0f} ({chg:+.1f}% vs prior month; 13F/short data lagged)"
        )
    inst = info.get("heldPercentInstitutions")
    if inst is not None:
        lines.append(f"Institutional ownership: {inst * 100:.1f}%")
    if not lines:
        return None
    return FlowsSnapshot(lines=lines)


async def _build_seasonality(ticker: str) -> SeasonalityNote | None:
    yf = get_yfinance_client()
    start = (date.today() - timedelta(days=365 * 11)).isoformat()
    bars = await yf.daily_bars(ticker, start, _today())
    if len(bars) < 200:
        return None

    month = date.today().month
    month_name = datetime(2000, month, 1).strftime("%B")
    by_year: dict[int, list[float]] = {}
    for i in range(1, len(bars)):
        ts = bars[i]["t"]
        dt = datetime.fromtimestamp(ts / 1000)
        if dt.month != month:
            continue
        prev = bars[i - 1]["c"]
        cur = bars[i]["c"]
        if prev <= 0:
            continue
        by_year.setdefault(dt.year, []).append((cur / prev - 1) * 100)

    yearly_returns = [sum(v) for v in by_year.values() if v]
    if len(yearly_returns) < 4:
        return None
    wins = sum(1 for r in yearly_returns if r > 0)
    avg = statistics.mean(yearly_returns)
    return SeasonalityNote(
        text=(
            f"{ticker.upper()} in {month_name}: positive in {wins} of the last {len(yearly_returns)} "
            f"years, average return {avg:+.1f}% (calendar month, not holding-period forecast)."
        )
    )


async def _build_vol_term(ticker: str) -> VolTermStructure | None:
    def _fetch() -> VolTermStructure | None:
        import yfinance as yf

        tk = yf.Ticker(ticker)
        if not getattr(tk, "options", None) or not tk.options:
            return None
        exps = list(tk.options)[:4]
        points: list[VolTermPoint] = []
        spot = tk.fast_info.get("last_price") or tk.info.get("currentPrice")
        for exp in exps[:3]:
            try:
                chain = tk.option_chain(exp)
            except Exception:
                continue
            exp_date = datetime.strptime(exp, "%Y-%m-%d").date()
            dte = max((exp_date - date.today()).days, 1)
            calls = chain.calls
            if calls.empty or spot is None:
                continue
            calls = calls.copy()
            calls["dist"] = (calls["strike"] - spot).abs()
            row = calls.sort_values("dist").iloc[0]
            iv = row.get("impliedVolatility")
            if iv is None or iv <= 0:
                continue
            points.append(
                VolTermPoint(label=f"{dte}d", dte=dte, iv_pct=round(float(iv) * 100, 1))
            )
        if len(points) < 2:
            return None
        front, back = points[0].iv_pct, points[-1].iv_pct
        if front > back + 3:
            shape = "backwardation"
            narrative = (
                f"Front-month IV ({front:.1f}%) > back ({back:.1f}%) — market pricing a near-term event "
                f"or earnings skew; favor expiries after the front bump."
            )
        elif back > front + 3:
            shape = "contango"
            narrative = (
                f"Term structure in contango ({points[0].label} {front:.1f}% → {points[-1].label} {back:.1f}%) — "
                f"typical carry; calendar/diagonal structures can harvest roll-down."
            )
        else:
            shape = "flat"
            narrative = (
                f"IV term structure relatively flat ({front:.1f}% → {back:.1f}%) — "
                f"no strong event premium in the front."
            )
        return VolTermStructure(points=points, shape=shape, narrative=narrative)

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch)


_RATING_KEY_LABELS = {
    "strong_buy": "Strong Buy",
    "buy": "Buy",
    "hold": "Hold",
    "underperform": "Underperform",
    "sell": "Sell",
    "strong_sell": "Strong Sell",
    "none": "—",
}


def _label_from_mean(score: float) -> str:
    if score <= 1.5:
        return "Strong Buy"
    if score <= 2.5:
        return "Buy"
    if score <= 3.5:
        return "Hold"
    if score <= 4.5:
        return "Underperform"
    return "Sell"


def _pct_vs(spot: float, target: float | None) -> float | None:
    if target is None or spot <= 0:
        return None
    return round((target / spot - 1) * 100, 2)


async def _build_analyst_consensus(
    ticker: str,
    info: dict,
    spot: float | None,
) -> AnalystConsensus | None:
    sym = ticker.upper()
    spot_px = spot or info.get("currentPrice") or info.get("regularMarketPrice")
    if not spot_px or spot_px <= 0:
        return None

    mean_t = info.get("targetMeanPrice")
    high_t = info.get("targetHighPrice")
    low_t = info.get("targetLowPrice")
    if mean_t is None and high_t is None and low_t is None:
        return None

    key = str(info.get("recommendationKey") or "").lower().replace(" ", "_")
    mean_score = info.get("recommendationMean")
    rating = _RATING_KEY_LABELS.get(key) or (
        _label_from_mean(float(mean_score)) if mean_score else "—"
    )
    n_analysts = info.get("numberOfAnalystOpinions")

    buy_c = hold_c = sell_c = None
    fh = get_finnhub_client(os.environ.get("FINNHUB_API_KEY", ""))
    if fh:
        try:
            trends = await fh.recommendation_trends(sym)
            if trends:
                latest = trends[0]
                buy_c = (latest.get("buy") or 0) + (latest.get("strongBuy") or 0)
                hold_c = latest.get("hold") or 0
                sell_c = (latest.get("sell") or 0) + (latest.get("strongSell") or 0)
        except Exception:
            logger.debug("Finnhub recommendation trends failed for %s", sym, exc_info=True)

    upside_mean = _pct_vs(spot_px, mean_t)
    upside_high = _pct_vs(spot_px, high_t)
    downside_low = _pct_vs(spot_px, low_t)

    target_range = ""
    if mean_t:
        target_range = f"${mean_t:,.2f} mean"
        if low_t and high_t:
            target_range += f" (range ${low_t:,.2f}–${high_t:,.2f})"
    elif low_t and high_t:
        target_range = f"${low_t:,.2f}–${high_t:,.2f}"

    up_s = f"+{upside_mean:.1f}% to mean" if upside_mean is not None else ""
    down_s = f"{downside_low:+.1f}% to low" if downside_low is not None else ""
    parts = [f"Street consensus: {rating}"]
    if n_analysts:
        parts[0] += f" ({int(n_analysts)} analysts)"
    if target_range:
        parts.append(f"Targets {target_range} vs spot ${spot_px:,.2f}")
    if up_s and down_s:
        parts.append(f"Upside {up_s} · Downside {down_s}")
    elif up_s:
        parts.append(f"Upside {up_s}")
    if buy_c is not None and hold_c is not None:
        parts.append(f"Recent ratings mix: {buy_c} buy / {hold_c} hold / {sell_c or 0} sell")

    return AnalystConsensus(
        consensus_rating=rating,
        rating_score=round(float(mean_score), 2) if mean_score else None,
        num_analysts=int(n_analysts) if n_analysts else None,
        target_mean=float(mean_t) if mean_t else None,
        target_high=float(high_t) if high_t else None,
        target_low=float(low_t) if low_t else None,
        current_price=round(float(spot_px), 2),
        upside_to_mean_pct=upside_mean,
        upside_to_high_pct=upside_high,
        downside_to_low_pct=downside_low,
        buy_count=buy_c,
        hold_count=hold_c,
        sell_count=sell_c,
        narrative=" ".join(parts) + ".",
    )


async def gather_market_intel(
    ticker: str,
    view: ParsedView,
    enriched: dict[str, Any] | None = None,
) -> MarketIntel:
    enriched = enriched or {}
    sym = ticker.upper()
    try:
        info = await get_yfinance_client().ticker_info(sym)
    except Exception:
        info = {}

    analyst = _build_analyst_consensus(sym, info, view.underlying_price)
    sector, peers, macro, catalysts, flows, seasonality, vol_term, analyst_result = (
        await asyncio.gather(
            _build_sector(sym, info),
            _build_peers(sym, info),
            _build_macro(view),
            _build_catalysts(sym, enriched),
            _build_flows(sym),
            _build_seasonality(sym),
            _build_vol_term(sym),
            analyst,
        )
    )

    catalyst_list = list(catalysts)
    stale_note = _catalysts_stale_note(catalyst_list)

    return MarketIntel(
        sector=sector,
        peers=list(peers),
        macro=list(macro),
        catalysts=catalyst_list,
        catalysts_stale_note=stale_note,
        flows=flows,
        seasonality=seasonality,
        vol_term=vol_term,
        analyst=analyst_result,
    )
