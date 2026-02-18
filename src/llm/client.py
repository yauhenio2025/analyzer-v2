"""Shared LLM client for Anthropic Claude API.

Extracted from src/api/routes/llm.py to be reusable across:
- Profile generation (llm routes)
- Operationalization generation (llm routes)
- Transformation execution (transformation executor)
"""

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Default models
EXTRACTION_MODEL = "claude-haiku-4-5-20251001"
EXTRACTION_MODEL_FALLBACK = "claude-sonnet-4-5-20250929"
GENERATION_MODEL = "claude-opus-4-5-20251101"


def get_anthropic_client():
    """Get Anthropic client if API key is available.

    Returns None if ANTHROPIC_API_KEY is not set or anthropic is not installed.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic

        return anthropic.Anthropic(api_key=api_key)
    except ImportError:
        logger.warning("anthropic library not installed")
        return None


def parse_llm_json_response(raw_text: str) -> dict:
    """Parse JSON from LLM response, handling markdown code fences.

    LLMs sometimes wrap JSON in ```json ... ``` fences despite being
    told not to. This function strips those fences before parsing.

    Args:
        raw_text: Raw text from LLM response

    Returns:
        Parsed dict from JSON

    Raises:
        json.JSONDecodeError: If the text cannot be parsed as JSON
    """
    content = raw_text.strip()

    # Strip leading markdown fence (```json or ```)
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]

    # Strip trailing fence
    if content.endswith("```"):
        content = content.rsplit("```", 1)[0]

    content = content.strip()
    return json.loads(content)


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
    client = get_anthropic_client()
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

    for attempt_model in [model, fallback_model]:
        try:
            response = client.messages.create(model=attempt_model, **kwargs)
            raw_text = response.content[0].text
            total_tokens = (
                response.usage.input_tokens + response.usage.output_tokens
            )
            return raw_text, attempt_model, total_tokens
        except Exception as e:
            if attempt_model == fallback_model:
                raise RuntimeError(
                    f"Both {model} and {fallback_model} failed: {e}"
                ) from e
            logger.warning(
                f"Model {attempt_model} failed, trying {fallback_model}: {e}"
            )

    # Should never reach here, but just in case
    raise RuntimeError("All model attempts exhausted")
