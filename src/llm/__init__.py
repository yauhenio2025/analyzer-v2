"""Shared LLM client utilities.

Provides common functions for interacting with LLM APIs (Anthropic, Google),
used by both the LLM routes (profile generation, operationalizations)
and the transformation executor (extraction, summarization).
"""

from src.llm.client import (
    get_anthropic_client,
    parse_llm_json_response,
    call_extraction_model,
)
from src.llm.backends import (
    LLMCallResult,
    ModelBackend,
    AnthropicBackend,
    GeminiBackend,
)
from src.llm.factory import get_backend

__all__ = [
    "get_anthropic_client",
    "parse_llm_json_response",
    "call_extraction_model",
    "LLMCallResult",
    "ModelBackend",
    "AnthropicBackend",
    "GeminiBackend",
    "get_backend",
]
