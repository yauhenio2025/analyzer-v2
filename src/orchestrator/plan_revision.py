"""Plan revision — pre-execution and mid-course adaptive replanning.

Two revision points:
1. Pre-execution: After plan generation, before execution starts. An LLM reviews
   the plan and checks whether profiling phases produce what synthesis phases need.
2. Mid-course: After Phases 1.0 and 1.5 complete, before Phase 2.0 starts. The LLM
   reviews actual profiling output and adjusts remaining phases.

Both revisions use Opus with high thinking effort for meta-reasoning about plan quality.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PlanRevisionEntry(BaseModel):
    """Record of a single plan revision."""

    revision_number: int
    revision_type: str = Field(
        ...,
        description="Type of revision: 'pre_execution' or 'mid_course'",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    changes_summary: str = Field(
        default="",
        description="Human-readable summary of changes made",
    )
    phases_added: list[float] = Field(default_factory=list)
    phases_modified: list[float] = Field(default_factory=list)
    revision_rationale: str = Field(
        default="",
        description="Why the revision was needed",
    )
    model_used: str = Field(default="")


# ──────────────────────────────────────────────────────────
# Pre-Execution Plan Revision
# ──────────────────────────────────────────────────────────

_PRE_EXECUTION_SYSTEM = """You are a plan reviewer for an intellectual genealogy analysis system.
You are reviewing an analysis plan BEFORE execution begins.

Your task: Read the plan's phases and evaluate whether the profiling/foundational phases
(0.5, 1.0, 1.5) will produce sufficient input for the analysis/synthesis phases (2.0, 3.0, 4.0).

Return a JSON object with this structure:
{
  "revision_needed": true/false,
  "revision_rationale": "Why changes are needed (or 'Plan is adequate')",
  "changes_summary": "Brief summary of all changes",
  "phases_added": [list of new phase numbers],
  "phases_modified": [list of modified phase numbers],
  "revised_phases": [
    ... complete list of ALL phases (existing + new/modified) in the revised plan ...
    Each phase must include: phase_number, phase_name, chain_key or engine_key,
    depth, model_hint, iteration_mode, depends_on, requires_full_documents,
    rationale, estimated_tokens, estimated_cost_usd,
    and optionally: chapter_targets, document_scope, supplementary_chains,
    max_context_chars_override, per_work_chain_map, per_work_overrides
  ]
}

If no revision is needed, set revision_needed=false and return the original phases unchanged."""

_PRE_EXECUTION_PROMPT = """# Plan Review: Pre-Execution Self-Critique

## Current Plan
{plan_json}

## Book Samples (what we know about the corpus)
{book_samples_json}

## Analysis Objective
{objective_text}

## Engine Catalog Summary
{catalog_summary}

## SPECIFIC CHECKS (evaluate each):

1. **CHAPTER GRANULARITY**: Does any downstream engine (concept_semantic_constellation,
   inferential_commitment_mapper, concept_evolution) need to trace concepts to specific
   chapters? If so, does Phase 0.5 include chapter_role_analyzer at sufficient depth?

2. **NARRATIVE FOUNDATION**: Does any downstream engine analyze argument strategy, rhetorical
   moves, or framing? If so, is narrative_structure_analyzer included upstream?

3. **VOCABULARY COMPLETENESS**: Does deep_summarization's conceptual_vocabulary dimension
   provide sufficient vocabulary mapping for downstream concept_evolution and
   concept_appropriation_tracker? If not, should we deepen from standard to deep?

4. **BACKGROUND WORK PROFILING**: Are any prior works book-length (>50K chars)? If so, are
   they getting prior_work_profiling before scanning? Check per_work_chain_map.

5. **CHAPTER DEEP DIVES**: Does the chapter_structure in book samples reveal any chapters
   that are disproportionately large or whose titles suggest concentrated conceptual
   content? If so, add chapter_targets for those chapters.

6. **MODEL ROUTING**: Are summarization phases using sonnet/gemini (not opus)?
   Are synthesis/revision phases using opus?

7. **DEEP TEXT PROFILING**: For target works >20K words, is Phase 0.5 (deep_text_profiling)
   present? If not, it MUST be added — this is required for book-length works.

Review the plan and return the JSON response."""


def revise_plan_pre_execution(
    plan_dict: dict,
    book_samples: list[dict],
    objective_text: str,
    catalog_summary: str = "",
) -> Optional[dict]:
    """Review and optionally revise a plan before execution begins.

    Args:
        plan_dict: The current plan as a dict (serialized WorkflowExecutionPlan)
        book_samples: Serialized BookSamples
        objective_text: The objective's planner_strategy text
        catalog_summary: Optional abbreviated catalog text

    Returns:
        A PlanRevisionEntry dict + revised phases if revision was needed, else None.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("No ANTHROPIC_API_KEY — skipping pre-execution plan revision")
        return None

    # Build prompt
    plan_json = json.dumps(
        {"phases": plan_dict.get("phases", [])},
        indent=2,
        default=str,
    )
    book_samples_json = json.dumps(book_samples, indent=2, default=str)

    prompt = _PRE_EXECUTION_PROMPT.format(
        plan_json=plan_json,
        book_samples_json=book_samples_json,
        objective_text=objective_text,
        catalog_summary=catalog_summary[:10000] if catalog_summary else "(not provided)",
    )

    try:
        import httpx
        from anthropic import Anthropic

        client = Anthropic(
            timeout=httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0),
        )

        logger.info("Running pre-execution plan revision (Opus, adaptive thinking)...")

        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=16000,
            thinking={
                "type": "enabled",
                "budget_tokens": 10000,
            },
            system=_PRE_EXECUTION_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract text response
        raw_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                raw_text = block.text
                break

        # Parse JSON
        content = raw_text.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]

        result = json.loads(content.strip())

        if not result.get("revision_needed", False):
            logger.info("Pre-execution revision: no changes needed")
            return None

        revision = PlanRevisionEntry(
            revision_number=1,
            revision_type="pre_execution",
            changes_summary=result.get("changes_summary", ""),
            phases_added=result.get("phases_added", []),
            phases_modified=result.get("phases_modified", []),
            revision_rationale=result.get("revision_rationale", ""),
            model_used="claude-opus-4-6",
        )

        logger.info(
            f"Pre-execution revision: {revision.changes_summary}\n"
            f"  Phases added: {revision.phases_added}\n"
            f"  Phases modified: {revision.phases_modified}"
        )

        return {
            "revision": revision.model_dump(),
            "revised_phases": result.get("revised_phases", []),
        }

    except Exception as e:
        logger.error(f"Pre-execution plan revision failed (non-fatal): {e}", exc_info=True)
        return None


# ──────────────────────────────────────────────────────────
# Mid-Course Plan Revision
# ──────────────────────────────────────────────────────────

_MID_COURSE_SYSTEM = """You are a plan reviewer for an intellectual genealogy analysis system.
You are reviewing a plan MID-EXECUTION after target profiling phases have completed.

You have the actual output from completed phases. Based on what was LEARNED,
assess whether remaining phases need adjustment.

IMPORTANT: You CANNOT change phases that have already completed. You can only
modify or add phases that haven't started yet.

Return a JSON object with the same structure as pre-execution revision:
{
  "revision_needed": true/false,
  "revision_rationale": "...",
  "changes_summary": "...",
  "phases_added": [...],
  "phases_modified": [...],
  "revised_phases": [... ALL remaining phases (not yet executed) ...]
}

If no revision is needed, set revision_needed=false."""

_MID_COURSE_PROMPT = """# Plan Review: Mid-Course Correction

## Current Plan (full)
{plan_json}

## Completed Phase Outputs

### Phase 1.0 Output (Target Profiling)
{phase_1_output}

### Phase 1.5 Output (Relationship Classification)
{phase_1_5_output}

## Remaining Phases (these can be modified)
{remaining_phases_json}

## Book Samples
{book_samples_json}

## SPECIFIC REASSESSMENTS (evaluate each):

1. **CHAPTER IMPORTANCE**: Phase 1.0 profiling may have revealed specific chapters as
   conceptually crucial. Check: did the profiling mention specific chapters or sections
   as containing key concepts? If so, add Phase 1.7/1.8 for chapter-level deep dives.

2. **REASONING PATTERNS**: Did the profiling reveal reasoning modes not covered by the
   current plan? E.g., if the target uses game theory, check if
   specialized_reasoning_classifier is in the plan. If it uses extensive historical
   narrative, check if temporal engines are included.

3. **PER-WORK RELEVANCE**: Phase 1.5 classified prior works. Are any "direct_precursor"
   works NOT getting deep scanning? Are any "tangential" works still getting deep scanning?
   Upgrade/downgrade as needed.

4. **PRIOR WORK COMPLEXITY**: For direct_precursor works that are book-length, did we assign
   prior_work_profiling chain? If not, add it now — these works need deep summaries before
   scanning can be productive.

5. **MISSING DIMENSIONS**: Does the Phase 1.0 output suggest analytical dimensions that the
   current plan doesn't cover? E.g., if the target work's profiling reveals heavy reliance
   on metaphor, ensure metaphor-related engines are in Phase 3.0.

Review and return the JSON response."""


def revise_plan_mid_course(
    plan_dict: dict,
    phase_outputs: dict[float, str],
    book_samples: list[dict],
    completed_phases: set[float],
) -> Optional[dict]:
    """Review and optionally revise a plan mid-course after profiling completes.

    Called after Phases 1.0 and 1.5 complete, before Phase 2.0 starts.

    Args:
        plan_dict: The current plan as a dict
        phase_outputs: Map of phase_number -> prose output for completed phases
        book_samples: Serialized BookSamples
        completed_phases: Set of phase numbers that have already completed

    Returns:
        A PlanRevisionEntry dict + revised remaining phases if revision was needed, else None.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("No ANTHROPIC_API_KEY — skipping mid-course plan revision")
        return None

    # Separate completed from remaining phases
    all_phases = plan_dict.get("phases", [])
    remaining_phases = [
        p for p in all_phases
        if p.get("phase_number", 0) not in completed_phases
    ]

    # Truncate phase outputs to avoid exceeding context
    phase_1_output = phase_outputs.get(1.0, "(not available)")
    if len(phase_1_output) > 50000:
        phase_1_output = phase_1_output[:50000] + "\n\n[... truncated ...]"

    phase_1_5_output = phase_outputs.get(1.5, "(not available)")
    if len(phase_1_5_output) > 30000:
        phase_1_5_output = phase_1_5_output[:30000] + "\n\n[... truncated ...]"

    prompt = _MID_COURSE_PROMPT.format(
        plan_json=json.dumps({"phases": all_phases}, indent=2, default=str),
        phase_1_output=phase_1_output,
        phase_1_5_output=phase_1_5_output,
        remaining_phases_json=json.dumps(remaining_phases, indent=2, default=str),
        book_samples_json=json.dumps(book_samples, indent=2, default=str),
    )

    try:
        import httpx
        from anthropic import Anthropic

        client = Anthropic(
            timeout=httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0),
        )

        logger.info("Running mid-course plan revision (Opus, adaptive thinking)...")

        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=16000,
            thinking={
                "type": "enabled",
                "budget_tokens": 10000,
            },
            system=_MID_COURSE_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                raw_text = block.text
                break

        content = raw_text.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]

        result = json.loads(content.strip())

        if not result.get("revision_needed", False):
            logger.info("Mid-course revision: no changes needed")
            return None

        # Determine revision number based on existing history
        existing_revisions = plan_dict.get("revision_history", [])
        revision_number = len(existing_revisions) + 1

        revision = PlanRevisionEntry(
            revision_number=revision_number,
            revision_type="mid_course",
            changes_summary=result.get("changes_summary", ""),
            phases_added=result.get("phases_added", []),
            phases_modified=result.get("phases_modified", []),
            revision_rationale=result.get("revision_rationale", ""),
            model_used="claude-opus-4-6",
        )

        logger.info(
            f"Mid-course revision: {revision.changes_summary}\n"
            f"  Phases added: {revision.phases_added}\n"
            f"  Phases modified: {revision.phases_modified}"
        )

        return {
            "revision": revision.model_dump(),
            "revised_phases": result.get("revised_phases", []),
        }

    except Exception as e:
        logger.error(f"Mid-course plan revision failed (non-fatal): {e}", exc_info=True)
        return None


def should_trigger_mid_course_revision(
    completed_phases: set[float],
    current_revision: int,
) -> bool:
    """Check if mid-course revision should trigger.

    Conditions:
    - Phases 1.0 AND 1.5 have completed
    - No phase >= 2.0 has completed
    - At most 1 prior revision (don't revise endlessly)
    """
    has_profiling = 1.0 in completed_phases and 1.5 in completed_phases
    no_downstream = all(p < 2.0 for p in completed_phases)
    not_over_revised = current_revision < 2

    return has_profiling and no_downstream and not_over_revised


def apply_revision_to_plan(
    plan_dict: dict,
    revision_result: dict,
    completed_phases: set[float],
) -> dict:
    """Apply a revision result to the plan dict.

    For pre-execution revision: replaces all phases.
    For mid-course revision: keeps completed phases, replaces remaining.

    Args:
        plan_dict: Current plan dict (will be modified in place)
        revision_result: Result from revise_plan_pre_execution or revise_plan_mid_course
        completed_phases: Set of already-completed phase numbers

    Returns:
        The modified plan_dict
    """
    revision_entry = revision_result["revision"]
    revised_phases = revision_result["revised_phases"]

    # For mid-course: keep completed phases, replace remaining
    if revision_entry.get("revision_type") == "mid_course":
        existing_completed = [
            p for p in plan_dict.get("phases", [])
            if p.get("phase_number", 0) in completed_phases
        ]
        plan_dict["phases"] = existing_completed + revised_phases
    else:
        # Pre-execution: replace all phases
        plan_dict["phases"] = revised_phases

    # Sort by phase number
    plan_dict["phases"].sort(key=lambda p: p.get("phase_number", 0))

    # Update revision tracking
    if "revision_history" not in plan_dict:
        plan_dict["revision_history"] = []
    plan_dict["revision_history"].append(revision_entry)
    plan_dict["current_revision"] = revision_entry.get("revision_number", 1)

    return plan_dict
