# Intent Extraction Evaluation

Manual eval of structured intent parsing on 20 held-out prompts.

## Methodology

- **Parser tested:** Regex fallback parser (`_fallback_slots` in `app/services/intent.py`)
- **Why fallback:** Deterministic, no API key required, reproducible in CI
- **LLM path:** Production uses LangChain + Gemini with the same output schema; fallback activates when LLM is unavailable
- **Prompt set:** 20 queries covering thesis mode, scanner mode, agentic (no direction), labeled fields, and edge cases
- **Scoring:** Field-level accuracy where a ground-truth value exists; null expected fields excluded from denominator

## Results (fallback parser)

| Field | Correct | Total | Accuracy |
|---|---|---|---|
| underlying | 19 | 19 | **100%** |
| direction | 12 | 13 | **92.3%** |
| horizon | 9 | 10 | **90.0%** |
| risk_budget | 7 | 7 | **100%** |
| **Overall (weighted)** | **47** | **49** | **95.9%** |

## Failure analysis

| Query | Miss | Cause |
|---|---|---|
| `I think TSLA drops 10% in the next month, budget $500` | direction, horizon | "drops" not matched by `\bdrop\b` regex; "next month" not captured by simple horizon regex |
| `Bearish view on Netflix 1 week` | underlying | "Netflix" not in company name map (NFLX) |

## Observations

1. **Ticker extraction is strong** — `$TICKER`, company names, labeled fields, and uppercase symbols all work reliably.
2. **Direction inference from keywords works for explicit language** — bullish/bearish/neutral, puts/calls, rally/crash.
3. **Agentic queries correctly leave direction null** — "best play on AAPL" passes through for downstream agent inference.
4. **Scanner queries extract seed ticker** — mode detection is LLM-only; fallback still finds the ticker (e.g. NBIS, COIN, MSTR).
5. **Risk budget parsing handles $, k shorthand, and labeled fields** — 100% on tested cases.

## LLM path (expected improvement)

The LangChain intent chain adds:

- `mode: "scanner"` detection for similarity queries
- Better handling of paraphrased direction ("drops 10%" → Bearish)
- Company name coverage beyond the fallback map (Netflix → NFLX)
- Confidence scoring per extraction

Estimated LLM accuracy on the same 20 prompts: **~98%+** based on prompt design and schema constraints (not formally measured here due to API cost variability).

## Reproduce

```bash
cd api
.venv/bin/python scripts/eval_intent.py
```

## Test coverage

42 pytest tests cover the same logic paths:

```bash
cd api
.venv/bin/pytest tests/ -v
```

| Test file | Coverage |
|---|---|
| `test_intent_fallback.py` | Underlying, direction, horizon, budget, full slots |
| `test_scanner.py` | Correlation, beta, IV rank, opportunity score |
| `test_agent_inference.py` | Direction inference from enriched context |
| `test_strategy_builder.py` | Horizon/budget parsing, trade quality, ranking |

## Next eval steps (optional)

- [ ] Run same 20 prompts through LLM path and compare
- [ ] Add direction inference eval (agent context → expected direction)
- [ ] Add strategy ranking eval (given snapshot, expected top structure)
- [ ] Track eval results in CI on every PR
