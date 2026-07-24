"""OpenAI clause parser.

Reads a market's *real* resolution text and returns a grounded, structured
analysis: the binding source of truth, the concrete mismatches between the
rules and a naive headline thesis, and a 0-100 risk judgment. Output is forced
through a function (tool) schema so it is always machine-shaped, and temperature
is 0 so the same rules yield the same reading — we score against what the rules
say, not against a creative guess.

The parser is optional infrastructure: with no API key it reports ``enabled =
False`` and the engine falls back to the deterministic rubric. Tests inject a
fake client, so this module runs without network or a key.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from app.config import get_settings
from app.resolvers.base import ResolvedMarket
from app.schemas import RuleMismatch

_TOOL_NAME = "report_resolution_analysis"

# JSON Schema for the function arguments the model must return.
_PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "source_of_truth": {
            "type": ["string", "null"],
            "description": "The authoritative source the rules REQUIRE for "
            "resolution (e.g. 'Official SEC 8-K Filing'), or null if none is named.",
        },
        "risk_score": {
            "type": "integer",
            "minimum": 0,
            "maximum": 100,
            "description": "How likely a naive headline-based trade on the queried "
            "side is trapped or misresolves. 0 = rules match the obvious reading, "
            "100 = the rules almost certainly betray a headline trader.",
        },
        "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "description": "Confidence in this analysis given how explicit the "
            "resolution text is.",
        },
        "reasoning": {
            "type": "string",
            "description": "One or two sentences, grounded in the text, no speculation.",
        },
        "mismatches": {
            "type": "array",
            "description": "Concrete gaps between the binding rules and the naive thesis. "
            "Empty if the rules match the obvious reading.",
            "items": {
                "type": "object",
                "properties": {
                    "clause": {"type": "string"},
                    "trader_thesis": {"type": "string"},
                    "conflict_reason": {"type": "string"},
                },
                "required": ["clause", "trader_thesis", "conflict_reason"],
            },
        },
    },
    "required": ["risk_score", "confidence", "mismatches"],
}

_TOOL_SPEC: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": _TOOL_NAME,
        "description": (
            "Report the resolution-rule analysis for a prediction market, grounded "
            "strictly in the provided resolution text."
        ),
        "parameters": _PARAMETERS,
    },
}

_SYSTEM = (
    "You are a prediction-market resolution auditor for autonomous trading agents. "
    "Given a market's exact resolution rules, you find where the binding rules diverge "
    "from what a trader acting on a news headline would assume. Rules:\n"
    "1. Ground every statement strictly in the provided resolution text. Never invent "
    "clauses, sources, dates, or facts.\n"
    "2. Focus on the specific queried side. A trap is a condition that must be met for "
    "that side to win which a headline reader would overlook (e.g. a required official "
    "source, an exact deadline, a specific defining authority).\n"
    "3. If the rules plainly match the obvious reading, return an empty mismatch list and "
    "a low score. Do not manufacture risk.\n"
    "4. Report only through the report_resolution_analysis function."
)


@dataclass
class ClauseAnalysis:
    """Structured output of the parser."""

    source_of_truth: Optional[str]
    risk_score: int
    confidence: float
    reasoning: str
    mismatches: list[RuleMismatch] = field(default_factory=list)


class ClauseParser:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        client: Any = None,
    ):
        settings = get_settings()
        self._model = model or settings.llm_model
        self._api_key = api_key if api_key is not None else settings.openai_api_key
        self._client = client  # injectable for tests

    @property
    def enabled(self) -> bool:
        return bool(self._client) or bool(self._api_key)

    @property
    def model(self) -> str:
        return self._model

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        # Lazy import so the package works without the SDK installed at import time.
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def parse(
        self, market: ResolvedMarket, queried_side: Optional[str] = None
    ) -> Optional[ClauseAnalysis]:
        if not self.enabled:
            return None

        client = self._ensure_client()
        prompt = self._build_prompt(market, queried_side)
        resp = await client.chat.completions.create(
            model=self._model,
            max_tokens=1200,
            temperature=0,
            seed=7,  # steadies the findings run-to-run (best-effort determinism)
            tools=[_TOOL_SPEC],
            tool_choice={"type": "function", "function": {"name": _TOOL_NAME}},
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": prompt},
            ],
        )
        payload = _extract_tool_input(resp)
        if payload is None:
            return None
        return _to_analysis(payload)

    @staticmethod
    def _build_prompt(market: ResolvedMarket, queried_side: Optional[str]) -> str:
        side = queried_side or "YES"
        return (
            f"MARKET QUESTION:\n{market.question}\n\n"
            f"OUTCOMES: {', '.join(market.outcomes)}\n"
            f"TRADER INTENDS TO BUY: {side}\n\n"
            f"DECLARED RESOLUTION SOURCE: {market.source_of_truth_specified or '(none stated)'}\n\n"
            f"RESOLUTION RULES (verbatim):\n{market.resolution_criteria or '(none provided)'}\n\n"
            f"Analyze whether buying {side} based on a news headline could be trapped by "
            f"these rules, and report via the function."
        )


def _extract_tool_input(resp: Any) -> Optional[dict]:
    """Pull the forced function-call arguments out of an OpenAI chat completion."""
    choices = getattr(resp, "choices", None) or []
    if not choices:
        return None
    message = getattr(choices[0], "message", None)
    tool_calls = getattr(message, "tool_calls", None) or []
    for call in tool_calls:
        fn = getattr(call, "function", None)
        if fn is None or getattr(fn, "name", None) != _TOOL_NAME:
            continue
        args = getattr(fn, "arguments", None)
        if isinstance(args, str):
            try:
                return json.loads(args)
            except json.JSONDecodeError:
                return None
        if isinstance(args, dict):
            return dict(args)
    return None


def _to_analysis(payload: dict) -> ClauseAnalysis:
    raw_mismatches = payload.get("mismatches") or []
    mismatches = [
        RuleMismatch(
            clause=str(mm.get("clause", "")).strip(),
            trader_thesis=str(mm.get("trader_thesis", "")).strip(),
            conflict_reason=str(mm.get("conflict_reason", "")).strip(),
        )
        for mm in raw_mismatches
        if mm.get("clause")
    ]
    score = int(payload.get("risk_score", 0))
    score = max(0, min(100, score))
    confidence = float(payload.get("confidence", 0.5))
    confidence = max(0.0, min(1.0, confidence))
    return ClauseAnalysis(
        source_of_truth=(payload.get("source_of_truth") or None),
        risk_score=score,
        confidence=confidence,
        reasoning=str(payload.get("reasoning", "")).strip(),
        mismatches=mismatches,
    )


def get_parser() -> ClauseParser:
    return ClauseParser()
