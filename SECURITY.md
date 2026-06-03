# Security — ThetaLens

This document describes how secrets are managed and how to keep production secure.

## Secret storage (never in git)

| Secret | Where it lives | Never in |
|---|---|---|
| `GOOGLE_API_KEY` | Render env (dashboard) | repo, frontend, logs |
| `POLYGON_API_KEY` | Render env | repo, frontend, logs |
| `FINNHUB_API_KEY` | Render env | repo, frontend, logs |
| `ADMIN_API_KEY` | Render env (optional) | repo, frontend |
| `VITE_API_BASE` | Vercel env or build config | must be public URL only |

**Local development:** copy `api/.env.example` → `api/.env` and fill in keys.  
`api/.env` is gitignored. **Never commit it.**

**Production:** set secrets only in [Render Dashboard](https://dashboard.render.com) → `thetalens-api` → Environment.  
Use `sync: false` in `render.yaml` so Blueprint never writes secrets to the repo.

## Platform setup checklist

### Render (API)

1. `APP_ENV=production`
2. `GOOGLE_API_KEY`, `POLYGON_API_KEY`, `FINNHUB_API_KEY` — from provider dashboards
3. `CORS_ORIGINS=https://thetalens.app,https://www.thetalens.app`
4. `ADMIN_API_KEY` — optional random string for `/api/runtime` admin access

### Vercel (frontend)

1. `VITE_API_BASE=https://thetalens-api.onrender.com` (Production + Preview)
2. Do **not** add backend API keys to Vercel — they would ship in the JS bundle

### Provider key restrictions

- **Google AI Studio:** restrict key to your API usage; rotate if exposed
- **Polygon:** enable usage alerts; use separate keys for dev vs prod if possible
- **Finnhub:** monitor free-tier limits

## What the app does to protect secrets

- **Startup validation** — production fails fast if required keys or `CORS_ORIGINS` are missing
- **Log redaction** — API keys and tokens are stripped from log output
- **Safe client errors** — stack traces, upstream URLs, and provider responses are not returned to browsers
- **Google API** — key sent via `x-goog-api-key` header, not URL query params
- **Rate limiting** — per-IP limits on expensive endpoints; shared via Redis when `REDIS_URL` is set (multi-instance)
- **CORS** — production allows only `thetalens.app` + your Vercel preview pattern (not all `*.vercel.app`)
- **Docs disabled** — `/docs`, `/openapi.json` off in production
- **Debug routes hidden** — `/api/agent/run` and `/api/runtime` return 404 in production unless admin key is set
- **Security headers** — HSTS, CSP, frame denial on Vercel and API
- **Frontend** — no `console.log` of requests; errors sanitized; no secrets in bundle

## Key rotation

If a key may have leaked (committed, shared in chat, screenshot, etc.):

1. **Revoke** the key in the provider dashboard immediately
2. **Issue** a new key
3. **Update** Render env var → redeploy API
4. **Verify** `/health` and a test query on thetalens.app

Rotate on a schedule (e.g. every 90 days) or when team members with access leave.

## Incident response

1. Revoke compromised keys at the provider
2. Rotate all keys that shared the same machine or `.env` file
3. Check provider usage dashboards for anomalous traffic
4. Review Render logs for unusual IP volume (rate limit 429s)
5. Redeploy API after env updates

## CI / pre-commit

GitHub Actions runs:

- **gitleaks** — blocks commits containing secret patterns
- **pytest** — API unit tests

Run locally before push:

```bash
cd api && pip install -r requirements-dev.txt && pytest tests/ -v
```

## Files safe to commit

- `api/.env.example`, `web/.env.example` — placeholders only
- `render.yaml` — secret *names* only (`sync: false`), never values
- `web/src/lib/apiBase.ts` — public API URL only

## Files that must stay local / platform-only

- `api/.env`
- `web/.env`, `web/.env.local`, `web/.env.production`
