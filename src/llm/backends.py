"""LLM backend abstraction for multi-model support.

Provides a unified interface for calling different LLM providers
(Anthropic Claude, Google Gemini) with consistent response format.

Each backend handles provider-specific concerns:
- Client creation and timeout configuration
- Context window management (1M beta for Anthropic, native 1M for Gemini)
- Thinking/reasoning configuration
- Response parsing and token counting
- Streaming with heartbeat monitoring
- Partial output salvage on connection errors

The engine_runner handles model-agnostic concerns:
- Retry with exponential backoff
- Sync vs streaming routing
- Model config resolution
- Document chunking
"""

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@dataclass
class LLMCallResult:
    """Normalized response from any LLM backend."""

    content: str
    model_id: str
    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    duration_ms: int
    partial: bool = False
    connection_error: Optional[str] = None


# Constants shared across backends
HEARTBEAT_TIMEOUT = 120  # seconds without data before considering stalled
HEARTBEAT_LOG_INTERVAL = 30  # Log every 30s to confirm call is alive
MIN_SALVAGEABLE_CHARS = 5000  # Minimum text chars to salvage on connection error


@runtime_checkable
class ModelBackend(Protocol):
    """Protocol for LLM backend implementations."""

    @property
    def model_id(self) -> str: ...

    @property
    def max_output_tokens(self) -> int: ...

    @property
    def supports_thinking(self) -> bool: ...

    @property
    def native_context_limit(self) -> int:
        """Native context window in tokens (before any beta extensions)."""
        ...

    def execute_sync(
        self,
        system_prompt: str,
        user_message: str,
        *,
        max_tokens: int,
        thinking_effort: Optional[str] = None,
        use_extended_context: bool = False,
        label: str = "",
    ) -> LLMCallResult: ...

    def execute_streaming(
        self,
        system_prompt: str,
        user_message: str,
        *,
        max_tokens: int,
        thinking_effort: Optional[str] = None,
        use_extended_context: bool = False,
        label: str = "",
        cancellation_check: Optional[Callable[[], bool]] = None,
    ) -> LLMCallResult: ...


class AnthropicBackend:
    """Anthropic Claude backend.

    Handles:
    - Standard 200K vs 1M beta context window management
    - Adaptive thinking with effort levels
    - Streaming with heartbeat monitoring and partial salvage
    - Max_tokens adjustment to fit standard context
    """

    def __init__(self, model_id: str = "claude-sonnet-4-6"):
        self._model_id = model_id

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def max_output_tokens(self) -> int:
        if "opus-4-6" in self._model_id:
            return 128_000
        return 64_000

    @property
    def supports_thinking(self) -> bool:
        return "haiku" not in self._model_id

    @property
    def native_context_limit(self) -> int:
        return 200_000

    def execute_sync(
        self,
        system_prompt: str,
        user_message: str,
        *,
        max_tokens: int,
        thinking_effort: Optional[str] = None,
        use_extended_context: bool = False,
        label: str = "",
    ) -> LLMCallResult:
        """Execute a synchronous (non-streaming) Anthropic call.

        Bypasses the streaming throughput bottleneck on Render (streaming SSE
        events arrive at ~0.5/s vs ~42 tokens/s for sync).

        Timeout: 20 min read timeout handles up to ~50K output tokens at 42 tok/s.
        """
        import httpx
        from anthropic import Anthropic

        client = Anthropic(
            timeout=httpx.Timeout(
                connect=60.0,
                read=1200.0,  # 20 min for large outputs
                write=120.0,  # 2 min for large prompts
                pool=60.0,
            ),
        )
        start_time = time.time()

        total_chars = len(system_prompt) + len(user_message)
        estimated_input_tokens = total_chars // 4

        STANDARD_CONTEXT_LIMIT = 200_000
        MIN_OUTPUT_TOKENS = 8_000

        use_beta = use_extended_context or (estimated_input_tokens > 180_000)

        if not use_beta:
            headroom = STANDARD_CONTEXT_LIMIT - estimated_input_tokens - 2_000
            if headroom < max_tokens and headroom >= MIN_OUTPUT_TOKENS:
                logger.info(
                    f"[{label}] Reducing max_tokens {max_tokens} -> {headroom} "
                    f"to fit standard 200K context (~{estimated_input_tokens:,} input tokens)"
                )
                max_tokens = headroom
            elif headroom < MIN_OUTPUT_TOKENS:
                use_beta = True
                logger.info(
                    f"[{label}] Input too large for standard context "
                    f"(~{estimated_input_tokens:,} tokens), switching to 1M beta"
                )

        kwargs: dict[str, Any] = {
            "model": self._model_id,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_message}],
        }

        # Thinking in sync mode (works for Anthropic, unlike streaming-only myth)
        if thinking_effort and self.supports_thinking:
            kwargs["thinking"] = {"type": "adaptive"}
            kwargs["output_config"] = {"effort": thinking_effort}

        beta_tag = "[1M]" if use_beta else "[std]"
        logger.info(
            f"[{label}] Anthropic sync {beta_tag}: ~{estimated_input_tokens:,} input tokens, "
            f"max_tokens={max_tokens}, effort={thinking_effort or 'none'}"
        )

        if use_beta:
            response = client.beta.messages.create(
                **kwargs,
                betas=["context-1m-2025-08-07"],
            )
        else:
            response = client.messages.create(**kwargs)

        duration_ms = int((time.time() - start_time) * 1000)

        raw_text = ""
        thinking_tokens = 0
        for block in response.content:
            if hasattr(block, "thinking"):
                thinking_tokens += len(block.thinking)
            elif hasattr(block, "text"):
                raw_text += block.text

        if not raw_text.strip():
            raise RuntimeError(f"[{label}] Empty response from {self._model_id}")

        logger.info(
            f"[{label}] Sync completed: {response.usage.input_tokens}+"
            f"{response.usage.output_tokens} tokens, {duration_ms}ms, "
            f"{len(raw_text):,} chars"
        )

        return LLMCallResult(
            content=raw_text.strip(),
            model_id=self._model_id,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            thinking_tokens=thinking_tokens,
            duration_ms=duration_ms,
        )

    def execute_streaming(
        self,
        system_prompt: str,
        user_message: str,
        *,
        max_tokens: int,
        thinking_effort: Optional[str] = None,
        use_extended_context: bool = False,
        label: str = "",
        cancellation_check: Optional[Callable[[], bool]] = None,
    ) -> LLMCallResult:
        """Execute a streaming Anthropic call with heartbeat monitoring.

        CRITICAL: Accumulates text incrementally from stream deltas so that
        partial output can be salvaged on connection errors.
        """
        import httpx
        from anthropic import Anthropic

        client = Anthropic(
            timeout=httpx.Timeout(
                connect=60.0,
                read=300.0,  # 5 min max silence on socket
                write=60.0,
                pool=60.0,
            ),
        )
        start_time = time.time()

        kwargs: dict[str, Any] = {
            "model": self._model_id,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_message}],
        }

        total_chars = len(system_prompt) + len(user_message)
        estimated_input_tokens = total_chars // 4
        use_beta = use_extended_context or (total_chars > 780_000)

        STANDARD_CONTEXT_LIMIT = 200_000
        MIN_OUTPUT_TOKENS = 8_000

        original_max_tokens = max_tokens
        if use_beta:
            max_safe_output = STANDARD_CONTEXT_LIMIT - estimated_input_tokens - 2_000
            if max_safe_output >= MIN_OUTPUT_TOKENS:
                reduced_max = min(max_tokens, max(max_safe_output, MIN_OUTPUT_TOKENS))
                logger.info(
                    f"[{label}] Avoiding 1M beta: ~{estimated_input_tokens:,} input tokens, "
                    f"max_tokens {max_tokens} -> {reduced_max} to fit standard 200K"
                )
                kwargs["max_tokens"] = reduced_max
                use_beta = False
            else:
                logger.info(
                    f"[{label}] Using 1M beta: ~{estimated_input_tokens:,} input tokens "
                    f"exceeds standard context"
                )

        # Adaptive thinking
        if thinking_effort and self.supports_thinking:
            kwargs["thinking"] = {"type": "adaptive"}
            kwargs["output_config"] = {"effort": thinking_effort}

        # Incremental accumulation
        raw_text = ""
        thinking_text = ""
        input_tokens = 0
        output_tokens = 0
        last_chunk_time = time.time()
        last_heartbeat_log = time.time()
        chunk_count = 0
        connection_error = None

        downgraded_from_1m = use_extended_context and not use_beta

        for stream_attempt in range(2):
            if stream_attempt == 1:
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

                        if hasattr(event, "type") and event.type == "content_block_delta":
                            delta = event.delta
                            if hasattr(delta, "type"):
                                if delta.type == "text_delta" and hasattr(delta, "text"):
                                    raw_text += delta.text
                                elif delta.type == "thinking_delta" and hasattr(delta, "thinking"):
                                    thinking_text += delta.thinking

                        if hasattr(event, "type") and event.type == "message_delta":
                            if hasattr(event, "usage") and hasattr(event.usage, "output_tokens"):
                                output_tokens = event.usage.output_tokens

                        now = time.time()
                        if now - last_chunk_time > HEARTBEAT_TIMEOUT:
                            raise TimeoutError(
                                f"[{label}] No data for {HEARTBEAT_TIMEOUT}s -- stalled"
                            )
                        last_chunk_time = now

                        if now - last_heartbeat_log > HEARTBEAT_LOG_INTERVAL:
                            elapsed = int(now - start_time)
                            beta_tag = " [1M]" if use_beta else " [std]"
                            logger.info(
                                f"[{label}]{beta_tag} Streaming: {chunk_count} chunks, "
                                f"{elapsed}s, {len(raw_text):,} text, "
                                f"{len(thinking_text):,} thinking"
                            )
                            last_heartbeat_log = now

                        if cancellation_check and cancellation_check():
                            raise InterruptedError(f"[{label}] Cancelled during streaming")

                    # Stream completed — get final message
                    response = stream.get_final_message()

                    final_text = ""
                    final_thinking = ""
                    for block in response.content:
                        if hasattr(block, "thinking"):
                            final_thinking += block.thinking
                        elif hasattr(block, "text"):
                            final_text += block.text

                    if len(final_text) >= len(raw_text):
                        raw_text = final_text
                    if len(final_thinking) >= len(thinking_text):
                        thinking_text = final_thinking

                    input_tokens = response.usage.input_tokens
                    output_tokens = response.usage.output_tokens

                break  # Success

            except InterruptedError:
                raise

            except Exception as e:
                error_str = str(e).lower()
                is_context_error = (
                    "prompt is too long" in error_str
                    or "context_length_exceeded" in error_str
                    or "too many tokens" in error_str
                    or ("max_tokens" in error_str and "maximum allowed" in error_str)
                )

                if is_context_error and downgraded_from_1m and not use_beta and stream_attempt == 0:
                    logger.warning(
                        f"[{label}] Standard rejected input, falling back to 1M beta"
                    )
                    use_beta = True
                    downgraded_from_1m = False
                    kwargs["max_tokens"] = original_max_tokens
                    continue

                if len(raw_text.strip()) >= MIN_SALVAGEABLE_CHARS:
                    duration_ms = int((time.time() - start_time) * 1000)
                    logger.warning(
                        f"[{label}] Connection lost, salvaging {len(raw_text):,} chars. "
                        f"Error: {e}"
                    )
                    if input_tokens == 0:
                        input_tokens = total_chars // 4
                    if output_tokens == 0:
                        output_tokens = len(raw_text) // 4
                    connection_error = str(e)
                    break
                else:
                    raise

        duration_ms = int((time.time() - start_time) * 1000)

        if not raw_text.strip():
            raise RuntimeError(f"[{label}] Empty response from {self._model_id}")

        return LLMCallResult(
            content=raw_text.strip(),
            model_id=self._model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            thinking_tokens=len(thinking_text),
            duration_ms=duration_ms,
            partial=connection_error is not None,
            connection_error=connection_error,
        )


class GeminiBackend:
    """Google Gemini backend.

    Handles:
    - Native 1M context window (no beta needed)
    - Thinking with thinking_budget
    - Temperature must be 1.0 for thinking mode
    - Streaming with heartbeat monitoring
    - Partial output salvage on connection errors

    Requires GEMINI_API_KEY environment variable.
    Requires google-genai package: pip install google-genai
    """

    # Map effort levels to thinking budgets (tokens)
    EFFORT_TO_BUDGET = {
        "low": 4096,
        "medium": 16384,
        "high": 32768,
    }

    def __init__(self, model_id: str = "gemini-3.1-pro-preview"):
        self._model_id = model_id

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def max_output_tokens(self) -> int:
        return 65_536

    @property
    def supports_thinking(self) -> bool:
        return True

    @property
    def native_context_limit(self) -> int:
        return 1_048_576

    def _get_client(self):
        """Get a Gemini client. Lazy import to avoid requiring google-genai."""
        try:
            from google import genai
        except ImportError:
            raise RuntimeError(
                "google-genai package not installed. "
                "Install with: pip install google-genai"
            )

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY not set. Set the environment variable to use Gemini."
            )
        return genai.Client(api_key=api_key)

    def execute_sync(
        self,
        system_prompt: str,
        user_message: str,
        *,
        max_tokens: int,
        thinking_effort: Optional[str] = None,
        use_extended_context: bool = False,
        label: str = "",
    ) -> LLMCallResult:
        """Execute a synchronous Gemini call.

        Gemini supports thinking in sync mode (unlike Anthropic's streaming-only
        thinking). Context window is natively 1M — no beta header needed.
        """
        from google import genai

        client = self._get_client()
        start_time = time.time()

        total_chars = len(system_prompt) + len(user_message)
        estimated_input_tokens = total_chars // 4

        logger.info(
            f"[{label}] Gemini sync: ~{estimated_input_tokens:,} input tokens, "
            f"max_tokens={max_tokens}, effort={thinking_effort or 'none'}"
        )

        config_kwargs: dict[str, Any] = {
            "system_instruction": system_prompt,
            "max_output_tokens": min(max_tokens, self.max_output_tokens),
        }

        if thinking_effort and thinking_effort in self.EFFORT_TO_BUDGET:
            config_kwargs["thinking_config"] = genai.types.ThinkingConfig(
                thinking_budget=self.EFFORT_TO_BUDGET[thinking_effort],
            )
            config_kwargs["temperature"] = 1.0  # Required for thinking mode

        config = genai.types.GenerateContentConfig(**config_kwargs)

        response = client.models.generate_content(
            model=self._model_id,
            contents=user_message,
            config=config,
        )

        duration_ms = int((time.time() - start_time) * 1000)

        # Extract text (separate thinking from output)
        raw_text = ""
        thinking_chars = 0
        if response.candidates and response.candidates[0].content:
            for part in response.candidates[0].content.parts:
                text = getattr(part, "text", "") or ""
                if getattr(part, "thought", False):
                    thinking_chars += len(text)
                else:
                    raw_text += text

        if not raw_text.strip():
            raise RuntimeError(f"[{label}] Empty response from {self._model_id}")

        # Token counting
        usage = getattr(response, "usage_metadata", None)
        input_tokens = getattr(usage, "prompt_token_count", estimated_input_tokens) if usage else estimated_input_tokens
        output_tokens = getattr(usage, "candidates_token_count", len(raw_text) // 4) if usage else len(raw_text) // 4

        logger.info(
            f"[{label}] Gemini sync completed: {input_tokens}+"
            f"{output_tokens} tokens, {duration_ms}ms, "
            f"{len(raw_text):,} chars"
        )

        return LLMCallResult(
            content=raw_text.strip(),
            model_id=self._model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            thinking_tokens=thinking_chars,
            duration_ms=duration_ms,
        )

    def execute_streaming(
        self,
        system_prompt: str,
        user_message: str,
        *,
        max_tokens: int,
        thinking_effort: Optional[str] = None,
        use_extended_context: bool = False,
        label: str = "",
        cancellation_check: Optional[Callable[[], bool]] = None,
    ) -> LLMCallResult:
        """Execute a streaming Gemini call with heartbeat monitoring.

        Accumulates text incrementally for partial salvage on connection errors.
        """
        from google import genai

        client = self._get_client()
        start_time = time.time()

        total_chars = len(system_prompt) + len(user_message)
        estimated_input_tokens = total_chars // 4

        config_kwargs: dict[str, Any] = {
            "system_instruction": system_prompt,
            "max_output_tokens": min(max_tokens, self.max_output_tokens),
        }

        if thinking_effort and thinking_effort in self.EFFORT_TO_BUDGET:
            config_kwargs["thinking_config"] = genai.types.ThinkingConfig(
                thinking_budget=self.EFFORT_TO_BUDGET[thinking_effort],
            )
            config_kwargs["temperature"] = 1.0

        config = genai.types.GenerateContentConfig(**config_kwargs)

        logger.info(
            f"[{label}] Gemini streaming: ~{estimated_input_tokens:,} input tokens, "
            f"max_tokens={max_tokens}, thinking={'yes' if thinking_effort else 'no'}"
        )

        raw_text = ""
        thinking_text = ""
        last_chunk_time = time.time()
        last_heartbeat_log = time.time()
        chunk_count = 0
        connection_error = None
        last_usage = None

        try:
            for chunk in client.models.generate_content_stream(
                model=self._model_id,
                contents=user_message,
                config=config,
            ):
                chunk_count += 1

                # Extract text from chunk parts
                try:
                    if chunk.candidates and chunk.candidates[0].content:
                        for part in chunk.candidates[0].content.parts:
                            text = getattr(part, "text", "") or ""
                            if getattr(part, "thought", False):
                                thinking_text += text
                            else:
                                raw_text += text
                except (IndexError, AttributeError):
                    pass  # Some chunks may be metadata-only

                # Track usage from last chunk
                if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                    last_usage = chunk.usage_metadata

                now = time.time()
                if now - last_chunk_time > HEARTBEAT_TIMEOUT:
                    raise TimeoutError(
                        f"[{label}] No data for {HEARTBEAT_TIMEOUT}s -- stalled"
                    )
                last_chunk_time = now

                if now - last_heartbeat_log > HEARTBEAT_LOG_INTERVAL:
                    elapsed = int(now - start_time)
                    logger.info(
                        f"[{label}] Gemini streaming: {chunk_count} chunks, "
                        f"{elapsed}s, {len(raw_text):,} text, "
                        f"{len(thinking_text):,} thinking"
                    )
                    last_heartbeat_log = now

                if cancellation_check and cancellation_check():
                    raise InterruptedError(f"[{label}] Cancelled during streaming")

        except InterruptedError:
            raise

        except Exception as e:
            if len(raw_text.strip()) >= MIN_SALVAGEABLE_CHARS:
                duration_ms = int((time.time() - start_time) * 1000)
                logger.warning(
                    f"[{label}] Gemini connection lost, salvaging "
                    f"{len(raw_text):,} chars. Error: {e}"
                )
                connection_error = str(e)
            else:
                raise

        duration_ms = int((time.time() - start_time) * 1000)

        if not raw_text.strip():
            raise RuntimeError(f"[{label}] Empty response from {self._model_id}")

        # Token counting from usage metadata
        input_tokens = estimated_input_tokens
        output_tokens = len(raw_text) // 4
        if last_usage:
            input_tokens = getattr(last_usage, "prompt_token_count", input_tokens)
            output_tokens = getattr(last_usage, "candidates_token_count", output_tokens)

        logger.info(
            f"[{label}] Gemini streaming completed: {input_tokens}+{output_tokens} tokens, "
            f"{duration_ms}ms, {len(raw_text):,} chars"
        )

        return LLMCallResult(
            content=raw_text.strip(),
            model_id=self._model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            thinking_tokens=len(thinking_text),
            duration_ms=duration_ms,
            partial=connection_error is not None,
            connection_error=connection_error,
        )
