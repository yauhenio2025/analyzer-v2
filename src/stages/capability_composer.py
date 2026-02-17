"""Capability-based prompt composer for prose-output analysis.

Composes prompts from CapabilityEngineDefinition, producing instructions
that ask the LLM for PROSE output — not JSON. This is the core of the
schema-on-read architecture: rich analytical prose now, structure at
presentation time.

Two composition modes:
1. compose_capability_prompt() — whole-engine prompt (original, backward-compat)
2. compose_pass_prompt() — per-pass prompt using analytical stances

The prompt structure for per-pass:
1. Engine's problematique (intellectual framing)
2. Analytical stance (cognitive posture for this pass)
3. Pass-specific focus dimensions with depth guidance
4. Shared context from prior passes (plain text)
5. Pass-specific description (what this pass should accomplish)
"""

import logging
from typing import Optional

from pydantic import BaseModel, Field

from src.engines.schemas_v2 import CapabilityEngineDefinition, PassDefinition
from src.operations.registry import StanceRegistry
from src.operationalizations.registry import get_operationalization_registry

logger = logging.getLogger(__name__)

# Module-level stance registry reference
_stance_registry: StanceRegistry | None = None


def init_stance_registry(registry: StanceRegistry) -> None:
    """Set the stance registry for prompt composition."""
    global _stance_registry
    _stance_registry = registry


def _get_stance_registry() -> StanceRegistry:
    """Get or create the stance registry."""
    global _stance_registry
    if _stance_registry is None:
        _stance_registry = StanceRegistry()
    return _stance_registry


class CapabilityPrompt(BaseModel):
    """A composed capability-based prompt for prose analysis."""

    engine_key: str
    engine_name: str
    depth: str = "standard"
    prompt: str
    dimension_count: int = 0
    focus_dimensions: list[str] = Field(default_factory=list)
    has_shared_context: bool = False


class PassPrompt(BaseModel):
    """A composed per-pass prompt using analytical stances."""

    engine_key: str
    engine_name: str
    depth: str
    pass_number: int
    pass_label: str
    stance_key: str
    stance_name: str
    prompt: str
    focus_dimensions: list[str] = Field(default_factory=list)
    consumes_from: list[int] = Field(default_factory=list)
    has_shared_context: bool = False


def compose_capability_prompt(
    cap_def: CapabilityEngineDefinition,
    depth: str = "standard",
    shared_context: Optional[str] = None,
    focus_dimensions: Optional[list[str]] = None,
) -> CapabilityPrompt:
    """Compose a prose-focused prompt from a capability definition.

    Args:
        cap_def: The capability engine definition
        depth: Analysis depth — "surface", "standard", or "deep"
        shared_context: Plain text from prior engines/passes
        focus_dimensions: Subset of dimension keys to explore (None = all)

    Returns:
        CapabilityPrompt with rendered prompt text
    """
    sections: list[str] = []

    # ── 1. Intellectual framing ──────────────────────
    sections.append(_compose_framing(cap_def))

    # ── 2. Analytical dimensions ──────────────────────
    dimensions = cap_def.analytical_dimensions
    if focus_dimensions:
        dimensions = [d for d in dimensions if d.key in focus_dimensions]

    if dimensions:
        sections.append(_compose_dimensions(dimensions, depth))

    # ── 3. Shared context from prior analysis ──────────────────────
    if shared_context:
        sections.append(_compose_shared_context(shared_context))

    # ── 4. Output instructions ──────────────────────
    sections.append(_compose_output_instructions(cap_def, depth))

    prompt = "\n\n".join(sections)

    return CapabilityPrompt(
        engine_key=cap_def.engine_key,
        engine_name=cap_def.engine_name,
        depth=depth,
        prompt=prompt,
        dimension_count=len(dimensions),
        focus_dimensions=[d.key for d in dimensions],
        has_shared_context=shared_context is not None,
    )


def compose_pass_prompt(
    cap_def: CapabilityEngineDefinition,
    pass_def: PassDefinition,
    depth: str = "standard",
    shared_context: Optional[str] = None,
) -> PassPrompt:
    """Compose a per-pass prompt using analytical stances.

    This is the multi-pass composition mode. Each pass gets:
    1. Engine's problematique (framing)
    2. The analytical stance (cognitive posture)
    3. Only the dimensions this pass focuses on
    4. Prior pass output as shared context
    5. The pass-specific description

    Args:
        cap_def: The capability engine definition
        pass_def: The specific pass to compose for
        depth: Analysis depth — determines dimension guidance
        shared_context: Prose output from prior passes

    Returns:
        PassPrompt with rendered prompt text
    """
    sections: list[str] = []
    reg = _get_stance_registry()

    # ── 1. Intellectual framing (same as whole-engine) ──────────
    sections.append(_compose_framing(cap_def))

    # ── 2. Analytical stance ──────────────────────────────────
    stance = reg.get(pass_def.stance)
    if stance:
        sections.append(_compose_stance_section(stance.name, stance.stance, stance.cognitive_mode))
    else:
        logger.warning(f"Stance '{pass_def.stance}' not found in registry")

    # ── 3. Pass-specific dimensions ───────────────────────────
    if pass_def.focus_dimensions:
        dimensions = [
            d for d in cap_def.analytical_dimensions
            if d.key in pass_def.focus_dimensions
        ]
        if dimensions:
            sections.append(_compose_dimensions(dimensions, depth))

    # ── 4. Shared context from prior passes ───────────────────
    if shared_context:
        sections.append(_compose_shared_context(shared_context))

    # ── 5. Pass-specific instructions ─────────────────────────
    sections.append(_compose_pass_instructions(cap_def, pass_def, depth))

    prompt = "\n\n".join(sections)

    return PassPrompt(
        engine_key=cap_def.engine_key,
        engine_name=cap_def.engine_name,
        depth=depth,
        pass_number=pass_def.pass_number,
        pass_label=pass_def.label,
        stance_key=pass_def.stance,
        stance_name=stance.name if stance else pass_def.stance,
        prompt=prompt,
        focus_dimensions=pass_def.focus_dimensions,
        consumes_from=pass_def.consumes_from,
        has_shared_context=shared_context is not None,
    )


def compose_all_pass_prompts(
    cap_def: CapabilityEngineDefinition,
    depth: str = "standard",
    use_operationalizations: bool = True,
) -> list[PassPrompt]:
    """Compose prompts for all passes in a depth level.

    Returns a list of PassPrompts in pass order, WITHOUT shared context
    filled in (that comes at runtime when prior pass output is available).
    This is useful for previewing the full pass structure.

    Checks the operationalization registry first. If an operationalization
    exists for this engine at this depth, builds PassDefinitions from
    the operationalization layer instead of inline engine YAML passes.
    Falls back to inline passes if no operationalization is found.
    """
    # ── Try operationalization layer first ──────────────────────────
    if use_operationalizations:
        pass_defs = _build_pass_defs_from_operationalization(
            cap_def.engine_key, depth
        )
        if pass_defs:
            logger.debug(
                f"Using operationalization layer for {cap_def.engine_key} at {depth}: "
                f"{len(pass_defs)} passes"
            )
            prompts = []
            for pass_def in pass_defs:
                prompt = compose_pass_prompt(
                    cap_def=cap_def,
                    pass_def=pass_def,
                    depth=depth,
                    shared_context=None,
                )
                prompts.append(prompt)
            return prompts

    # ── Fall back to inline passes from engine YAML ────────────────
    depth_level = None
    for dl in cap_def.depth_levels:
        if dl.key == depth:
            depth_level = dl
            break

    if not depth_level or not depth_level.passes:
        logger.info(
            f"No pass definitions for {cap_def.engine_key} at depth={depth}, "
            f"falling back to whole-engine prompt"
        )
        return []

    prompts = []
    for pass_def in sorted(depth_level.passes, key=lambda p: p.pass_number):
        prompt = compose_pass_prompt(
            cap_def=cap_def,
            pass_def=pass_def,
            depth=depth,
            shared_context=None,  # No context in preview mode
        )
        prompts.append(prompt)

    return prompts


def _build_pass_defs_from_operationalization(
    engine_key: str,
    depth: str,
) -> list[PassDefinition] | None:
    """Build PassDefinitions from the operationalization registry.

    Returns None if no operationalization exists for this engine/depth,
    triggering fallback to inline passes.
    """
    op_reg = get_operationalization_registry()
    op = op_reg.get(engine_key)
    if op is None:
        return None

    depth_seq = op.get_depth_sequence(depth)
    if depth_seq is None or not depth_seq.passes:
        return None

    pass_defs = []
    for entry in sorted(depth_seq.passes, key=lambda p: p.pass_number):
        stance_op = op.get_stance_op(entry.stance_key)
        if stance_op is None:
            logger.warning(
                f"Operationalization for {engine_key} references stance "
                f"'{entry.stance_key}' but no operationalization found — skipping pass"
            )
            continue

        pass_defs.append(
            PassDefinition(
                pass_number=entry.pass_number,
                label=stance_op.label,
                stance=entry.stance_key,
                description=stance_op.description,
                focus_dimensions=stance_op.focus_dimensions,
                focus_capabilities=stance_op.focus_capabilities,
                consumes_from=entry.consumes_from,
            )
        )

    return pass_defs if pass_defs else None


def _compose_stance_section(name: str, stance_text: str, cognitive_mode: str) -> str:
    """Compose the analytical stance section."""
    return "\n".join([
        "## Analytical Stance for This Pass",
        "",
        f"**{name}** — _{cognitive_mode}_",
        "",
        stance_text.strip(),
    ])


def _compose_pass_instructions(
    cap_def: CapabilityEngineDefinition,
    pass_def: PassDefinition,
    depth: str,
) -> str:
    """Compose pass-specific output instructions."""
    lines = [
        f"## Pass {pass_def.pass_number}: {pass_def.label}",
        "",
        pass_def.description.strip(),
        "",
        "Write thorough **analytical prose**. Your output will be read by "
        "the next analytical pass, which will build directly on your "
        "observations, reasoning, and tentative connections.",
        "",
    ]

    # If this pass feeds downstream, note it
    if cap_def.composability.shares_with:
        # Only include shares relevant to this pass's dimensions
        relevant_shares = {
            k: v for k, v in cap_def.composability.shares_with.items()
            if not pass_def.focus_dimensions or any(
                dim_key in k for dim_key in pass_def.focus_dimensions
            )
        }
        if relevant_shares:
            lines.extend([
                "**For the next pass**: Ensure your prose clearly surfaces:",
            ])
            for dim_key, desc in relevant_shares.items():
                lines.append(f"- {desc}")
            lines.append("")

    return "\n".join(lines)


def _compose_framing(cap_def: CapabilityEngineDefinition) -> str:
    """Compose the intellectual framing section."""
    lines = [
        f"# {cap_def.engine_name}",
        "",
        "## Analytical Framework",
        "",
        cap_def.problematique.strip(),
    ]

    if cap_def.researcher_question:
        lines.extend([
            "",
            f"**Core Question**: {cap_def.researcher_question}",
        ])

    lineage = cap_def.intellectual_lineage
    if lineage.traditions or lineage.key_concepts:
        lines.extend(["", "**Intellectual Tradition**:"])
        if lineage.traditions:
            trad_names = [t.name if hasattr(t, 'name') else t for t in lineage.traditions]
            lines.append(f"- Traditions: {', '.join(trad_names)}")
        if lineage.key_concepts:
            concept_names = [c.name if hasattr(c, 'name') else c for c in lineage.key_concepts]
            lines.append(f"- Key concepts: {', '.join(concept_names)}")

    return "\n".join(lines)


def _compose_dimensions(
    dimensions: list,
    depth: str,
) -> str:
    """Compose the analytical dimensions section with probing questions."""
    lines = ["## Analytical Dimensions", ""]
    lines.append(f"Analyze the following dimensions at **{depth}** depth:")
    lines.append("")

    for dim in dimensions:
        lines.append(f"### {dim.key.replace('_', ' ').title()}")
        lines.append("")
        lines.append(dim.description.strip())
        lines.append("")

        # Add depth-specific guidance
        guidance = dim.depth_guidance.get(depth)
        if guidance:
            lines.append(f"**Depth guidance ({depth})**: {guidance}")
            lines.append("")

        # Add probing questions
        if dim.probing_questions:
            lines.append("**Probing questions**:")
            for q in dim.probing_questions:
                lines.append(f"- {q}")
            lines.append("")

    return "\n".join(lines)


def _compose_shared_context(shared_context: str) -> str:
    """Compose the shared context section."""
    return "\n".join([
        "## Prior Analysis Context",
        "",
        "The following analysis has already been conducted on this material. "
        "Build on these findings — do not repeat them, but deepen, challenge, "
        "or synthesize where relevant.",
        "",
        "---",
        "",
        shared_context.strip(),
        "",
        "---",
    ])


def _compose_output_instructions(
    cap_def: CapabilityEngineDefinition,
    depth: str,
) -> str:
    """Compose the output format instructions — prose, not JSON."""
    # Get depth level description
    depth_desc = ""
    for dl in cap_def.depth_levels:
        if dl.key == depth:
            depth_desc = dl.description
            break

    lines = [
        "## Output Instructions",
        "",
        "Write thorough **analytical prose** — not bullet points, not JSON, "
        "not tables. Your output will be read by another analyst or LLM who "
        "needs to understand your reasoning, not just your conclusions.",
        "",
        "**Structure your analysis naturally** — use section headings for major "
        "analytical dimensions, but let the material guide the organization. "
        "Some dimensions may deserve deep exploration; others may be brief. "
        "Follow the evidence, not a template.",
        "",
        "**Be specific** — cite textual evidence, name specific works and ideas, "
        "trace specific causal chains. Vague generalizations are useless.",
        "",
    ]

    if depth_desc:
        lines.extend([
            f"**Depth level ({depth})**: {depth_desc}",
            "",
        ])

    # Composability hints
    if cap_def.composability.shares_with:
        lines.extend([
            "**For downstream analysis**: Your output may feed into further analysis. "
            "Ensure you clearly identify:",
        ])
        for dim_key, desc in cap_def.composability.shares_with.items():
            lines.append(f"- {dim_key}: {desc}")
        lines.append("")

    return "\n".join(lines)
