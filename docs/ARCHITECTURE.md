# ThetaLens Architecture

One-page reference for the intent → agent → tools → strategy builder pipeline.

## System overview

ThetaLens is a three-phase application:

1. **Intent** — parse natural language into structured trading intent
2. **Research** — agentic ReAct loop gathers market context via tools
3. **Build** — deterministic strategy engine ranks option structures

The frontend is a single-page React app with phase-based routing (no React Router). The backend is FastAPI with SSE streaming for the agent.

---

## Phase 1: Intent extraction

**Entry:** `POST /api/intent` → `app/services/intent.py`

```
User query
    │
    ▼
LangChain intent chain (Gemini/Gemma)
    │  structured output → IntentSlots
    ▼
CapturedIntent { underlying, direction, horizon, risk_budget, mode }
    │
    ├── mode = "thesis"  → agent research flow
    └── mode = "scanner" → scanner flow
```

**Fallback:** If the LLM is unavailable, regex-based `_fallback_slots()` parses tickers, direction keywords, horizon, and budget locally.

**Design choice:** No user clarification prompts. Missing direction and magnitude are filled downstream by the agent.

---

## Phase 2: Research agent

**Entry:** `POST /api/agent/stream` → `app/agents/thesis_agent.py`

```
ThesisAgent.run(intent)
    │
    ▼
ReAct loop (max 10 steps)
    │
    ├── THINKING  → streamed to UI
    ├── TOOL_CALL → streamed to UI
    ├── TOOL_RESULT → streamed to UI
    │
    ▼
Tool registry (app/tools/registry.py)
    │
    ├── get_iv_rank
    ├── get_upcoming_earnings
    ├── get_news_sentiment
    ├── get_historical_post_earnings_move
    ├── get_expected_move
    ├── calculate_magnitude
    └── assess_structure_fit
    │
    ▼
Enriched context dict → CONTEXT event
```

**Direction inference:** When direction is null/unsure, `_infer_direction_from_context()` uses sentiment score, earnings window, and IV regime after tools complete.

**Multi-source routing** (`app/tools/providers.py`):

| Tool data | Primary | Fallback |
|---|---|---|
| Daily bars, spot | yfinance | Polygon |
| Peers, earnings, sentiment | Finnhub | Polygon |

---

## Phase 3: Strategy builder

**Entry:** `_build_strategies()` in `app/api/routes/agent.py`

```
Enriched context
    │
    ▼
load_snapshot(ticker, target_dte, sigma=realized_vol)
    │  Polygon: options contract reference (puts + calls)
    │  Pricing: Black-Scholes using agent's RV as sigma
    ▼
ParsedView + MarketSnapshot
    │
    ▼
build_strategies() — app/services/strategy_builder.py
    │
    ├── Select templates by direction (Bullish / Bearish / Neutral)
    ├── Filter by avoid_structures from agent
    ├── Build legs from live contract strikes
    ├── Score by EV, POP, IV regime, earnings, liquidity
    └── Rank and return top strategies
    │
    ▼
STRATEGIES SSE event → frontend StrategyCard + PayoffChart
```

**Scoring formula (simplified):**

```
base_score = 58 + EV/6 - penalties
final_score = 0.7 * base_score + 0.3 * trade_quality_score
```

Structures with verdict "Avoid" are dropped. Fallback retries without avoid filters or with Neutral direction if empty.

---

## Scanner mode (parallel path)

**Entry:** `POST /api/scanner` → `app/services/scanner.py`

```
Seed ticker
    │
    ├── Finnhub company_peers (deduped)
    ├── yfinance: 90d bars per peer (parallel)
    ├── Compute: beta, correlation, 30d RVol, IV rank, opportunity score
    └── Filter: min 200K avg volume
    │
    ▼
SeedContext + top 5 ScannerStock results
    │
    ▼
User clicks "Build Strategies" → pre-fills intent → agent flow
```

---

## Frontend phases

| Phase | Component | Trigger |
|---|---|---|
| `input` | Query box + examples | Default |
| `checking` | Intent evaluation | Submit |
| `scanning` | ScannerView | mode = scanner |
| `researching` | AgentView (SSE) | mode = thesis |
| `analyzing` | Reasoning + sidebar | Agent complete |
| `complete` | Strategy cards | Strategies loaded |

SSE handled by `useAgentStream` hook; reasoning trace in `ReasoningTrace.tsx`.

---

## Key files

| File | Role |
|---|---|
| `api/app/chains/intent_chain.py` | LLM prompt for intent extraction |
| `api/app/agents/thesis_agent.py` | ReAct agent + direction inference |
| `api/app/tools/registry.py` | Tool definitions + implementations |
| `api/app/tools/providers.py` | yfinance + Finnhub clients |
| `api/app/services/strategy_builder.py` | Template selection + ranking |
| `api/app/services/market_data.py` | Polygon options snapshot loader |
| `api/app/services/scanner.py` | Peer discovery + opportunity scoring |
| `web/src/App.tsx` | Phase state machine |
| `web/src/hooks/useAgentStream.ts` | SSE consumer |

---

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `GOOGLE_API_KEY` | Yes | LLM (intent + agent) |
| `POLYGON_API_KEY` | Yes | Options contract reference |
| `FINNHUB_API_KEY` | No | Peers, earnings, sentiment (recommended) |
| `LLM_ACTIVE` | No | `gemini` or `ollama` |
| `AGENT_MODEL` | No | Override default Gemma model |

---

## Deployment notes

- **Frontend:** Static build from `web/` (Vercel, Netlify, etc.)
- **API:** `uvicorn app.main:app` on Railway, Fly.io, Render, etc.
- Set `CORS_ORIGINS` to your frontend URL in production.
- Proxy `/api` from frontend or set `VITE_API_BASE` to the API URL.
