"""Export helpers: shareable line, thesis risk, provenance, sentiment headlines."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from app.schemas.analysis import DataProvenance, ParsedView
from app.schemas.research_report import SentimentHeadline

if TYPE_CHECKING:
    from app.schemas.research_report import ResearchReport


def format_data_as_of_display(provenance: DataProvenance) -> str:
    iso = provenance.spot_as_of
    source = provenance.spot_source or "yfinance"
    opts = "Options modeled at EOD mid (Black–Scholes)."
    if not iso:
        return f"Data via {source}. {opts}"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        human = dt.strftime("%B %-d, %Y, %-I:%M %p UTC")
    except ValueError:
        human = iso
    return f"Data as of {human} via {source}. {opts}"


def build_vol_context_line(enriched: dict[str, Any]) -> str:
    iv = enriched.get("get_iv_rank") or {}
    if iv.get("error"):
        return ""
    rank = iv.get("iv_rank")
    rv = iv.get("current_rv_30d")
    regime = iv.get("regime", "Mid")
    if rank is None or rv is None:
        return ""
    note = iv.get("note") or "Rank is 30d realized-vol percentile over ~252 sessions."
    if regime == "High":
        so_what = "Premium is relatively rich — structures that benefit from vol mean reversion or net-short vega merit scrutiny."
    elif regime == "Low":
        so_what = "Premium is relatively cheap — debit and long-vega structures are comparatively better supported."
    else:
        so_what = "Vol is mid-range — neither extreme favors aggressive premium selling nor long-vol lottery tickets."
    return f"Realized-vol rank {rank} ({regime}) with 30d RV ~{rv}%. {note} {so_what}"


def extract_sentiment_headlines(enriched: dict[str, Any], limit: int = 5) -> list[SentimentHeadline]:
    news = enriched.get("get_news_sentiment") or {}
    raw = news.get("headlines") or news.get("sample_headlines") or []
    out: list[SentimentHeadline] = []
    for h in raw[:limit]:
        if isinstance(h, str):
            out.append(SentimentHeadline(title=h))
        elif isinstance(h, dict):
            out.append(
                SentimentHeadline(
                    title=h.get("title") or h.get("headline") or "",
                    published=h.get("published") or h.get("date") or "",
                    source=h.get("source") or "",
                    tone=h.get("tone") or "",
                )
            )
    return [x for x in out if x.title.strip()]


def build_thesis_risk_callout(
    view: ParsedView,
    enriched: dict[str, Any],
) -> str | None:
    """Strongest contrarian risk — used by fallback brief when agent text is missing."""
    dir_l = view.direction.lower()
    risks: list[tuple[int, str]] = []

    news = enriched.get("get_news_sentiment") or {}
    sent = str(news.get("overall_sentiment", "")).lower()
    if sent and dir_l:
        if (dir_l == "bullish" and sent == "bearish") or (dir_l == "bearish" and sent == "bullish"):
            risks.append(
                (
                    90,
                    f"Headline sentiment is {sent} while your thesis is {dir_l} — "
                    f"you are fading near-term consensus.",
                )
            )

    iv = enriched.get("get_iv_rank") or {}
    if iv.get("regime") == "High" and dir_l == "bullish":
        risks.append(
            (
                70,
                "Rich vol regime — bullish debit structures pay elevated premium "
                "unless you have a strong timing edge.",
            )
        )

    em = enriched.get("get_expected_move") or {}
    if em.get("expected_move_pct") and view.magnitude:
        risks.append(
            (
                50,
                f"Options imply ±{em.get('expected_move_pct')}% — thesis must clear that move band.",
            )
        )

    if not risks:
        earnings = enriched.get("get_upcoming_earnings") or {}
        if not earnings.get("estimated_next_earnings"):
            return (
                f"No near-term earnings catalyst — the {dir_l} view must be driven "
                f"by sector/macro tape, not a discrete event."
            )
        return None

    risks.sort(key=lambda x: -x[0])
    return risks[0][1]


def build_export_shareable_line(report: "ResearchReport") -> str:
    view = report.parsed_view
    sym = view.underlying.upper()
    dir_short = (view.direction or "—").lower()[:4]
    horizon = view.horizon_label or view.horizon
    spot = view.underlying_price
    sector_name = "Sector"
    sector_ytd = ""
    if report.market_intel and report.market_intel.sector:
        s = report.market_intel.sector
        sector_ytd = f"{s.ticker_return_pct:+.1f}% YTD"
        if s.sector_etfs:
            sector_name = s.sector_etfs[0].label
        elif s.benchmark_label:
            sector_name = f"vs {s.benchmark_label}"
    tail = f"{sector_name} {sector_ytd}".strip()
    return f"{sym} {dir_short} {horizon} | Spot ${spot:.2f} | {tail}"
