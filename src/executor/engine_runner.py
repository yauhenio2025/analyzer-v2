"""Single LLM call execution with retry, streaming, and model selection.

This is the atomic unit of execution. Every analytical LLM call in the
executor flows through `run_engine_call()` (or `run_engine_call_auto()`
which handles document chunking for large inputs).

Key features:
- Plan-driven model selection (not hardcoded dicts)
- Multi-model support via ModelBackend abstraction (Anthropic, Gemini)
- Streaming with extended thinking for supported models
- 1M context window support (beta for Anthropic, native for Gemini)
- Exponential backoff retry (5 attempts)
- Heartbeat monitoring for long calls (60s timeout per chunk)
- Cancellation checks between retries
- Document chunking (DISABLED — whole-book 1M beta sync is 13x faster)

Ported from The Critic's `_call_claude_raw()` with plan-driven model selection.
"""

import logging
import os
import time
from typing import Any, Callable, Optional

from src.llm.factory import get_backend

logger = logging.getLogger(__name__)

# --- Sync vs Streaming strategy ---
#
# On Render (and similar PaaS), streaming SSE throughput is ~100x slower
# than sync API calls (0.5 vs 42+ tokens/s). This is due to reverse proxy
# buffering of SSE events.
#
# Sync API: Full response generated server-side, returned in one HTTP response.
#   - Pro: Full speed (~42 tokens/s), simpler, more reliable
#   - Con: No partial output salvage
#
# Streaming API: Response streamed as SSE events.
#   - Pro: Extended thinking, partial output salvage, progress visibility
#   - Con: 100x slower on Render, complex heartbeat/timeout logic
#
# Default: SYNC for all calls (massive speed improvement on Render).
# Set ENABLE_STREAMING=true to use streaming with thinking (for local dev).
PREFER_SYNC = os.environ.get("ENABLE_STREAMING", "").lower() not in ("1", "true", "yes")

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
    "gemini": {
        "model": "gemini-3.1-pro-preview",
        "max_tokens": 65536,
        "effort": "medium",
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

# Document chunking for large inputs.
# DISABLED: Empirical data from production sync calls shows the whole-book
# approach is ~13x FASTER than chunking:
#   - Whole book [1M beta sync]: 200K tokens -> 5K output in ~100s (37 tok/s)
#   - Chunked (5 chunks): 50K tokens each -> 10K output/chunk in ~250s, then synthesis
#     Total: ~4,400s per engine vs ~313s whole-book
CHUNK_THRESHOLD = 999_999_999  # effectively disabled — whole book as one call
MAX_CHUNK_CHARS = 180_000  # chars per chunk (only used if threshold lowered)


def resolve_model_config(
    phase_number: float,
    model_hint: Optional[str] = None,
    depth: str = "standard",
    requires_full_documents: bool = False,
) -> dict:
    """Resolve model configuration for an engine call.

    Priority: model_hint > phase default > depth-based heuristic.

    model_hint can be:
    - A config key: 'opus', 'sonnet', 'haiku', 'gemini'
    - A full model ID: 'claude-sonnet-4-6', 'gemini-3.1-pro-preview'
    """
    # If model_hint is a full model ID, build config from it
    if model_hint and (model_hint.startswith("claude-") or model_hint.startswith("gemini-") or model_hint.startswith("openrouter/")):
        if model_hint.startswith("openrouter/"):
            config = {
                "model": model_hint,
                "max_tokens": 32768,
                "effort": None,  # OpenRouter: no thinking support
            }
        elif model_hint.startswith("gemini-"):
            config = {
                "model": model_hint,
                "max_tokens": 65536,
                "effort": "medium",
            }
        else:
            config = {
                "model": model_hint,
                "max_tokens": 128000 if "opus-4-6" in model_hint else 64000,
                "effort": "medium" if "haiku" not in model_hint else None,
            }
        config["use_1m_context"] = requires_full_documents
        return config

    # model_hint as config key
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
        model_hint: Override model selection ('opus', 'sonnet', 'haiku', 'gemini',
                    or full model ID like 'gemini-3.1-pro-preview')
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

    # Decide: sync or streaming?
    # Sync is the default on Render (100x faster for Anthropic).
    # For Gemini, sync is also fine (thinking works in sync mode).
    is_gemini = config["model"].startswith("gemini-")
    is_openrouter = config["model"].startswith("openrouter/")
    use_sync = PREFER_SYNC or force_no_thinking or is_openrouter  # Always sync for OpenRouter

    # For Anthropic sync, disable thinking (it works but we historically avoid it
    # to match production behavior). For Gemini sync, thinking works fine.
    # For OpenRouter, thinking is never supported.
    if use_sync and not is_gemini and not is_openrouter:
        config["effort"] = None

    # Dynamic effort scaling based on input size.
    # Extended thinking on very large inputs (>100K tokens) is extremely slow
    # regardless of model — disable or downgrade to save time.
    total_input_chars = len(system_prompt) + len(user_message)
    effort = config.get("effort")
    if effort and total_input_chars > 400_000:
        logger.info(
            f"[{label}] Disabling thinking: {total_input_chars:,} chars "
            f"(~{total_input_chars // 4:,} tokens) too large"
        )
        effort = None
    elif effort and total_input_chars > 200_000:
        if effort != "low":
            logger.info(
                f"[{label}] Downgrading effort to 'low': {total_input_chars:,} chars"
            )
            effort = "low"

    logger.info(
        f"[{label}] Starting LLM call: model={config['model']}, "
        f"mode={'sync' if use_sync else 'streaming'}, "
        f"effort={effort or 'none'}, "
        f"1M={'yes' if config.get('use_1m_context') else 'no'}, "
        f"total_chars={total_input_chars:,} (~{total_input_chars // 4:,} tokens), "
        f"system_len={len(system_prompt):,}, user_len={len(user_message):,}"
    )

    backend = get_backend(config["model"])
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
            if use_sync:
                result_obj = backend.execute_sync(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    max_tokens=config["max_tokens"],
                    thinking_effort=effort,
                    use_extended_context=config.get("use_1m_context", False),
                    label=label,
                )
            else:
                result_obj = backend.execute_streaming(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    max_tokens=config["max_tokens"],
                    thinking_effort=effort,
                    use_extended_context=config.get("use_1m_context", False),
                    label=label,
                    cancellation_check=cancellation_check,
                )

            result = {
                "content": result_obj.content,
                "model_used": result_obj.model_id,
                "input_tokens": result_obj.input_tokens,
                "output_tokens": result_obj.output_tokens,
                "thinking_tokens": result_obj.thinking_tokens,
                "duration_ms": result_obj.duration_ms,
                "retries": attempt,
            }
            if result_obj.partial:
                result["partial"] = True
                result["connection_error"] = result_obj.connection_error

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


# ============================================================
# Document Chunking for Large Inputs
# ============================================================


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
    """Run with document chunking: split -> extract per chunk -> synthesize.

    Each chunk call uses the STANDARD context window (not 1M beta) since
    chunks are designed to be ~50K tokens. This gives ~43 tokens/s output
    instead of the ~0.5 tokens/s we'd get with the full document.
    """
    chunks = _split_text_at_paragraphs(user_message, MAX_CHUNK_CHARS)

    logger.info(
        f"[{label}] CHUNKING: {len(user_message):,} chars -> "
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
        # force_no_thinking=True because chunk extraction is a read-and-extract task.
        result = run_engine_call(
            system_prompt=system_prompt,
            user_message=framed_chunk,
            phase_number=phase_number,
            model_hint=model_hint,
            depth=depth,
            requires_full_documents=False,
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
        f"---\n{system_prompt[:8000]}\n---\n\n"
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
        requires_full_documents=False,
        cancellation_check=cancellation_check,
        label=synthesis_label,
    )

    total_calls = len(chunks) + 1

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
            sub_chunks = _split_at_sentences(chunk, max_chars)
            final_chunks.extend(sub_chunks)
        else:
            final_chunks.append(chunk)

    return final_chunks if final_chunks else [text]


def _split_at_sentences(text: str, max_chars: int) -> list[str]:
    """Split text at sentence boundaries when paragraph splitting isn't enough."""
    import re

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
