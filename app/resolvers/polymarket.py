"""Polymarket adapter — the real v1 target (UMA optimistic oracle).

Turns a polymarket.com URL into normalized resolution facts by reading the
public Gamma API. The adapter is deliberately dumb: it fetches and normalizes,
it does not score risk or call the LLM (that is the engine's job).

Gamma facts we depend on:
  - description ......... contains the real resolution criteria / source of truth
  - resolutionSource .... explicit source when set (often empty -> LLM extracts it)
  - resolvedBy .......... UMA adapter address (presence => UMA optimistic oracle)
  - umaBond / umaReward . UMA economic params (confirm oracle type)
  - customLiveness ...... challenge window in seconds (0 => UMA default 7200s = 2h)
  - closed / umaResolutionStatuses . live resolution state
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.resolvers.base import (
    MarketResolver,
    ResolvedMarket,
    ResolverError,
)
from app.schemas import OracleState, Platform

# UMA OOv2 default challenge window when a market sets no customLiveness.
_UMA_DEFAULT_LIVENESS_S = 7200


class PolymarketResolver(MarketResolver):
    platform = Platform.POLYMARKET

    def __init__(self, gamma_url: Optional[str] = None, timeout: float = 20.0):
        self._gamma = (gamma_url or get_settings().polymarket_gamma_url).rstrip("/")
        self._timeout = timeout

    # -- routing -------------------------------------------------------------
    def matches(self, url: str) -> bool:
        host = (urlparse(url).hostname or "").lower()
        return host == "polymarket.com" or host.endswith(".polymarket.com")

    @staticmethod
    def _slug_from_url(url: str) -> str:
        # Use the LAST path segment — the most specific slug. Handles
        # /market/<slug>, /<slug>, and /event/<event>/<market> (picks <market>).
        # A bare /event/<slug> falls back to event lookup in _fetch_market.
        parts = [p for p in urlparse(url).path.split("/") if p]
        if not parts:
            raise ResolverError(f"No market slug in URL: {url}")
        return parts[-1]

    # -- fetch ---------------------------------------------------------------
    async def resolve(self, url: str, queried_side: Optional[str] = None) -> ResolvedMarket:
        slug = self._slug_from_url(url)
        market = await self._fetch_market(slug)
        return self._normalize(market, url)

    async def _fetch_market(self, slug: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            # 1) Direct market slug — the common single-binary-market case.
            markets = await self._get_json(client, "/markets", {"slug": slug})
            if markets:
                return markets[0]

            # 2) Event slug — the public /event/<slug> URL. May hold many markets.
            events = await self._get_json(client, "/events", {"slug": slug})
            if events:
                sub = events[0].get("markets", []) or []
                if len(sub) == 1:
                    return sub[0]
                if len(sub) > 1:
                    questions = ", ".join(
                        m.get("question", m.get("groupItemTitle", "?")) for m in sub[:8]
                    )
                    raise ResolverError(
                        f"Event '{slug}' contains {len(sub)} sub-markets; link a single "
                        f"market. Sub-markets: {questions}"
                    )

        raise ResolverError(f"Market not found for slug: {slug}")

    async def _get_json(
        self, client: httpx.AsyncClient, path: str, params: dict
    ) -> list[dict]:
        try:
            r = await client.get(f"{self._gamma}{path}", params=params)
            r.raise_for_status()
        except httpx.HTTPError as exc:
            raise ResolverError(f"Gamma API request failed ({path}): {exc}") from exc
        data = r.json()
        if isinstance(data, dict):
            data = data.get("data", [data])
        return data if isinstance(data, list) else []

    # -- normalize -----------------------------------------------------------
    def _normalize(self, m: dict[str, Any], url: str) -> ResolvedMarket:
        outcomes = _as_list(m.get("outcomes"))
        resolution_source = (m.get("resolutionSource") or "").strip() or None
        description = (m.get("description") or "").strip()

        oracle_type = "UMA_OOv2" if m.get("resolvedBy") or m.get("umaBond") else "UNKNOWN"
        challenge_hours = self._challenge_window_hours(m)
        state = self._oracle_state(m)

        raw_sources = [
            {
                "label": "Polymarket resolution criteria",
                "snippet": description[:600],
                "url": url,
            }
        ]
        if resolution_source:
            raw_sources.append(
                {"label": "Declared resolution source", "snippet": resolution_source, "url": url}
            )

        return ResolvedMarket(
            platform=Platform.POLYMARKET,
            market_id=str(m.get("conditionId") or m.get("id") or m.get("slug") or ""),
            market_url=url,
            question=(m.get("question") or "").strip(),
            outcomes=outcomes or ["Yes", "No"],
            resolution_criteria=description,
            source_of_truth_specified=resolution_source,  # LLM refines this from description
            oracle_type=oracle_type,
            challenge_window_hours=challenge_hours,
            current_oracle_state=state,
            raw_sources=raw_sources,
        )

    @staticmethod
    def _challenge_window_hours(m: dict[str, Any]) -> Optional[float]:
        liveness = m.get("customLiveness")
        try:
            seconds = float(liveness) if liveness else 0.0
        except (TypeError, ValueError):
            seconds = 0.0
        if seconds <= 0:
            seconds = _UMA_DEFAULT_LIVENESS_S if (m.get("resolvedBy") or m.get("umaBond")) else 0
        return round(seconds / 3600.0, 2) if seconds else None

    @staticmethod
    def _oracle_state(m: dict[str, Any]) -> OracleState:
        if m.get("closed") is True:
            return OracleState.RESOLVED
        statuses = m.get("umaResolutionStatuses") or []
        blob = " ".join(str(s).lower() for s in statuses)
        if "disput" in blob:
            return OracleState.DISPUTED
        if "propos" in blob:
            return OracleState.PROPOSED
        if m.get("active") is True:
            return OracleState.UNRESOLVED
        return OracleState.UNKNOWN


def _as_list(value: Any) -> list[str]:
    """Gamma sometimes returns outcomes as a JSON-encoded string."""
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str) and value.strip().startswith("["):
        import json

        try:
            return [str(v) for v in json.loads(value)]
        except json.JSONDecodeError:
            return []
    return []
