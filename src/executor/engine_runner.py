"""Single LLM call execution with retry, streaming, and model selection.

This is the atomic unit of execution. Every analytical LLM call in the
executor flows through `run_engine_call()`.

Key features:
- Plan-driven model selection (not hardcoded dicts)
- Streaming with extended thinking for Opus calls
- 1M context window support via beta header
- Exponential backoff retry (5 attempts)
- Heartbeat monitoring for long calls (60s timeout per chunk)
- Cancellation checks between retries

Ported from The Critic's `_call_claude_raw()` with plan-driven model selection.
"""

import json
import logging
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# --- Model configurations ---

MODEL_CONFIGS = {
    "opus": {
        "model": "claude-opus-4-5-20251101",
        "max_tokens": 128000,
        "thinking_budget": 10000,
        "use_thinking": True,
    },
    "sonnet": {
        "model": "claude-sonnet-4-5-20250929",
        "max_tokens": 64000,
        "thinking_budget": 5000,
        "use_thinking": True,
    },
    "haiku": {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 16000,
        "thinking_budget": 0,
        "use_thinking": False,
    },
}

# Default model per phase characteristic
PHASE_MODEL_DEFAULTS = {
    # Phase 1.0: Deep profiling needs Opus
    1.0: "opus",
    # Phase 1.5: Classification is simpler, Sonnet suffices
    1.5: "sonnet",
    # Phase 2.0: Scanning prior works, Sonnet with high effort
    2.0: "sonnet",
    # Phase 3.0: Synthesis needs Opus for quality
    3.0: "opus",
    # Phase 4.0: Final synthesis needs Opus
    4.0: "opus",
}

# Retry settings
MAX_RETRIES = 5
RETRY_DELAYS = [30, 60, 90, 120, 180]  # seconds
HEARTBEAT_TIMEOUT = 120  # seconds without a chunk before considering stalled


def resolve_model_config(
    phase_number: float,
    model_hint: Optional[str] = None,
    depth: str = "standard",
    requires_full_documents: bool = False,
) -> dict:
    """Resolve model configuration for an engine call.

    Priority: model_hint > phase default > depth-based heuristic.
    """
    # Determine model key
    if model_hint and model_hint in MODEL_CONFIGS:
        model_key = model_hint
    elif phase_number in PHASE_MODEL_DEFAULTS:
        model_key = PHASE_MODEL_DEFAULTS[phase_number]
    elif depth == "deep":
        model_key = "opus"
    else:
        model_key = "sonnet"

    config = dict(MODEL_CONFIGS[model_key])
    config["use_1m_context"] = requires_full_documents

    # Deep depth gets higher thinking budget
    if depth == "deep" and config["use_thinking"]:
        config["thinking_budget"] = max(config["thinking_budget"], 10000)

    return config


def run_engine_call(
    system_prompt: str,
    user_message: str,
    *,
    phase_number: float = 1.0,
    model_hint: Optional[str] = None,
    depth: str = "standard",
    requires_full_documents: bool = False,
    cancellation_check: Optional[Callable[[], bool]] = None,
    label: str = "",
) -> dict:
    """Execute a single LLM call with streaming, retry, and model selection.

    Args:
        system_prompt: The composed system prompt for this engine/pass
        user_message: The user message (document text + context)
        phase_number: Current phase number (for model selection)
        model_hint: Override model selection ('opus', 'sonnet', 'haiku')
        depth: Analysis depth ('surface', 'standard', 'deep')
        requires_full_documents: Whether to use 1M context window
        cancellation_check: Callable that returns True to cancel
        label: Human-readable label for logging

    Returns:
        dict with keys: content, model_used, input_tokens, output_tokens,
        thinking_tokens, duration_ms, retries
    """
    config = resolve_model_config(phase_number, model_hint, depth, requires_full_documents)
    label = label or f"Phase {phase_number}"

    logger.info(
        f"[{label}] Starting LLM call: model={config['model']}, "
        f"thinking={'enabled' if config['use_thinking'] else 'disabled'}, "
        f"1M={'yes' if config['use_1m_context'] else 'no'}, "
        f"system_len={len(system_prompt):,}, user_len={len(user_message):,}"
    )

    last_error = None

    for attempt in range(MAX_RETRIES):
        if cancellation_check and cancellation_check():
            raise InterruptedError(f"[{label}] Cancelled before attempt {attempt + 1}")

        if attempt > 0:
            delay = RETRY_DELAYS[min(attempt - 1, len(RETRY_DELAYS) - 1)]
            logger.warning(
                f"[{label}] Retry {attempt}/{MAX_RETRIES} after {delay}s "
                f"(previous error: {last_error})"
            )
            time.sleep(delay)

        try:
            result = _execute_streaming_call(
                system_prompt=system_prompt,
                user_message=user_message,
                config=config,
                label=label,
                cancellation_check=cancellation_check,
            )
            result["retries"] = attempt
            logger.info(
                f"[{label}] Completed: {result['input_tokens']}+{result['output_tokens']} tokens, "
                f"{result['thinking_tokens']} thinking tokens, {result['duration_ms']}ms"
            )
            return result

        except InterruptedError:
            raise  # Don't retry cancellations

        except Exception as e:
            last_error = str(e)
            logger.error(f"[{label}] Attempt {attempt + 1} failed: {last_error}")

            # Don't retry on certain errors
            error_str = str(e).lower()
            if "invalid_api_key" in error_str or "authentication" in error_str:
                raise RuntimeError(f"[{label}] Authentication error (not retrying): {e}")
            if "context_length_exceeded" in error_str or "too many tokens" in error_str:
                raise RuntimeError(f"[{label}] Context too long (not retrying): {e}")

    raise RuntimeError(
        f"[{label}] Failed after {MAX_RETRIES} attempts. Last error: {last_error}"
    )


def _execute_streaming_call(
    system_prompt: str,
    user_message: str,
    config: dict,
    label: str,
    cancellation_check: Optional[Callable[[], bool]] = None,
) -> dict:
    """Execute a single streaming LLM call.

    Uses streaming for all calls (required for extended thinking and 1M context).
    Monitors heartbeat to detect stalled connections.
    """
    from anthropic import Anthropic

    client = Anthropic()
    start_time = time.time()

    # Build API call kwargs
    kwargs: dict[str, Any] = {
        "model": config["model"],
        "max_tokens": config["max_tokens"],
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}],
    }

    # Extended thinking
    if config["use_thinking"] and config["thinking_budget"] > 0:
        kwargs["thinking"] = {
            "type": "enabled",
            "budget_tokens": config["thinking_budget"],
        }

    # 1M context window
    use_beta = config.get("use_1m_context", False)

    # Accumulate response
    raw_text = ""
    thinking_text = ""
    input_tokens = 0
    output_tokens = 0
    last_chunk_time = time.time()

    if use_beta:
        # Use beta endpoint for 1M context
        stream_cm = client.beta.messages.stream(
            **kwargs,
            betas=["interleaved-thinking-2025-05-14"],
        )
    else:
        stream_cm = client.messages.stream(**kwargs)

    with stream_cm as stream:
        for event in stream:
            # Heartbeat check
            now = time.time()
            if now - last_chunk_time > HEARTBEAT_TIMEOUT:
                raise TimeoutError(
                    f"[{label}] No data received for {HEARTBEAT_TIMEOUT}s — connection stalled"
                )
            last_chunk_time = now

            # Cancellation check during streaming
            if cancellation_check and cancellation_check():
                raise InterruptedError(f"[{label}] Cancelled during streaming")

        # Get final message
        response = stream.get_final_message()

    # Extract content from response blocks
    for block in response.content:
        if hasattr(block, "thinking"):
            thinking_text += block.thinking
        elif hasattr(block, "text"):
            raw_text += block.text

    # Token counts
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens

    duration_ms = int((time.time() - start_time) * 1000)

    if not raw_text.strip():
        raise RuntimeError(f"[{label}] Empty response from {config['model']}")

    return {
        "content": raw_text.strip(),
        "model_used": config["model"],
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "thinking_tokens": len(thinking_text),
        "duration_ms": duration_ms,
    }
