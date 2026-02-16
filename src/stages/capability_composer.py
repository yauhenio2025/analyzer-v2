"""Capability-based prompt composer for prose-output analysis.

Composes prompts from CapabilityEngineDefinition, producing instructions
that ask the LLM for PROSE output — not JSON. This is the core of the
schema-on-read architecture: rich analytical prose now, structure at
presentation time.

The prompt structure:
1. Engine's problematique (intellectual framing)
2. Selected analytical dimensions with probing questions
3. Depth-specific guidance
4. Shared context from prior engines/passes (plain text)
5. Instruction: write thorough analytical prose
"""

import logging
from typing import Optional

from pydantic import BaseModel, Field

from src.engines.schemas_v2 import CapabilityEngineDefinition

logger = logging.getLogger(__name__)


class CapabilityPrompt(BaseModel):
    """A composed capability-based prompt for prose analysis."""

    engine_key: str
    engine_name: str
    depth: str = "standard"
    prompt: str
    dimension_count: int = 0
    focus_dimensions: list[str] = Field(default_factory=list)
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
            lines.append(f"- Traditions: {', '.join(lineage.traditions)}")
        if lineage.key_concepts:
            lines.append(f"- Key concepts: {', '.join(lineage.key_concepts)}")

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
