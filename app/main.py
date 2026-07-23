"""FastAPI application — the ASP's public surface.

Phase 2 adds API-key auth, per-call audit logging + metering, and the
management routes the developer portal will drive (mint keys, read usage,
read the audit trail). Later phases add x402 payment (Phase 3), the oracle
monitor (Phase 4), and the portal UI (Phase 5).
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__, mcp_server, redis_client
from app.api_models import (
    ApiKeyOut,
    CallLogOut,
    CreatedKeyOut,
    CreateKeyRequest,
    MonitorEventOut,
    MonitorSubscriptionOut,
    SettlementOut,
    SetWebhookRequest,
)
from app.config import get_settings
from app.db import get_session, init_db, init_engine
from app.engine import score_market
from app.llm import get_parser
from app.models import ApiKey
from app.payments.facilitator import Facilitator
from app.payments.gate import PaymentState, require_payment
from app.payments.x402 import encode_header
from app.resolvers import UnsupportedPlatformError, resolve_market
from app.resolvers.base import ResolverError
from app.schemas import ErrorCode, ErrorResponse, VerifyRequest, VerifyResponse
from app.security import require_admin, require_api_key
from app.services import audit as audit_service
from app.services import keys as key_service
from app.services import monitor as monitor_service
from app.services import payments as payment_service
from app.services.cache_layer import analyze_cached, resolve_cached
from app.services.ratelimit import enforce_rate_limit


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_engine()
    await init_db()
    monitor_task: asyncio.Task | None = None
    if get_settings().monitor_enabled:
        monitor_task = asyncio.create_task(monitor_service.run_loop())
    try:
        yield
    finally:
        if monitor_task is not None:
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass


app = FastAPI(
    title="Resolution Simulation Layer",
    version=__version__,
    summary="Pre-trade compliance engine for prediction-market trading agents.",
    lifespan=lifespan,
)


@app.get("/health", tags=["ops"])
async def health() -> dict:
    return {"status": "ok", "version": __version__}


# --------------------------------------------------------------------------- #
# Verification (billable, authenticated)
# --------------------------------------------------------------------------- #
@app.post(
    "/verify-resolution-rules",
    response_model=VerifyResponse,
    responses={
        401: {"model": ErrorResponse},
        402: {"description": "Payment required (x402). See the PAYMENT-REQUIRED header."},
        429: {"description": "Rate limit exceeded for this API key."},
        422: {"model": ErrorResponse},
        400: {"model": ErrorResponse},
    },
    tags=["verification"],
)
async def verify_resolution_rules(
    req: VerifyRequest,
    http_response: Response,
    api_key: ApiKey = Depends(enforce_rate_limit),
    payment: PaymentState = Depends(require_payment),
    session: AsyncSession = Depends(get_session),
):
    """Score a prediction market's resolution risk before an agent trades it."""
    started = time.perf_counter()

    def elapsed_ms() -> int:
        return int((time.perf_counter() - started) * 1000)

    try:
        response, llm_used = await _resolve_score_monitor(
            session,
            market_url=req.market_url,
            queried_side=req.queried_side,
            subscribe_monitor=req.subscribe_monitor,
            api_key_id=api_key.id,
        )
    except UnsupportedPlatformError as exc:
        # Service could not be delivered -> do not settle (no charge).
        return await _error(
            session, 400, ErrorCode.UNSUPPORTED_PLATFORM, str(exc), req, api_key, elapsed_ms()
        )
    except ResolverError as exc:
        return await _error(
            session, 422, ErrorCode.PARSE_FAILED, str(exc), req, api_key, elapsed_ms()
        )

    # Result produced -> now settle the payment (if x402 is on) and receipt it.
    if payment.required and payment.verified:
        await _settle(session, payment, response.request_id, api_key.id, http_response)

    await key_service.touch_usage(session, api_key)
    await _record_and_publish(
        session, response, api_key_id=api_key.id, llm_used=llm_used, latency_ms=elapsed_ms()
    )
    return response


# --------------------------------------------------------------------------- #
# Key management + audit (portal / admin)
# --------------------------------------------------------------------------- #
@app.post(
    "/admin/keys",
    response_model=CreatedKeyOut,
    dependencies=[Depends(require_admin)],
    tags=["admin"],
)
async def create_key(
    body: CreateKeyRequest,
    session: AsyncSession = Depends(get_session),
):
    """Mint a new API key. The plaintext secret is returned once."""
    issued = await key_service.issue_key(session, label=body.label)
    out = ApiKeyOut.from_orm_key(issued.record).model_dump()
    return CreatedKeyOut(api_key=issued.plaintext, **out)


@app.post("/demo/key", response_model=CreatedKeyOut, tags=["keys"])
async def create_demo_key(request: Request, session: AsyncSession = Depends(get_session)):
    """Public, IP-throttled demo-key minting for the web console.

    Lets the browser auto-mint a key without exposing the admin route, so
    ADMIN_TOKEN can stay set in production. Throttled via Redis (fail-open)."""
    settings = get_settings()
    if not settings.demo_key_enabled:
        raise HTTPException(status_code=404, detail="Demo keys are disabled.")

    ip = request.client.host if request.client else "unknown"
    minute = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    count = await redis_client.incr_with_expiry(f"rate:demokey:{ip}:{minute}", ttl=70)
    if count is not None and count > settings.demo_key_per_minute:
        raise HTTPException(
            status_code=429,
            detail="Too many demo keys from this address; try again shortly.",
            headers={"Retry-After": "60"},
        )

    issued = await key_service.issue_key(session, label="web-demo")
    out = ApiKeyOut.from_orm_key(issued.record).model_dump()
    return CreatedKeyOut(api_key=issued.plaintext, **out)


@app.get("/keys/me", response_model=ApiKeyOut, tags=["keys"])
async def key_me(api_key: ApiKey = Depends(require_api_key)):
    """Return the calling key's own metadata + usage count."""
    return ApiKeyOut.from_orm_key(api_key)


@app.get("/audit/logs", response_model=list[CallLogOut], tags=["audit"])
async def audit_logs(
    limit: int = 50,
    offset: int = 0,
    api_key: ApiKey = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
):
    """Return the calling key's own audit trail, newest first."""
    logs = await audit_service.list_logs(
        session, api_key_id=api_key.id, limit=limit, offset=offset
    )
    return [CallLogOut.from_orm_log(c) for c in logs]


@app.get("/payments/receipts", response_model=list[SettlementOut], tags=["payments"])
async def payment_receipts(
    limit: int = 50,
    offset: int = 0,
    api_key: ApiKey = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
):
    """Return the calling key's own x402 settlement receipts, newest first."""
    rows = await payment_service.list_settlements(
        session, api_key_id=api_key.id, limit=limit, offset=offset
    )
    return [SettlementOut.from_orm_settlement(s) for s in rows]


# --------------------------------------------------------------------------- #
# Oracle monitor (Phase 4)
# --------------------------------------------------------------------------- #
@app.get("/monitors", response_model=list[MonitorSubscriptionOut], tags=["monitor"])
async def list_monitors(
    limit: int = 50,
    offset: int = 0,
    api_key: ApiKey = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
):
    """List the calling key's monitor subscriptions, newest first."""
    subs = await monitor_service.list_subscriptions(
        session, api_key_id=api_key.id, limit=limit, offset=offset
    )
    return [MonitorSubscriptionOut.from_orm_sub(s) for s in subs]


@app.get("/monitors/{monitor_id}", response_model=MonitorSubscriptionOut, tags=["monitor"])
async def get_monitor(
    monitor_id: str,
    api_key: ApiKey = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
):
    sub = await monitor_service.get_subscription(session, monitor_id, api_key_id=api_key.id)
    if sub is None:
        raise HTTPException(status_code=404, detail="Monitor not found.")
    return MonitorSubscriptionOut.from_orm_sub(sub)


@app.put("/monitors/{monitor_id}/webhook", response_model=MonitorSubscriptionOut, tags=["monitor"])
async def set_monitor_webhook(
    monitor_id: str,
    body: SetWebhookRequest,
    api_key: ApiKey = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
):
    """Set the webhook URL that dispute alerts for this monitor POST to."""
    sub = await monitor_service.get_subscription(session, monitor_id, api_key_id=api_key.id)
    if sub is None:
        raise HTTPException(status_code=404, detail="Monitor not found.")
    sub.webhook_url = body.webhook_url
    await session.commit()
    await session.refresh(sub)
    return MonitorSubscriptionOut.from_orm_sub(sub)


@app.delete("/monitors/{monitor_id}", tags=["monitor"])
async def unsubscribe_monitor(
    monitor_id: str,
    api_key: ApiKey = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
):
    """Deactivate a monitor subscription."""
    sub = await monitor_service.get_subscription(session, monitor_id, api_key_id=api_key.id)
    if sub is None:
        raise HTTPException(status_code=404, detail="Monitor not found.")
    sub.active = False
    await session.commit()
    return {"monitor_id": monitor_id, "active": False}


@app.post("/monitors/{monitor_id}/check", response_model=list[MonitorEventOut], tags=["monitor"])
async def check_monitor_now(
    monitor_id: str,
    api_key: ApiKey = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
):
    """Poll this monitor immediately. Returns any new alert (empty if unchanged)."""
    sub = await monitor_service.get_subscription(session, monitor_id, api_key_id=api_key.id)
    if sub is None:
        raise HTTPException(status_code=404, detail="Monitor not found.")
    event = await monitor_service.poll_subscription(session, sub)
    return [MonitorEventOut.from_orm_event(event)] if event is not None else []


@app.get("/alerts", response_model=list[MonitorEventOut], tags=["monitor"])
async def list_alerts(
    monitor_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    api_key: ApiKey = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
):
    """List dispute alerts across the calling key's monitors, newest first."""
    events = await monitor_service.list_events(
        session, api_key_id=api_key.id, monitor_id=monitor_id, limit=limit, offset=offset
    )
    return [MonitorEventOut.from_orm_event(e) for e in events]


# --------------------------------------------------------------------------- #
# Live audit stream (Phase 7b) — public WebSocket over the Redis pub/sub channel
# --------------------------------------------------------------------------- #
@app.websocket("/ws/audits")
async def ws_audits(ws: WebSocket):
    """Stream every verify (globally) to the frontend live feed.

    Subscribes to the ``pubsub:live_audits`` Redis channel and forwards each
    message. Without Redis it sends a one-off 'offline' notice and idles.
    """
    await ws.accept()
    client = redis_client.get_client()
    channel = get_settings().live_audits_channel

    if client is None:
        await ws.send_json({"type": "info", "message": "live feed offline (no redis configured)"})
        try:
            await ws.receive_text()
        except WebSocketDisconnect:
            pass
        return

    pubsub = client.pubsub()
    await pubsub.subscribe(channel)

    async def forward() -> None:
        async for message in pubsub.listen():
            if message.get("type") == "message":
                data = message["data"]
                await ws.send_text(data if isinstance(data, str) else data.decode())

    forwarder = asyncio.create_task(forward())
    try:
        # Blocks until the client disconnects (the feed is server -> client only).
        await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        forwarder.cancel()
        try:
            await forwarder
        except BaseException:  # noqa: BLE001 - task teardown
            pass
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------------------------- #
# MCP endpoint (Phase 7d) — A2MCP-compatible tool surface for OKX
# --------------------------------------------------------------------------- #
@app.get("/mcp", tags=["mcp"], include_in_schema=False)
async def mcp_get() -> Response:
    # Streamable-HTTP: we don't offer a server-initiated SSE stream here.
    return Response(status_code=405)


@app.post("/mcp", tags=["mcp"])
async def mcp_endpoint(request: Request, session: AsyncSession = Depends(get_session)):
    """MCP Streamable-HTTP JSON-RPC endpoint exposing verify_resolution_rules."""
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse(mcp_server.rpc_error(None, mcp_server.PARSE_ERROR, "Parse error"))
    if not isinstance(payload, dict):
        return JSONResponse(
            mcp_server.rpc_error(None, mcp_server.INVALID_REQUEST, "Invalid Request")
        )

    method = payload.get("method")
    rpc_id = payload.get("id")
    params = payload.get("params") or {}

    # Notifications carry no id and expect no response body.
    if isinstance(method, str) and method.startswith("notifications/"):
        return Response(status_code=202)

    if method == "initialize":
        return JSONResponse(
            mcp_server.rpc_result(
                rpc_id,
                {
                    "protocolVersion": mcp_server.negotiate_version(params.get("protocolVersion")),
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": mcp_server.SERVER_INFO,
                    "instructions": mcp_server.INSTRUCTIONS,
                },
            )
        )

    if method == "ping":
        return JSONResponse(mcp_server.rpc_result(rpc_id, {}))

    if method == "tools/list":
        return JSONResponse(mcp_server.rpc_result(rpc_id, {"tools": [mcp_server.TOOL_DEF]}))

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        if name != mcp_server.TOOL_NAME:
            return JSONResponse(
                mcp_server.rpc_error(rpc_id, mcp_server.INVALID_PARAMS, f"Unknown tool: {name}")
            )
        market_url = args.get("market_url")
        if not market_url or not isinstance(market_url, str):
            return JSONResponse(
                mcp_server.rpc_error(rpc_id, mcp_server.INVALID_PARAMS, "market_url is required")
            )

        # Protect the free public tool from abuse (per-IP, fail-open).
        ip = request.client.host if request.client else "unknown"
        minute = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
        count = await redis_client.incr_with_expiry(f"rate:mcp:{ip}:{minute}", ttl=70)
        if count is not None and count > get_settings().rate_limit_per_minute:
            return JSONResponse(
                mcp_server.rpc_result(
                    rpc_id, mcp_server.tool_error("Rate limit exceeded; retry shortly.")
                )
            )

        queried_side = args.get("queried_side") or "YES"
        subscribe = bool(args.get("subscribe_monitor", False))
        started = time.perf_counter()
        try:
            response, llm_used = await _resolve_score_monitor(
                session,
                market_url=market_url,
                queried_side=queried_side,
                subscribe_monitor=subscribe,
                api_key_id=None,  # marketplace calls aren't tied to a local API key
            )
        except (UnsupportedPlatformError, ResolverError) as exc:
            # Tool-level error: surfaced to the calling agent, not a protocol error.
            return JSONResponse(mcp_server.rpc_result(rpc_id, mcp_server.tool_error(str(exc))))

        latency_ms = int((time.perf_counter() - started) * 1000)
        await _record_and_publish(
            session, response, api_key_id=None, llm_used=llm_used, latency_ms=latency_ms
        )
        return JSONResponse(mcp_server.rpc_result(rpc_id, mcp_server.tool_success(response)))

    return JSONResponse(
        mcp_server.rpc_error(rpc_id, mcp_server.METHOD_NOT_FOUND, f"Method not found: {method}")
    )


# --------------------------------------------------------------------------- #
# Shared verification core (used by REST /verify and the MCP tool)
# --------------------------------------------------------------------------- #
async def _resolve_score_monitor(
    session: AsyncSession,
    *,
    market_url: str,
    queried_side: str | None,
    subscribe_monitor: bool,
    api_key_id: int | None,
) -> tuple[VerifyResponse, bool]:
    """resolve (cached) -> analyze (cached) -> score -> monitor subscribe.

    Raises UnsupportedPlatformError / ResolverError for the caller to map to its
    protocol's error shape. Returns (response, llm_used)."""
    market = await resolve_cached(market_url, queried_side, resolver=resolve_market)
    # The LLM reads the real resolution text (cache-aside, ~15m); falls back to
    # the deterministic rubric when unset OR when the call fails.
    try:
        analysis = await analyze_cached(get_parser(), market, queried_side)
    except Exception:  # noqa: BLE001 - degrade to the deterministic rubric
        analysis = None

    response = score_market(
        market,
        analysis=analysis,
        queried_side=queried_side,
        subscribe_monitor=subscribe_monitor,
    )
    if response.monitor.subscribed and response.monitor.monitor_id:
        await monitor_service.create_subscription(
            session,
            monitor_id=response.monitor.monitor_id,
            api_key_id=api_key_id,
            market=market,
            queried_side=queried_side,
        )
    return response, analysis is not None


async def _record_and_publish(
    session: AsyncSession,
    response: VerifyResponse,
    *,
    api_key_id: int | None,
    llm_used: bool,
    latency_ms: int,
) -> None:
    """Persist the audit row and broadcast to the live feed (no-op sans Redis)."""
    await audit_service.record_success(
        session,
        response=response,
        api_key_id=api_key_id,
        llm_used=llm_used,
        latency_ms=latency_ms,
    )
    await redis_client.publish(
        get_settings().live_audits_channel,
        {
            "request_id": response.request_id,
            "market_url": response.market_url,
            "platform": response.platform.value,
            "action": response.action.value,
            "resolution_risk_score": response.resolution_risk_score,
            "confidence": response.confidence,
            "oracle_state": response.parsed_contract_data.current_oracle_state.value,
            "summary": response.summary,
            "checked_at": response.checked_at.isoformat(),
        },
    )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
async def _settle(
    session: AsyncSession,
    payment: PaymentState,
    request_id: str,
    api_key_id: int,
    http_response: Response,
) -> None:
    """Settle a verified payment, receipt it, and attach the PAYMENT-RESPONSE header."""
    settings = get_settings()
    facilitator = Facilitator(
        settings.okx_base_url, mode=settings.x402_mode, prefix=settings.okx_facilitator_prefix
    )
    result = await facilitator.settle(payment.payload, payment.requirements)
    await payment_service.record_settlement(
        session,
        request_id=request_id,
        api_key_id=api_key_id,
        requirements=payment.requirements,
        result=result,
        mode=settings.x402_mode,
    )
    http_response.headers["PAYMENT-RESPONSE"] = encode_header(result.to_response_dict())


async def _error(
    session: AsyncSession,
    status: int,
    code: ErrorCode,
    message: str,
    req: VerifyRequest,
    api_key: ApiKey,
    latency_ms: int,
) -> JSONResponse:
    payload = ErrorResponse(
        error_code=code, message=message, request_id=f"req_{uuid.uuid4().hex[:16]}"
    )
    await key_service.touch_usage(session, api_key)
    await audit_service.record_error(
        session,
        error=payload,
        market_url=req.market_url,
        queried_side=req.queried_side,
        api_key_id=api_key.id,
        latency_ms=latency_ms,
    )
    return JSONResponse(status_code=status, content=payload.model_dump(mode="json"))


# --------------------------------------------------------------------------- #
# Static web app (BetAudit portal). Mounted last so API routes always win.
# No-op until `web/dist` is built (npm run build), so tests/dev stay unaffected.
# --------------------------------------------------------------------------- #
_WEB_DIST = Path(
    os.environ.get("WEB_DIST_DIR") or (Path(__file__).resolve().parent.parent / "web" / "dist")
)
if _WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_WEB_DIST), html=True), name="web")
