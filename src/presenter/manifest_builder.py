"""Build the effective consumer-scoped semantic manifest for presentation."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Optional

from src.consumers.registry import get_consumer_registry
from src.renderers.registry import get_renderer_registry

from .scaffold_generator import resolve_scaffold_type
from .schemas import EffectiveManifestView, EffectivePresentationManifest, ViewPayload
from .view_hierarchy import is_chain_container_view, iter_active_child_views

MANIFEST_SCHEMA_VERSION = 1
TRACE_SCHEMA_VERSION = 1
RESOLVER_VERSION = "bounded-dynamism-phase2"
ALLOWED_SELECTION_PRIORITIES = {"primary", "secondary", "optional", "hidden"}
ALLOWED_NAVIGATION_STATES = {"normal", "collapsed_into_parent"}
PHASE2A_STRUCTURING_VIEW_KEYS = {
    "genealogy_target_profile",
    "genealogy_text_profiling",
}
DERIVATION_KIND_AUTO_CHAPTER = "auto_generated_chapter"
DERIVATION_KIND_CHILD_SYNTHESIZED = "child_synthesized"
DERIVATION_KIND_DIRECT_PARENT_DATA = "direct_parent_data"


def normalize_selection_priority(priority: Optional[str]) -> str:
    if priority in ALLOWED_SELECTION_PRIORITIES:
        return priority
    return "secondary"


def normalize_navigation_state(*, collapse_into_parent: bool) -> str:
    return "collapsed_into_parent" if collapse_into_parent else "normal"


def derive_legacy_visibility(
    *,
    authored_visibility: Optional[str],
    selection_priority: str,
    navigation_state: str,
) -> str:
    if navigation_state == "collapsed_into_parent":
        return "on_demand"
    if authored_visibility == "on_demand":
        return "on_demand"
    if selection_priority in {"optional", "hidden"}:
        return "on_demand"
    return authored_visibility or "if_data_exists"


def normalize_structuring_policy(
    *,
    view_def: Any,
) -> Optional[str]:
    if getattr(view_def, "view_key", None) not in PHASE2A_STRUCTURING_VIEW_KEYS:
        return None

    if (
        getattr(view_def, "surface_archetype", None) == "composite_overview"
        and getattr(view_def, "surface_role", None) == "parent_surface"
        and getattr(view_def, "child_display_mode", None) == "deep_dives"
    ):
        return "overview_parent"

    return "skip_parent"


def derive_view_derivation_kind(
    *,
    view_def: Any,
    payload: Optional[ViewPayload] = None,
    view_registry: Any = None,
) -> Optional[str]:
    if payload is not None and payload.view_key.startswith("auto_chapter_"):
        return DERIVATION_KIND_AUTO_CHAPTER

    if getattr(view_def, "view_key", None) not in PHASE2A_STRUCTURING_VIEW_KEYS:
        return None

    if view_registry is None:
        return None

    if is_chain_container_view(view_def, view_registry):
        return DERIVATION_KIND_CHILD_SYNTHESIZED

    ds = getattr(view_def, "data_source", None)
    if ds is None:
        return None

    if getattr(ds, "engine_key", None) and iter_active_child_views(view_registry, view_def.view_key):
        return DERIVATION_KIND_DIRECT_PARENT_DATA

    return None


def adapt_renderer_for_consumer(
    *,
    renderer_type: str,
    renderer_config: dict[str, Any],
    consumer_key: str,
) -> tuple[str, dict[str, Any], Optional[dict[str, Any]]]:
    """Return a consumer-supported renderer contract plus an adaptation report."""

    consumer = get_consumer_registry().get(consumer_key)
    if consumer is None:
        return renderer_type, renderer_config, None

    supported_renderers = set(consumer.supported_renderers or [])
    supported_sub_renderers = set(consumer.supported_sub_renderers or [])
    if renderer_type in supported_renderers or renderer_type in supported_sub_renderers:
        return renderer_type, renderer_config, None

    fallback_renderer = "raw_json" if "raw_json" in supported_renderers else renderer_type
    if fallback_renderer == renderer_type:
        return renderer_type, renderer_config, None

    return (
        fallback_renderer,
        {},
        {
            "field": "renderer_type",
            "before": renderer_type,
            "after": fallback_renderer,
            "reason": f"renderer_not_supported_by_consumer:{consumer_key}",
        },
    )


def derive_scaffold_hosting_mode(
    *,
    renderer_type: str,
    semantic_scaffold_type: str,
) -> str:
    if semantic_scaffold_type == "none":
        return "none"

    renderer_def = get_renderer_registry().get(renderer_type)
    if renderer_def and getattr(renderer_def, "integrates_scaffold", False):
        return "integrated"
    return "fallback"


def build_effective_manifest(
    *,
    job_id: str,
    plan_id: str,
    consumer_key: str,
    thinker_name: str,
    strategy_summary: str,
    payloads: dict[str, ViewPayload],
    all_outputs: list[dict[str, Any]],
    job: dict[str, Any],
) -> EffectivePresentationManifest:
    """Build the single capability-adapted semantic manifest for a page."""

    ordered_payloads = sorted(payloads.values(), key=lambda payload: (payload.position, payload.view_key))
    manifest_views: list[EffectiveManifestView] = []
    artifacts_ready = True

    for payload in ordered_payloads:
        renderer_type, renderer_config, _adaptation = adapt_renderer_for_consumer(
            renderer_type=payload.renderer_type,
            renderer_config=payload.renderer_config,
            consumer_key=consumer_key,
        )
        semantic_scaffold_type = resolve_scaffold_type(payload, payloads) or "none"
        scaffold_hosting_mode = derive_scaffold_hosting_mode(
            renderer_type=renderer_type,
            semantic_scaffold_type=semantic_scaffold_type,
        )
        display_parent_view_key = (
            None if getattr(payload, "promoted_to_top_level", False)
            else getattr(payload, "source_parent_view_key", None)
        )
        child_view_keys = sorted(child.view_key for child in (payload.children or []))

        manifest_view = EffectiveManifestView(
            view_key=payload.view_key,
            view_name=payload.view_name,
            description=payload.description,
            renderer_type=renderer_type,
            renderer_config=renderer_config,
            presentation_stance=payload.presentation_stance,
            selection_priority=payload.selection_priority or normalize_selection_priority(payload.priority),
            navigation_state=payload.navigation_state or "normal",
            promoted_to_top_level=bool(payload.promoted_to_top_level),
            source_parent_view_key=payload.source_parent_view_key,
            display_parent_view_key=display_parent_view_key,
            child_view_keys=child_view_keys,
            top_level_group=payload.top_level_group,
            position=payload.position,
            semantic_scaffold_type=semantic_scaffold_type,
            scaffold_hosting_mode=scaffold_hosting_mode,
            structuring_policy=payload.structuring_policy,
            derivation_kind=payload.derivation_kind or _derive_derivation_kind(payload),
            legacy_visibility=payload.visibility,
        )
        manifest_views.append(manifest_view)

        payload.selection_priority = manifest_view.selection_priority
        payload.navigation_state = manifest_view.navigation_state
        payload.renderer_type = manifest_view.renderer_type
        payload.renderer_config = manifest_view.renderer_config
        payload.semantic_scaffold_type = semantic_scaffold_type
        payload.scaffold_hosting_mode = scaffold_hosting_mode
        payload.structuring_policy = manifest_view.structuring_policy
        payload.derivation_kind = manifest_view.derivation_kind

        output_hashes = _collect_output_hashes_for_payload(payload, all_outputs)
        if _is_required_default_payload(payload) and not _is_payload_ready_for_default_page(
            payload,
            scaffold_type=semantic_scaffold_type,
            output_hashes=output_hashes,
        ):
            artifacts_ready = False

    contract_manifest = {
        "consumer_key": consumer_key,
        "views": [_manifest_identity_row(view) for view in manifest_views],
    }
    content_manifest = {
        "consumer_key": consumer_key,
        "views": [
            {
                "view_key": payload.view_key,
                "structured_data": payload.structured_data,
                "items": payload.items,
                "reading_scaffold": payload.reading_scaffold,
                "output_hashes": _collect_output_hashes_for_payload(payload, all_outputs),
            }
            for payload in ordered_payloads
        ],
    }

    return EffectivePresentationManifest(
        job_id=job_id,
        plan_id=plan_id,
        consumer_key=consumer_key,
        presentation_contract_version=1,
        presentation_hash=_stable_fingerprint(contract_manifest),
        presentation_content_hash=_stable_fingerprint(content_manifest),
        prepared_at=_resolve_prepared_at(job, all_outputs),
        artifacts_ready=artifacts_ready,
        manifest_schema_version=MANIFEST_SCHEMA_VERSION,
        trace_schema_version=TRACE_SCHEMA_VERSION,
        resolver_version=RESOLVER_VERSION,
        thinker_name=thinker_name,
        strategy_summary=strategy_summary,
        views=manifest_views,
        view_count=len(manifest_views),
    )


def _manifest_identity_row(view: EffectiveManifestView) -> dict[str, Any]:
    return {
        "view_key": view.view_key,
        "renderer_type": view.renderer_type,
        "renderer_config": view.renderer_config,
        "presentation_stance": view.presentation_stance,
        "selection_priority": view.selection_priority,
        "navigation_state": view.navigation_state,
        "promoted_to_top_level": view.promoted_to_top_level,
        "source_parent_view_key": view.source_parent_view_key,
        "display_parent_view_key": view.display_parent_view_key,
        "child_view_keys": view.child_view_keys,
        "top_level_group": view.top_level_group,
        "position": view.position,
        "semantic_scaffold_type": view.semantic_scaffold_type,
        "scaffold_hosting_mode": view.scaffold_hosting_mode,
        "structuring_policy": view.structuring_policy,
        "derivation_kind": view.derivation_kind,
    }


def _derive_derivation_kind(payload: ViewPayload) -> Optional[str]:
    if payload.view_key.startswith("auto_chapter_"):
        return DERIVATION_KIND_AUTO_CHAPTER
    return None


def _stable_fingerprint(value: Any) -> str:
    serialized = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _collect_output_hashes_for_payload(
    payload: ViewPayload,
    all_outputs: list[dict[str, Any]],
) -> list[str]:
    phase_number = getattr(payload, "phase_number", None)
    if phase_number is None:
        return []

    engine_key = getattr(payload, "engine_key", None)
    relevant = [
        output
        for output in all_outputs
        if output.get("phase_number") == phase_number
        and ((engine_key and output.get("engine_key") == engine_key) or (not engine_key))
    ]
    unique_hashes = {
        output.get("content_hash") or ""
        for output in relevant
        if output.get("content_hash")
    }
    return sorted(unique_hashes)


def _is_required_default_payload(payload: ViewPayload) -> bool:
    return getattr(payload, "visibility", "if_data_exists") != "on_demand"


def _is_payload_ready_for_default_page(
    payload: ViewPayload,
    *,
    scaffold_type: Optional[str],
    output_hashes: list[str],
) -> bool:
    if scaffold_type and scaffold_type != "none" and payload.reading_scaffold is None:
        return False

    if payload.items is not None:
        if not payload.items:
            return False
        if any(bool(item.get("has_structured_data")) for item in payload.items if isinstance(item, dict)):
            return True
        return bool(output_hashes)

    if payload.has_structured_data:
        return True

    return bool(output_hashes)


def _timestamp_sort_value(value: Any) -> str:
    """Normalize mixed DB/API timestamp shapes into a comparable ISO string."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        dt = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return dt.astimezone(UTC).isoformat()
    if isinstance(value, str):
        return value
    return str(value)


def _resolve_prepared_at(job: dict[str, Any], all_outputs: list[dict[str, Any]]) -> str:
    timestamps = [
        _timestamp_sort_value(output.get("created_at"))
        for output in all_outputs
        if output.get("created_at")
    ]
    for field in ("completed_at", "started_at", "created_at"):
        value = _timestamp_sort_value(job.get(field))
        if value:
            timestamps.append(value)
    return max(timestamps) if timestamps else datetime.now(UTC).isoformat()
