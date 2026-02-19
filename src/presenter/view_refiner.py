"""Post-execution view refinement — adjusts view recommendations based on actual results.

The planner (Milestone 1) generates recommended_views PRE-execution based on the
thinker's profile. This module REFINES those recommendations POST-execution based
on what the analysis actually produced.

Uses Sonnet (not Opus) — this is a lightweight curatorial decision, not deep analysis.
"""

import json
import logging
from typing import Optional

from src.executor.job_manager import get_job
from src.executor.output_store import load_phase_outputs
from src.llm.client import get_anthropic_client, parse_llm_json_response
from src.orchestrator.planner import load_plan
from src.views.registry import get_view_registry

from .schemas import RefinedViewRecommendation, ViewRefinementResult
from .store import save_view_refinement

logger = logging.getLogger(__name__)

REFINEMENT_MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 8000

SYSTEM_PROMPT = """You are a presentation curator for intellectual genealogy analyses.

You receive:
1. The original analysis plan (strategy, recommended views)
2. Execution results (phase statuses, output previews, token counts)
3. The available view definitions

Your job: REFINE the view recommendations based on what the analysis actually produced.

## Refinement Guidelines

### Priority Adjustments
- **Upgrade to primary**: If a phase produced unexpectedly rich output (many sections, specific findings, high token count)
- **Downgrade to secondary**: If output is thin or generic
- **Set to hidden**: If a phase failed or produced empty output
- **Keep as-is**: If the output matches expectations

### Data Quality Assessment
- **rich**: Output has clear structure, specific findings, multiple sections
- **standard**: Typical analytical output
- **thin**: Output is vague, lacks specifics, or is unusually short
- **empty**: Phase failed or produced no output

### When to Adjust Stances
- If analysis reveals heavy conceptual content → use 'narrative' stance
- If analysis reveals many quantifiable findings → use 'evidence' stance
- If analysis reveals comparative patterns → use 'comparison' stance

## Output Format

Return ONLY valid JSON (no markdown fences):

{
  "refined_views": [
    {
      "view_key": "genealogy_portrait",
      "priority": "primary",
      "presentation_stance_override": null,
      "rationale": "Why this priority based on actual results",
      "renderer_config_overrides": null,
      "data_quality_assessment": "rich"
    }
  ],
  "changes_summary": "2-3 sentences explaining what changed from the original plan and why"
}

Include ALL views from the original plan, plus any additional views worth showing.
The refined_views list should be complete — not a diff.
"""


def refine_views(
    job_id: str,
    plan_id: str,
) -> ViewRefinementResult:
    """Refine view recommendations based on actual execution results.

    Reads the job's phase results and output previews, then calls Sonnet
    to produce refined view recommendations.

    Returns ViewRefinementResult (also persisted to DB).
    """
    # Load the plan
    plan = load_plan(plan_id)
    if plan is None:
        raise ValueError(f"Plan not found: {plan_id}")

    # Load the job
    job = get_job(job_id)
    if job is None:
        raise ValueError(f"Job not found: {job_id}")

    if job["status"] not in ("completed", "failed"):
        raise ValueError(
            f"Job {job_id} is {job['status']} — refinement requires completed or failed status"
        )

    # Original recommended views from plan
    original_views = [v.model_dump() for v in plan.recommended_views]

    # Build context for the LLM
    context = _build_refinement_context(plan, job, job_id)

    # Call Sonnet
    client = get_anthropic_client()
    if client is None:
        # No LLM available — return original views unchanged
        logger.warning("No LLM client available — returning original views unrefined")
        return _passthrough_result(job_id, plan_id, original_views, plan)

    try:
        response = client.messages.create(
            model=REFINEMENT_MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": context}],
        )

        raw_text = response.content[0].text
        tokens_used = response.usage.input_tokens + response.usage.output_tokens
        model_used = REFINEMENT_MODEL

        # Parse response
        parsed = parse_llm_json_response(raw_text)

        refined_views = [
            RefinedViewRecommendation(**v)
            for v in parsed.get("refined_views", [])
        ]
        changes_summary = parsed.get("changes_summary", "")

        result = ViewRefinementResult(
            job_id=job_id,
            plan_id=plan_id,
            original_views=original_views,
            refined_views=refined_views,
            changes_summary=changes_summary,
            refinement_model=model_used,
            tokens_used=tokens_used,
        )

        # Persist to DB
        save_view_refinement(
            job_id=job_id,
            plan_id=plan_id,
            refined_views=[v.model_dump() for v in refined_views],
            changes_summary=changes_summary,
            model_used=model_used,
            tokens_used=tokens_used,
        )

        logger.info(
            f"Refined views for job {job_id}: {len(refined_views)} views, "
            f"{tokens_used} tokens, changes: {changes_summary[:100]}..."
        )
        return result

    except Exception as e:
        logger.error(f"View refinement LLM call failed: {e}")
        # Fall back to original views
        return _passthrough_result(job_id, plan_id, original_views, plan)


def _passthrough_result(
    job_id: str,
    plan_id: str,
    original_views: list[dict],
    plan,
) -> ViewRefinementResult:
    """Create a passthrough result using the plan's original views."""
    refined = [
        RefinedViewRecommendation(
            view_key=v.get("view_key", ""),
            priority=v.get("priority", "secondary"),
            presentation_stance_override=v.get("presentation_stance_override"),
            rationale=v.get("rationale", "Original plan recommendation (refinement skipped)"),
            data_quality_assessment="standard",
        )
        for v in original_views
    ]
    return ViewRefinementResult(
        job_id=job_id,
        plan_id=plan_id,
        original_views=original_views,
        refined_views=refined,
        changes_summary="No refinement applied — using original plan recommendations.",
        refinement_model="none",
        tokens_used=0,
    )


def _build_refinement_context(plan, job: dict, job_id: str) -> str:
    """Build the user message context for the refinement LLM call.

    Includes: plan strategy, original views, phase results, output previews,
    and available view definitions.
    """
    sections = []

    # 1. Plan context
    sections.append("## Analysis Plan\n")
    sections.append(f"**Thinker**: {plan.thinker_name}")
    sections.append(f"**Target Work**: {plan.target_work.title}")
    sections.append(f"**Research Question**: {plan.research_question or 'None specified'}")
    sections.append(f"\n**Strategy Summary**:\n{plan.strategy_summary}\n")

    # 2. Original recommended views
    sections.append("## Original Recommended Views\n")
    for v in plan.recommended_views:
        sections.append(
            f"- **{v.view_key}** [{v.priority}]: {v.rationale}"
        )
    sections.append("")

    # 3. Phase results
    sections.append("## Execution Results\n")
    sections.append(f"**Job Status**: {job['status']}")

    phase_results = job.get("phase_results", {})
    if isinstance(phase_results, str):
        phase_results = json.loads(phase_results) if phase_results else {}

    if phase_results:
        for pn, pr in sorted(phase_results.items(), key=lambda x: float(x[0])):
            status = pr.get("status", "unknown")
            duration = pr.get("duration_ms", 0)
            tokens = pr.get("total_tokens", 0)
            preview = pr.get("final_output_preview", "")
            error = pr.get("error", "")

            sections.append(f"\n### Phase {pn}: {pr.get('phase_name', 'Unknown')}")
            sections.append(f"- Status: {status}")
            sections.append(f"- Duration: {duration:,}ms")
            sections.append(f"- Tokens: {tokens:,}")
            if error:
                sections.append(f"- Error: {error}")
            if preview:
                sections.append(f"- Output preview: {preview[:500]}")
    else:
        sections.append("No phase results available.")

    # 4. Token summary
    sections.append(f"\n**Total LLM Calls**: {job.get('total_llm_calls', 0)}")
    sections.append(f"**Total Tokens**: {job.get('total_input_tokens', 0) + job.get('total_output_tokens', 0):,}")

    # 5. Available views
    sections.append("\n## Available View Definitions\n")
    view_registry = get_view_registry()
    for view_def in view_registry.list_all():
        ds = view_def.data_source
        sections.append(
            f"- **{view_def.view_key}** ({view_def.renderer_type}): "
            f"{view_def.view_name} — phase {ds.phase_number}, "
            f"engine={ds.engine_key or 'N/A'}, chain={ds.chain_key or 'N/A'}, "
            f"scope={ds.scope}, visibility={view_def.visibility}"
        )

    sections.append("\n## Instructions\n")
    sections.append(
        "Based on the execution results above, refine the recommended views. "
        "Adjust priorities, stances, and data quality assessments based on "
        "what each phase actually produced."
    )

    return "\n".join(sections)
