# BetAudit — Pre-Trade Resolution Auditor

> **A prediction-market bot is about to buy `YES` on a headline. BetAudit reads the market's
> _real_ resolution rules first — and tells it to stop when a hidden clause would trap the trade.**

Autonomous agents trade prediction markets on the headline. But a Polymarket market resolves on its
**fine print** — an "Official SEC 8-K filing," an exact deadline, a specific oracle — not the news.
BetAudit is a machine-to-machine ASP on the **OKX AI Marketplace** that closes that gap:

give it a market URL → it reads the actual resolution criteria, UMA oracle state, and dispute terms
→ it returns a **0–100 resolution risk score** and a verdict an agent acts on:
**`PROCEED` / `CAUTION` / `ABORT_TRADE`**. Grounded in the rules, not the headline.

**Live:** [betaudit.onrender.com](https://betaudit.onrender.com) · **Docs:** [/docs](https://betaudit.onrender.com/docs/) · **API:** [/api-docs](https://betaudit.onrender.com/api-docs) · **OKX:** A2MCP Agent #6141

### 30-second tour
- **Try it** — open the [live console](https://betaudit.onrender.com), click the example, watch a real market get audited.
- **Two ways to call it** — REST (`POST /verify-resolution-rules`) for apps, MCP (`POST /mcp`, tool `verify_resolution_rules`) for OKX agents. Same engine.
- **How the score is built** — resolve real rules (Polymarket Gamma) → LLM audits the clauses (grounded, temp 0) → explainable 0–100 score; degrades to a deterministic rubric with no LLM key.
- **Production-grade** — API-key auth + per-call audit + metering, Redis caching/rate-limiting/live-feed, optional x402 pay-per-call, and a post-trade oracle monitor that fires dispute alerts.
- **Deployed** — one Docker image (Node UI + Python API) on Render with managed Postgres + Redis.

- `POST /verify-resolution-rules` and `GET /health`
- Frozen response contract as Pydantic models (`app/schemas.py`)
- **Live Polymarket resolver** (`app/resolvers/polymarket.py`) — reads the Gamma API,
  extracts resolution rules, UMA oracle type, challenge window, and live oracle state.
  Kalshi is a drop-in behind the same interface.
- **OpenAI clause parser** (`app/llm/parser.py`) — reads the real resolution text and
  returns grounded rule mismatches + a 0–100 judgment via a forced function call, temperature 0.
- **Explainable engine** (`app/engine.py`) — LLM judgment drives content risk, oracle
  metadata adds auditable structural components; falls back to a deterministic rubric
  when no API key is set.
- **API keys + auth** (`app/security.py`, `app/services/keys.py`) — `X-API-Key` gate;
  keys are SHA-256 hashed, plaintext shown once. `POST /admin/keys` (admin-guarded)
  mints them; `GET /keys/me` shows usage.
- **Audit + metering** (`app/services/audit.py`, async SQLAlchemy in `app/db.py` +
  `app/models.py`) — every call (success or error) is logged and metered;
  `GET /audit/logs` returns the calling key's own trail.
- **x402 pay-per-call** (`app/payments/`) — optional payment gate speaking the
  OKX/X Layer x402 wire protocol: `402` + `PAYMENT-REQUIRED` challenge →
  client retries with `PAYMENT-SIGNATURE` → facilitator verify/settle →
  `PAYMENT-RESPONSE` receipt. Runs API-key-first (identity), then payment.
  `simulate` mode exercises the full handshake with no chain; `live` calls the
  OKX facilitator. Receipts at `GET /payments/receipts`.
- **Oracle monitor** (`app/services/monitor.py`) — `subscribe_monitor` on /verify
  registers the market; a poller re-resolves each subscription and, on an oracle
  state change, records a **dispute alert** (severity-classified) and best-effort
  delivers it to the subscription's webhook. Endpoints: `GET /monitors`,
  `GET /monitors/{id}`, `POST /monitors/{id}/check`, `PUT /monitors/{id}/webhook`,
  `DELETE /monitors/{id}`, `GET /alerts`. The background loop runs only when
  `MONITOR_ENABLED=true`; `check` triggers a poll on demand.
- **MCP endpoint** (`app/mcp_server.py`, `POST /mcp`) — a hand-rolled,
  spec-correct MCP Streamable-HTTP surface (JSON-RPC: `initialize`, `tools/list`,
  `tools/call`) exposing `verify_resolution_rules` as an MCP tool, so BetAudit is
  registerable as an **A2MCP** ASP on the OKX AI Marketplace. Reuses the exact
  verify engine as the REST path (shared core, no drift). Registration endpoint:
  `https://<host>/mcp`.
- **BetAudit web app** (`web/`, Vite + React + Tailwind) — the "Quantum Terminal"
  landing page whose **Simulation Terminal is wired to the real backend**: it
  auto-mints a dev API key, POSTs the pasted market URL to
  `/verify-resolution-rules`, and streams the real oracle metadata, rule
  mismatches, score, and a `SAFE_TO_BET` / `CAUTION_ADVISED` / `ABORT_BET`
  verdict. Built (`web/dist`) and served as static files by FastAPI — one origin,
  one deploy. Gracefully degrades to the deterministic rubric if the LLM errors.
- **Redis layer** (`app/redis_client.py`, `app/services/cache_layer.py`,
  `app/services/ratelimit.py`) — cache-aside over the Gamma round-trip (~1h) and
  the LLM evaluation (~15m), per-API-key rate limiting (429), and a
  `pubsub:live_audits` broadcast on every verify — consumed by a `/ws/audits`
  WebSocket that drives the landing page's live **Global Simulation Feed**.
  Entirely **fail-open**: no `REDIS_URL` (or Redis down) => caching/limiting/
  pub-sub no-op and the service runs identically, just uncached (feed shows
  "offline").
- Tests (`tests/`): resolver, parser (fake client), engine, endpoint (auth + DB +
  LLM-failure fallback), keys/metering/audit, x402 handshake + primitives,
  monitor detection/isolation, Redis cache hit/miss + rate-limit 429,
  + opt-in live Gamma/LLM tests.

### LLM configuration

Set `OPENAI_API_KEY` in `.env` to enable model scoring (model `gpt-4o`, override with `LLM_MODEL`).
Without a key the service still runs, using the deterministic metadata rubric.

Run the live Gamma integration test: `RUN_LIVE=1 pytest tests/test_live_gamma.py`

Run the live LLM test (hits OpenAI, needs `OPENAI_API_KEY`):
`RUN_LIVE_LLM=1 pytest tests/test_live_llm.py`

## Run it

```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"   # Windows
./.venv/Scripts/python.exe -m pytest -q
./.venv/Scripts/uvicorn.exe app.main:app --reload       # http://127.0.0.1:8000/docs
```

Copy `.env.example` to `.env` and fill in keys. Then mint an API key and call the endpoint:

```bash
# admin route is open locally when ADMIN_TOKEN is unset
curl -s -X POST localhost:8000/admin/keys -H 'content-type: application/json' -d '{"label":"dev"}'
# -> {"api_key":"rl_live_...", ...}   (shown once)

curl -s -X POST localhost:8000/verify-resolution-rules \
  -H "X-API-Key: rl_live_..." -H 'content-type: application/json' \
  -d '{"market_url":"https://polymarket.com/market/<slug>","queried_side":"YES"}'
```

### Web app (BetAudit)

```bash
cd web
npm install
npm run build            # -> web/dist, served by FastAPI at /
# then run uvicorn (above) and open http://127.0.0.1:8000/
```

For live UI development with hot reload, run the API on :8000 and, in another
shell, `npm run dev` in `web/` (the Vite dev server on :8443 proxies API calls
to :8000, so the browser stays same-origin — no CORS). The console mints a demo
key via the public, IP-throttled `POST /demo/key` route.

## Deploy (Render)

A multi-stage [`Dockerfile`](Dockerfile) builds the web app (Node) then runs the
API (Python), serving both from one origin. [`render.yaml`](render.yaml) is a
Blueprint that provisions the web service + managed **Postgres** + **Redis**
(Key Value) and wires `DATABASE_URL` / `REDIS_URL` automatically.

1. Push to GitHub → Render → **New > Blueprint** → pick the repo.
2. Set `OPENAI_API_KEY` in the dashboard (it's `sync:false`, kept out of git).
3. Deploy. `ADMIN_TOKEN` is auto-generated (admin routes locked); the web
   console keeps working via `/demo/key`. The DB schema auto-creates on boot.

The service is **fail-open** on Redis and the LLM, so a missing/rate-limited
dependency degrades gracefully rather than erroring.

## Architecture

```
request ──▶ API-key auth ──▶ x402 payment gate ──▶ (verify signature)
                                    │
market URL ──▶ resolver (Polymarket adapter)     ── normalized ResolvedMarket
                    │                                (real rules + oracle metadata)
                    ▼
              risk engine  ── deterministic rubric  ──▶  VerifyResponse
                    │        + OpenAI clause parser       (frozen JSON contract)
                    ▼
             settle payment ──▶ audit log + receipt ──▶ PAYMENT-RESPONSE header
                    │
            oracle monitor  ── post-trade dispute alerts (Phase 4)
```

## Roadmap

| Phase | Deliverable |
|------:|-------------|
| 0 ✅ | Scaffold: schema, resolver interface, endpoint, tests |
| 1 ✅ | Live Polymarket ingestion + Claude clause parser (real scores) |
| 2 ✅ | Persistence, API keys, per-call audit log + metering |
| 3 ✅ | x402 pay-per-call (simulate + live) — OKX ASP registration at deploy (Phase 7) |
| 4 ✅ | Oracle monitor + post-trade dispute alerts |
| 5 ✅ | BetAudit web app — live Simulation Terminal wired to the real API |
| 7a–b ✅ | Redis (caches + rate limit + pub/sub) + live Global Simulation Feed |
| 7d ✅ | MCP endpoint (`/mcp`) — A2MCP-registerable tool surface |
| 7c 🚧 | Docker + Render blueprint ready; deploy + OKX registration is the go-live step |
| 6 | Telegram bot (`@YourAuditBot`) |
| 8 | Demo production (trap market, Part A + Part B) |
