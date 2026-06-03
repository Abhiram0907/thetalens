from datetime import datetime, timedelta, timezone

from app.schemas.analysis import DataProvenance
from app.services.data_provenance import (
    build_data_provenance,
    build_vol_view_fields,
    spot_age_warning,
)
from app.services.market_data import MarketSnapshot, _price_contracts_bs


def test_spot_age_warning_when_stale():
    old = datetime.now(timezone.utc) - timedelta(hours=30)
    msg = spot_age_warning(old)
    assert msg is not None
    assert "not a live quote" in msg


def test_spot_age_warning_when_recent():
    recent = datetime.now(timezone.utc) - timedelta(hours=2)
    assert spot_age_warning(recent) is None


def test_build_vol_view_fields_from_agent():
    fields = build_vol_view_fields(
        {"iv_rank": 72.4, "regime": "High", "current_rv_30d": 48.2},
    )
    assert fields["realized_vol_rank"] == 72
    assert fields["realized_vol_regime"] == "High"
    assert fields["iv_rank"] == 72
    assert "realized vol" in fields["realized_vol_label"].lower()
    assert "not options IV" in fields["realized_vol_label"]


def test_price_contracts_uses_chain_implied_vol():
    refs = [
        {
            "ticker": "O:TEST260619C00100000",
            "strike_price": 100.0,
            "expiration_date": "2026-06-19",
            "contract_type": "call",
        }
    ]
    contracts, vol_input = _price_contracts_bs(
        refs, 100.0, iv_by_ticker={"O:TEST260619C00100000": 0.52}
    )
    assert vol_input == "implied"
    assert len(contracts) == 1
    assert contracts[0].iv == 0.52


def test_build_data_provenance_realized_vol():
    snap = MarketSnapshot(
        symbol="AAPL",
        spot=190.0,
        as_of=datetime.now(timezone.utc),
        contracts=[],
        front_expiry=None,
        back_expiry=None,
        spot_source="yfinance",
    )
    snap.pricing_vol_input = "realized_30d"
    prov = build_data_provenance(snap, sigma=0.42)
    assert prov.spot_source == "yfinance"
    assert prov.vol_input == "realized_30d"
    assert prov.options_price_method == "black_scholes_modeled"
    assert isinstance(prov, DataProvenance)
