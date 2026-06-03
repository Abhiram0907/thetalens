"""Build data-quality metadata for API responses."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from app.schemas.analysis import DataProvenance, ParsedView
from app.services.market_data import MarketSnapshot
from app.services.market_types import SpotSource, VolInput

_STALE_SPOT_HOURS = 24


def spot_age_warning(as_of: datetime | None) -> str | None:
    if as_of is None:
        return (
            "Underlying price timestamp is unknown; figure may not reflect the latest session."
        )
    now = datetime.now(timezone.utc)
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    age = now - as_of
    if age > timedelta(hours=_STALE_SPOT_HOURS):
        days = max(1, int(age.total_seconds() // 86400))
        return (
            f"Underlying price is about {days} day(s) old "
            f"({as_of.strftime('%Y-%m-%d %H:%M UTC')}); not a live quote."
        )
    return None


def resolve_vol_input(sigma: float | None) -> VolInput:
    if sigma is not None and sigma > 0:
        return "realized_30d"
    return "default"


def build_data_provenance(
    snapshot: MarketSnapshot,
    *,
    sigma: float | None = None,
) -> DataProvenance:
    spot_as_of = snapshot.as_of
    iso = spot_as_of.isoformat() if spot_as_of else None
    source: SpotSource = snapshot.spot_source if snapshot.spot_source in ("yfinance", "polygon") else "yfinance"
    vol_input = getattr(snapshot, "pricing_vol_input", None) or resolve_vol_input(sigma)
    return DataProvenance(
        spot_source=source,
        spot_as_of=iso,
        options_price_method="black_scholes_modeled",
        vol_input=vol_input,
        data_age_warning=spot_age_warning(spot_as_of),
    )


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def build_vol_view_fields(
    iv_data: dict | None,
    *,
    fallback_rank: int | None = None,
    fallback_label: str | None = None,
) -> dict[str, str | int]:
    """Populate realized-vol fields; keep iv_rank / iv_label as backward-compatible aliases."""
    data = iv_data or {}
    if data and not data.get("error"):
        rank = int(round(float(data.get("iv_rank", 50))))
        regime = str(data.get("regime", "Mid"))
        label = f"{_ordinal(rank)} percentile · 30d realized vol (not options IV)"
        return {
            "realized_vol_rank": rank,
            "realized_vol_regime": regime,
            "realized_vol_label": label,
            "iv_rank": rank,
            "iv_label": label,
            "volatility_view": regime,
        }

    rank = int(fallback_rank if fallback_rank is not None else 50)
    label = fallback_label or f"{_ordinal(rank)} percentile (estimated · not options IV)"
    regime = "Estimated"
    return {
        "realized_vol_rank": rank,
        "realized_vol_regime": regime,
        "realized_vol_label": label,
        "iv_rank": rank,
        "iv_label": label,
        "volatility_view": regime,
    }


def merge_parsed_view_vol(
    view: ParsedView,
    iv_data: dict | None,
    *,
    fallback_rank: int | None = None,
    fallback_label: str | None = None,
) -> ParsedView:
    fields = build_vol_view_fields(
        iv_data,
        fallback_rank=fallback_rank,
        fallback_label=fallback_label,
    )
    return view.model_copy(update=fields)
