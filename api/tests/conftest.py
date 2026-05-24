"""Shared pytest fixtures."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services.market_data import MarketSnapshot, OptionContract


def _contract(
    strike: float,
    expiry: date,
    contract_type: str,
    mid: float = 2.50,
) -> OptionContract:
    return OptionContract(
        ticker=f"O:{strike}{contract_type[0].upper()}",
        strike=strike,
        expiry=expiry,
        contract_type=contract_type,
        mid=mid,
        bid=None,
        ask=None,
        open_interest=100,
        iv=0.35,
        delta=None,
        gamma=None,
        theta=None,
        vega=None,
    )


@pytest.fixture
def sample_snapshot() -> MarketSnapshot:
    """Minimal option chain around $100 spot for strategy builder tests."""
    today = date.today()
    front = today + timedelta(days=30)
    back = today + timedelta(days=60)
    spot = 100.0
    ratios_puts = [0.92, 0.94, 0.95, 0.96, 0.98, 1.0]
    ratios_calls = [1.0, 1.03, 1.04, 1.05, 1.08, 1.1, 1.2]
    contracts: list[OptionContract] = []
    for exp in (front, back):
        for r in ratios_puts:
            contracts.append(_contract(round(spot * r, 2), exp, "put", mid=1.5 + r))
        for r in ratios_calls:
            contracts.append(_contract(round(spot * r, 2), exp, "call", mid=1.5 + r))
    return MarketSnapshot(
        symbol="TEST",
        spot=spot,
        as_of=None,
        contracts=contracts,
        front_expiry=front,
        back_expiry=back,
    )
