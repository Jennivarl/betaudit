"""Named resolution-risk factors — the vocabulary the scoring is built on.

The LLM's job is to *classify* which of these trap conditions a market's rules
impose (a fixed, closed vocabulary). The engine then assigns each a **fixed
weight** and sums them. So the score is fully deterministic and every point
traces to a labeled, human-readable reason — no opaque 0-100 guess.

Shared by the parser (builds the tool schema + prompt) and the engine (weights),
in its own module to avoid an import cycle between them.
"""

from __future__ import annotations

# code -> (weight, human-readable reason shown in the score breakdown)
CONTENT_FACTORS: dict[str, tuple[int, str]] = {
    "requires_official_source": (
        22,
        "Resolves only from a specific official source (a filing, a government "
        "site, a court, a named agency) that a headline may not satisfy.",
    ),
    "requires_multiple_sources": (
        22,
        "Needs several named sources to all agree before it resolves.",
    ),
    "subjective_or_consensus": (
        25,
        "Resolution hinges on subjective judgment or a vague 'consensus of "
        "credible reporting' with no clear bright line — dispute-prone.",
    ),
    "strict_deadline": (
        15,
        "There is a hard deadline; being late flips the outcome.",
    ),
    "exact_entity_match": (
        15,
        "Must be one exact entity, bill, number, or threshold — not a close variant.",
    ),
    "conditional_resolution": (
        12,
        "Multi-step or conditional resolution with fallbacks the headline ignores.",
    ),
}

FACTOR_CODES: list[str] = list(CONTENT_FACTORS.keys())

# One-line guidance per factor, embedded in the LLM tool schema + prompt.
FACTOR_GUIDE: dict[str, str] = {
    "requires_official_source": "the rules name a specific official/authoritative source "
    "(e.g. an SEC filing, a government website, a court, a named agency)",
    "requires_multiple_sources": "resolution requires several named sources to all agree",
    "subjective_or_consensus": "resolution depends on subjective judgment or a vague "
    "'consensus of credible reporting' with no clear bright line",
    "strict_deadline": "there is a hard deadline and being late changes the outcome",
    "exact_entity_match": "it must be one exact entity/bill/number/threshold, not a similar one",
    "conditional_resolution": "resolution has conditional fallbacks or multiple steps",
}


def factor_schema_description() -> str:
    """The `risk_factors` field description for the LLM tool schema."""
    parts = [f"'{code}' = {desc}" for code, desc in FACTOR_GUIDE.items()]
    return (
        "Which of these resolution-trap conditions the rules impose — select ALL "
        "that apply, or an empty list if the rules match the obvious reading. "
        "Options: " + "; ".join(parts) + "."
    )
