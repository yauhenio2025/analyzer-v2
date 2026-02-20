"""Single LLM call execution with retry, streaming, and model selection.

This is the atomic unit of execution. Every analytical LLM call in the
executor flows through `run_engine_call()` (or `run_engine_call_auto()`
which handles document chunking for large inputs).

Key features:
- Plan-driven model selection (not hardcoded dicts)
- Streaming with extended thinking for Opus calls
- 1M context window support via beta header
- Exponential backoff retry (5 attempts)
- Heartbeat monitoring for long calls (60s timeout per chunk)
- Cancellation checks between retries
- **Document chunking** for large inputs (>200K chars) to avoid O(n²)
  attention slowdown. Splits document → extracts per chunk → synthesizes.

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

# Document chunking thresholds
# At 200K chars (~50K tokens), generation speed is ~43 tokens/s (fast).
# At 735K chars (~183K tokens), generation speed drops to ~0.5 tokens/s (O(n²) attention).
# Chunking keeps each call fast by limiting input size.
CHUNK_THRESHOLD = 200_000  # chars — above this, use chunking
MAX_CHUNK_CHARS = 180_000  # Target chunk size (with headroom for system prompt)


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
    force_no_thinking: bool = False,
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
        force_no_thinking: If True, disable thinking regardless of model config.
            Used for chunk extraction calls where thinking adds latency without value.

    Returns:
        dict with keys: content, model_used, input_tokens, output_tokens,
        thinking_tokens, duration_ms, retries
    """
    config = resolve_model_config(phase_number, model_hint, depth, requires_full_documents)
    if force_no_thinking:
        config["effort"] = None
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
            # Use sync call for no-thinking extractions (bypasses Render streaming bottleneck)
            if force_no_thinking:
                result = _execute_sync_call(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    config=config,
                    label=label,
                )
            else:
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


def _execute_sync_call(
    system_prompt: str,
    user_message: str,
    config: dict,
    label: str,
) -> dict:
    """Execute a synchronous (non-streaming) LLM call.

    Used for chunk extraction calls where thinking is disabled. Synchronous
    calls bypass the streaming throughput bottleneck on Render free tier
    (streaming on Render delivers events at ~0.5/s vs ~38 tokens/s locally,
    a 100x degradation). Synchronous calls generate the full response
    server-side and return it in one HTTP response.

    Requirements:
    - No thinking (thinking requires streaming)
    - Response time < 5 minutes (the timeout)
    """
    import httpx
    from anthropic import Anthropic

    client = Anthropic(
        timeout=httpx.Timeout(
            connect=60.0,
            read=600.0,     # 10 min — generous for large inputs
            write=120.0,    # 2 min — large prompts take time to send
            pool=60.0,
        ),
    )
    start_time = time.time()

    kwargs: dict[str, Any] = {
        "model": config["model"],
        "max_tokens": config["max_tokens"],
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}],
    }

    # No thinking, no beta — simple synchronous call
    logger.info(f"[{label}] Sync call starting (no streaming)")

    response = client.messages.create(**kwargs)

    duration_ms = int((time.time() - start_time) * 1000)

    raw_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            raw_text += block.text

    if not raw_text.strip():
        raise RuntimeError(f"[{label}] Empty response from {config['model']}")

    logger.info(
        f"[{label}] Sync call completed: {response.usage.input_tokens}+"
        f"{response.usage.output_tokens} tokens, {duration_ms}ms, "
        f"{len(raw_text):,} chars"
    )

    return {
        "content": raw_text.strip(),
        "model_used": config["model"],
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "thinking_tokens": 0,
        "duration_ms": duration_ms,
    }


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

    # 1M context window decision.
    #
    # CRITICAL THROUGHPUT INSIGHT: The 1M beta endpoint appears to have severely
    # reduced throughput (~2 chars/sec) compared to the standard endpoint (~50+ chars/sec)
    # for the same input. We should AVOID the 1M beta whenever possible by reducing
    # max_tokens to fit within the standard 200K context window.
    #
    # Standard context window: input_tokens + max_tokens <= 200K tokens
    # If we can reduce max_tokens (typical extractions need 8-16K output, not 64K),
    # we can often fit large inputs without the 1M beta.
    total_chars = len(system_prompt) + len(user_message)
    estimated_input_tokens = total_chars // 4
    use_beta = config.get("use_1m_context", False) or (total_chars > 780_000)

    STANDARD_CONTEXT_LIMIT = 200_000  # tokens
    MIN_OUTPUT_TOKENS = 8_000  # minimum usable output for extractions

    if use_beta:
        # Check if we can avoid 1M beta by reducing max_tokens
        max_safe_output = STANDARD_CONTEXT_LIMIT - estimated_input_tokens - 2_000  # 2K safety margin
        if max_safe_output >= MIN_OUTPUT_TOKENS:
            # We can fit in standard context with reduced output!
            reduced_max = min(config["max_tokens"], max(max_safe_output, MIN_OUTPUT_TOKENS))
            logger.info(
                f"[{label}] Avoiding 1M beta for throughput: ~{estimated_input_tokens:,} input tokens, "
                f"max_tokens {config['max_tokens']} → {reduced_max} to fit standard 200K context"
            )
            kwargs["max_tokens"] = reduced_max
            use_beta = False
        else:
            # Input truly needs 1M context (>190K input tokens)
            logger.info(
                f"[{label}] Using 1M beta: ~{estimated_input_tokens:,} input tokens "
                f"exceeds standard context even with min output ({max_safe_output:,} available)"
            )

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

    # Track whether we optimistically downgraded from 1M beta (for fallback)
    downgraded_from_1m = config.get("use_1m_context", False) and not use_beta
    connection_error = None

    # Streaming loop: runs once normally, or twice if we need to fall back to 1M beta
    # after the standard endpoint rejects the input as too long.
    for stream_attempt in range(2):
        if stream_attempt == 1:
            # Second attempt: 1M beta fallback (only reached on context_length error)
            raw_text = ""
            thinking_text = ""
            chunk_count = 0
            last_chunk_time = time.time()
            last_heartbeat_log = time.time()

        if use_beta:
            stream_cm = client.beta.messages.stream(
                **kwargs,
                betas=["context-1m-2025-08-07"],
            )
        else:
            stream_cm = client.messages.stream(**kwargs)

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

                    # Periodic heartbeat logging
                    if now - last_heartbeat_log > HEARTBEAT_LOG_INTERVAL:
                        elapsed = int(now - start_time)
                        beta_tag = " [1M]" if use_beta else " [std]"
                        logger.info(
                            f"[{label}]{beta_tag} Still streaming: {chunk_count} chunks, "
                            f"{elapsed}s elapsed, {len(raw_text):,} text chars, "
                            f"{len(thinking_text):,} thinking chars"
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

            break  # Success — exit the stream_attempt loop

        except InterruptedError:
            raise  # Don't salvage on explicit cancellation

        except Exception as e:
            error_str = str(e).lower()
            is_context_error = (
                "prompt is too long" in error_str
                or "context_length_exceeded" in error_str
                or "too many tokens" in error_str
                or ("max_tokens" in error_str and "maximum allowed" in error_str)
            )

            # If standard endpoint rejected input, fall back to 1M beta
            if is_context_error and downgraded_from_1m and not use_beta and stream_attempt == 0:
                logger.warning(
                    f"[{label}] Standard endpoint rejected input "
                    f"({total_chars:,} chars, ~{estimated_input_tokens:,} est tokens). "
                    f"Falling back to 1M beta with original max_tokens={config['max_tokens']}"
                )
                use_beta = True
                downgraded_from_1m = False
                kwargs["max_tokens"] = config["max_tokens"]
                continue  # Retry with 1M beta

            # Check if we accumulated enough text to salvage
            if len(raw_text.strip()) >= MIN_SALVAGEABLE_CHARS:
                duration_ms = int((time.time() - start_time) * 1000)
                logger.warning(
                    f"[{label}] Connection lost after {chunk_count} chunks ({duration_ms}ms), "
                    f"salvaging {len(raw_text):,} text chars + {len(thinking_text):,} thinking chars. "
                    f"Error: {e}"
                )
                if input_tokens == 0:
                    input_tokens = total_chars // 4
                if output_tokens == 0:
                    output_tokens = len(raw_text) // 4
                connection_error = str(e)
                break  # Fall through to return partial result
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


# ============================================================
# Document Chunking for Large Inputs
# ============================================================
#
# Transformer attention scales O(n²) with input length. Empirical data:
#   30K tokens input → 43 tokens/s output (fast)
#   183K tokens input → 0.5 tokens/s output (140x slower)
#
# Solution: split large documents into chunks, extract per chunk,
# then synthesize results. Each chunk stays under ~50K tokens where
# generation is fast.


def run_engine_call_auto(
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
    """Auto-routing wrapper: uses chunking for large inputs, direct call for small.

    This is the primary entry point for engine calls in the chain runner.
    Same signature and return format as run_engine_call().

    When user_message exceeds CHUNK_THRESHOLD:
    1. Splits into chunks at paragraph boundaries
    2. Runs extraction on each chunk (fast, ~50K tokens each)
    3. Synthesizes chunk results into one coherent output
    """
    if len(user_message) > CHUNK_THRESHOLD:
        return _run_chunked(
            system_prompt=system_prompt,
            user_message=user_message,
            phase_number=phase_number,
            model_hint=model_hint,
            depth=depth,
            requires_full_documents=requires_full_documents,
            cancellation_check=cancellation_check,
            label=label,
        )
    else:
        return run_engine_call(
            system_prompt=system_prompt,
            user_message=user_message,
            phase_number=phase_number,
            model_hint=model_hint,
            depth=depth,
            requires_full_documents=requires_full_documents,
            cancellation_check=cancellation_check,
            label=label,
        )


def _run_chunked(
    system_prompt: str,
    user_message: str,
    *,
    phase_number: float,
    model_hint: Optional[str],
    depth: str,
    requires_full_documents: bool,
    cancellation_check: Optional[Callable[[], bool]],
    label: str,
) -> dict:
    """Run with document chunking: split → extract per chunk → synthesize.

    Each chunk call uses the STANDARD context window (not 1M beta) since
    chunks are designed to be ~50K tokens. This gives ~43 tokens/s output
    instead of the ~0.5 tokens/s we'd get with the full document.
    """
    chunks = _split_text_at_paragraphs(user_message, MAX_CHUNK_CHARS)

    logger.info(
        f"[{label}] CHUNKING: {len(user_message):,} chars → "
        f"{len(chunks)} chunks of ~{MAX_CHUNK_CHARS:,} chars each"
    )

    chunk_results = []
    total_input_tokens = 0
    total_output_tokens = 0
    total_thinking_tokens = 0
    total_duration_ms = 0
    total_retries = 0

    for i, chunk in enumerate(chunks):
        if cancellation_check and cancellation_check():
            raise InterruptedError(f"[{label}] Cancelled during chunking at chunk {i+1}")

        chunk_label = f"{label} [chunk {i+1}/{len(chunks)}]"

        # Frame the chunk so the model knows it's a section
        framed_chunk = (
            f"[DOCUMENT SECTION {i+1} OF {len(chunks)}]\n"
            f"[This is one section of a larger document. Analyze this section thoroughly.]\n\n"
            f"{chunk}\n\n"
            f"[END OF SECTION {i+1}]"
        )

        # Each chunk uses standard context (NOT 1M beta) — chunks are small enough.
        # force_no_thinking=True because chunk extraction is a read-and-extract task,
        # not a reasoning task. Thinking at medium effort on 47K token chunks causes
        # 0.55 tokens/s output — 80x slower than without thinking.
        result = run_engine_call(
            system_prompt=system_prompt,
            user_message=framed_chunk,
            phase_number=phase_number,
            model_hint=model_hint,
            depth=depth,
            requires_full_documents=False,  # Chunks fit in standard 200K context
            cancellation_check=cancellation_check,
            label=chunk_label,
            force_no_thinking=True,
        )

        chunk_results.append(result)
        total_input_tokens += result["input_tokens"]
        total_output_tokens += result["output_tokens"]
        total_thinking_tokens += result["thinking_tokens"]
        total_duration_ms += result["duration_ms"]
        total_retries += result.get("retries", 0)

        logger.info(
            f"[{label}] Chunk {i+1}/{len(chunks)} complete: "
            f"{result['input_tokens']}+{result['output_tokens']} tokens, "
            f"{result['duration_ms']}ms, {len(result['content']):,} chars output"
        )

    # --- Synthesis pass: merge chunk results into one coherent output ---
    if cancellation_check and cancellation_check():
        raise InterruptedError(f"[{label}] Cancelled before synthesis")

    synthesis_parts = []
    for i, r in enumerate(chunk_results):
        synthesis_parts.append(
            f"## Analysis of Document Section {i+1}/{len(chunks)}\n\n"
            f"{r['content']}"
        )
    synthesis_input = "\n\n---\n\n".join(synthesis_parts)

    synthesis_system = (
        f"You are synthesizing analyses from {len(chunks)} sections of a large document. "
        f"The document was too large to analyze in one pass, so it was split into "
        f"{len(chunks)} overlapping sections and each was analyzed separately using "
        f"the same analytical framework.\n\n"
        f"Your task: merge these section analyses into a SINGLE, coherent, comprehensive "
        f"analysis. Combine overlapping findings, resolve any contradictions between "
        f"sections, eliminate redundancy, and produce output that reads as if the entire "
        f"document was analyzed at once.\n\n"
        f"IMPORTANT:\n"
        f"- Maintain the analytical depth and structure expected by the original prompt\n"
        f"- If sections found the same concept/theme, consolidate into one entry\n"
        f"- If sections found contradictory evidence, note both perspectives\n"
        f"- Preserve specific textual evidence and citations from the sections\n"
        f"- The final output should be comprehensive but not repetitive\n\n"
        f"Here is the original analysis prompt for context:\n\n"
        f"---\n{system_prompt[:8000]}\n---\n\n"  # Truncate long system prompts
        f"Now synthesize the {len(chunks)} section analyses below into one unified output."
    )

    synthesis_label = f"{label} [synthesis of {len(chunks)} chunks]"

    logger.info(
        f"[{label}] Starting synthesis of {len(chunks)} chunk results "
        f"({len(synthesis_input):,} chars input)"
    )

    synthesis_result = run_engine_call(
        system_prompt=synthesis_system,
        user_message=synthesis_input,
        phase_number=phase_number,
        model_hint=model_hint,
        depth=depth,
        requires_full_documents=False,  # Synthesis input is manageable
        cancellation_check=cancellation_check,
        label=synthesis_label,
    )

    total_calls = len(chunks) + 1  # chunks + synthesis

    logger.info(
        f"[{label}] CHUNKING COMPLETE: {len(chunks)} chunks + 1 synthesis = "
        f"{total_calls} calls, {total_input_tokens + synthesis_result['input_tokens']:,} "
        f"total input tokens, {total_duration_ms + synthesis_result['duration_ms']:,}ms total, "
        f"{len(synthesis_result['content']):,} chars final output"
    )

    return {
        "content": synthesis_result["content"],
        "model_used": synthesis_result["model_used"],
        "input_tokens": total_input_tokens + synthesis_result["input_tokens"],
        "output_tokens": total_output_tokens + synthesis_result["output_tokens"],
        "thinking_tokens": total_thinking_tokens + synthesis_result["thinking_tokens"],
        "duration_ms": total_duration_ms + synthesis_result["duration_ms"],
        "retries": total_retries + synthesis_result.get("retries", 0),
        "chunked": True,
        "num_chunks": len(chunks),
    }


def _split_text_at_paragraphs(text: str, max_chars: int) -> list[str]:
    """Split text into chunks at paragraph boundaries.

    Tries to split at double-newlines (paragraph breaks) to maintain
    coherent units of text. Falls back to sentence boundaries for
    oversized paragraphs.

    Returns at least 1 chunk.
    """
    if len(text) <= max_chars:
        return [text]

    chunks = []
    paragraphs = text.split("\n\n")
    current_chunk = ""

    for para in paragraphs:
        # Would adding this paragraph exceed the limit?
        if len(current_chunk) + len(para) + 2 > max_chars and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = para
        else:
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    # Handle edge case: single paragraph exceeding max_chars
    final_chunks = []
    for chunk in chunks:
        if len(chunk) > max_chars * 1.5:
            # Hard split at sentence boundaries
            sub_chunks = _split_at_sentences(chunk, max_chars)
            final_chunks.extend(sub_chunks)
        else:
            final_chunks.append(chunk)

    return final_chunks if final_chunks else [text]


def _split_at_sentences(text: str, max_chars: int) -> list[str]:
    """Split text at sentence boundaries when paragraph splitting isn't enough."""
    import re
    # Split on sentence-ending punctuation followed by space
    sentences = re.split(r'(?<=[.!?])\s+', text)

    chunks = []
    current = ""
    for sent in sentences:
        if len(current) + len(sent) + 1 > max_chars and current:
            chunks.append(current.strip())
            current = sent
        else:
            current = current + " " + sent if current else sent

    if current.strip():
        chunks.append(current.strip())

    return chunks if chunks else [text]
