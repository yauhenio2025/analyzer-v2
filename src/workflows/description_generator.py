"""Auto-generate accurate descriptions for chains and workflow phases.

When engine composition changes (engines added/removed from chains), descriptions
must stay accurate. This module provides template-based description generation
that enumerates engines by name and count, preserving a human-written base summary.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.chains.schemas import EngineChainSpec
    from src.engines.registry import EngineRegistry
    from src.workflows.schemas import WorkflowPhase

logger = logging.getLogger(__name__)


def _get_engine_display_name(engine_key: str, engine_registry: "EngineRegistry") -> str:
    """Get human-readable engine name from registry, falling back to key."""
    engine = engine_registry.get(engine_key)
    if engine:
        return engine.engine_name
    # Fallback: convert snake_case to Title Case
    return engine_key.replace("_", " ").title()


def generate_chain_description(
    chain: "EngineChainSpec",
    engine_registry: "EngineRegistry",
) -> str:
    """Generate an accurate chain description from its current engine list.

    Uses the chain's base_description as the invariant summary, then appends
    an accurate engine enumeration.

    Format:
        "{base_description}. Runs {N} engines in sequence:
        (1) {engine_name}; (2) {engine_name}; ... (N) {engine_name}.
        Each engine builds on the previous engine's output."

    Args:
        chain: The chain definition (with potentially updated engine_keys)
        engine_registry: Registry for looking up engine display names

    Returns:
        Complete description string with accurate engine enumeration
    """
    base = chain.base_description
    if not base:
        # No base_description means we can't auto-generate
        # Return existing description unchanged
        return chain.description

    # Build engine enumeration
    engine_parts = []
    for i, key in enumerate(chain.engine_keys, 1):
        name = _get_engine_display_name(key, engine_registry)
        engine_parts.append(f"({i}) {name}")

    engine_enum = "; ".join(engine_parts)
    n = len(chain.engine_keys)

    # Compose the full description
    blend_verb = {
        "sequential": "in sequence",
        "parallel": "in parallel",
        "merge": "with merged output",
        "llm_selection": "via LLM selection",
    }.get(chain.blend_mode.value if hasattr(chain.blend_mode, 'value') else chain.blend_mode, "in sequence")

    description = f"{base}. Runs {n} engines {blend_verb}: {engine_enum}."

    if chain.pass_context and chain.blend_mode.value == "sequential":
        description += " Each engine builds on the previous engine's output."

    return description


def generate_phase_description(
    phase: "WorkflowPhase",
    chain: "EngineChainSpec | None",
    engine_registry: "EngineRegistry",
) -> str:
    """Generate an accurate phase description from its current engine/chain setup.

    Uses the phase's base_phase_description as the invariant summary, then appends
    engine/chain details.

    Args:
        phase: The workflow phase definition
        chain: The chain definition if phase is chain-backed, None otherwise
        engine_registry: Registry for looking up engine display names

    Returns:
        Complete phase description string
    """
    base = phase.base_phase_description
    if not base:
        # No base means we can't auto-generate
        return phase.phase_description

    # Case 1: Chain-backed phase
    if chain is not None:
        engine_parts = []
        for i, key in enumerate(chain.engine_keys, 1):
            name = _get_engine_display_name(key, engine_registry)
            engine_parts.append(f"({i}) {name}")

        engine_enum = "; ".join(engine_parts)
        n = len(chain.engine_keys)

        # Use a comma separator to avoid "through... through" when base already mentions chain
        return (
            f"{base} — {n}-engine chain: {engine_enum}. "
            f"Each engine runs at the workflow's configured depth using its own "
            f"multi-pass stance progression."
        )

    # Case 2: Standalone engine
    if phase.engine_key:
        name = _get_engine_display_name(phase.engine_key, engine_registry)
        return f"{base} using {name}."

    # Case 3: Custom prompt template or no execution target
    return base
