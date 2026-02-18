"""Transformation executor — applies transformation specs to data.

Handles all 5 transformation types:
- none: passthrough
- schema_map: rename fields via mapping
- llm_extract: Claude Haiku structured extraction from prose
- llm_summarize: Claude Haiku summarization
- aggregate: group-by, count, sort operations

Uses in-memory TTL cache to avoid redundant LLM calls.
"""

import hashlib
import json
import logging
import time
from typing import Any, Optional

from pydantic import BaseModel, Field

from src.llm.client import call_extraction_model, parse_llm_json_response
from src.transformations.schemas import AggregateConfig

logger = logging.getLogger(__name__)

# Cache TTL: 1 hour
DEFAULT_CACHE_TTL = 3600


class TransformationResult(BaseModel):
    """Result of a transformation execution."""

    success: bool
    data: Any = None
    error: Optional[str] = None
    transformation_type: str
    model_used: Optional[str] = None
    token_count: Optional[int] = None
    cached: bool = False
    execution_time_ms: int = 0


class _CacheEntry:
    """In-memory cache entry with TTL."""

    __slots__ = ("data", "created_at", "ttl")

    def __init__(self, data: Any, ttl: int = DEFAULT_CACHE_TTL):
        self.data = data
        self.created_at = time.time()
        self.ttl = ttl

    @property
    def expired(self) -> bool:
        return time.time() - self.created_at > self.ttl


class TransformationExecutor:
    """Executes transformations against data.

    Stateless except for an optional in-memory TTL cache.
    The executor resolves stance_key via the StanceRegistry if needed.
    """

    def __init__(self):
        self._cache: dict[str, _CacheEntry] = {}

    async def execute(
        self,
        data: Any,
        transformation_type: str,
        field_mapping: Optional[dict[str, str]] = None,
        llm_extraction_schema: Optional[dict[str, Any]] = None,
        llm_prompt_template: Optional[str] = None,
        stance_key: Optional[str] = None,
        aggregate_config: Optional[AggregateConfig] = None,
        model: str = "claude-haiku-4-5-20251001",
        model_fallback: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 8000,
        cache_key: Optional[str] = None,
    ) -> TransformationResult:
        """Execute a transformation on data.

        Args:
            data: The raw data to transform
            transformation_type: One of none/schema_map/llm_extract/llm_summarize/aggregate
            field_mapping: For schema_map type
            llm_extraction_schema: For llm_extract type
            llm_prompt_template: System prompt for LLM types
            stance_key: Optional stance for LLM context
            aggregate_config: For aggregate type
            model: Primary LLM model
            model_fallback: Fallback LLM model
            max_tokens: Max tokens for LLM response
            cache_key: Optional cache key; if set, results are cached

        Returns:
            TransformationResult with success/error and transformed data
        """
        start_time = time.time()

        # Check cache
        effective_cache_key = cache_key or self._compute_cache_key(
            data, transformation_type, field_mapping, llm_prompt_template
        )
        cached = self._get_cached(effective_cache_key)
        if cached is not None:
            elapsed = int((time.time() - start_time) * 1000)
            return TransformationResult(
                success=True,
                data=cached,
                transformation_type=transformation_type,
                cached=True,
                execution_time_ms=elapsed,
            )

        try:
            if transformation_type == "none":
                result_data = self._execute_none(data)
                model_used = None
                token_count = None

            elif transformation_type == "schema_map":
                if not field_mapping:
                    return TransformationResult(
                        success=False,
                        error="schema_map requires field_mapping",
                        transformation_type=transformation_type,
                    )
                result_data = self._execute_schema_map(data, field_mapping)
                model_used = None
                token_count = None

            elif transformation_type == "llm_extract":
                if not llm_prompt_template:
                    return TransformationResult(
                        success=False,
                        error="llm_extract requires llm_prompt_template",
                        transformation_type=transformation_type,
                    )
                result_data, model_used, token_count = await self._execute_llm_extract(
                    data=data,
                    schema=llm_extraction_schema,
                    prompt_template=llm_prompt_template,
                    stance_key=stance_key,
                    model=model,
                    model_fallback=model_fallback,
                    max_tokens=max_tokens,
                )

            elif transformation_type == "llm_summarize":
                if not llm_prompt_template:
                    return TransformationResult(
                        success=False,
                        error="llm_summarize requires llm_prompt_template",
                        transformation_type=transformation_type,
                    )
                result_data, model_used, token_count = await self._execute_llm_summarize(
                    data=data,
                    prompt_template=llm_prompt_template,
                    stance_key=stance_key,
                    model=model,
                    model_fallback=model_fallback,
                    max_tokens=max_tokens,
                )

            elif transformation_type == "aggregate":
                config = aggregate_config or AggregateConfig()
                result_data = self._execute_aggregate(data, config)
                model_used = None
                token_count = None

            else:
                return TransformationResult(
                    success=False,
                    error=f"Unknown transformation type: {transformation_type}",
                    transformation_type=transformation_type,
                )

            # Cache result
            self._set_cached(effective_cache_key, result_data)

            elapsed = int((time.time() - start_time) * 1000)
            return TransformationResult(
                success=True,
                data=result_data,
                transformation_type=transformation_type,
                model_used=model_used,
                token_count=token_count,
                cached=False,
                execution_time_ms=elapsed,
            )

        except Exception as e:
            elapsed = int((time.time() - start_time) * 1000)
            logger.error(
                f"Transformation execution failed ({transformation_type}): {e}"
            )
            return TransformationResult(
                success=False,
                error=str(e),
                transformation_type=transformation_type,
                execution_time_ms=elapsed,
            )

    # ── Type implementations ──────────────────────────────

    def _execute_none(self, data: Any) -> Any:
        """Passthrough — return data unchanged."""
        return data

    def _execute_schema_map(
        self, data: Any, field_mapping: dict[str, str]
    ) -> Any:
        """Apply field_mapping: rename keys in data.

        Works on dicts (rename keys) and lists of dicts (rename keys in each).
        """
        if isinstance(data, dict):
            return self._map_dict(data, field_mapping)
        elif isinstance(data, list):
            return [
                self._map_dict(item, field_mapping) if isinstance(item, dict) else item
                for item in data
            ]
        return data

    def _map_dict(self, d: dict, mapping: dict[str, str]) -> dict:
        """Rename keys in a dict according to mapping."""
        result = {}
        for key, value in d.items():
            new_key = mapping.get(key, key)
            result[new_key] = value
        return result

    async def _execute_llm_extract(
        self,
        data: Any,
        schema: Optional[dict[str, Any]],
        prompt_template: str,
        stance_key: Optional[str],
        model: str,
        model_fallback: str,
        max_tokens: int,
    ) -> tuple[Any, str, int]:
        """Extract structured data from prose using Claude.

        The prompt_template is used as the system prompt.
        The data is serialized and sent as the user message.
        """
        # Build user message with data
        data_str = self._serialize_data(data)
        stance_text = self._resolve_stance(stance_key) if stance_key else ""

        user_message = (
            f"Extract structured data from the following analytical output. "
            f"Return ONLY valid JSON.\n\n"
        )
        if stance_text:
            user_message += f"Presentation stance: {stance_text}\n\n"
        user_message += f"---\n\n{data_str}"

        raw_text, model_used, token_count = call_extraction_model(
            prompt=user_message,
            system_prompt=prompt_template,
            model=model,
            fallback_model=model_fallback,
            max_tokens=max_tokens,
        )

        result = parse_llm_json_response(raw_text)
        return result, model_used, token_count

    async def _execute_llm_summarize(
        self,
        data: Any,
        prompt_template: str,
        stance_key: Optional[str],
        model: str,
        model_fallback: str,
        max_tokens: int,
    ) -> tuple[Any, str, int]:
        """Summarize data using Claude.

        Similar to llm_extract but returns the raw text as a summary
        rather than structured JSON.
        """
        data_str = self._serialize_data(data)
        stance_text = self._resolve_stance(stance_key) if stance_key else ""

        user_message = "Summarize the following analytical output.\n\n"
        if stance_text:
            user_message += f"Presentation stance: {stance_text}\n\n"
        user_message += f"---\n\n{data_str}"

        raw_text, model_used, token_count = call_extraction_model(
            prompt=user_message,
            system_prompt=prompt_template,
            model=model,
            fallback_model=model_fallback,
            max_tokens=max_tokens,
        )

        # Try to parse as JSON; if it fails, return as text
        try:
            result = parse_llm_json_response(raw_text)
        except (json.JSONDecodeError, Exception):
            result = {"summary": raw_text.strip()}

        return result, model_used, token_count

    def _execute_aggregate(self, data: Any, config: AggregateConfig) -> Any:
        """Apply aggregation operations to data.

        Works on lists of dicts. Supports group_by, count, sum, sort, limit.
        """
        if not isinstance(data, list):
            return data

        items = data

        # Group by field
        if config.group_by:
            groups: dict[str, list] = {}
            for item in items:
                if isinstance(item, dict):
                    key = str(item.get(config.group_by, "unknown"))
                    groups.setdefault(key, []).append(item)
                else:
                    groups.setdefault("unknown", []).append(item)

            result_items = []
            for group_key, group_items in groups.items():
                entry: dict[str, Any] = {
                    config.group_by: group_key,
                    "count": len(group_items),
                    "items": group_items,
                }
                # Sum fields
                for sf in config.sum_fields:
                    entry[f"{sf}_sum"] = sum(
                        item.get(sf, 0)
                        for item in group_items
                        if isinstance(item, dict)
                    )
                result_items.append(entry)

            items = result_items

        # Count field (without grouping)
        elif config.count_field:
            counts: dict[str, int] = {}
            for item in items:
                if isinstance(item, dict):
                    val = str(item.get(config.count_field, "unknown"))
                    counts[val] = counts.get(val, 0) + 1
            items = [
                {config.count_field: k, "count": v}
                for k, v in counts.items()
            ]

        # Sort
        if config.sort_by and isinstance(items, list) and items:
            reverse = config.sort_order == "desc"
            try:
                items = sorted(
                    items,
                    key=lambda x: x.get(config.sort_by, 0) if isinstance(x, dict) else 0,
                    reverse=reverse,
                )
            except (TypeError, AttributeError):
                pass

        # Limit
        if config.limit and isinstance(items, list):
            items = items[: config.limit]

        return items

    # ── Helpers ────────────────────────────────────────────

    def _serialize_data(self, data: Any) -> str:
        """Serialize data to string for LLM input."""
        if isinstance(data, str):
            return data
        try:
            return json.dumps(data, indent=2, default=str)
        except (TypeError, ValueError):
            return str(data)

    def _resolve_stance(self, stance_key: str) -> str:
        """Resolve a stance_key to its prose description."""
        try:
            from src.operations.registry import StanceRegistry

            reg = StanceRegistry()
            stance = reg.get(stance_key)
            if stance:
                return stance.stance
        except Exception as e:
            logger.warning(f"Failed to resolve stance '{stance_key}': {e}")
        return f"[Stance: {stance_key}]"

    def _compute_cache_key(
        self,
        data: Any,
        transformation_type: str,
        field_mapping: Optional[dict] = None,
        prompt_template: Optional[str] = None,
    ) -> str:
        """Compute a cache key from input parameters."""
        data_str = self._serialize_data(data)
        key_parts = f"{transformation_type}:{data_str[:2000]}:{field_mapping}:{prompt_template[:200] if prompt_template else ''}"
        return hashlib.md5(key_parts.encode()).hexdigest()

    def _get_cached(self, cache_key: str) -> Optional[Any]:
        """Get cached result if not expired."""
        entry = self._cache.get(cache_key)
        if entry and not entry.expired:
            return entry.data
        if entry:
            del self._cache[cache_key]
        return None

    def _set_cached(self, cache_key: str, data: Any) -> None:
        """Cache a result."""
        # Evict expired entries periodically (every 100 writes)
        if len(self._cache) > 100:
            expired_keys = [
                k for k, v in self._cache.items() if v.expired
            ]
            for k in expired_keys:
                del self._cache[k]

        self._cache[cache_key] = _CacheEntry(data)


# Global executor instance
_executor: Optional[TransformationExecutor] = None


def get_transformation_executor() -> TransformationExecutor:
    """Get the global transformation executor instance."""
    global _executor
    if _executor is None:
        _executor = TransformationExecutor()
    return _executor
