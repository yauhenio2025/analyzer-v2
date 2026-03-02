"""
Design Token Generator - LLM generation with DB + in-memory caching.

Generates complete DesignTokenSet for a style school using:
1. In-memory cache (dict) for zero-latency repeated fetches
2. Database cache (design_token_cache table) for cross-restart persistence
3. LLM generation via Anthropic tool_use for structured output

Uses Sonnet 4.5 for generation (good balance of quality and speed).
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from .registry import get_style_registry
from .schemas import StyleSchool
from .token_schema import DesignTokenSet
from .token_prompt import (
    build_token_generation_prompt,
    get_token_tool_definition,
    STRUCTURAL_INVARIANTS,
)

logger = logging.getLogger(__name__)

# Model for token generation
TOKEN_GENERATION_MODEL = "claude-sonnet-4-5-20250929"
TOKEN_GENERATION_MAX_TOKENS = 16000

# In-memory cache: school_key -> DesignTokenSet
_memory_cache: dict[str, DesignTokenSet] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash_style_json(style_json: dict) -> str:
    """Create a stable SHA-256 hash of the style guide JSON.

    Used as cache invalidation key: if the school definition changes,
    the cached tokens are stale.
    """
    canonical = json.dumps(style_json, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _inject_structural_invariants(token_dict: dict) -> dict:
    """Inject fixed spacing and radius values into the scales tier.

    The LLM may generate these but we override with our canonical values
    to ensure structural consistency across all schools.
    """
    if "scales" in token_dict:
        for key, value in STRUCTURAL_INVARIANTS.items():
            token_dict["scales"][key] = value
    return token_dict


# ---------------------------------------------------------------------------
# Database cache operations
# ---------------------------------------------------------------------------

def _get_cached_from_db(school_key: str, expected_hash: str) -> Optional[dict]:
    """Check the database cache for a valid token set.

    Returns the token_set dict if found and hash matches, else None.
    """
    from ..executor.db import execute, _json_loads

    row = execute(
        "SELECT school_json_hash, token_set FROM design_token_cache WHERE school_key = %s",
        (school_key,),
        fetch="one",
    )
    if row is None:
        logger.debug(f"Token cache miss (no row): {school_key}")
        return None

    if row["school_json_hash"] != expected_hash:
        logger.info(
            f"Token cache stale for {school_key}: "
            f"stored hash {row['school_json_hash'][:12]}... != expected {expected_hash[:12]}..."
        )
        return None

    logger.info(f"Token cache hit: {school_key}")
    token_set = row["token_set"]
    return _json_loads(token_set)


def _save_to_db(
    school_key: str,
    school_json_hash: str,
    token_set: DesignTokenSet,
    model_used: str,
    tokens_used: int,
) -> None:
    """Upsert the token set into the database cache."""
    from ..executor.db import execute, _json_dumps, _is_postgres

    token_json = _json_dumps(token_set.model_dump())
    now = datetime.now(timezone.utc).isoformat()

    if _is_postgres():
        execute(
            """
            INSERT INTO design_token_cache
                (school_key, school_json_hash, token_set, model_used, tokens_used, generated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (school_key) DO UPDATE SET
                school_json_hash = EXCLUDED.school_json_hash,
                token_set = EXCLUDED.token_set,
                model_used = EXCLUDED.model_used,
                tokens_used = EXCLUDED.tokens_used,
                generated_at = EXCLUDED.generated_at
            """,
            (school_key, school_json_hash, token_json, model_used, tokens_used, now),
        )
    else:
        execute(
            """
            INSERT OR REPLACE INTO design_token_cache
                (school_key, school_json_hash, token_set, model_used, tokens_used, generated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (school_key, school_json_hash, token_json, model_used, tokens_used, now),
        )

    logger.info(f"Saved token cache: {school_key} (model={model_used}, tokens={tokens_used})")


# ---------------------------------------------------------------------------
# LLM generation
# ---------------------------------------------------------------------------

def _call_llm_for_tokens(style_guide_json: dict) -> tuple[dict, str, int]:
    """Call the LLM to generate a DesignTokenSet via tool_use.

    Uses Anthropic's tool_use feature to force structured JSON output
    matching the DesignTokenSet schema.

    Returns:
        Tuple of (token_dict, model_used, total_tokens)

    Raises:
        RuntimeError: If the LLM call fails or returns unexpected format
    """
    from ..llm.client import get_anthropic_client

    client = get_anthropic_client()
    if client is None:
        raise RuntimeError(
            "LLM service unavailable. Set ANTHROPIC_API_KEY environment variable."
        )

    prompt = build_token_generation_prompt(style_guide_json)
    tool_def = get_token_tool_definition()

    school_key = style_guide_json.get("key", "unknown")
    logger.info(f"Generating design tokens for {school_key} via {TOKEN_GENERATION_MODEL}...")

    response = client.messages.create(
        model=TOKEN_GENERATION_MODEL,
        max_tokens=TOKEN_GENERATION_MAX_TOKENS,
        tools=[tool_def],
        tool_choice={"type": "tool", "name": "generate_tokens"},
        messages=[{"role": "user", "content": prompt}],
    )

    # Extract the tool_use block from the response
    tool_use_block = None
    for block in response.content:
        if block.type == "tool_use" and block.name == "generate_tokens":
            tool_use_block = block
            break

    if tool_use_block is None:
        raise RuntimeError(
            f"LLM did not return a tool_use block for generate_tokens. "
            f"Response content types: {[b.type for b in response.content]}"
        )

    token_dict = tool_use_block.input
    total_tokens = response.usage.input_tokens + response.usage.output_tokens

    logger.info(
        f"Token generation complete for {school_key}: "
        f"{response.usage.input_tokens} input + {response.usage.output_tokens} output = {total_tokens} total tokens"
    )

    return token_dict, TOKEN_GENERATION_MODEL, total_tokens


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_design_tokens(school_key: str) -> DesignTokenSet:
    """Get or generate a complete design token set for a style school.

    Resolution order:
    1. In-memory cache (zero latency)
    2. Database cache (fast, cross-restart)
    3. LLM generation (slow, ~10-20s)

    Args:
        school_key: The style school key (e.g., "minimalist_precision")

    Returns:
        Complete DesignTokenSet

    Raises:
        ValueError: If school_key is not found
        RuntimeError: If LLM generation fails
    """
    # 1. Check in-memory cache
    if school_key in _memory_cache:
        logger.debug(f"Token memory cache hit: {school_key}")
        return _memory_cache[school_key]

    # 2. Load school definition
    registry = get_style_registry()
    try:
        school_enum = StyleSchool(school_key)
    except ValueError:
        raise ValueError(f"Unknown style school: {school_key}")

    style = registry.get_style(school_enum)
    if style is None:
        raise ValueError(f"Style definition not found for: {school_key}")

    style_json = style.model_dump()
    style_hash = _hash_style_json(style_json)

    # 3. Check database cache
    cached_dict = _get_cached_from_db(school_key, style_hash)
    if cached_dict is not None:
        try:
            tokens = DesignTokenSet(**cached_dict)
            _memory_cache[school_key] = tokens
            return tokens
        except Exception as e:
            logger.warning(f"Cached token set failed validation for {school_key}: {e}")
            # Fall through to regeneration

    # 4. Generate via LLM
    token_dict, model_used, total_tokens = _call_llm_for_tokens(style_json)

    # 5. Inject structural invariants
    token_dict = _inject_structural_invariants(token_dict)

    # 6. Validate with Pydantic
    tokens = DesignTokenSet(**token_dict)

    # 7. Cache to DB
    _save_to_db(school_key, style_hash, tokens, model_used, total_tokens)

    # 8. Cache in memory
    _memory_cache[school_key] = tokens

    logger.info(f"Design tokens generated and cached for {school_key}")
    return tokens


async def get_cached_tokens(school_key: str) -> Optional[DesignTokenSet]:
    """Get cached tokens without triggering generation.

    Checks in-memory cache first, then database cache.
    Returns None if no cached tokens exist (does NOT call LLM).
    """
    # Check memory
    if school_key in _memory_cache:
        return _memory_cache[school_key]

    # Check DB (need the hash, so load the style)
    registry = get_style_registry()
    try:
        school_enum = StyleSchool(school_key)
    except ValueError:
        return None

    style = registry.get_style(school_enum)
    if style is None:
        return None

    style_json = style.model_dump()
    style_hash = _hash_style_json(style_json)

    cached_dict = _get_cached_from_db(school_key, style_hash)
    if cached_dict is not None:
        try:
            tokens = DesignTokenSet(**cached_dict)
            _memory_cache[school_key] = tokens
            return tokens
        except Exception:
            return None

    return None


async def clear_token_cache(school_key: str) -> None:
    """Clear the token cache for a school (both in-memory and DB).

    Used before regeneration to force a fresh LLM call.
    """
    from ..executor.db import execute

    # Clear memory cache
    _memory_cache.pop(school_key, None)

    # Clear DB cache
    execute(
        "DELETE FROM design_token_cache WHERE school_key = %s",
        (school_key,),
    )

    logger.info(f"Token cache cleared: {school_key}")


def tokens_to_css(tokens: DesignTokenSet) -> str:
    """Convert a DesignTokenSet to CSS custom properties.

    Generates a complete CSS string with all tokens as --token-name: value
    custom properties, wrapped in a :root selector.

    Args:
        tokens: The complete token set

    Returns:
        CSS string with custom properties
    """
    lines = [
        f"/* Design Tokens: {tokens.school_name} */",
        f"/* Generated: {tokens.generated_at} | Version: {tokens.version} */",
        "",
        ":root {",
    ]

    def _emit_flat(prefix: str, obj: dict) -> None:
        """Recursively emit CSS custom properties from a dict."""
        for key, value in obj.items():
            if isinstance(value, dict):
                _emit_flat(f"{prefix}-{key}", value)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        _emit_flat(f"{prefix}-{key}-{i}", item)
                    else:
                        lines.append(f"  --{prefix}-{key}-{i}: {item};")
            else:
                css_key = f"{prefix}-{key}".replace("_", "-")
                lines.append(f"  --{css_key}: {value};")

    # Emit each tier
    token_dict = tokens.model_dump()
    for tier_name in ["primitives", "surfaces", "scales", "semantic", "categorical", "components"]:
        tier_data = token_dict.get(tier_name, {})
        lines.append(f"")
        lines.append(f"  /* --- {tier_name.upper()} --- */")
        _emit_flat(tier_name, tier_data)

    lines.append("}")
    lines.append("")

    return "\n".join(lines)
