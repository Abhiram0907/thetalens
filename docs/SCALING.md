# Production scaling — 2-month trial (100+ concurrent users)

Use this guide when upgrading ThetaLens from the free stack to paid tiers for a ~2-month evaluation at production load.

**Goal:** ~100 users actively using the app at the same time (not 100 requests/second). A typical session is one long-lived SSE agent stream (1–4 minutes) plus a few REST calls.

---

## Bottleneck summary

| Layer | Free tier today | Symptom at scale | Recommended trial tier |
|-------|-----------------|------------------|-------------------------|
| **Render API** | Free (512 MB, 0.1 CPU, sleeps when idle) | Cold starts (~30s), timeouts, single instance | **Standard** + **autoscaling** 2–6 instances (Pro workspace) |
| **Rate limits** | In-memory per instance | Limits reset per instance; unfair under load balancer | **Render Key Value (Redis)** + `REDIS_URL` |
| **Polygon** | 5 req/min | 429s, failed strategy builds | **Options Starter** or **Developer** (unlimited REST) |
| **Finnhub** | Free (60 calls/min) | Degraded peers/earnings/sentiment | **All-In-One** or monitor usage |
| **Google AI** | Gemma 4 26B default | Quota/latency under burst | Keep Gemma; set billing alerts; optional `AGENT_MODEL=flash` for faster/cheaper runs |
| **Vercel** | Hobby | Usually fine for static SPA | **Pro** only if you need team analytics or higher build limits |

---

## 1. Render (API)

### Apply blueprint changes

[`render.yaml`](../render.yaml) is configured for a production trial:

- `plan: standard` (2 GB RAM, 1 CPU) — no spin-down
- `scaling:` **2–6 instances** (requires **Pro workspace** or higher for autoscaling)
- `maxShutdownDelaySeconds: 120` — graceful drain for open agent streams
- `thetalens-redis` Key Value — shared rate-limit state

After merging, in the Render dashboard:

1. **Blueprint sync** or redeploy `thetalens-api`.
2. Confirm **autoscaling** (min 2, max 6) and **Standard** instance type.
3. Set secrets unchanged: `GOOGLE_API_KEY`, `POLYGON_API_KEY`, `FINNHUB_API_KEY`, `CORS_ORIGINS`.
4. `REDIS_URL` should appear automatically from the Key Value service; if not, add it manually from the Redis **Internal Connection** string.

### Optional tuning (Render env)

| Variable | Suggested (trial) | Notes |
|----------|-------------------|--------|
| `GOOGLE_MODEL` | `flash` (default) or `pro` | `flash` → gemini-2.5-flash; `pro` → gemini-2.5-pro (best quality) |
| `RATE_LIMIT_AGENT_STREAM` | `12/minute` | Per IP; raise if many users share one NAT |
| `RATE_LIMIT_AGENT_RUN` | `6/minute` | Debug route (404 in prod without admin key) |
| `RATE_LIMIT_SCANNER` | `25/minute` | |
| `RATE_LIMIT_ANALYZE` | `25/minute` | |
| `RATE_LIMIT_INTENT` | `40/minute` | |

### Capacity rough math

- Each active thesis ≈ 1 SSE connection + ~7–15 Polygon/Finnhub calls + up to 10 LLM steps.
- **2–6 × Standard** (autoscaling): scales with CPU/memory; good for **~30–100+** simultaneous agent streams depending on load.
- If autoscaling lags during SSE-heavy traffic (many idle connections), raise `minInstances` to **3** in `render.yaml` or use **Pro** instance type (2 CPU).

### SSE note

Keep **one uvicorn process per instance** (current `startCommand`). Do not add multiple workers per instance without sticky sessions — SSE breaks on round-robin between workers on the same machine.

---

## 2. Polygon (options data)

ThetaLens uses Polygon for options contract reference and news fallback. **Free tier (5 req/min) will not survive production.**

1. Upgrade at [polygon.io/pricing](https://polygon.io/pricing) (or Massive) to at least **Options Starter** (~$29/mo) for unlimited REST on your use case.
2. For **live NBBO / real-time quotes** (not implemented yet), you need higher tiers (Developer/Advanced).
3. Rotate `POLYGON_API_KEY` in Render after upgrading.
4. Enable **usage alerts** in the Polygon dashboard.

The app retries on 429 with backoff; paid tiers remove the hard 5/min wall.

---

## 3. Finnhub

Recommended for peers, earnings calendar, and NLP sentiment.

1. Upgrade from free if you see 429s in Render logs during scanner peaks.
2. [Finnhub pricing](https://finnhub.io/pricing) — **All-In-One** is the common next step.
3. Without Finnhub, the app falls back to Polygon heuristics (lower quality sentiment).

---

## 4. Google AI (Gemma / Gemini)

1. Enable **billing** and **quota alerts** in [Google AI Studio](https://aistudio.google.com/).
2. Default agent model: `gemma-4-26b-a4b-it` via `AGENT_MODEL` or [`api/llm.yaml`](../api/llm.yaml).
3. For cost/latency during the trial, try `AGENT_MODEL=gemini-2.5-flash` on Render and compare quality.
4. Intent chain uses the same `llm.yaml` active provider (`LLM_ACTIVE=gemini`).

---

## 5. Vercel (frontend)

Usually no change required:

- `VITE_API_BASE` → your Render API URL
- Custom domain + `CORS_ORIGINS` on Render

Upgrade Vercel to **Pro** only if you need preview protection, more concurrent builds, or Web Analytics beyond the free tier.

---

## 6. Redis-backed rate limiting

When `REDIS_URL` is set (production blueprint), API rate limits are shared across all instances.

Local dev: omit `REDIS_URL` — limits stay in-memory (`memory://`).

Verify after deploy:

```bash
curl -s https://thetalens-api.onrender.com/health
# Run several rapid requests; 429 should be consistent across instances (hard to test without load tool)
```

---

## 7. Rollout checklist (2-month trial)

- [ ] Upgrade **Polygon** → paid options tier; update Render key
- [ ] Upgrade **Finnhub** if scanner/agent logs show rate errors
- [ ] Deploy **render.yaml** (Standard × 3 + Redis)
- [ ] Confirm `REDIS_URL` on API service
- [ ] Set Google billing alerts
- [ ] Smoke test: intent → agent stream → strategies on [thetalens.app](https://thetalens.app)
- [ ] Watch Render metrics (CPU, memory, instance count) for 48h
- [ ] Watch Polygon/Google dashboards for quota spikes
- [ ] Calendar reminder: review costs and scale down before month 3 if not continuing

---

## 8. Estimated monthly cost (trial ballpark)

| Service | Approx. |
|---------|---------|
| Render Standard (avg ~3 instances) | ~$75 |
| Render Pro workspace | plan fee + usage |
| Render Key Value (starter) | ~$10 |
| Polygon Options Starter | ~$29 |
| Finnhub (if upgraded) | ~$0–50 |
| Google AI (usage) | ~$20–200+ depending on traffic |
| Vercel | $0–20 |
| **Total** | **~$130–400/mo** |

Adjust instances and models to fit budget. Scale down `numInstances` to 2 if traffic is lower than expected.

---

## 9. After the trial

- Drop to **1–2 Standard** instances if daily active users &lt; 50.
- Keep Polygon paid if you stay in production.
- Remove Redis if you return to a single instance (limits become in-memory again).
- Consider autoscaling (`scaling:` in `render.yaml`) on a **Pro workspace** if traffic is spiky.

See also: [DEPLOYMENT.md](DEPLOYMENT.md), [ARCHITECTURE.md](ARCHITECTURE.md).
