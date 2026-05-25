# Deployment — Render (API) + Vercel (Web)

ThetaLens runs as two services:

| Service | Platform | Root directory |
|---|---|---|
| FastAPI backend | [Render](https://render.com) | `api/` |
| React frontend | [Vercel](https://vercel.com) | `web/` |

The frontend calls the API directly via `VITE_API_BASE` (required in production for SSE agent streaming).

---

## 1. Deploy the API on Render

### Option A — Blueprint (recommended)

1. Push this repo to GitHub.
2. In Render: **New → Blueprint** → connect the repo.
3. Render reads [`render.yaml`](../render.yaml) and creates `thetalens-api`.
4. When prompted, set secret env vars:
   - `GOOGLE_API_KEY` — [Google AI Studio](https://aistudio.google.com/apikey)
   - `POLYGON_API_KEY` — [Polygon.io](https://polygon.io/)
   - `FINNHUB_API_KEY` — [Finnhub](https://finnhub.io/) (optional but recommended)
   - `CORS_ORIGINS` — your Vercel URL, e.g. `https://thetalens.vercel.app` (add preview URL later if needed)

5. Wait for deploy; note the service URL, e.g. `https://thetalens-api.onrender.com`.
6. Verify: `curl https://thetalens-api.onrender.com/health` → `{"status":"ok"}`.

### Option B — Manual web service

1. **New → Web Service** → connect repo.
2. **Root Directory:** `api`
3. **Runtime:** Python 3
4. **Build Command:** `pip install -r requirements.txt`
5. **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
6. **Health Check Path:** `/health`
7. Add the env vars from Option A.

### Render env vars

| Variable | Required | Notes |
|---|---|---|
| `GOOGLE_API_KEY` | Yes | Gemini / Gemma for intent + agent |
| `POLYGON_API_KEY` | Yes | Options chain reference |
| `FINNHUB_API_KEY` | No | Peers, news, earnings |
| `CORS_ORIGINS` | Yes (prod) | Comma-separated frontend origin(s) |
| `LLM_ACTIVE` | No | Default `gemini` |
| `AGENT_MODEL` | No | Override default Gemma model |

Preview Vercel deploys (`*.vercel.app`) are allowed automatically when `CORS_ORIGINS` is set.

---

## 2. Deploy the frontend on Vercel

1. In Vercel: **Add New → Project** → import the same GitHub repo.
2. **Root Directory:** `web` (click Edit).
3. Framework preset should detect **Vite** (or use [`web/vercel.json`](../web/vercel.json)).
4. **Environment variables:**

   | Name | Value |
   |---|---|
   | `VITE_API_BASE` | `https://thetalens-api.onrender.com` (your Render URL, no trailing slash) |

5. Deploy. Open the Vercel URL and run a thesis query.

6. If you get CORS errors, add your exact Vercel URL to Render `CORS_ORIGINS` and redeploy the API.

### Vercel preview deploys

Each preview gets a unique `*.vercel.app` URL. The API allows those origins when `CORS_ORIGINS` is configured — no extra step per preview.

---

## 3. Wire them together (checklist)

```
Render API URL  ──►  Vercel VITE_API_BASE
Vercel URL      ──►  Render CORS_ORIGINS
```

1. Deploy API first → copy Render URL.
2. Set `VITE_API_BASE` on Vercel → redeploy frontend.
3. Set `CORS_ORIGINS` on Render to your production Vercel URL → redeploy API.
4. Test intent → agent stream → strategy cards end-to-end.

---

## 4. Local vs production

| | Local | Production |
|---|---|---|
| `VITE_API_BASE` | unset | Render API URL |
| API CORS | localhost:5173 (built-in) | `CORS_ORIGINS` env var |
| API proxy | Vite dev server | Direct fetch to Render |

---

## 5. Notes

- **Free Render tier** spins down after inactivity; first request may take ~30s (cold start).
- **SSE streaming** (`/api/agent/stream`) goes browser → Render directly; do not proxy through Vercel.
- **Secrets** live only in Render/Vercel dashboards — never commit `.env` files.
- Upgrade Render plan if agent runs hit timeout limits on long research sessions.
