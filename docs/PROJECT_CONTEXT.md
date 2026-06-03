# ThetaLens — Project Context for LLM Analysis

> **Purpose of this document:** Provide enough context for another LLM to analyze ThetaLens and suggest product improvements, UX enhancements, feature priorities, competitive positioning, and technical roadmap ideas — without access to the codebase.
>
> **Last updated:** May 2026  
> **Live product:** [thetalens.app](https://thetalens.app)  
> **API:** `https://thetalens-api.onrender.com`  
> **License:** MIT · **Disclaimer:** Educational/research only — not investment advice

---

## How to use this with another LLM

Paste this entire document and ask questions like:

- *"What are the highest-impact product improvements for a v2?"*
- *"How would you differentiate this from OptionStrat / Market Chameleon / broker research tools?"*
- *"What's missing for users to trust and act on these recommendations?"*
- *"Suggest a monetization model that fits the current architecture."*
- *"Critique the agent + deterministic engine split — what should move where?"*
- *"What UX changes would reduce time-to-value for first-time users?"*

---

## 1. Executive summary

**ThetaLens** is an agentic options research platform. Users describe a trade thesis in plain English (e.g., *"NVDA bullish rally after earnings, $1,000 risk, two weeks"*) and receive:

1. Structured intent parsing (ticker, direction, horizon, risk budget)
2. Live agentic market research streamed to the UI (volatility regime, earnings, sentiment, expected move)
3. Deterministic strategy construction — ranked option structures with payoff charts, greeks, EV/POP, and execution quality warnings

A secondary **scanner mode** finds peer tickers that move similarly to a seed symbol, ranked by IV opportunity.

**Core design philosophy:**

- **No clarification loops** — missing direction/magnitude are inferred downstream by the agent, not asked of the user
- **Hybrid AI + math** — LLM researches context; Black–Scholes + scoring engine builds/ranks structures deterministically
- **Transparency** — reasoning traces, tool calls, and disclaimers throughout
- **Stateless** — no accounts, no persistence, no saved theses

---

## 2. Target users and use cases

### Primary users

| Persona | Goal | Current fit |
|---------|------|-------------|
| **Retail options researcher** | Explore structures for a directional/volatility view before placing a trade | Strong — thesis flow + payoff viz |
| **Volatility trader** | Find high-IV peers or premium-selling setups | Moderate — scanner + IV rank tooling |
| **Learning trader** | Understand why a structure fits a thesis | Strong — agent trace + education copy on cards |
| **Active trader needing execution** | Get trade-ready orders with live quotes | Weak — quotes are estimated, no broker integration |

### Example user journeys

**Journey A — Thesis research (primary)**
```
Type: "NVDA bullish rally, 2 weeks, risk $1000"
  → Intent extracted (ticker, direction, horizon, budget)
  → Agent streams research (IV rank, earnings, sentiment, expected move...)
  → Direction inferred if missing
  → 3–5 ranked strategies appear with payoff charts
  → User expands top card to review legs, greeks, scenarios, management rules
```

**Journey B — Scanner → thesis**
```
Type: "Stocks that move like NBIS"
  → Scanner finds peers ranked by opportunity score
  → User clicks "Build Strategies" on a result
  → Pre-fills thesis intent → runs agent flow for that ticker
```

**Journey C — Vague query (agentic)**
```
Type: "Best play on AAPL"
  → Direction left null at intent stage
  → Agent infers direction from sentiment, IV regime, earnings proximity
  → Strategies built for inferred direction
```

---

## 3. Feature inventory (current state)

### What exists today

| Feature | Status | Notes |
|---------|--------|-------|
| Natural language intent parsing | ✅ Shipped | LangChain + Gemini; regex fallback |
| ReAct research agent (7 tools) | ✅ Shipped | SSE-streamed to UI, max 10 steps |
| Direction inference | ✅ Shipped | When user omits or is uncertain |
| Strategy builder (15+ templates) | ✅ Shipped | Bullish, Bearish, Neutral structures |
| Payoff charts | ✅ Shipped | Client-side d3-shape from legs |
| Strategy cards (expandable) | ✅ Shipped | Legs, metrics, greeks, scenarios, management rules, education |
| IV rank + regime badge | ✅ Shipped | During agent research phase |
| Similar-stock scanner | ✅ Shipped | Peer discovery + opportunity scoring |
| Reasoning trace (live) | ✅ Shipped | Thinking, tool calls, results |
| Post-build reasoning panel | ✅ Shipped | Animated step reveal |
| Financial disclaimers | ✅ Shipped | Inline, banner, footer variants |
| Rate limiting | ✅ Shipped | slowapi, in-memory |
| CI (tests + build + secret scan) | ✅ Shipped | GitHub Actions |
| Intent eval script | ✅ Shipped | 20 held-out prompts, 95.9% fallback accuracy |

### What does NOT exist

| Gap | Impact |
|-----|--------|
| User accounts / auth | No history, personalization, or retention |
| Saved theses / watchlists | One-shot sessions only |
| Real-time / live option quotes | Uses prior aggregate mids; liquidity warnings flag this |
| Broker integration / order export | Research-only; user must manually trade elsewhere |
| Portfolio context | No existing positions or P&L awareness |
| Backtesting / historical performance | No "how would this have done" validation |
| Multi-leg adjustment / rolling guidance | Static management rules, not interactive |
| Mobile-optimized UX | Desktop-first SPA |
| Collaborative / shareable research | No links to saved runs |
| Premium data tier | Polygon free tier limits (5 req/min) |
| Chat UI ( `/api/chat` exists) | Endpoint exists but not wired into main UI |
| Formal LLM intent eval | Only regex fallback formally measured |

---

## 4. Product modes

### Mode 1: Thesis research

**Input:** Free-text query with ticker, optional direction, horizon, risk budget  
**Output:** Ranked option structures + enriched market context  
**Pipeline:** Intent → Agent (SSE) → Strategy builder → UI

### Mode 2: Scanner

**Input:** Similarity query (e.g., "stocks like COIN")  
**Output:** Top 5 peer tickers with stats + opportunity score  
**Pipeline:** Intent (mode=scanner) → Scanner API → table UI → optional handoff to thesis flow

**Scanner opportunity score (0–100):**
- 40% IV rank (higher = more premium-selling opportunity)
- 25% absolute correlation to seed
- 15% beta magnitude
- 10% 30-day realized vol
- 10% earnings proximity bonus

Filters: minimum ~200K average volume.

### Mode 3: Direct analyze (legacy)

**Input:** Structured query  
**Output:** Strategies without agent research  
**Status:** Still used as frontend fallback if agent build fails; not primary UX path

---

## 5. Architecture overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Frontend (React 19 + Vite + Tailwind 4)                        │
│  Phase state machine: input → checking → researching/scanning   │
│                     → analyzing → complete                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │ REST + SSE
┌──────────────────────────▼──────────────────────────────────────┐
│  API (FastAPI + Pydantic)                                       │
│  /api/intent  /api/agent/stream  /api/scanner  /api/analyze     │
└──────────────────────────┬──────────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
   Intent Chain      Thesis Agent      Strategy Builder
   (LangChain)       (ReAct + 7 tools)  (deterministic)
         │                 │                 │
         └─────────────────┼─────────────────┘
                           ▼
              Market Data (yfinance, Finnhub, Polygon)
```

**Deployment:**
- API: Render (`api/`)
- Web: Vercel (`web/`)
- No database — fully stateless

---

## 6. AI layer — agents and tools

### Intent extraction

- **Model:** Google Gemma 4 26B (via LangChain structured output)
- **Output schema:** `underlying`, `direction`, `magnitude`, `horizon`, `risk_budget`, `mode` (thesis | scanner)
- **Fallback:** Regex parser if LLM unavailable (~96% field accuracy on 20 test prompts)
- **Design rule:** Never asks clarifying questions; magnitude always null (agent calculates later)

### Thesis research agent (ReAct)

- **Loop:** Max 10 steps, one tool at a time
- **Streaming:** SSE events — `thinking`, `tool_call`, `tool_result`, `reasoning`, `context`, `strategies`, `error`, `done`
- **Direction inference:** After tools complete, uses sentiment score, earnings window, IV regime, expected move

**7 agent tools:**

| Tool | Purpose |
|------|---------|
| `get_iv_rank` | 30d RV vs 252d range → IV rank + regime (Low/Mid/High) |
| `get_upcoming_earnings` | Earnings date within trade window |
| `get_historical_post_earnings_move` | Post-earnings move history (last N quarters) |
| `get_news_sentiment` | Headline sentiment (Finnhub NLP or Polygon heuristic) |
| `get_expected_move` | Market-implied move over target DTE |
| `calculate_magnitude` | Thesis magnitude from expected move + history |
| `assess_structure_fit` | Recommended/contraindicated structures given regime + direction |

### Strategy builder (NOT an LLM)

Deterministic engine that:
1. Selects templates by direction (Bullish / Bearish / Neutral)
2. Filters structures the agent flagged as contraindicated
3. Maps to live Polygon contract strikes
4. Prices with Black–Scholes (sigma = agent's 30d realized vol)
5. Scores and ranks; drops "Avoid" verdicts

**Templates by direction:**

- **Bullish:** Bull Put Spread, Long LEAPS Call, Bull Call Spread, Call Diagonal
- **Bearish:** Bear Call Spread, Long Put, Bear Put Spread, Put Diagonal, Broken-Wing Butterfly
- **Neutral:** Iron Condor, Long Strangle, Put Calendar, Iron Butterfly, Put Diagonal

**Scoring formula:**
```
base_score = 58 + EV/6 - penalties (earnings, liquidity, IV mismatch, etc.)
final_score = 0.7 × base_score + 0.3 × trade_quality_score
```

**Trade quality verdicts:** `Tradeable` | `Caution` | `Avoid` — based on quote confidence, earnings timing, IV regime fit, sizing warnings.

**UI note:** Rank #1 can still show `Caution` or `Avoid` execution quality — the card surfaces a hint: *"Best thesis match; verify live quotes and catalysts before sizing."*

---

## 7. Data sources and limitations

| Data | Primary | Fallback | Limitation |
|------|---------|----------|------------|
| Daily bars, spot price | yfinance | Polygon | Not real-time; prev close |
| Company peers | Finnhub | Polygon | US equities/ETFs only |
| News sentiment, earnings | Finnhub | Polygon heuristic | NLP quality varies |
| Options contract reference | Polygon | — | Free tier: 5 req/min, aggregate mids |
| Option pricing (build) | Black–Scholes (RV-calibrated) | — | Model prices, not market mids |

**Honest product constraints to factor into improvement suggestions:**

- Quotes are **estimated** — educational disclaimer required everywhere
- No historical options data for backtesting
- Agent tool calling requires Google API; Ollama path is stub-only
- Rate limiting uses Redis when `REDIS_URL` is set (see `docs/SCALING.md`); otherwise in-memory per instance
- Ticker parsing assumes 1–5 letter US symbols

---

## 8. Frontend UX (current)

### Phase state machine (no React Router)

| Phase | UI | User sees |
|-------|-----|-----------|
| `input` | Query textarea + example chips | Landing / query entry |
| `checking` | Loading | "Extracting intent…" |
| `scanning` | ScannerView table | Peer rankings |
| `researching` | AgentView + ReasoningTrace | Live agent thinking + tool calls |
| `analyzing` | ReasoningPanel + ViewSidebar | Parsed view summary |
| `complete` | StrategyCard list | Ranked structures with payoff |

### Key UI components

- **StrategyCard** — expandable card with legs, max gain/loss, breakevens, POP, EV, greeks, payoff chart, scenarios, management rules, education bullets, execution quality badge
- **PayoffChart** — P&L at expiry visualization
- **ReasoningTrace** — live SSE bubbles during research
- **IVRankBadge** — regime chip during agent phase
- **ScannerView** — sortable peer table with opportunity score bar

### UX patterns

- Dark theme, gold accent (`#c9a655`)
- Staggered animations for reasoning steps and strategy cards
- Cmd/Ctrl+Enter to submit
- Demo query chips for onboarding
- Vercel Analytics on frontend

---

## 9. API reference (summary)

| Endpoint | Rate limit | Description |
|----------|------------|-------------|
| `POST /api/intent` | 30/min | Structured intent extraction |
| `POST /api/agent/stream` | 8/min | SSE ReAct agent + strategy build |
| `POST /api/agent/run` | 4/min | Non-streaming (hidden in prod) |
| `POST /api/scanner` | 20/min | Similar-stock scanner |
| `POST /api/analyze` | 20/min | Legacy direct analyze |
| `POST /api/chat` | 30/min | Chat completion (unused in UI) |
| `GET /api/runtime` | — | LLM config (admin key in prod) |
| `GET /health` | — | Health check |

---

## 10. Tech stack

| Layer | Technology |
|-------|------------|
| Frontend | React 19, TypeScript, Vite 5, Tailwind CSS 4, d3-shape, react-markdown |
| Backend | Python 3.12+, FastAPI, Pydantic v2 |
| AI | LangChain Core, Google Gemini/Gemma, optional Ollama |
| Agent | Custom ReAct loop, SSE streaming |
| Market data | yfinance, Finnhub, Polygon.io |
| Options math | Black–Scholes, greeks aggregation, payoff simulation |
| Database | **None** |
| CI | GitHub Actions — Gitleaks, pytest (43 tests), web build |
| Hosting | Render (API) + Vercel (web) |

---

## 11. Evaluation and quality metrics

### Intent parsing (regex fallback, 20 prompts)

| Field | Accuracy |
|-------|----------|
| underlying | 100% |
| direction | 92.3% |
| horizon | 90.0% |
| risk_budget | 100% |
| **Overall** | **95.9%** |

Known fallback failures: "drops" not matched; "Netflix" not in company name map; "next month" horizon edge cases. LLM path expected ~98%+.

### Test coverage

43 pytest tests across:
- Intent fallback parsing
- Scanner math (correlation, beta, IV rank, opportunity score)
- Agent direction inference
- Strategy builder ranking and trade quality

### Not yet formally evaluated

- LLM intent path on held-out set
- End-to-end strategy ranking quality vs human expert
- Agent tool selection optimality
- User satisfaction / conversion (no analytics on research → action)

---

## 12. Competitive landscape (context for differentiation)

ThetaLens sits between:

| Category | Examples | ThetaLens difference |
|----------|----------|---------------------|
| **Options visualization tools** | OptionStrat, OptionsProfitCalculator | Adds agentic research + thesis-driven ranking, not just manual leg entry |
| **Market screeners** | Market Chameleon, Barchart IV screener | Combines screener (scanner) with structure recommendations |
| **Broker research** | Thinkorswim Analyze, IBKR Option Wizard | Independent, multi-source; not tied to execution |
| **AI finance chatbots** | ChatGPT plugins, generic finance bots | Domain-specific tools + deterministic options math, not hallucinated strikes |

**Current moat (weak but real):**
- Agentic research trace → structured strategy output pipeline
- Hybrid LLM + BS engine reduces pure-hallucination risk on strikes/greeks
- Scanner → thesis handoff loop

**Current weaknesses vs competitors:**
- No live quotes or broker tie-in
- No manual strategy builder / leg editor
- No saved history
- Limited ticker universe (US equities)
- Single-query session model

---

## 13. Open product questions (good prompts for LLM analysis)

Use these as starting points when asking another LLM for insights:

### Product strategy
1. Should ThetaLens optimize for **research depth** (more agent tools, richer context) or **speed to trade** (fewer steps, pre-built templates)?
2. Is the **no-clarification** design right, or would targeted micro-questions improve trust/conversion?
3. What's the minimum viable **persistence layer** (saved runs? share links? watchlists?) without becoming a broker?
4. Should scanner and thesis be **merged into one flow** or stay separate modes?

### Trust and accuracy
5. How should the product communicate **quote uncertainty** without killing usefulness?
6. What **validation UX** would help users sanity-check agent reasoning (e.g., source links, confidence intervals)?
7. Should strategy ranking show **why not** the #2 structure, not just why #1?

### Monetization (architecture is stateless today)
8. Freemium with rate limits vs subscription vs API access — what fits best?
9. Would a **premium data tier** (live quotes, more tickers) be the first paid feature?

### UX
10. The flow has 5+ phases — where is the biggest **drop-off risk**?
11. Should the agent trace be **collapsed by default** for power users who want strategies faster?
12. What would a **mobile-first** version prioritize?

### Technical / AI
13. Should more logic move **into the agent** (dynamic structure invention) vs stay in the **deterministic builder** (reliability)?
14. Is 7 tools enough, or should the agent access **historical vol surfaces, skew, term structure**?
15. How to evaluate agent quality **automatically** beyond unit tests?

### Growth
16. What **viral/share** mechanics work for research tools without giving investment advice?
17. SEO/content strategy: glossary, strategy explainers, or ticker-specific landing pages?

---

## 14. Key file map (for humans with repo access)

```
thetalens/
├── api/app/agents/thesis_agent.py      # ReAct agent + direction inference
├── api/app/chains/intent_chain.py      # LLM intent extraction
├── api/app/tools/registry.py           # 7 agent tools
├── api/app/services/strategy_builder.py # Template selection + scoring
├── api/app/services/scanner.py         # Peer scanner + opportunity score
├── web/src/App.tsx                     # Phase state machine
├── web/src/components/StrategyCard.tsx # Main results UI
├── web/src/hooks/useAgentStream.ts     # SSE consumer
└── docs/ARCHITECTURE.md                # Pipeline deep-dive
```

---

## 15. Suggested LLM analysis template

Copy this prompt after pasting the document above:

```
You are a product strategist and senior fintech PM reviewing ThetaLens, an agentic options research platform (context above).

Please provide:

1. **Top 5 product improvements** ranked by impact vs effort, with rationale
2. **UX critique** of the current phase-based flow — where users likely drop off and how to fix it
3. **Trust gaps** — what would make a retail options trader skeptical, and specific fixes
4. **Differentiation** — how to stand out vs OptionStrat, broker tools, and generic AI chat
5. **Monetization options** that fit a stateless, no-broker architecture
6. **AI architecture feedback** — is the agent + deterministic builder split optimal?
7. **Quick wins** (ship in <1 week) vs **strategic bets** (1–3 month roadmap)

Be specific. Reference features from the context doc. Flag anything that could create regulatory issues (investment advice, suitability, etc.).
```

---

*ThetaLens is for educational and research purposes only. Not investment advice. Options trading involves substantial risk.*
