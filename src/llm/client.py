"""Shared LLM client for Anthropic Claude API.

Extracted from src/api/routes/llm.py to be reusable across:
- Profile generation (llm routes)
- Operationalization generation (llm routes)
- Transformation execution (transformation executor)
"""

import json
import logging
import os
import re
from typing import Any, Optional

try:
    from json_repair import repair_json

    HAS_JSON_REPAIR = True
except Exception:
    repair_json = None
    HAS_JSON_REPAIR = False

logger = logging.getLogger(__name__)

# Default models
EXTRACTION_MODEL = "claude-haiku-4-5-20251001"
EXTRACTION_MODEL_FALLBACK = "claude-sonnet-4-6"
GENERATION_MODEL = "claude-sonnet-4-6"


def get_anthropic_client(read_timeout_s: float = 300.0):
    """Get Anthropic client if API key is available.

    Configured with HTTP timeouts to prevent infinite hangs on dead sockets.
    Returns None if ANTHROPIC_API_KEY is not set or anthropic is not installed.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import httpx
        import anthropic

        return anthropic.Anthropic(
            api_key=api_key,
            timeout=httpx.Timeout(
                connect=60.0,
                read=read_timeout_s,
                write=60.0,
                pool=60.0,
            ),
        )
    except ImportError:
        logger.warning("anthropic library not installed")
        return None


def _strip_markdown_fences(raw_text: str) -> str:
    """Strip common markdown fences from an LLM response."""
    content = raw_text.strip()

    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]

    if content.endswith("```"):
        content = content.rsplit("```", 1)[0]

    return content.strip()


def _extract_json_candidate(content: str) -> str:
    """Extract the most likely JSON object/array substring from content."""
    obj_start = content.find("{")
    obj_end = content.rfind("}") + 1
    arr_start = content.find("[")
    arr_end = content.rfind("]") + 1

    if obj_start >= 0 and obj_end > obj_start:
        if arr_start >= 0 and arr_start < obj_start and arr_end > arr_start:
            return content[arr_start:arr_end].strip()
        return content[obj_start:obj_end].strip()

    if arr_start >= 0 and arr_end > arr_start:
        return content[arr_start:arr_end].strip()

    return content.strip()


def _regex_repair_json(content: str) -> str:
    """Apply lightweight repairs for common malformed-JSON patterns."""
    repaired = content
    repaired = re.sub(r",\s*([\]}])", r"\1", repaired)
    repaired = re.sub(r'}\s*"', '},"', repaired)
    repaired = re.sub(r'"\s*\{', '",{', repaired)
    repaired = re.sub(r"\}\s*\{", "},{", repaired)
    repaired = re.sub(r"\]\s*\{", "],{", repaired)
    repaired = re.sub(r'"\s+(")', r'", \1', repaired)
    repaired = re.sub(r"(\d)\s+(\")", r"\1, \2", repaired)
    return repaired


def _load_json(content: str) -> Any:
    """Load JSON and normalize scalars into a dict wrapper."""
    parsed = json.loads(content)
    if isinstance(parsed, (dict, list)):
        return parsed
    return {"value": parsed}


def parse_llm_json_response(raw_text: str) -> Any:
    """Parse JSON from LLM response with repair strategies.

    Tries:
    1. direct JSON parse after fence stripping
    2. substring extraction of the first object/array span
    3. `json_repair` if installed
    4. lightweight regex repairs
    5. regex repairs followed by `json_repair`
    """
    stripped = _strip_markdown_fences(raw_text)
    candidate = _extract_json_candidate(stripped)

    attempts: list[str] = []
    for value in (stripped, candidate):
        value = value.strip()
        if value and value not in attempts:
            attempts.append(value)

    parse_error: Optional[json.JSONDecodeError] = None

    for content in attempts:
        try:
            return _load_json(content)
        except json.JSONDecodeError as e:
            parse_error = e

        if HAS_JSON_REPAIR:
            try:
                return _load_json(repair_json(content, return_objects=False))
            except Exception:
                pass

        try:
            return _load_json(_regex_repair_json(content))
        except json.JSONDecodeError:
            pass

        if HAS_JSON_REPAIR:
            try:
                repaired = _regex_repair_json(content)
                return _load_json(repair_json(repaired, return_objects=False))
            except Exception:
                pass

    if parse_error is not None:
        raise parse_error
    raise json.JSONDecodeError("No JSON object or array found", raw_text, 0)


def repair_json_with_llm(
    malformed_json: str,
    model: str = EXTRACTION_MODEL_FALLBACK,
    fallback_model: str = EXTRACTION_MODEL_FALLBACK,
    max_tokens: int = 12000,
) -> tuple[str, str, int]:
    """Ask an LLM to repair malformed JSON while preserving content."""
    repair_prompt = (
        "You are a JSON repair assistant.\n"
        "Return ONLY valid JSON.\n"
        "Preserve all fields and content.\n"
        "Fix malformed syntax such as trailing commas, unescaped quotes, "
        "missing commas, and truncated closures.\n\n"
        "MALFORMED JSON:\n"
        f"{malformed_json}"
    )
    return call_extraction_model(
        prompt=repair_prompt,
        model=model,
        fallback_model=fallback_model,
        max_tokens=max_tokens,
    )


def call_extraction_model(
    prompt: str,
    model: str = EXTRACTION_MODEL,
    fallback_model: str = EXTRACTION_MODEL_FALLBACK,
    max_tokens: int = 8000,
    system_prompt: Optional[str] = None,
) -> tuple[str, str, int]:
    """Call Claude for extraction/transformation with fallback.

    Uses Haiku by default (fast, cheap, good at structured extraction).
    Falls back to Sonnet if Haiku fails.

    Args:
        prompt: The user message content
        model: Primary model to use
        fallback_model: Model to try if primary fails
        max_tokens: Maximum tokens in response
        system_prompt: Optional system prompt

    Returns:
        Tuple of (raw_response_text, model_used, total_tokens)

    Raises:
        RuntimeError: If both models fail
    """
    read_timeout_s = float(
        os.environ.get("ANTHROPIC_EXTRACTION_READ_TIMEOUT_S", "180")
    )
    client = get_anthropic_client(read_timeout_s=read_timeout_s)
    if client is None:
        raise RuntimeError(
            "LLM service unavailable. Set ANTHROPIC_API_KEY environment variable."
        )

    messages = [{"role": "user", "content": prompt}]
    kwargs = {
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system_prompt:
        kwargs["system"] = system_prompt

    attempt_models: list[str] = []
    for candidate in (model, fallback_model):
        if candidate and candidate not in attempt_models:
            attempt_models.append(candidate)
    emergency_fallback = os.environ.get(
        "ANTHROPIC_EXTRACTION_EMERGENCY_FALLBACK",
        EXTRACTION_MODEL,
    )
    if emergency_fallback and emergency_fallback not in attempt_models:
        if any("sonnet" in candidate for candidate in attempt_models):
            attempt_models.append(emergency_fallback)

    for idx, attempt_model in enumerate(attempt_models):
        try:
            response = client.messages.create(model=attempt_model, **kwargs)
            raw_text = response.content[0].text
            total_tokens = (
                response.usage.input_tokens + response.usage.output_tokens
            )
            return raw_text, attempt_model, total_tokens
        except Exception as e:
            is_last_attempt = idx == len(attempt_models) - 1
            if is_last_attempt:
                raise RuntimeError(
                    f"All extraction models failed ({', '.join(attempt_models)}): {e}"
                ) from e
            logger.warning(
                "Model %s failed within %.1fs read timeout, trying %s: %s",
                attempt_model,
                read_timeout_s,
                attempt_models[idx + 1],
                e,
            )

    # Should never reach here, but just in case
