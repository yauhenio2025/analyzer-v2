"""Cross-phase context assembly for the executor.

The context broker reads prose outputs from prior phases and assembles
them into a markdown document that the next LLM call reads as context.

Key design: context_emphasis from the plan is injected as a framing
paragraph before the assembled context. This is how the orchestrator's
intellectual strategy gets threaded through the execution.

Ported from The Critic's context_broker.py with emphasis injection added.
"""

import logging
from typing import Optional

from src.executor.output_store import load_outputs_for_context

logger = logging.getLogger(__name__)

# Truncate individual context blocks beyond this to stay within limits
MAX_CHARS_PER_BLOCK = 50_000


def assemble_phase_context(
    job_id: str,
    upstream_phases: list[float],
    context_emphasis: Optional[str] = None,
    max_chars_per_block: int = MAX_CHARS_PER_BLOCK,
    phase_max_chars_override: Optional[dict[float, int]] = None,
) -> str:
    """Assemble prose context from upstream phases for the next phase.

    Args:
        job_id: The job whose outputs to read
        upstream_phases: Which phase numbers to include
        context_emphasis: Plan-driven emphasis text to inject as framing
        max_chars_per_block: Default truncation for individual blocks
        phase_max_chars_override: Per-phase override for max chars.
            Keys are phase_numbers, values are char limits.
            Allows Phase 1.0's rich analysis to pass through at higher limits
            when it has supplementary engines (Milestone 5).

    Returns:
        Markdown-formatted context string ready to inject into a prompt.
        Empty string if no outputs found.
    """
    if not upstream_phases:
        return ""

    outputs = load_outputs_for_context(job_id, phase_numbers=upstream_phases)

    if not outputs:
        logger.warning(
            f"No outputs found for context assembly: job={job_id}, "
            f"phases={upstream_phases}"
        )
        return ""

    # Build labeled context blocks
    blocks = []
    for output in outputs:
        # Use phase-specific char cap if available (Milestone 5)
        phase_num = output.get("phase_number", 0)
        effective_max = max_chars_per_block
        if phase_max_chars_override and phase_num in phase_max_chars_override:
            effective_max = phase_max_chars_override[phase_num]

        block = _format_output_block(output, effective_max)
        if block:
            blocks.append(block)

    if not blocks:
        return ""

    # Assemble the full context document
    parts = []

    # Header
    parts.append(
        "# Prior Analysis Context\n\n"
        "The following analyses have already been conducted on this material. "
        "Build on these findings — deepen, challenge, or synthesize where relevant. "
        "Do not repeat what has been established.\n"
    )

    # Inject context emphasis if present (this is the orchestrator's strategy)
    if context_emphasis:
        parts.append(
            f"## Analytical Emphasis for This Phase\n\n"
            f"**{context_emphasis}**\n"
        )

    # Context blocks
    parts.append("\n---\n\n".join(blocks))

    context = "\n\n".join(parts)

    logger.info(
        f"Assembled context for job={job_id}: "
        f"{len(blocks)} blocks from phases {upstream_phases}, "
        f"{len(context):,} chars total"
        + (f", emphasis injected" if context_emphasis else "")
    )

    return context


def assemble_inner_pass_context(
    prior_pass_outputs: dict[int, str],
    consumes_from: list[int],
    pass_stances: Optional[dict[int, str]] = None,
) -> str:
    """Assemble context from prior inner passes within an engine.

    This handles the within-engine multi-pass context: each pass can
    consume output from specific prior passes (defined by the
    operationalization's consumes_from field).

    Args:
        prior_pass_outputs: pass_number -> prose output
        consumes_from: Which pass numbers to include
        pass_stances: Optional pass_number -> stance_key for labeling

    Returns:
        Markdown context from consumed passes.
    """
    if not consumes_from:
        return ""

    blocks = []
    for pass_num in sorted(consumes_from):
        if pass_num not in prior_pass_outputs:
            continue

        content = prior_pass_outputs[pass_num]
        stance_label = ""
        if pass_stances and pass_num in pass_stances:
            stance_label = f" ({pass_stances[pass_num]})"

        block = (
            f"## Output from Pass {pass_num}{stance_label}\n\n"
            f"{content}"
        )
        blocks.append(block)

    if not blocks:
        return ""

    return (
        "## Shared Context from Prior Passes\n\n"
        + "\n\n---\n\n".join(blocks)
    )


def assemble_chain_context(
    previous_engine_output: Optional[str],
    engine_label: str = "prior engine",
) -> str:
    """Assemble context from the previous engine in a chain.

    In sequential chains, each engine receives the output of the
    previous engine as context.
    """
    if not previous_engine_output:
        return ""

    return (
        f"## Previous Analysis (from {engine_label})\n\n"
        f"{previous_engine_output}"
    )


def _format_output_block(output: dict, max_chars: int) -> str:
    """Format a single output record as a labeled markdown block."""
    phase_num = output.get("phase_number", "?")
    engine_key = output.get("engine_key", "unknown")
    work_key = output.get("work_key", "")
    stance_key = output.get("stance_key", "")
    role = output.get("role", "")
    content = output.get("content", "")

    if not content.strip():
        return ""

    # Build header
    header_parts = [f"Phase {phase_num}", engine_key]
    if work_key:
        header_parts.append(f"Work: {work_key}")
    if stance_key:
        header_parts.append(f"Stance: {stance_key}")
    if role:
        header_parts.append(f"Role: {role}")

    header = " | ".join(header_parts)

    # Truncate if needed
    if len(content) > max_chars:
        content = content[:max_chars] + "\n\n[... truncated for context length ...]"

    return f"### {header}\n\n{content}"
