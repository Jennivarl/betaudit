"""LLM layer: the OpenAI clause parser that turns raw resolution text into
structured rule mismatches and a grounded risk judgment.
"""

from app.llm.parser import ClauseAnalysis, ClauseParser, get_parser

__all__ = ["ClauseAnalysis", "ClauseParser", "get_parser"]
