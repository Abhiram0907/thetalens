"""Evaluate fallback intent parser accuracy on a fixed prompt set."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.intent import _fallback_slots


@dataclass
class EvalCase:
    query: str
    underlying: str | None
    direction: str | None
    horizon: str | None
    risk_budget: str | None
    mode: str = "thesis"


CASES: list[EvalCase] = [
    EvalCase("NVDA bullish rally, 2 weeks, risk $1000", "NVDA", "Bullish", "2 weeks", "$1,000"),
    EvalCase("I think TSLA drops 10% in the next month, budget $500", "TSLA", "Bearish", "1 month", "$500"),
    EvalCase("What's the best options play on AAPL right now?", "AAPL", None, None, None),
    EvalCase("Play AMD earnings with $750", "AMD", None, None, "$750"),
    EvalCase("SPY range-bound sideways for 3 weeks", "SPY", "Neutral", "3 weeks", None),
    EvalCase("Microsoft puts, bearish, 1 month", "MSFT", "Bearish", "1 month", None),
    EvalCase("$META long calls, 45 days", "META", "Bullish", "45 days", None),
    EvalCase("Amazon looks weak, short term", "AMZN", "Bearish", None, None),
    EvalCase("Stocks that move like NBIS", "NBIS", None, None, None),  # mode not in fallback
    EvalCase("Find tickers similar to COIN", "COIN", None, None, None),
    EvalCase("Underlying: HOOD\nDirection: Bullish\nHorizon: 60 days\nRisk budget: $300", "HOOD", "Bullish", "60 days", "$300"),
    EvalCase("Nvidia going up after earnings, max loss 2k", "NVDA", "Bullish", None, "$2,000"),
    EvalCase("Neutral iron condor on QQQ, 30 days", "QQQ", "Neutral", "30 days", None),
    EvalCase("I want to sell premium on INTC", "INTC", None, None, None),
    EvalCase("Tesla crash incoming, buy puts $500 risk", "TSLA", "Bearish", None, "$500"),
    EvalCase("Best LEAP on Apple 6 months", "AAPL", None, "6 months", None),
    EvalCase("GOOG bullish 2-3 weeks", "GOOG", "Bullish", "2–3 weeks", None),
    EvalCase("Risk budget: $250 on NVDA calls", "NVDA", "Bullish", None, "$250"),
    EvalCase("What moves similar to MSTR?", "MSTR", None, None, None),
    EvalCase("Bearish view on Netflix 1 week", None, "Bearish", "1 week", None),  # NFLX not in company map
]


def _match(expected: str | None, actual: str | None) -> bool:
    if expected is None:
        return actual is None
    if actual is None:
        return False
    return expected.lower() in actual.lower() or actual.lower() in expected.lower()


def run_eval() -> dict:
    fields = ["underlying", "direction", "horizon", "risk_budget"]
    totals = {f: {"correct": 0, "total": 0} for f in fields}
    rows: list[dict] = []

    for case in CASES:
        slots = _fallback_slots(case.query)
        row = {"query": case.query[:50]}
        for field in fields:
            expected = getattr(case, field)
            actual = getattr(slots, field)
            if expected is not None:
                totals[field]["total"] += 1
                ok = _match(expected, actual)
                if ok:
                    totals[field]["correct"] += 1
                row[field] = "✓" if ok else f"✗ ({actual})"
            else:
                row[field] = "—" if actual is None else f"~ ({actual})"
        rows.append(row)

    weighted_correct = sum(t["correct"] for t in totals.values())
    weighted_total = sum(t["total"] for t in totals.values())
    overall = round(100 * weighted_correct / weighted_total, 1) if weighted_total else 0

    return {"rows": rows, "totals": totals, "overall_pct": overall}


def main() -> None:
    result = run_eval()
    print(f"Overall field accuracy (fallback parser): {result['overall_pct']}%")
    print()
    for field, stats in result["totals"].items():
        if stats["total"]:
            pct = round(100 * stats["correct"] / stats["total"], 1)
            print(f"  {field}: {stats['correct']}/{stats['total']} ({pct}%)")
    print()
    for row in result["rows"]:
        print(f"- {row['query']}")
        print(f"    underlying={row['underlying']} direction={row['direction']} "
              f"horizon={row['horizon']} budget={row['risk_budget']}")


if __name__ == "__main__":
    main()
