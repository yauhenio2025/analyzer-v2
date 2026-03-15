"""Reconstruct a versioned presentation decision trace on demand."""

from __future__ import annotations

from typing import Any, Optional

from src.executor.job_manager import get_job
from src.orchestrator.planner import load_plan
from src.views.registry import get_view_registry

from .composition_resolver import (
    resolve_effective_composition,
    resolve_effective_render_contract,
)
from .manifest_builder import (
    RESOLVER_VERSION,
    TRACE_SCHEMA_VERSION,
    adapt_renderer_for_consumer,
    derive_view_derivation_kind,
    derive_legacy_visibility,
    normalize_navigation_state,
    normalize_selection_priority,
    normalize_structuring_policy,
)
from .presentation_api import build_presentation_manifest, _get_recommendations, _resolve_workflow_key
from .recommendation_defaults import get_default_recommendations_for_workflow
from .schemas import (
    DecisionTraceChange,
    DecisionTraceEntry,
    EffectiveManifestView,
    IgnoredOverride,
    PresentationDecisionTrace,
)
from .variant_store import load_selected_variants


def build_presentation_trace(
    job_id: str,
    *,
    consumer_key: str,
) -> PresentationDecisionTrace:
    """Build a versioned read-only decision trace for a job + consumer."""

    job = get_job(job_id)
    if job is None:
        raise ValueError(f"Job not found: {job_id}")

    plan = load_plan(job["plan_id"])
    workflow_key = _resolve_workflow_key(job, plan)
    final_manifest = build_presentation_manifest(job_id, consumer_key=consumer_key, slim=True)
    final_view_keys = [view.view_key for view in final_manifest.views]
    view_registry = get_view_registry()

    baseline_recs = _rec_by_key(
        get_default_recommendations_for_workflow(
            workflow_key,
            consumer_key=consumer_key,
        )
    )
    planner_recs = _rec_by_key(
        [v.model_dump() for v in plan.recommended_views] if plan and plan.recommended_views else list(baseline_recs.values())
    )
    final_recs = _rec_by_key(
        _get_recommendations(
            job_id,
            job["plan_id"],
            workflow_key=workflow_key,
            consumer_key=consumer_key,
        )
    )
    final_manifest_by_key = {view.view_key: view for view in final_manifest.views}

    authored_snapshot, authored_ignored, authored_reasons = _build_stage_snapshot(
        job_id=job_id,
        final_view_keys=final_view_keys,
        view_registry=view_registry,
        stage="authored_default",
        consumer_key=consumer_key,
        recs_by_key=baseline_recs,
        final_manifest_by_key=final_manifest_by_key,
        include_selected_variants=False,
    )
    planner_snapshot, planner_ignored, planner_reasons = _build_stage_snapshot(
        job_id=job_id,
        final_view_keys=final_view_keys,
        view_registry=view_registry,
        stage="planner_recommendation",
        consumer_key=consumer_key,
        recs_by_key=planner_recs,
        final_manifest_by_key=final_manifest_by_key,
        include_selected_variants=False,
    )
    refinement_snapshot, refinement_ignored, refinement_reasons = _build_stage_snapshot(
        job_id=job_id,
        final_view_keys=final_view_keys,
        view_registry=view_registry,
        stage="stored_refinement",
        consumer_key=consumer_key,
        recs_by_key=final_recs,
        final_manifest_by_key=final_manifest_by_key,
        include_selected_variants=False,
    )
    deterministic_snapshot, deterministic_ignored, deterministic_reasons = _build_stage_snapshot(
        job_id=job_id,
        final_view_keys=final_view_keys,
        view_registry=view_registry,
        stage="deterministic_contract_resolution",
        consumer_key=consumer_key,
        recs_by_key=final_recs,
        final_manifest_by_key=final_manifest_by_key,
        include_selected_variants=True,
    )
    scaffold_snapshot, scaffold_ignored, scaffold_reasons = _build_stage_snapshot(
        job_id=job_id,
        final_view_keys=final_view_keys,
        view_registry=view_registry,
        stage="semantic_scaffold_resolution",
        consumer_key=consumer_key,
        recs_by_key=final_recs,
        final_manifest_by_key=final_manifest_by_key,
        include_selected_variants=True,
    )
    final_snapshot = [view.model_copy(deep=True) for view in final_manifest.views]
    final_ignored = _collect_capability_adaptation_ignored(
        deterministic_snapshot=deterministic_snapshot,
        consumer_key=consumer_key,
    )

    snapshots = [
        ("authored_default", "Authored defaults before planner/runtime changes", authored_snapshot, authored_ignored, authored_reasons),
        ("planner_recommendation", "Planner recommendations applied", planner_snapshot, planner_ignored, planner_reasons),
        ("stored_refinement", "Stored refinement overrides applied", refinement_snapshot, refinement_ignored, refinement_reasons),
        ("deterministic_contract_resolution", "Deterministic inheritance and template resolution applied", deterministic_snapshot, deterministic_ignored, deterministic_reasons),
        ("semantic_scaffold_resolution", "Semantic scaffold contracts resolved", scaffold_snapshot, scaffold_ignored, scaffold_reasons),
        (
            "consumer_capability_adaptation",
            "Consumer capability adaptation and scaffold hosting resolved",
            final_snapshot,
            final_ignored,
            {},
        ),
    ]

    entries: list[DecisionTraceEntry] = []
    previous_snapshot: list[EffectiveManifestView] = []
    for stage, reason, snapshot, ignored, change_reasons in snapshots:
        entries.append(
            DecisionTraceEntry(
                stage=stage,
                reason=reason,
                applied_changes=_diff_snapshots(previous_snapshot, snapshot, change_reasons),
                ignored_changes=ignored,
                snapshot=snapshot,
            )
        )
        previous_snapshot = snapshot

    return PresentationDecisionTrace(
        job_id=job_id,
        plan_id=job["plan_id"],
        consumer_key=consumer_key,
        manifest_schema_version=final_manifest.manifest_schema_version,
        trace_schema_version=TRACE_SCHEMA_VERSION,
        resolver_version=RESOLVER_VERSION,
        entries=entries,
        final_manifest=final_manifest,
    )


def _build_stage_snapshot(
    *,
    job_id: str,
    final_view_keys: list[str],
    view_registry,
    stage: str,
    consumer_key: str,
    recs_by_key: dict[str, dict[str, Any]],
    final_manifest_by_key: dict[str, EffectiveManifestView],
    include_selected_variants: bool,
) -> tuple[list[EffectiveManifestView], list[IgnoredOverride], dict[tuple[str, str], str]]:
    snapshot: list[EffectiveManifestView] = []
    ignored: list[IgnoredOverride] = []
    change_reasons: dict[tuple[str, str], str] = {}

    for view_key in final_view_keys:
        final_view = final_manifest_by_key[view_key]
        view_def = view_registry.get(view_key)
        if view_def is None:
            snapshot.append(final_view.model_copy(deep=True))
            continue

        rec = _stage_rec(
            view_def=view_def,
            rec=recs_by_key.get(view_key),
        )
        base_position = (
            rec.get("top_level_position_override")
            if rec.get("top_level_position_override") is not None
            else getattr(view_def, "position", 0)
        )
        selection_priority = normalize_selection_priority(rec.get("priority"))
        navigation_state = normalize_navigation_state(
            collapse_into_parent=bool(rec.get("collapse_into_parent", False))
        )
        promoted = bool(rec.get("promote_to_top_level", False))
        display_parent = None if promoted else getattr(view_def, "parent_view_key", None)
        legacy_visibility = derive_legacy_visibility(
            authored_visibility=getattr(view_def, "visibility", None),
            selection_priority=selection_priority,
            navigation_state=navigation_state,
        )
        structuring_policy = normalize_structuring_policy(view_def=view_def)
        derivation_kind = derive_view_derivation_kind(
            view_def=view_def,
            view_registry=view_registry,
        )

        if stage == "authored_default":
            composition = resolve_effective_composition(
                view_def=view_def,
                rec=None,
                consumer_key=consumer_key,
                job_id=job_id if include_selected_variants else None,
            )
            semantic_scaffold_type = "none"
            scaffold_hosting_mode = "none"
            renderer_type = composition.renderer_type
            renderer_config = composition.renderer_config
        elif stage == "planner_recommendation":
            composition = resolve_effective_composition(
                view_def=view_def,
                rec=recs_by_key.get(view_key),
                consumer_key=consumer_key,
                job_id=job_id if include_selected_variants else None,
            )
            semantic_scaffold_type = "none"
            scaffold_hosting_mode = "none"
            renderer_type = composition.renderer_type
            renderer_config = composition.renderer_config
        elif stage == "stored_refinement":
            composition = resolve_effective_composition(
                view_def=view_def,
                rec=recs_by_key.get(view_key),
                consumer_key=consumer_key,
                job_id=job_id if include_selected_variants else None,
            )
            semantic_scaffold_type = "none"
            scaffold_hosting_mode = "none"
            renderer_type = composition.renderer_type
            renderer_config = composition.renderer_config
        elif stage == "deterministic_contract_resolution":
            composition = resolve_effective_render_contract(
                view_def=view_def,
                rec=recs_by_key.get(view_key),
                consumer_key=consumer_key,
                job_id=job_id if include_selected_variants else None,
                view_registry=view_registry,
            )
            semantic_scaffold_type = "none"
            scaffold_hosting_mode = "none"
            renderer_type = composition.renderer_type
            renderer_config = composition.renderer_config
        elif stage == "semantic_scaffold_resolution":
            composition = resolve_effective_render_contract(
                view_def=view_def,
                rec=recs_by_key.get(view_key),
                consumer_key=consumer_key,
                job_id=job_id if include_selected_variants else None,
                view_registry=view_registry,
            )
            semantic_scaffold_type = final_view.semantic_scaffold_type
            scaffold_hosting_mode = "none"
            renderer_type = composition.renderer_type
            renderer_config = composition.renderer_config
        else:
            raise ValueError(f"Unsupported trace stage: {stage}")

        template_selection_reason = getattr(composition, "template_selection_reason", None)
        if template_selection_reason and stage in {"stored_refinement", "deterministic_contract_resolution"}:
            change_reasons[(view_key, "renderer_config")] = template_selection_reason
        if include_selected_variants:
            for selected_variant in load_selected_variants(job_id, view_key):
                rationale = selected_variant.get("rationale") or ""
                dimension = selected_variant.get("dimension")
                if dimension == "renderer_type":
                    if rationale:
                        change_reasons[(view_key, "renderer_type")] = rationale
                        change_reasons[(view_key, "renderer_config")] = rationale
                elif dimension == "sub_renderer_strategy" and rationale:
                    change_reasons[(view_key, "renderer_config")] = rationale
        if structuring_policy is not None:
            change_reasons[(view_key, "structuring_policy")] = "phase2a_structuring_normalization"
        if derivation_kind in {"child_synthesized", "direct_parent_data"}:
            change_reasons[(view_key, "derivation_kind")] = "phase2a_structuring_normalization"
        if stage == "semantic_scaffold_resolution" and final_view.semantic_scaffold_type != "none":
            change_reasons[(view_key, "semantic_scaffold_type")] = "semantic_scaffold_resolution"

        trace_view = EffectiveManifestView(
            view_key=view_key,
            view_name=rec.get("display_label_override") or view_def.view_name,
            description=view_def.description,
            renderer_type=renderer_type,
            renderer_config=renderer_config,
            presentation_stance=composition.presentation_stance,
            selection_priority=selection_priority,
            navigation_state=navigation_state,
            promoted_to_top_level=promoted,
            source_parent_view_key=getattr(view_def, "parent_view_key", None),
            display_parent_view_key=display_parent,
            child_view_keys=[],
            top_level_group=rec.get("top_level_group"),
            position=base_position,
            semantic_scaffold_type=semantic_scaffold_type,
            scaffold_hosting_mode=scaffold_hosting_mode,
            structuring_policy=structuring_policy,
            derivation_kind=derivation_kind or final_view.derivation_kind,
            legacy_visibility=legacy_visibility,
        )
        snapshot.append(trace_view)
        ignored.extend(
            IgnoredOverride(
                view_key=view_key,
                field=item.get("field", ""),
                value=item.get("value"),
                reason=item.get("reason", ""),
            )
            for item in composition.dropped_overrides
        )

    child_map: dict[Optional[str], list[str]] = {}
    for view in snapshot:
        child_map.setdefault(view.display_parent_view_key, []).append(view.view_key)
    for view in snapshot:
        view.child_view_keys = sorted(child_map.get(view.view_key, []))

    return sorted(snapshot, key=lambda view: (view.position, view.view_key)), ignored, change_reasons


def _stage_rec(
    *,
    view_def,
    rec: Optional[dict[str, Any]],
) -> dict[str, Any]:
    default_priority = "optional" if getattr(view_def, "visibility", None) == "on_demand" else "secondary"
    base = {
        "view_key": view_def.view_key,
        "priority": default_priority,
        "rationale": "",
        "promote_to_top_level": False,
        "collapse_into_parent": False,
    }
    if rec:
        base.update({k: v for k, v in rec.items() if v is not None})
    return base


def _rec_by_key(recs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {rec["view_key"]: rec for rec in recs if rec.get("view_key")}


def _collect_capability_adaptation_ignored(
    *,
    deterministic_snapshot: list[EffectiveManifestView],
    consumer_key: str,
) -> list[IgnoredOverride]:
    ignored: list[IgnoredOverride] = []
    for view in deterministic_snapshot:
        _renderer_type, _renderer_config, adaptation = adapt_renderer_for_consumer(
            renderer_type=view.renderer_type,
            renderer_config=view.renderer_config,
            consumer_key=consumer_key,
        )
        if adaptation is None:
            continue
        ignored.append(
            IgnoredOverride(
                view_key=view.view_key,
                field=adaptation.get("field", "renderer_type"),
                value=adaptation.get("before"),
                reason=adaptation.get("reason", "consumer_capability_adaptation"),
            )
        )
    return ignored


def _diff_snapshots(
    previous: list[EffectiveManifestView],
    current: list[EffectiveManifestView],
    change_reasons: Optional[dict[tuple[str, str], str]] = None,
) -> list[DecisionTraceChange]:
    prev_by_key = {view.view_key: view for view in previous}
    changes: list[DecisionTraceChange] = []
    change_reasons = change_reasons or {}
    fields = (
        "renderer_type",
        "renderer_config",
        "presentation_stance",
        "selection_priority",
        "navigation_state",
        "promoted_to_top_level",
        "display_parent_view_key",
        "structuring_policy",
        "derivation_kind",
        "semantic_scaffold_type",
        "scaffold_hosting_mode",
    )
    for view in current:
        prev = prev_by_key.get(view.view_key)
        if prev is None:
            for field in fields:
                changes.append(
                    DecisionTraceChange(
                        view_key=view.view_key,
                        field=field,
                        before=None,
                        after=getattr(view, field),
                        reason=change_reasons.get((view.view_key, field), ""),
                    )
                )
            continue
        for field in fields:
            before = getattr(prev, field)
            after = getattr(view, field)
            if before != after:
                changes.append(
                    DecisionTraceChange(
                        view_key=view.view_key,
                        field=field,
                        before=before,
                        after=after,
                        reason=change_reasons.get((view.view_key, field), ""),
                    )
                )
    return changes
