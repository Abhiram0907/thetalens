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
   - `CORS_ORIGINS` — `https://thetalens.app,https://www.thetalens.app` (already set in `render.yaml`)

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
| `GOOGLE_MODEL` | No | Model alias: `flash` (default), `pro`, `gemma-26b` — see `api/llm.yaml` |

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

### Preview vs Production (Vercel)

Vercel has two deployment environments:

| Environment | When it deploys | Typical URL |
|---|---|---|
| **Production** | Push/merge to `main` (or your production branch), or `vercel --prod` | `https://thetalens.app` |
| **Preview** | Push to any other branch, open a PR, or `vercel` (no `--prod`) | Auto-generated `*.vercel.app` |

Each preview gets two URL types:

- **Branch URL** — always the latest commit on that branch (e.g. `thetalens-git-feature-abc.vercel.app`)
- **Commit URL** — pinned to one deployment (e.g. `thetalens-abc123.vercel.app`)

PR comments and the Vercel dashboard link to these automatically.

#### Env vars per environment

In **Project → Settings → Environment Variables**, scope `VITE_API_BASE`:

| Variable | Production | Preview | Development |
|---|---|---|---|
| `VITE_API_BASE` | ✅ same Render API URL | ✅ same Render API URL (recommended) | leave unset locally |

`VITE_*` values are **baked in at build time** — changing an env var requires a redeploy for that environment.

**Recommended setup:** enable `VITE_API_BASE` for both **Production** and **Preview**, both pointing at your Render API. You usually do not need a separate staging API unless you want one.

#### CORS for previews

On Render, set `CORS_ORIGINS` to your **production** frontend origins only:

```
https://thetalens.app,https://www.thetalens.app
```

Preview `*.vercel.app` URLs are already allowed by the API when `CORS_ORIGINS` is set (see `api/app/main.py`). You do **not** need to add every preview URL manually.

#### Workflow

1. Open a PR → Vercel builds a **Preview** → test against live Render API.
2. Merge to `main` → Vercel builds **Production** → live site updates.
3. Custom domain always serves **Production** only (not previews).

### Vercel preview deploys (summary)

Each preview gets a unique `*.vercel.app` URL. The API allows those origins when `CORS_ORIGINS` is configured — no extra step per preview.

### Custom domain (thetalens.app)

1. In Vercel: **Project → Settings → Domains** → add your domain.
2. At your DNS provider (Cloudflare, Namecheap, Route 53, etc.), add the records Vercel shows. For the **root domain** (`@`), Vercel currently recommends:

   | Type | Name | Value |
   |---|---|---|
   | A | `@` | `216.198.79.1` |

   Older Vercel IPs (`76.76.21.21`) and `cname.vercel-dns.com` still work; use whatever Vercel displays for your project.

3. If you also want `www`, Vercel will show a **CNAME** for `www` → `cname.vercel-dns.com` (or the new equivalent). Add that at your DNS provider too.

4. Wait for DNS propagation (minutes to 48 hours). Vercel shows **Valid Configuration** when ready.

5. **Update Render `CORS_ORIGINS`** to include your custom domain (comma-separated, no trailing slash):

   ```
   https://thetalens.app,https://www.thetalens.app
   ```

   Redeploy the API after changing env vars.

6. No change to `VITE_API_BASE` — that still points at your Render API URL, not your custom frontend domain.

**Cloudflare tip:** If the domain is proxied (orange cloud), SSL mode **Full** is usually fine. If verification stalls, try DNS-only (grey cloud) until Vercel validates, then re-enable proxy.

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

| | Local | Preview (Vercel) | Production (Vercel) |
|---|---|---|---|
| Trigger | `npm run dev` | PR / non-`main` push | Merge to `main` |
| Frontend URL | localhost:5173 | `*.vercel.app` | `https://thetalens.app` |
| `VITE_API_BASE` | unset | Render API URL | Render API URL |
| API CORS | localhost (built-in) | `*.vercel.app` regex | `CORS_ORIGINS` + regex |

---

## 5. Notes

- **Free Render tier** spins down after inactivity; first request may take ~30s (cold start).
- **SSE streaming** (`/api/agent/stream`) goes browser → Render directly; do not proxy through Vercel.
- **Secrets** live only in Render/Vercel dashboards — never commit `.env` files.
- Upgrade Render plan if agent runs hit timeout limits on long research sessions.

## 6. Production scaling (100+ concurrent users)

For a paid 2-month trial, see **[SCALING.md](SCALING.md)**. Summary:

1. Sync [`render.yaml`](../render.yaml) — **Standard** plan, **3 instances**, **Redis** for shared rate limits.
2. Upgrade **Polygon** off the free tier (5 req/min).
3. Set billing alerts on **Google AI**; optionally try `AGENT_MODEL=gemini-2.5-flash` for lower latency.
4. Tune `RATE_LIMIT_*` env vars if many users share one IP (corporate NAT).
