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
        # Sonnet 4.6 — medium effort is Anthropic's recommended default.
        # "high" effort causes 20+ min thinking phases on 180K token inputs.
        "model": "claude-sonnet-4-6",
        "max_tokens": 64000,
        "effort": "medium",
    },
    "sonnet": {
        "model": "claude-sonnet-4-6",
        "max_tokens": 64000,
        "effort": "medium",
    },
    "haiku": {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 16000,
        "effort": None,  # no thinking for Haiku
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

    # Note: We no longer upgrade effort to "high" for deep depth.
    # "high" effort on large inputs (180K+ tokens) causes 15+ min thinking phases.
    # "medium" is Anthropic's recommended default for Sonnet 4.6.

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

    total_input_chars = len(system_prompt) + len(user_message)
    logger.info(
        f"[{label}] Starting LLM call: model={config['model']}, "
        f"effort={config.get('effort', 'none')}, "
        f"1M={'yes' if config['use_1m_context'] else 'no'}, "
        f"total_chars={total_input_chars:,} (~{total_input_chars//4:,} tokens), "
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
            if "prompt is too long" in error_str:
                raise RuntimeError(f"[{label}] Prompt too long (not retrying): {e}")
            if "max_tokens" in error_str and "maximum allowed" in error_str:
                raise RuntimeError(f"[{label}] max_tokens exceeds model limit (not retrying): {e}")

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

    CRITICAL: Accumulates text incrementally from stream deltas so that partial
    output can be salvaged on connection errors. Without this, a connection reset
    after 2+ hours of Opus streaming loses ALL output.

    Uses httpx read timeout (5 min) as a network-level safety net. If the TCP
    socket blocks for >5 min (dead connection without RST), httpx raises
    ReadTimeout which our exception handler catches. This prevents daemon threads
    from hanging forever on dead sockets — the in-loop heartbeat check only works
    while events are flowing.
    """
    import httpx
    from anthropic import Anthropic

    # Configure HTTP timeouts to prevent infinite hangs on dead sockets.
    # The read timeout (300s) is the max time between any two bytes on the wire.
    # This is our last-resort safety net — the in-loop heartbeat check (120s)
    # catches stalls when events flow but the loop iterates; the httpx timeout
    # catches stalls when the socket itself blocks (no events at all).
    client = Anthropic(
        timeout=httpx.Timeout(
            connect=60.0,     # 60s to establish TCP connection
            read=300.0,       # 5 min max silence on the socket
            write=60.0,       # 60s to send the request
            pool=60.0,        # 60s to acquire a connection from pool
        ),
    )
    start_time = time.time()

    # Build API call kwargs
    kwargs: dict[str, Any] = {
        "model": config["model"],
        "max_tokens": config["max_tokens"],
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}],
    }

    # 1M context window — also auto-enable if prompt is very large
    total_chars = len(system_prompt) + len(user_message)
    use_beta = config.get("use_1m_context", False)
    if not use_beta and total_chars > 600_000:
        # ~150K tokens at 4 chars/token — approaching 200K limit, use 1M
        logger.info(f"[{label}] Auto-enabling 1M context: {total_chars:,} chars in prompt")
        use_beta = True

    # Dynamic effort scaling based on input size.
    # Extended thinking on very large inputs (>100K tokens) is extremely slow
    # regardless of effort level — 2-3 chars/sec thinking rate, 0 text output
    # for 20+ minutes. The raw document text provides sufficient signal for
    # extraction tasks; thinking adds minimal value at massive latency cost.
    configured_effort = config.get("effort")
    if configured_effort and total_chars > 400_000:
        # >100K tokens: disable thinking entirely — extraction from large text
        logger.info(
            f"[{label}] Disabling thinking: {total_chars:,} chars (~{total_chars//4:,} tokens) "
            f"too large for efficient thinking"
        )
        configured_effort = None
    elif configured_effort and total_chars > 200_000:
        # 50-100K tokens: downgrade to low effort
        if configured_effort != "low":
            logger.info(
                f"[{label}] Downgrading effort to 'low': {total_chars:,} chars "
                f"(~{total_chars//4:,} tokens) is large input"
            )
            configured_effort = "low"

    # Adaptive thinking (GA on Sonnet 4.6 / Opus 4.6 — no beta header needed)
    # Uses output_config.effort instead of deprecated budget_tokens
    if configured_effort:
        kwargs["thinking"] = {"type": "adaptive"}
        kwargs["output_config"] = {"effort": configured_effort}

    # Accumulate response INCREMENTALLY from stream deltas
    # This is critical: if the connection drops after hours of streaming,
    # we can salvage the partial output instead of losing everything.
    raw_text = ""
    thinking_text = ""
    input_tokens = 0
    output_tokens = 0
    last_chunk_time = time.time()
    last_heartbeat_log = time.time()
    chunk_count = 0
    HEARTBEAT_LOG_INTERVAL = 30  # Log every 30s to confirm call is alive
    MIN_SALVAGEABLE_CHARS = 5000  # Minimum text chars to salvage on connection error

    if use_beta:
        # Use beta endpoint for 1M context window
        stream_cm = client.beta.messages.stream(
            **kwargs,
            betas=["context-1m-2025-08-07"],
        )
    else:
        stream_cm = client.messages.stream(**kwargs)

    connection_error = None

    try:
        with stream_cm as stream:
            for event in stream:
                chunk_count += 1

                # --- Accumulate text from stream deltas ---
                if hasattr(event, "type") and event.type == "content_block_delta":
                    delta = event.delta
                    if hasattr(delta, "type"):
                        if delta.type == "text_delta" and hasattr(delta, "text"):
                            raw_text += delta.text
                        elif delta.type == "thinking_delta" and hasattr(delta, "thinking"):
                            thinking_text += delta.thinking

                # Track output tokens from message_delta events
                if hasattr(event, "type") and event.type == "message_delta":
                    if hasattr(event, "usage") and hasattr(event.usage, "output_tokens"):
                        output_tokens = event.usage.output_tokens

                # Heartbeat check
                now = time.time()
                if now - last_chunk_time > HEARTBEAT_TIMEOUT:
                    raise TimeoutError(
                        f"[{label}] No data received for {HEARTBEAT_TIMEOUT}s — connection stalled"
                    )
                last_chunk_time = now

                # Periodic heartbeat logging (now includes accumulated text size)
                if now - last_heartbeat_log > HEARTBEAT_LOG_INTERVAL:
                    elapsed = int(now - start_time)
                    logger.info(
                        f"[{label}] Still streaming: {chunk_count} chunks, {elapsed}s elapsed, "
                        f"{len(raw_text):,} text chars, {len(thinking_text):,} thinking chars"
                    )
                    last_heartbeat_log = now

                # Cancellation check during streaming
                if cancellation_check and cancellation_check():
                    raise InterruptedError(f"[{label}] Cancelled during streaming")

            # Stream completed normally — get final message for accurate counts
            response = stream.get_final_message()

            # Use final message content (most accurate, includes all blocks)
            final_text = ""
            final_thinking = ""
            for block in response.content:
                if hasattr(block, "thinking"):
                    final_thinking += block.thinking
                elif hasattr(block, "text"):
                    final_text += block.text

            # Prefer final message content if available (belt-and-suspenders)
            if len(final_text) >= len(raw_text):
                raw_text = final_text
            if len(final_thinking) >= len(thinking_text):
                thinking_text = final_thinking

            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

    except InterruptedError:
        raise  # Don't salvage on explicit cancellation

    except Exception as e:
        # Check if we accumulated enough text to salvage
        if len(raw_text.strip()) >= MIN_SALVAGEABLE_CHARS:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.warning(
                f"[{label}] Connection lost after {chunk_count} chunks ({duration_ms}ms), "
                f"salvaging {len(raw_text):,} text chars + {len(thinking_text):,} thinking chars. "
                f"Error: {e}"
            )
            # Estimate tokens if we don't have accurate counts
            if input_tokens == 0:
                input_tokens = total_chars // 4
            if output_tokens == 0:
                output_tokens = len(raw_text) // 4
            connection_error = str(e)
            # Fall through to return partial result
        else:
            raise  # Not enough output to salvage — let retry logic handle it

    duration_ms = int((time.time() - start_time) * 1000)

    if not raw_text.strip():
        raise RuntimeError(f"[{label}] Empty response from {config['model']}")

    result = {
        "content": raw_text.strip(),
        "model_used": config["model"],
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "thinking_tokens": len(thinking_text),
        "duration_ms": duration_ms,
    }

    if connection_error:
        result["partial"] = True
        result["connection_error"] = connection_error
        logger.info(
            f"[{label}] Returning partial result: {len(raw_text):,} chars "
            f"(connection lost: {connection_error})"
        )

    return result
