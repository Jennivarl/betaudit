# syntax=docker/dockerfile:1

# ── Stage 1: build the BetAudit web app (Node) ──────────────────────────────
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm ci
COPY web/ ./
RUN npm run build

# ── Stage 2: runtime (Python + FastAPI) ─────────────────────────────────────
FROM python:3.12-slim AS runtime
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    WEB_DIST_DIR=/app/web/dist

# Install the API + deps.
COPY pyproject.toml ./
COPY app ./app
RUN pip install .

# Bring in the built frontend (served as static by FastAPI).
COPY --from=web /web/dist ./web/dist

EXPOSE 8000
# Render (and most PaaS) inject $PORT; default to 8000 locally.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
