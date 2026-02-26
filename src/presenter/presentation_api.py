"""Presentation API — assembles render-ready page payloads for the consumer.

Combines view definitions, structured data (from presentation_cache),
and raw prose (from phase_outputs) into a single PagePresentation
that The Critic can render directly.
"""

import json
import logging
from typing import Any, Optional

from src.executor.job_manager import get_job
from src.executor.output_store import (
    load_all_job_outputs,
    load_phase_outputs,
    load_presentation_cache,
    load_presentation_cache_batch,
    get_latest_output_for_phase,
)
from src.orchestrator.planner import load_plan
from src.views.registry import get_view_registry

from .schemas import PagePresentation, ViewPayload
from .store import load_view_refinement

logger = logging.getLogger(__name__)


def _resolve_workflow_key(job: dict, plan=None) -> str:
    """Resolve workflow_key from job record, falling back to plan, then default."""
    if job and job.get("workflow_key"):
        return job["workflow_key"]
    if plan and hasattr(plan, "workflow_key") and plan.workflow_key:
        return plan.workflow_key
    return "intellectual_genealogy"


def assemble_page(job_id: str, slim: bool = False) -> PagePresentation:
    """Assemble a complete page presentation for a job.

    This is the primary consumer endpoint. It:
    1. Loads the plan + job metadata
    2. Prefetches ALL outputs in a single query (avoids N+1)
    3. Gets refined view recommendations (or plan defaults)
    4. For each view, loads structured data or raw prose
    5. Builds the parent-child view tree
    6. Returns a complete PagePresentation

    When slim=True, skips raw prose content to reduce response size
    from ~1MB to ~10KB. Use the /view/{job_id}/{view_key} endpoint
    to lazy-load prose for individual views.
    """
    # Load job
    job = get_job(job_id)
    if job is None:
        raise ValueError(f"Job not found: {job_id}")

    plan_id = job["plan_id"]

    # Load plan for context
    plan = load_plan(plan_id)
    thinker_name = plan.thinker_name if plan else ""
    strategy_summary = plan.strategy_summary if plan else ""

    # Resolve workflow_key dynamically from job record
    workflow_key = _resolve_workflow_key(job, plan)

    # Prefetch ALL outputs in a single query to avoid N+1 per-view queries.
    # In slim mode, skip the content column entirely (saves ~1MB of data transfer).
    all_outputs = load_all_job_outputs(job_id, include_content=not slim)
    outputs_cache = _build_outputs_cache(all_outputs)

    # Prefetch ALL presentation_cache entries for this job's outputs in one query.
    # Eliminates ~50-70 individual cache lookups (each costing ~200ms cross-region).
    output_ids = [o["id"] for o in all_outputs]
    cache_batch = load_presentation_cache_batch(output_ids)

    # Get recommended views (refined or plan defaults)
    recommended = _get_recommendations(job_id, plan_id, workflow_key=workflow_key)

    # Build recommendation lookup
    rec_by_key = {r["view_key"]: r for r in recommended}

    # Load view registry
    view_registry = get_view_registry()

    # Build ViewPayloads
    payloads: dict[str, ViewPayload] = {}

    for rec in recommended:
        if rec.get("priority") == "hidden":
            continue

        view_def = view_registry.get(rec["view_key"])
        if view_def is None:
            logger.warning(f"View definition not found: {rec['view_key']}")
            continue

        payload = _build_view_payload(
            view_def=view_def,
            rec=rec,
            job_id=job_id,
            outputs_cache=outputs_cache,
            cache_batch=cache_batch,
            slim=slim,
        )
        payloads[payload.view_key] = payload

    # Also include views that aren't in recommendations but are active for the workflow
    all_workflow_views = view_registry.for_workflow(workflow_key)
    for view_def in all_workflow_views:
        if view_def.view_key in payloads:
            continue
        if view_def.status != "active":
            continue
        if view_def.visibility == "on_demand":
            # Include on-demand views with low priority
            payload = _build_view_payload(
                view_def=view_def,
                rec={"view_key": view_def.view_key, "priority": "optional", "rationale": ""},
                job_id=job_id,
                outputs_cache=outputs_cache,
                cache_batch=cache_batch,
                slim=slim,
            )
            payloads[payload.view_key] = payload

    # Auto-generate views for chapter-targeted phases that have no view definitions
    if plan:
        _inject_chapter_views(plan, payloads, job_id, outputs_cache=outputs_cache, cache_batch=cache_batch, slim=slim)

    # Build parent-child tree
    top_level = _build_view_tree(payloads, view_registry)

    # Execution summary
    execution_summary = _build_execution_summary(job)

    # Check if refinement was applied
    refinement = load_view_refinement(job_id)
    refinement_applied = refinement is not None
    refinement_summary = refinement.get("changes_summary", "") if refinement else ""

    return PagePresentation(
        job_id=job_id,
        plan_id=plan_id,
        thinker_name=thinker_name,
        strategy_summary=strategy_summary,
        views=top_level,
        view_count=len(payloads),
        execution_summary=execution_summary,
        refinement_applied=refinement_applied,
        refinement_summary=refinement_summary,
    )


def assemble_single_view(job_id: str, view_key: str) -> Optional[ViewPayload]:
    """Assemble a single view payload (for lazy loading on-demand views)."""
    job = get_job(job_id)
    if job is None:
        raise ValueError(f"Job not found: {job_id}")

    # Resolve workflow_key dynamically from job record
    workflow_key = _resolve_workflow_key(job)

    view_registry = get_view_registry()
    view_def = view_registry.get(view_key)
    if view_def is None:
        return None

    # Check recommendations for this view
    recommended = _get_recommendations(job_id, job["plan_id"], workflow_key=workflow_key)
    rec = next(
        (r for r in recommended if r["view_key"] == view_key),
        {"view_key": view_key, "priority": "optional", "rationale": ""},
    )

    payload = _build_view_payload(
        view_def=view_def,
        rec=rec,
        job_id=job_id,
    )

    # Include children
    all_views = view_registry.for_workflow(workflow_key)
    children_defs = [
        v for v in all_views
        if v.parent_view_key == view_key and v.status == "active"
    ]
    for child_def in sorted(children_defs, key=lambda v: v.position):
        child_rec = next(
            (r for r in recommended if r["view_key"] == child_def.view_key),
            {"view_key": child_def.view_key, "priority": "secondary", "rationale": ""},
        )
        child_payload = _build_view_payload(
            view_def=child_def,
            rec=child_rec,
            job_id=job_id,
        )
        payload.children.append(child_payload)

    return payload


def get_presentation_status(job_id: str) -> dict:
    """Check which views have data ready, need transformation, or are empty."""
    job = get_job(job_id)
    if job is None:
        raise ValueError(f"Job not found: {job_id}")

    recommended = _get_recommendations(job_id, job["plan_id"])
    view_registry = get_view_registry()

    statuses = []
    for rec in recommended:
        view_def = view_registry.get(rec["view_key"])
        if view_def is None:
            statuses.append({
                "view_key": rec["view_key"],
                "status": "not_found",
                "has_prose": False,
                "has_structured_data": False,
            })
            continue

        phase_number = view_def.data_source.phase_number
        engine_key = view_def.data_source.engine_key

        # Check for prose outputs
        outputs = load_phase_outputs(
            job_id=job_id,
            phase_number=phase_number,
            engine_key=engine_key,
        ) if phase_number is not None else []

        has_prose = len(outputs) > 0

        # Check for cached structured data
        has_structured = False
        if outputs:
            latest = max(outputs, key=lambda o: o.get("pass_number", 0))
            from src.transformations.registry import get_transformation_registry
            transform_registry = get_transformation_registry()
            templates = []
            if engine_key:
                templates = transform_registry.for_engine(engine_key)
            for t in templates:
                cached = load_presentation_cache(
                    output_id=latest["id"],
                    section=t.template_key,
                )
                if cached is not None:
                    has_structured = True
                    break

        statuses.append({
            "view_key": rec["view_key"],
            "priority": rec.get("priority", "secondary"),
            "status": "ready" if has_structured else ("prose_only" if has_prose else "empty"),
            "has_prose": has_prose,
            "has_structured_data": has_structured,
        })

    return {
        "job_id": job_id,
        "views": statuses,
        "total": len(statuses),
        "ready": sum(1 for s in statuses if s["status"] == "ready"),
        "prose_only": sum(1 for s in statuses if s["status"] == "prose_only"),
        "empty": sum(1 for s in statuses if s["status"] == "empty"),
    }


# --- Internal helpers ---


def _build_outputs_cache(all_outputs: list[dict]) -> dict:
    """Index prefetched outputs for fast lookup by (phase_number, engine_key).

    Returns a dict with keys:
      - ("all",)  → all outputs
      - (phase_number,) → outputs for that phase
      - (phase_number, engine_key) → outputs for that phase+engine
    """
    cache: dict[tuple, list[dict]] = {("all",): all_outputs}
    for o in all_outputs:
        pn = o.get("phase_number")
        ek = o.get("engine_key")
        cache.setdefault((pn,), []).append(o)
        cache.setdefault((pn, ek), []).append(o)
    return cache


def _get_cached_outputs(
    outputs_cache: dict,
    phase_number: Optional[float],
    engine_key: Optional[str],
) -> list[dict]:
    """Retrieve outputs from the prefetched cache."""
    if phase_number is None:
        return []
    if engine_key is not None:
        return outputs_cache.get((phase_number, engine_key), [])
    return outputs_cache.get((phase_number,), [])


def _get_recommendations(job_id: str, plan_id: str, workflow_key: str = "intellectual_genealogy") -> list[dict]:
    """Get view recommendations — refined if available, else plan defaults."""
    refinement = load_view_refinement(job_id)
    if refinement and refinement.get("refined_views"):
        return refinement["refined_views"]

    plan = load_plan(plan_id)
    if plan and plan.recommended_views:
        return [v.model_dump() for v in plan.recommended_views]

    # Fallback: all active views for this workflow
    view_registry = get_view_registry()
    return [
        {"view_key": v.view_key, "priority": "secondary", "rationale": ""}
        for v in view_registry.for_workflow(workflow_key)
        if v.status == "active"
    ]


def _build_view_payload(
    view_def,
    rec: dict,
    job_id: str,
    outputs_cache: Optional[dict] = None,
    cache_batch: Optional[dict] = None,
    slim: bool = False,
) -> ViewPayload:
    """Build a ViewPayload for a single view definition."""
    ds = view_def.data_source
    phase_number = ds.phase_number
    engine_key = ds.engine_key
    chain_key = ds.chain_key
    scope = ds.scope

    # Resolve stance (recommendation override takes precedence)
    stance = rec.get("presentation_stance_override") or view_def.presentation_stance

    # Resolve renderer_config (with optional overrides)
    renderer_config = dict(view_def.renderer_config)
    config_overrides = rec.get("renderer_config_overrides")
    if config_overrides:
        renderer_config.update(config_overrides)

    # Load data
    structured_data = None
    raw_prose = None
    items = None
    has_structured = False

    if scope == "per_item":
        items = _load_per_item_data(
            job_id, phase_number, engine_key,
            chain_key=chain_key, outputs_cache=outputs_cache,
            cache_batch=cache_batch, slim=slim,
        )
    else:
        structured_data, raw_prose = _load_aggregated_data(
            job_id, phase_number, engine_key, chain_key,
            outputs_cache=outputs_cache, cache_batch=cache_batch, slim=slim,
        )
        has_structured = structured_data is not None

    return ViewPayload(
        view_key=view_def.view_key,
        view_name=view_def.view_name,
        description=view_def.description,
        renderer_type=view_def.renderer_type,
        renderer_config=renderer_config,
        presentation_stance=stance,
        priority=rec.get("priority", "secondary"),
        rationale=rec.get("rationale", ""),
        data_quality=rec.get("data_quality_assessment", "standard"),
        phase_number=phase_number,
        engine_key=engine_key,
        chain_key=chain_key,
        scope=scope,
        has_structured_data=has_structured,
        structured_data=structured_data,
        raw_prose=raw_prose,
        items=items,
        tab_count=None,  # TODO: resolve tab_count_field
        visibility=view_def.visibility,
        position=view_def.position,
        children=[],
    )


def _resolve_chain_engine_keys(chain_key: str) -> list[str]:
    """Resolve a chain_key to the list of engine keys in that chain."""
    from src.chains.registry import get_chain_registry
    chain_registry = get_chain_registry()
    chain = chain_registry.get(chain_key)
    if chain is None:
        logger.warning(f"Chain not found: {chain_key}")
        return []
    return list(chain.engine_keys)


def _load_aggregated_data(
    job_id: str,
    phase_number: Optional[float],
    engine_key: Optional[str],
    chain_key: Optional[str],
    outputs_cache: Optional[dict] = None,
    cache_batch: Optional[dict] = None,
    slim: bool = False,
) -> tuple[Optional[dict], Optional[str]]:
    """Load structured data and/or raw prose for an aggregated view.

    For chain-backed views (chain_key set, engine_key None), resolves the
    chain's engine keys and searches templates for ALL engines in the chain.
    Also concatenates ALL engine outputs for the phase into raw_prose.

    When slim=True, skips building raw_prose (returns None for prose).
    When outputs_cache is provided, uses prefetched data instead of querying DB.

    Returns (structured_data, raw_prose).
    """
    if phase_number is None:
        return None, None

    # Load outputs — from cache if available, else query DB
    if outputs_cache is not None:
        outputs = _get_cached_outputs(outputs_cache, phase_number, engine_key)
        if not outputs and chain_key:
            outputs = _get_cached_outputs(outputs_cache, phase_number, None)
    else:
        outputs = load_phase_outputs(
            job_id=job_id,
            phase_number=phase_number,
            engine_key=engine_key,
        )
        if not outputs and chain_key:
            outputs = load_phase_outputs(job_id=job_id, phase_number=phase_number)

    if not outputs:
        return None, None

    # Build raw_prose (skip in slim mode)
    raw_prose = None
    if not slim:
        if chain_key and not engine_key:
            sorted_outputs = sorted(outputs, key=lambda o: o.get("pass_number", 0))
            prose_parts = []
            for o in sorted_outputs:
                content = o.get("content", "")
                if content:
                    eng = o.get("engine_key", "unknown")
                    prose_parts.append(f"## [{eng}]\n\n{content}")
            raw_prose = "\n\n---\n\n".join(prose_parts) if prose_parts else ""
        else:
            sorted_outputs = sorted(outputs, key=lambda o: o.get("pass_number", 0))
            if len(sorted_outputs) > 1:
                prose_parts = []
                for o in sorted_outputs:
                    content = o.get("content", "")
                    if content:
                        prose_parts.append(f"## [Pass {o.get('pass_number', 0)}]\n\n{content}")
                raw_prose = "\n\n---\n\n".join(prose_parts) if prose_parts else ""
            else:
                raw_prose = sorted_outputs[0].get("content", "") if sorted_outputs else ""

    # Get latest output for structured data lookup
    latest = max(outputs, key=lambda o: o.get("pass_number", 0))

    # Check presentation_cache for structured data
    structured_data = None
    from src.transformations.registry import get_transformation_registry
    transform_registry = get_transformation_registry()

    # Determine which engine keys to search templates for
    search_engine_keys = []
    if engine_key:
        search_engine_keys = [engine_key]
    elif chain_key:
        search_engine_keys = _resolve_chain_engine_keys(chain_key)

    # For multi-pass single-engine views, the bridge caches with
    # content_override (concatenated passes) but skips freshness check.
    # We must also skip freshness here since raw_prose is the concatenation
    # but the cache was saved without a source hash.
    is_multi_pass_single_engine = (
        engine_key and not chain_key
        and len(outputs) > 1
    )

    for ek in search_engine_keys:
        templates = transform_registry.for_engine(ek)
        for t in templates:
            # Use batch cache if available (zero DB queries)
            if cache_batch is not None:
                cached = cache_batch.get((latest["id"], t.template_key))
            else:
                # Fallback to individual query
                skip_freshness = (chain_key and not engine_key) or is_multi_pass_single_engine
                cached = load_presentation_cache(
                    output_id=latest["id"],
                    section=t.template_key,
                    source_content=None if skip_freshness else raw_prose,
                )
            if cached is not None:
                structured_data = cached
                break
        if structured_data is not None:
            break

    return structured_data, raw_prose


def _load_per_item_data(
    job_id: str,
    phase_number: Optional[float],
    engine_key: Optional[str],
    chain_key: Optional[str] = None,
    outputs_cache: Optional[dict] = None,
    cache_batch: Optional[dict] = None,
    slim: bool = False,
) -> list[dict]:
    """Load per-item data (one entry per prior work).

    For chain-backed per-item views, loads ALL phase outputs, groups by
    work_key, concatenates all engine outputs per work_key, and searches
    templates using chain engine keys.

    When outputs_cache is provided, uses prefetched data instead of querying DB.
    When slim=True, skips raw_prose in each item.

    Returns a list of {work_key, structured_data, raw_prose} dicts.
    """
    if phase_number is None:
        return []

    # Load outputs — from cache if available, else query DB
    if outputs_cache is not None:
        outputs = _get_cached_outputs(outputs_cache, phase_number, engine_key)
        if not outputs and chain_key and not engine_key:
            outputs = _get_cached_outputs(outputs_cache, phase_number, None)
    else:
        outputs = load_phase_outputs(
            job_id=job_id,
            phase_number=phase_number,
            engine_key=engine_key,
        )
        # For chain-backed views with no engine_key, get all outputs for the phase
        if not outputs and chain_key and not engine_key:
            outputs = load_phase_outputs(job_id=job_id, phase_number=phase_number)

    # Group by work_key
    if chain_key and not engine_key:
        # Chain-backed: collect ALL outputs per work_key, concatenate content
        by_work_all: dict[str, list[dict]] = {}
        for o in outputs:
            work_key = o.get("work_key", "")
            if not work_key:
                continue
            by_work_all.setdefault(work_key, []).append(o)

        by_work: dict[str, dict] = {}
        for work_key, work_outputs in by_work_all.items():
            sorted_wo = sorted(work_outputs, key=lambda o: o.get("pass_number", 0))
            # Use the last output as the "primary" (for output_id, cache lookup)
            latest = sorted_wo[-1]
            # Concatenate all engine outputs for this work
            prose_parts = []
            for wo in sorted_wo:
                content = wo.get("content", "")
                if content:
                    eng = wo.get("engine_key", "unknown")
                    prose_parts.append(f"## [{eng}]\n\n{content}")
            combined_content = "\n\n---\n\n".join(prose_parts) if prose_parts else ""
            # Store combined content in a synthetic entry
            by_work[work_key] = {**latest, "_combined_content": combined_content}
    else:
        # Single engine: keep latest pass per work_key
        by_work = {}
        for o in outputs:
            work_key = o.get("work_key", "")
            if not work_key:
                continue
            existing = by_work.get(work_key)
            if existing is None or o.get("pass_number", 0) > existing.get("pass_number", 0):
                by_work[work_key] = o

    items = []
    from src.transformations.registry import get_transformation_registry
    transform_registry = get_transformation_registry()

    # Determine which engine keys to search templates for
    search_engine_keys = []
    if engine_key:
        search_engine_keys = [engine_key]
    elif chain_key:
        search_engine_keys = _resolve_chain_engine_keys(chain_key)

    for work_key, output in sorted(by_work.items()):
        content = "" if slim else output.get("_combined_content", output.get("content", ""))

        # Check for structured data
        structured = None
        for ek in search_engine_keys:
            templates = transform_registry.for_engine(ek)
            for t in templates:
                section = f"{t.template_key}:{work_key}"
                # Use batch cache if available (zero DB queries)
                if cache_batch is not None:
                    cached = cache_batch.get((output["id"], section))
                else:
                    # Fallback to individual query
                    cached = load_presentation_cache(
                        output_id=output["id"],
                        section=section,
                        source_content=None if (chain_key and not engine_key) else content,
                    )
                if cached is not None:
                    structured = cached
                    break
            if structured is not None:
                break

        items.append({
            "work_key": work_key,
            "has_structured_data": structured is not None,
            "structured_data": structured,
            "raw_prose": content if not slim else None,
        })

    return items


def _inject_chapter_views(
    plan,
    payloads: dict[str, ViewPayload],
    job_id: str,
    outputs_cache: Optional[dict] = None,
    cache_batch: Optional[dict] = None,
    slim: bool = False,
) -> None:
    """Auto-generate ViewPayloads for chapter-targeted phases.

    The planner can dynamically create phases with document_scope="chapter".
    Since no static view definitions exist for these dynamic phases, we
    auto-generate per-item views so chapter outputs appear in the frontend.
    """
    for phase in plan.phases:
        if phase.skip:
            continue
        doc_scope = getattr(phase, "document_scope", "whole") or "whole"
        if doc_scope != "chapter":
            continue

        # Check if any existing view already covers this phase
        phase_covered = any(
            p.phase_number == phase.phase_number
            for p in payloads.values()
        )
        if phase_covered:
            continue

        # Build a synthetic per-item view for this chapter-targeted phase
        view_key = f"auto_chapter_{phase.phase_number}"

        # Load chapter items using the same per_item loader
        chain_key = phase.chain_key
        engine_key = phase.engine_key
        items = _load_per_item_data(
            job_id, phase.phase_number, engine_key, chain_key=chain_key,
            outputs_cache=outputs_cache, cache_batch=cache_batch, slim=slim,
        )

        # Add chapter metadata to each item
        chapter_targets = getattr(phase, "chapter_targets", None) or []
        chapter_lookup = {ct.chapter_id: ct for ct in chapter_targets}
        for item in items:
            wk = item.get("work_key", "")
            ct = chapter_lookup.get(wk)
            if ct:
                item["_is_chapter"] = True
                item["_chapter_title"] = ct.chapter_title
                item["_chapter_rationale"] = ct.rationale
            else:
                item["_is_chapter"] = True
                item["_chapter_title"] = wk

        if not items:
            continue

        chapter_count = len(items)
        engine_label = chain_key or engine_key or "analysis"

        payload = ViewPayload(
            view_key=view_key,
            view_name=f"Chapter Analysis — Phase {phase.phase_number}",
            description=(
                f"Per-chapter analysis from {phase.phase_name} "
                f"({chapter_count} chapters, engine: {engine_label})"
            ),
            renderer_type="per_item_cards",
            renderer_config={"card_style": "chapter"},
            presentation_stance=None,
            priority="primary",
            rationale=phase.rationale or "Chapter-level targeting by adaptive planner",
            data_quality="standard" if items else "empty",
            phase_number=phase.phase_number,
            engine_key=engine_key,
            chain_key=chain_key,
            scope="per_item",
            has_structured_data=any(i.get("has_structured_data") for i in items),
            items=items,
            tab_count=chapter_count,
            visibility="if_data_exists",
            position=phase.phase_number * 10,  # Sort after corresponding phase
        )
        payloads[view_key] = payload
        logger.info(
            f"Auto-generated chapter view '{view_key}' for phase {phase.phase_number}: "
            f"{chapter_count} chapter items"
        )


def _build_view_tree(
    payloads: dict[str, ViewPayload],
    view_registry,
) -> list[ViewPayload]:
    """Build parent-child view tree from flat dict.

    Returns top-level views sorted by position, with children nested.
    """
    # Wire children to parents
    top_level: list[ViewPayload] = []

    for key, payload in payloads.items():
        view_def = view_registry.get(key)
        parent_key = view_def.parent_view_key if view_def else None

        if parent_key and parent_key in payloads:
            payloads[parent_key].children.append(payload)
        else:
            top_level.append(payload)

    # Sort by position
    top_level.sort(key=lambda v: v.position)
    for payload in payloads.values():
        payload.children.sort(key=lambda v: v.position)

    return top_level


def _build_execution_summary(job: dict) -> dict:
    """Build execution summary from job record."""
    phase_results = job.get("phase_results", {})
    if isinstance(phase_results, str):
        phase_results = json.loads(phase_results) if phase_results else {}

    return {
        "status": job.get("status", "unknown"),
        "total_llm_calls": job.get("total_llm_calls", 0),
        "total_input_tokens": job.get("total_input_tokens", 0),
        "total_output_tokens": job.get("total_output_tokens", 0),
        "created_at": job.get("created_at", ""),
        "started_at": job.get("started_at", ""),
        "completed_at": job.get("completed_at", ""),
        "phase_results": phase_results,
    }
