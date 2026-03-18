"""Post-execution view refinement — adjusts view recommendations based on actual results.

The planner (Milestone 1) generates recommended_views PRE-execution based on the
thinker's profile. This module REFINES those recommendations POST-execution based
on what the analysis actually produced.

Uses Sonnet (not Opus) — this is a lightweight curatorial decision, not deep analysis.
"""

import json
import logging
import re
from types import SimpleNamespace
from typing import Optional

from src.executor.plan_context import load_effective_plan
from src.executor.job_manager import get_job
from src.executor.output_store import load_phase_outputs
from src.llm.client import get_anthropic_client, parse_llm_json_response
from src.renderers.registry import get_renderer_registry
from src.sub_renderers.registry import get_sub_renderer_registry
from src.transformations.registry import get_transformation_registry
from src.views.registry import get_view_registry

from .recommendation_defaults import get_default_recommendations_for_workflow
from .schemas import RefinedViewRecommendation, ViewRefinementResult
from .store import load_view_refinement, save_view_refinement
from .view_hierarchy import (
    iter_active_child_views as _iter_active_child_views,
    match_container_sections_to_children as _match_container_sections_to_children,
    resolve_parent_section_binding,
)
from .variant_store import summarize_selections
from .work_key_utils import try_split_collapsed_outputs as _try_split_collapsed_outputs

logger = logging.getLogger(__name__)

REFINEMENT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8000


def _baseline_recommendations(plan, *, consumer_key: str) -> list:
    if plan.recommended_views:
        return list(plan.recommended_views)
    return [
        SimpleNamespace(
            view_key=row["view_key"],
            priority=row.get("priority", "secondary"),
            rationale=row.get("rationale", ""),
        )
        for row in get_default_recommendations_for_workflow(
            plan.workflow_key,
            consumer_key=consumer_key,
        )
    ]

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

### Renderer Recommendations
- If the current container renderer is a poor fit, set renderer_type_override
- Based on the data shape of each view's output, recommend renderer_config_overrides
- For accordion views with structured sections, recommend section_renderers:
  {"section_renderers": {"section_key": {"renderer_type": "chip_grid", "config": {...}}}}
- Match presentation stance to renderer affinities from the catalog
- Available section renderer types: chip_grid, mini_card_list, concept_dossier_cards, key_value_table, prose_block, annotated_prose, stat_row, comparison_panel, timeline_strip, directional_transfer_list, rich_description_list, dimension_analysis_cards
- Example: a view with stance "evidence" and array-of-objects data → accordion + mini_card_list or concept_dossier_cards sections
- Example: a view with stance "comparison" → table or comparison_panel sections
- Example: a view with arrays of strings/tags → chip_grid sections
- Example: a view with key→value mappings → key_value_table sections
- Example: a view with long analytical prose, synthetic judgment, counterfactual reasoning, or architectural summary → annotated_prose sections
- Example: concept inventories with explicit definitions, roles, and related terms → concept_dossier_cards
- Example: named analytical axes with significance and exemplar concepts → dimension_analysis_cards
- Use renderer_type_override aggressively when actual content strongly favors a different structure.
- Treat default view definitions as starting hypotheses, not constraints.
- If view-specific template metadata lists multiple compatible renderers, use that as permission to switch.
- If project preference summaries show repeated user selections, treat them as a weak prior, not a rule.
- Leave renderer_type_override null if the existing renderer remains the best fit

### Content Signature Heuristics
- Dialectical tensions, contradictions, paired oppositions, and argumentative reversals often want comparison-oriented structures.
- Temporal development, phased evolution, chronology, or recurring shifts across works often want timeline-oriented structures.
- Repeated evidence-bearing instances, tactic inventories, or per-work findings often want card_grid or table structures.
- Metaphor-rich, rhetorical, or narrative-heavy synthesis often wants prose or tab layouts.
- When a view already has bespoke sub-renderers in its config (for example `dialectical_pair`, `move_repertoire`, `intensity_matrix`), preserve or extend them if the output clearly fits.

## Output Format

Return ONLY valid JSON (no markdown fences):

{
  "refined_views": [
    {
      "view_key": "genealogy_portrait",
      "priority": "primary",
      "presentation_stance_override": null,
      "renderer_type_override": null,
      "rationale": "Why this priority based on actual results",
      "renderer_config_overrides": {
        "section_renderers": {
          "core_concepts": {"renderer_type": "concept_dossier_cards", "config": {"title_field": "term", "subtitle_field": "role"}},
          "concept_clusters": {"renderer_type": "chip_grid", "config": {"label_field": "cluster_name"}}
        }
      },
      "display_label_override": null,
      "top_level_group": null,
      "promote_to_top_level": false,
      "collapse_into_parent": false,
      "top_level_position_override": null,
      "data_quality_assessment": "rich"
    }
  ],
  "changes_summary": "2-3 sentences explaining what changed from the original plan and why"
}

Include ALL views from the original plan, plus any additional views worth showing.
The refined_views list should be complete — not a diff.
Set renderer_config_overrides to null for views that don't need section-level adjustments.
Use hierarchy overrides sparingly:
- promote_to_top_level when a child tab has a materially stronger content signature than its parent overview and deserves major navigation
- collapse_into_parent when a child tab is auxiliary, redundant, or mostly metadata relative to the parent overview
- display_label_override may be used at child-tab level to shorten generic labels or clarify a distinctive content signature, not for cosmetic churn
"""


def refine_views(
    job_id: str,
    plan_id: str,
    *,
    consumer_key: str,
) -> ViewRefinementResult:
    """Refine view recommendations based on actual execution results.

    Reads the job's phase results and output previews, then calls Sonnet
    to produce refined view recommendations.

    Returns ViewRefinementResult (also persisted to DB).
    """
    # Load the plan
    plan = load_effective_plan(job_id, plan_id)
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

    # Original recommended views from plan, or workflow-page defaults for legacy jobs
    original_views = [
        {
            "view_key": v.view_key,
            "priority": getattr(v, "priority", "secondary"),
            "presentation_stance_override": getattr(v, "presentation_stance_override", None),
            "rationale": getattr(v, "rationale", ""),
        }
        for v in _baseline_recommendations(plan, consumer_key=consumer_key)
    ]
    phase_results = _parse_phase_results(job)

    # Reuse persisted refinement when the job/plan pair has already been curated.
    # clear_refinement=True on the compose endpoint remains the explicit invalidation knob.
    cached_refinement = load_view_refinement(job_id)
    if cached_refinement and cached_refinement.get("plan_id") == plan_id:
        refined_views, changes_summary = _finalize_refined_views(
            job_id=job_id,
            plan=plan,
            phase_results=phase_results,
            original_views=original_views,
            raw_refined_views=cached_refinement.get("refined_views", []),
            changes_summary=cached_refinement.get("changes_summary", ""),
        )
        if [v.model_dump() for v in refined_views] != cached_refinement.get("refined_views", []):
            save_view_refinement(
                job_id=job_id,
                plan_id=plan_id,
                refined_views=[v.model_dump() for v in refined_views],
                changes_summary=changes_summary,
                model_used=cached_refinement.get("model_used", ""),
                tokens_used=cached_refinement.get("tokens_used", 0),
            )
        logger.info(
            f"Reusing cached refinement for job {job_id}: "
            f"{len(refined_views)} views, model={cached_refinement.get('model_used', '')}"
        )
        return ViewRefinementResult(
            job_id=job_id,
            plan_id=plan_id,
            original_views=original_views,
            refined_views=refined_views,
            changes_summary=changes_summary,
            refinement_model=cached_refinement.get("model_used", ""),
            tokens_used=cached_refinement.get("tokens_used", 0),
        )

    # Build context for the LLM
    context = _build_refinement_context(
        plan,
        job,
        job_id,
        consumer_key=consumer_key,
    )

    # Call Sonnet
    client = get_anthropic_client()
    if client is None:
        # No LLM available — return original views unchanged
        logger.warning("No LLM client available — returning original views unrefined")
        return _finalize_passthrough_result(job_id, plan_id, original_views, plan, phase_results)

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

        refined_views, changes_summary = _finalize_refined_views(
            job_id=job_id,
            plan=plan,
            phase_results=phase_results,
            original_views=original_views,
            raw_refined_views=parsed.get("refined_views", []),
            changes_summary=parsed.get("changes_summary", ""),
        )

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
        return _finalize_passthrough_result(job_id, plan_id, original_views, plan, phase_results)


def deterministic_refine_views(
    job_id: str,
    plan_id: str,
    *,
    consumer_key: str,
) -> ViewRefinementResult:
    """Build and persist deterministic, non-LLM refinement for a job.

    This is the fallback path for legacy/offline rebuilds where we want
    hierarchy guardrails and empty-view suppression without making a fresh
    curator-model call.
    """
    plan = load_effective_plan(job_id, plan_id)
    if plan is None:
        raise ValueError(f"Plan not found: {plan_id}")

    job = get_job(job_id)
    if job is None:
        raise ValueError(f"Job not found: {job_id}")

    if job["status"] not in ("completed", "failed"):
        raise ValueError(
            f"Job {job_id} is {job['status']} — refinement requires completed or failed status"
        )

    original_views = [
        {
            "view_key": v.view_key,
            "priority": getattr(v, "priority", "secondary"),
            "presentation_stance_override": getattr(v, "presentation_stance_override", None),
            "rationale": getattr(v, "rationale", ""),
        }
        for v in _baseline_recommendations(plan, consumer_key=consumer_key)
    ]
    phase_results = _parse_phase_results(job)
    result = _finalize_passthrough_result(job_id, plan_id, original_views, plan, phase_results)

    save_view_refinement(
        job_id=job_id,
        plan_id=plan_id,
        refined_views=[v.model_dump() for v in result.refined_views],
        changes_summary=result.changes_summary,
        model_used="deterministic",
        tokens_used=0,
    )
    return result


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
            renderer_type_override=v.get("renderer_type_override"),
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


def _finalize_passthrough_result(
    job_id: str,
    plan_id: str,
    original_views: list[dict],
    plan,
    phase_results: dict,
) -> ViewRefinementResult:
    """Apply deterministic guardrails to a passthrough refinement result."""
    passthrough = _passthrough_result(job_id, plan_id, original_views, plan)
    refined_views, changes_summary = _finalize_refined_views(
        job_id=job_id,
        plan=plan,
        phase_results=phase_results,
        original_views=original_views,
        raw_refined_views=[v.model_dump() for v in passthrough.refined_views],
        changes_summary=passthrough.changes_summary,
    )
    passthrough.refined_views = refined_views
    passthrough.changes_summary = changes_summary
    return passthrough


def _parse_phase_results(job: dict) -> dict:
    """Normalize phase_results into a dict."""
    phase_results = job.get("phase_results", {})
    if isinstance(phase_results, str):
        phase_results = json.loads(phase_results) if phase_results else {}
    return phase_results or {}


def _get_phase_result(phase_results: dict, phase_number: Optional[float]) -> dict:
    """Resolve a phase result row by numeric phase_number."""
    if phase_number is None:
        return {}

    keys = [str(phase_number)]
    try:
        keys.append(f"{float(phase_number):.1f}")
    except Exception:
        pass

    for key in keys:
        result = phase_results.get(key)
        if isinstance(result, dict):
            return result
    return {}


def _load_direct_view_data_presence(job_id: str) -> dict[str, bool]:
    """Check whether each active view has direct phase-backed data."""
    view_registry = get_view_registry()
    active_views = [v for v in view_registry.list_all() if getattr(v, "status", "active") == "active"]
    outputs_cache: dict[tuple, bool] = {}
    direct_presence: dict[str, bool] = {}

    for view_def in active_views:
        ds = view_def.data_source
        if ds.phase_number is None:
            direct_presence[view_def.view_key] = True
            continue

        cache_key = (ds.phase_number, ds.engine_key, ds.chain_key, ds.scope)
        if cache_key not in outputs_cache:
            outputs = load_phase_outputs(
                job_id=job_id,
                phase_number=ds.phase_number,
                engine_key=ds.engine_key,
            )
            if not outputs and ds.chain_key and not ds.engine_key:
                outputs = load_phase_outputs(
                    job_id=job_id,
                    phase_number=ds.phase_number,
                )
            outputs_cache[cache_key] = bool(outputs)
        direct_presence[view_def.view_key] = outputs_cache[cache_key]

    return direct_presence


def _coerce_recommendation(raw: dict | RefinedViewRecommendation) -> RefinedViewRecommendation:
    """Normalize a recommendation payload into the schema model."""
    if isinstance(raw, RefinedViewRecommendation):
        return raw
    return RefinedViewRecommendation(**raw)


def _baseline_recommendation(original: dict) -> RefinedViewRecommendation:
    """Create a recommendation model from an original plan entry."""
    return RefinedViewRecommendation(
        view_key=original.get("view_key", ""),
        priority=original.get("priority", "secondary"),
        presentation_stance_override=original.get("presentation_stance_override"),
        renderer_type_override=original.get("renderer_type_override"),
        rationale=original.get("rationale", ""),
        renderer_config_overrides=original.get("renderer_config_overrides"),
        display_label_override=original.get("display_label_override"),
        top_level_group=original.get("top_level_group"),
        promote_to_top_level=original.get("promote_to_top_level", False),
        collapse_into_parent=original.get("collapse_into_parent", False),
        top_level_position_override=original.get("top_level_position_override"),
        data_quality_assessment=original.get("data_quality_assessment", "standard"),
    )


def _finalize_refined_views(
    job_id: str,
    plan,
    phase_results: dict,
    original_views: list[dict],
    raw_refined_views: list[dict | RefinedViewRecommendation],
    changes_summary: str,
) -> tuple[list[RefinedViewRecommendation], str]:
    """Enforce completeness and hide empty/skipped-phase views deterministically."""
    view_registry = get_view_registry()
    active_views = sorted(
        [v for v in view_registry.list_all() if getattr(v, "status", "active") == "active"],
        key=lambda v: (getattr(v, "position", 0), v.view_key),
    )
    direct_data = _load_direct_view_data_presence(job_id)

    ordered_keys: list[str] = []
    rec_by_key: dict[str, RefinedViewRecommendation] = {}

    for original in original_views:
        key = original.get("view_key", "")
        if not key:
            continue
        ordered_keys.append(key)
        rec_by_key[key] = _baseline_recommendation(original)

    for raw in raw_refined_views:
        rec = _coerce_recommendation(raw)
        if rec.view_key not in ordered_keys:
            ordered_keys.append(rec.view_key)
        rec_by_key[rec.view_key] = rec

    auto_added_children: list[str] = []
    for view_def in active_views:
        if not getattr(view_def, "parent_view_key", None):
            continue
        if not direct_data.get(view_def.view_key):
            continue
        if view_def.view_key in rec_by_key:
            continue

        ordered_keys.append(view_def.view_key)
        rec_by_key[view_def.view_key] = RefinedViewRecommendation(
            view_key=view_def.view_key,
            priority="secondary",
            rationale="Auto-included because this child view has data.",
            data_quality_assessment="standard",
        )
        auto_added_children.append(view_def.view_key)

    required_children: list[str] = []
    for parent_key in ordered_keys:
        if not parent_key:
            continue

        parent_rec = rec_by_key.get(parent_key)
        if parent_rec is None or parent_rec.priority == "hidden":
            continue

        parent_view = view_registry.get(parent_key)
        if parent_view is None:
            continue

        child_views = _iter_active_child_views(view_registry, parent_key)
        if not child_views:
            continue

        for child_view in _match_container_sections_to_children(parent_view, child_views).values():
            if not direct_data.get(child_view.view_key):
                continue

            child_rec = rec_by_key.get(child_view.view_key)
            reason = "Auto-included because the visible parent container depends on this child section."
            if child_rec is None:
                ordered_keys.append(child_view.view_key)
                rec_by_key[child_view.view_key] = RefinedViewRecommendation(
                    view_key=child_view.view_key,
                    priority="secondary",
                    rationale=reason,
                    data_quality_assessment="standard",
                )
                required_children.append(child_view.view_key)
                continue

            if child_rec.priority == "hidden":
                child_rec.priority = "secondary"
                child_rec.data_quality_assessment = (
                    child_rec.data_quality_assessment
                    if child_rec.data_quality_assessment != "empty"
                    else "standard"
                )
                if reason not in child_rec.rationale:
                    child_rec.rationale = f"{child_rec.rationale} {reason}".strip()
                required_children.append(child_view.view_key)

    hidden_by_guardrail: list[str] = []
    for view_key in ordered_keys:
        rec = rec_by_key[view_key]
        view_def = view_registry.get(view_key)
        if view_def is None:
            continue

        ds = view_def.data_source
        if ds.phase_number is None:
            continue
        if direct_data.get(view_key):
            continue

        phase_result = _get_phase_result(phase_results, ds.phase_number)
        phase_status = phase_result.get("status", "no_outputs")
        reason = (
            f"Automatically hidden because phase {ds.phase_number:.1f} "
            f"is '{phase_status}' and this view has no direct outputs."
        )
        if rec.priority != "hidden":
            hidden_by_guardrail.append(view_key)
        rec.priority = "hidden"
        rec.data_quality_assessment = "empty"
        if reason not in rec.rationale:
            rec.rationale = f"{rec.rationale} {reason}".strip()

    suppressed_for_integrity = _apply_semantic_integrity_suppression(
        job_id=job_id,
        ordered_keys=ordered_keys,
        rec_by_key=rec_by_key,
        active_views=active_views,
    )

    hierarchy_notes = _apply_deterministic_hierarchy_policy(
        job_id=job_id,
        ordered_keys=ordered_keys,
        rec_by_key=rec_by_key,
        view_registry=view_registry,
        direct_data=direct_data,
        phase_results=phase_results,
    )

    summary_parts = [changes_summary.strip()] if changes_summary and changes_summary.strip() else []
    if auto_added_children:
        preview = ", ".join(auto_added_children[:4])
        suffix = "..." if len(auto_added_children) > 4 else ""
        summary_parts.append(f"Auto-included data-bearing child views: {preview}{suffix}.")
    if required_children:
        preview = ", ".join(required_children[:4])
        suffix = "..." if len(required_children) > 4 else ""
        summary_parts.append(f"Required container child sections were restored: {preview}{suffix}.")
    if hidden_by_guardrail:
        preview = ", ".join(hidden_by_guardrail[:6])
        suffix = "..." if len(hidden_by_guardrail) > 6 else ""
        summary_parts.append(f"Guardrail hid views with no direct outputs: {preview}{suffix}.")
    if suppressed_for_integrity:
        preview = ", ".join(suppressed_for_integrity[:6])
        suffix = "..." if len(suppressed_for_integrity) > 6 else ""
        summary_parts.append(
            f"Semantic-integrity guardrail suppressed low-signal comparative views: {preview}{suffix}."
        )
    if hierarchy_notes["promoted"]:
        preview = ", ".join(hierarchy_notes["promoted"][:4])
        suffix = "..." if len(hierarchy_notes["promoted"]) > 4 else ""
        summary_parts.append(f"Deterministic hierarchy promoted child views to top-level: {preview}{suffix}.")
    if hierarchy_notes["collapsed"]:
        preview = ", ".join(hierarchy_notes["collapsed"][:4])
        suffix = "..." if len(hierarchy_notes["collapsed"]) > 4 else ""
        summary_parts.append(f"Deterministic hierarchy collapsed auxiliary child tabs into parents: {preview}{suffix}.")
    if hierarchy_notes["relabeled"]:
        preview = ", ".join(hierarchy_notes["relabeled"][:4])
        suffix = "..." if len(hierarchy_notes["relabeled"]) > 4 else ""
        summary_parts.append(f"Deterministic hierarchy relabeled child tabs for navigation clarity: {preview}{suffix}.")

    return [rec_by_key[key] for key in ordered_keys], " ".join(summary_parts).strip()


def _apply_semantic_integrity_suppression(
    job_id: str,
    ordered_keys: list[str],
    rec_by_key: dict[str, RefinedViewRecommendation],
    active_views: list,
) -> list[str]:
    """Hide per-item views that do not have enough meaningful comparison items."""
    outputs_cache: dict[tuple, list[dict]] = {}
    suppressed: list[str] = []
    view_by_key = {view.view_key: view for view in active_views}

    for view_key in ordered_keys:
        rec = rec_by_key.get(view_key)
        view_def = view_by_key.get(view_key)
        if rec is None or view_def is None or rec.priority == "hidden":
            continue

        ds = getattr(view_def, "data_source", None)
        if ds is None or getattr(ds, "scope", "") != "per_item" or ds.phase_number is None:
            continue

        cache_key = (ds.phase_number, ds.engine_key, ds.chain_key, ds.scope)
        if cache_key not in outputs_cache:
            outputs = load_phase_outputs(
                job_id=job_id,
                phase_number=ds.phase_number,
                engine_key=ds.engine_key,
            )
            if not outputs and ds.chain_key and not ds.engine_key:
                outputs = load_phase_outputs(job_id=job_id, phase_number=ds.phase_number)
            outputs_cache[cache_key] = outputs
        outputs = outputs_cache[cache_key]
        if not outputs:
            continue

        work_keys = {row.get("work_key", "") for row in outputs if row.get("work_key")}
        if ds.chain_key and work_keys == {"target"}:
            split_result = _try_split_collapsed_outputs(outputs, job_id, ds.chain_key)
            if split_result is not None:
                work_keys = {wk for wk in split_result.keys() if wk}

        meaningful_work_keys = {
            work_key for work_key in work_keys
            if work_key and work_key != "target"
        }
        if len(meaningful_work_keys) >= 2:
            continue

        rec.priority = "hidden"
        rec.data_quality_assessment = "thin"
        if work_keys == {"target"}:
            reason = (
                "Automatically hidden because this per-item view collapsed to the placeholder "
                "work_key 'target' and does not form a meaningful comparison surface."
            )
        else:
            reason = (
                "Automatically hidden because this per-item view has fewer than two meaningful "
                "work items and does not sustain a comparison surface."
            )
        if reason not in rec.rationale:
            rec.rationale = f"{rec.rationale} {reason}".strip()
        suppressed.append(view_key)

    return suppressed


def _apply_deterministic_hierarchy_policy(
    job_id: str,
    ordered_keys: list[str],
    rec_by_key: dict[str, RefinedViewRecommendation],
    view_registry,
    direct_data: dict[str, bool],
    phase_results: dict,
) -> dict[str, list[str]]:
    """Apply bounded, non-LLM hierarchy improvements to child views."""
    notes = {"promoted": [], "collapsed": [], "relabeled": []}
    active_views = sorted(
        [v for v in view_registry.list_all() if getattr(v, "status", "active") == "active"],
        key=lambda v: (getattr(v, "position", 0), v.view_key),
    )
    materiality = _load_view_materiality(job_id, active_views, phase_results)

    top_level_defs = []
    for key in ordered_keys:
        view_def = view_registry.get(key)
        rec = rec_by_key.get(key)
        if view_def is None or rec is None or rec.priority == "hidden":
            continue
        if getattr(view_def, "parent_view_key", None) is None:
            top_level_defs.append(view_def)

    for parent_view in active_views:
        parent_key = parent_view.view_key
        parent_rec = rec_by_key.get(parent_key)
        if parent_rec is None or parent_rec.priority == "hidden":
            continue

        child_views = sorted(
            _iter_active_child_views(view_registry, parent_key),
            key=lambda v: (getattr(v, "position", 0), v.view_key),
        )
        visible_children = [
            child
            for child in child_views
            if child.view_key in rec_by_key
            and rec_by_key[child.view_key].priority != "hidden"
            and direct_data.get(child.view_key)
        ]
        if not visible_children:
            continue

        for child_view in visible_children:
            child_rec = rec_by_key[child_view.view_key]
            if child_rec.display_label_override:
                continue
            compact_label = _compact_child_label(
                child_view=child_view,
                parent_view=parent_view,
                view_registry=view_registry,
                signals=materiality.get(child_view.view_key, {}).get("signals", []),
                promoted=child_rec.promote_to_top_level,
            )
            if compact_label and compact_label != child_view.view_name:
                child_rec.display_label_override = compact_label
                notes["relabeled"].append(f"{child_view.view_key}->{compact_label}")

        if _should_collapse_singleton_auxiliary_child(parent_view, visible_children):
            child_view = visible_children[0]
            child_rec = rec_by_key[child_view.view_key]
            if not child_rec.promote_to_top_level and not child_rec.collapse_into_parent:
                child_rec.collapse_into_parent = True
                child_rec.rationale = (
                    f"{child_rec.rationale} Collapsed into the parent because it is an auxiliary singleton child view."
                ).strip()
                notes["collapsed"].append(child_view.view_key)
            continue

        promoted_key = _choose_child_for_top_level_promotion(
            parent_view=parent_view,
            visible_children=visible_children,
            top_level_defs=top_level_defs,
            materiality=materiality,
            view_registry=view_registry,
        )
        if promoted_key is None:
            continue

        child_rec = rec_by_key[promoted_key]
        if not child_rec.promote_to_top_level:
            child_rec.promote_to_top_level = True
            if child_rec.top_level_group is None:
                child_rec.top_level_group = parent_rec.top_level_group
            child_rec.rationale = (
                f"{child_rec.rationale} Promoted to top-level because this child tab has a materially stronger"
                f" content signature than the parent overview."
            ).strip()
            notes["promoted"].append(promoted_key)

        promoted_view = view_registry.get(promoted_key)
        if promoted_view is not None and not child_rec.display_label_override:
            promoted_label = _compact_child_label(
                child_view=promoted_view,
                parent_view=parent_view,
                view_registry=view_registry,
                signals=materiality.get(promoted_key, {}).get("signals", []),
                promoted=True,
            )
            if promoted_label and promoted_label != promoted_view.view_name:
                child_rec.display_label_override = promoted_label
                notes["relabeled"].append(f"{promoted_key}->{promoted_label}")

    return notes


def _load_view_materiality(job_id: str, active_views: list, phase_results: dict) -> dict[str, dict]:
    """Collect lightweight richness signals for deterministic hierarchy policy."""
    outputs_cache: dict[tuple, list[dict]] = {}
    metrics: dict[str, dict] = {}

    for view_def in active_views:
        ds = getattr(view_def, "data_source", None)
        if ds is None or ds.phase_number is None:
            metrics[view_def.view_key] = {
                "output_count": 0,
                "work_count": 0,
                "chars": 0,
                "signals": [],
                "preview": "",
            }
            continue

        cache_key = (ds.phase_number, ds.engine_key, ds.chain_key, ds.scope)
        if cache_key not in outputs_cache:
            outputs = load_phase_outputs(
                job_id=job_id,
                phase_number=ds.phase_number,
                engine_key=ds.engine_key,
            )
            if not outputs and ds.chain_key and not ds.engine_key:
                outputs = load_phase_outputs(job_id=job_id, phase_number=ds.phase_number)
            outputs_cache[cache_key] = outputs
        outputs = outputs_cache[cache_key]

        latest_output = max(
            outputs,
            key=lambda row: (
                row.get("pass_number", 0),
                row.get("created_at") or "",
                row.get("id") or "",
            ),
            default=None,
        )
        preview = _normalize_preview((latest_output or {}).get("content", ""))
        if not preview:
            phase_result = _get_phase_result(phase_results, ds.phase_number)
            preview = _normalize_preview(phase_result.get("final_output_preview", ""))

        metrics[view_def.view_key] = {
            "output_count": len(outputs),
            "work_count": len({row.get("work_key") for row in outputs if row.get("work_key")}),
            "chars": len((latest_output or {}).get("content", "")),
            "signals": _infer_content_signals(preview),
            "preview": preview,
        }

    return metrics


def _should_collapse_singleton_auxiliary_child(parent_view, visible_children: list) -> bool:
    """Collapse a lone auxiliary child that does not merit normal child-tab space."""
    if len(visible_children) != 1:
        return False

    child_view = visible_children[0]
    if getattr(child_view, "renderer_type", None) in _COLLAPSE_RENDERERS:
        return True

    return (
        getattr(parent_view, "renderer_type", None) == "prose"
        and child_view.view_name.lower().endswith("profile")
    )


def _choose_child_for_top_level_promotion(
    parent_view,
    visible_children: list,
    top_level_defs: list,
    materiality: dict[str, dict],
    view_registry,
) -> Optional[str]:
    """Choose one standout child to promote when a container has a dominant section."""
    if not _is_chain_container_candidate(parent_view, view_registry):
        return None
    if len(visible_children) < 2:
        return None

    candidates: list[tuple[int, int, int, float, str]] = []
    for child_view in visible_children:
        if _child_name_overlaps_top_level(child_view, parent_view, top_level_defs):
            continue
        metric = materiality.get(child_view.view_key, {})
        score = _promotion_score(child_view, metric, view_registry)
        if score < 7:
            continue
        candidates.append(
            (
                score,
                len(metric.get("signals", [])),
                metric.get("chars", 0),
                -float(getattr(child_view, "position", 0) or 0),
                child_view.view_key,
            )
        )

    if not candidates:
        return None

    candidates.sort(reverse=True)
    return candidates[0][-1]


def _is_chain_container_candidate(parent_view, view_registry) -> bool:
    """True when the parent is a section-backed chain container."""
    return bool(
        getattr(getattr(parent_view, "data_source", None), "chain_key", None)
        and not getattr(getattr(parent_view, "data_source", None), "engine_key", None)
        and _match_container_sections_to_children(
            parent_view,
            _iter_active_child_views(view_registry, parent_view.view_key),
        )
    )


def _promotion_score(child_view, metric: dict, view_registry) -> int:
    """Bounded materiality score for child-tab promotion."""
    score = 0
    score += min(metric.get("output_count", 0), 4)
    score += min(metric.get("work_count", 0), 3)
    chars = metric.get("chars", 0)
    if chars >= 8000:
        score += 1
    if chars >= 16000:
        score += 1
    if chars >= 30000:
        score += 1
    score += sum(_PROMOTION_SIGNAL_WEIGHTS.get(signal, 0) for signal in metric.get("signals", []))
    if getattr(getattr(child_view, "data_source", None), "scope", "") == "per_item":
        score += 1
    if getattr(child_view, "renderer_type", None) in _PROMOTION_RENDERERS:
        score += 1
    if resolve_parent_section_binding(child_view, view_registry):
        score += 1
    return score


def _child_name_overlaps_top_level(child_view, parent_view, top_level_defs: list) -> bool:
    """Avoid promoting a child whose label would duplicate an existing top-level branch."""
    child_tokens = _title_tokens(getattr(child_view, "view_name", ""))
    if not child_tokens:
        return False

    for top in top_level_defs:
        if top is None or top.view_key == parent_view.view_key:
            continue
        overlap = child_tokens & _title_tokens(getattr(top, "view_name", ""))
        if not overlap:
            continue
        if len(overlap) >= 2:
            return True
        if overlap & {"evolution", "profile", "portrait", "relationship", "conditions", "tactics"}:
            return True
    return False


def _title_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(token) > 2 and token not in _TITLE_STOPWORDS
    }


def _compact_child_label(
    child_view,
    parent_view,
    view_registry,
    signals: list[str],
    promoted: bool,
) -> Optional[str]:
    """Suggest a shorter, clearer child-tab label when the current one is generic."""
    binding = resolve_parent_section_binding(child_view, view_registry)
    label = (binding or {}).get("section_title") or getattr(child_view, "view_name", "")
    original = label

    for pattern, replacement in _GENERIC_CHILD_LABEL_REPLACEMENTS:
        label = pattern.sub(replacement, label)
    label = re.sub(r"\s{2,}", " ", label).strip(" -")

    if promoted and "narrative_metaphor" in signals and label.lower() == "narrative structure":
        label = "Narrative Arc"

    if getattr(parent_view, "renderer_type", None) == "prose" and label.lower() == "author intellectual profile":
        label = "Author Profile"

    if not label or label == original:
        return None
    return label


_CONTENT_SIGNAL_RULES: list[tuple[str, list[str]]] = [
    ("dialectical_tension", ["dialectic", "dialectical", "contradiction", "tension", "antinomy", "reversal"]),
    ("temporal_evolution", ["timeline", "chronolog", "trajectory", "evolution", "phase", "turning point", "sequence"]),
    ("narrative_metaphor", ["metaphor", "narrative", "story", "myth", "allegory", "image", "figur"]),
    ("repeated_evidence", ["evidence", "instance", "example", "pattern", "distribution", "quote", "trace"]),
    ("comparison", ["compare", "comparison", "contrast", "versus", "vs.", "difference", "opposition"]),
]

_PROMOTION_SIGNAL_WEIGHTS = {
    "temporal_evolution": 3,
    "comparison": 2,
    "dialectical_tension": 2,
    "narrative_metaphor": 2,
    "repeated_evidence": 2,
}

_PROMOTION_RENDERERS = {"accordion", "tab", "card_grid", "timeline", "prose"}
_COLLAPSE_RENDERERS = {"stat_summary", "table"}
_TITLE_STOPWORDS = {"the", "and", "of", "for", "in", "to", "a", "an", "map"}
_GENERIC_CHILD_LABEL_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bSummarization\b", flags=re.I), "Summary"),
    (re.compile(r"\bIntellectual Profile\b", flags=re.I), "Profile"),
    (re.compile(r"\bAnalysis\b$", flags=re.I), ""),
    (re.compile(r"\bDetail\b$", flags=re.I), ""),
]


def _normalize_preview(text: str, limit: int = 240) -> str:
    """Collapse whitespace for compact context snippets."""
    if not text:
        return ""
    compact = re.sub(r"\s+", " ", text).strip()
    return compact[:limit]


def _infer_content_signals(text: str) -> list[str]:
    """Infer coarse presentation signals from prose previews."""
    if not text:
        return []

    lowered = text.lower()
    signals: list[str] = []
    for signal, keywords in _CONTENT_SIGNAL_RULES:
        if any(keyword in lowered for keyword in keywords):
            signals.append(signal)

    year_hits = len(re.findall(r"\b(?:18|19|20)\d{2}\b", text))
    if year_hits >= 2 and "temporal_evolution" not in signals:
        signals.append("temporal_evolution")

    if re.search(r"(?:^|\s)(?:1\.|2\.|3\.|-|\*)\s", text) and "repeated_evidence" not in signals:
        signals.append("repeated_evidence")

    return signals[:4]


def _summarize_renderer_config(view_def) -> str:
    """Return a compact summary of the current renderer config."""
    config = view_def.renderer_config or {}
    bits: list[str] = []

    if config.get("cell_renderer"):
        bits.append(f"cell={config['cell_renderer']}")
    if config.get("group_by"):
        bits.append(f"group_by={config['group_by']}")
    if config.get("columns"):
        bits.append(f"columns={config['columns']}")
    if config.get("expandable") is not None:
        bits.append(f"expandable={config['expandable']}")
    if config.get("layout"):
        bits.append(f"layout={config['layout']}")
    if config.get("variant"):
        bits.append(f"variant={config['variant']}")

    sections = config.get("sections")
    if isinstance(sections, list):
        bits.append(f"sections={len(sections)}")

    section_renderers = config.get("section_renderers")
    if isinstance(section_renderers, dict) and section_renderers:
        rendered = []
        for key, value in list(section_renderers.items())[:4]:
            if isinstance(value, dict):
                rendered.append(f"{key}:{value.get('renderer_type', '?')}")
        if rendered:
            bits.append("section_renderers=" + ", ".join(rendered))

    return "; ".join(bits) if bits else "none"


def _find_template_options(view_def) -> tuple[list[str], list[str], list[str]]:
    """Find compatible renderer/preset/sub-renderer options for a view's data source."""
    ds = view_def.data_source
    registry = get_transformation_registry()
    engine_keys: list[str] = []

    if ds.engine_key:
        engine_keys = [ds.engine_key]
    elif ds.chain_key:
        from src.chains.registry import get_chain_registry

        chain = get_chain_registry().get(ds.chain_key)
        if chain:
            engine_keys = list(chain.engine_keys)

    renderers: set[str] = set()
    presets: list[str] = []
    compatible_subs: set[str] = set()

    for engine_key in engine_keys:
        for template in registry.for_engine(engine_key):
            renderers.update(template.applicable_renderer_types)
            if template.renderer_config_presets:
                for renderer_key, preset in template.renderer_config_presets.items():
                    preset_keys = ", ".join(list(preset.keys())[:4])
                    presets.append(f"{renderer_key}[{preset_keys}]")
            compatible_subs.update(template.compatible_sub_renderers)

    return sorted(renderers), sorted(set(presets)), sorted(compatible_subs)


def _load_project_preference_lines(project_id: Optional[str]) -> tuple[list[str], dict[str, list[str]]]:
    """Summarize variant selections for project-scoped refinement."""
    if not project_id:
        return [], {}

    try:
        rows = summarize_selections(project_id)
    except Exception as exc:
        logger.debug(f"Could not load variant summaries for project {project_id}: {exc}")
        return [], {}

    if not rows:
        return [], {}

    lines: list[str] = []
    by_view: dict[str, list[str]] = {}
    for row in rows:
        line = (
            f"{row['view_key']} / {row['dimension']}: "
            f"{row['selected_renderer']} over {row['base_renderer']} "
            f"({row['selection_count']} selections)"
        )
        lines.append(line)
        by_view.setdefault(row["view_key"], []).append(line)

    return lines[:12], by_view


def _build_view_signal_lines(
    plan,
    job_id: str,
    phase_results: dict,
    project_preferences: dict[str, list[str]],
    *,
    consumer_key: str,
) -> list[str]:
    """Build compact, per-view context for the refinement LLM."""
    view_registry = get_view_registry()
    lines: list[str] = []

    for recommendation in _baseline_recommendations(plan, consumer_key=consumer_key):
        view_def = view_registry.get(recommendation.view_key)
        if view_def is None:
            continue

        ds = view_def.data_source
        if ds is None:
            continue
        outputs = load_phase_outputs(
            job_id=job_id,
            phase_number=ds.phase_number,
            engine_key=ds.engine_key,
        ) if ds.phase_number is not None else []

        if not outputs and ds.chain_key and not ds.engine_key:
            outputs = load_phase_outputs(job_id=job_id, phase_number=ds.phase_number)

        latest_output = max(outputs, key=lambda row: row.get("pass_number", 0)) if outputs else None
        output_preview = _normalize_preview((latest_output or {}).get("content", ""))
        preview = output_preview

        phase_result = _get_phase_result(phase_results, ds.phase_number)
        if not preview:
            preview = _normalize_preview(phase_result.get("final_output_preview", ""))

        renderers, presets, compatible_subs = _find_template_options(view_def)
        signals = _infer_content_signals(preview)
        prefs = project_preferences.get(view_def.view_key, [])

        bits = [
            f"- **{view_def.view_key}** default={view_def.renderer_type}",
            f"stance={view_def.presentation_stance}",
            f"phase={ds.phase_number if ds.phase_number is not None else 'n/a'}",
            f"scope={ds.scope}",
            f"config={_summarize_renderer_config(view_def)}",
        ]

        if outputs:
            work_keys = sorted({row.get("work_key", "") for row in outputs if row.get("work_key")})
            bits.append(f"outputs={len(outputs)}")
            if work_keys:
                bits.append(f"works={len(work_keys)}")
            if latest_output:
                bits.append(f"chars={len(latest_output.get('content', ''))}")

        if signals:
            bits.append("signals=" + ", ".join(signals))
        if renderers:
            bits.append("compatible_renderers=" + ", ".join(renderers[:6]))
        if presets:
            bits.append("presets=" + "; ".join(presets[:4]))
        if compatible_subs:
            bits.append("compatible_sub_renderers=" + ", ".join(compatible_subs[:6]))
        if prefs:
            bits.append("project_preferences=" + " | ".join(prefs[:2]))
        if preview:
            bits.append(f'preview="{preview}"')

        lines.append(" ; ".join(bits))

    return lines


def _build_refinement_context(
    plan,
    job: dict,
    job_id: str,
    *,
    consumer_key: str,
) -> str:
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
    for v in _baseline_recommendations(plan, consumer_key=consumer_key):
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

    # 5. Project preference summaries from prior variant selections
    project_preference_lines, project_preferences_by_view = _load_project_preference_lines(job.get("project_id"))
    sections.append("\n## Project Preference Signals\n")
    if project_preference_lines:
        sections.extend(f"- {line}" for line in project_preference_lines)
    else:
        sections.append("No prior variant selection summaries for this project.")

    # 6. View-specific composition signals
    sections.append("\n## View-Specific Composition Signals\n")
    view_signal_lines = _build_view_signal_lines(
        plan=plan,
        job_id=job_id,
        phase_results=phase_results,
        project_preferences=project_preferences_by_view,
        consumer_key=consumer_key,
    )
    if view_signal_lines:
        sections.extend(view_signal_lines)
    else:
        sections.append("No view-specific composition signals available.")

    # 7. Available views
    sections.append("\n## Available View Definitions\n")
    view_registry = get_view_registry()
    for view_def in view_registry.list_all():
        ds = view_def.data_source
        sections.append(
            f"- **{view_def.view_key}** ({view_def.renderer_type}): "
            f"{view_def.view_name} — phase {ds.phase_number}, "
            f"engine={ds.engine_key or 'N/A'}, chain={ds.chain_key or 'N/A'}, "
            f"scope={ds.scope}, visibility={view_def.visibility}, "
            f"config={_summarize_renderer_config(view_def)}"
        )

    # 8. Renderer catalog
    sections.append("\n## Available Renderers\n")
    renderer_registry = get_renderer_registry()
    for rdef in renderer_registry.list_all():
        affinities = ", ".join(
            f"{k}:{v}" for k, v in sorted(
                rdef.stance_affinities.items(), key=lambda x: -x[1]
            )
        )
        sections.append(
            f"- **{rdef.renderer_key}** ({rdef.category}): {rdef.renderer_name} "
            f"— shapes: {', '.join(rdef.ideal_data_shapes)}, "
            f"affinities: [{affinities}]"
        )
        if rdef.available_section_renderers:
            sections.append(
                f"  Sub-renderers: {', '.join(rdef.available_section_renderers)}"
            )

    # 9. Sub-renderer catalog
    sections.append("\n## Available Sub-Renderers\n")
    sub_renderer_registry = get_sub_renderer_registry()
    for sr in sorted(sub_renderer_registry.list_all(), key=lambda r: r.sub_renderer_key):
        if sr.status != "active":
            continue
        affinities = ", ".join(
            f"{k}:{v}" for k, v in sorted(
                sr.stance_affinities.items(), key=lambda x: -x[1]
            )
        )
        sections.append(
            f"- **{sr.sub_renderer_key}** ({sr.category}): {sr.sub_renderer_name} "
            f"— shapes: {', '.join(sr.ideal_data_shapes)}, "
            f"parents: {', '.join(sr.parent_renderer_types)}, "
            f"affinities: [{affinities}]"
        )

    sections.append("\n## Instructions\n")
    sections.append(
        "Based on the execution results above, refine the recommended views. "
        "Adjust priorities, stances, data quality assessments, and "
        "renderer_type_override / renderer_config_overrides (especially section_renderers "
        "for accordion views) based on what each phase actually produced. Use the "
        "view-specific composition signals and project preference signals as evidence, "
        "not as rigid rules."
    )

    return "\n".join(sections)
