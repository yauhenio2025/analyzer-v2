"""Consumer-scoped delivery styling for ordinary presenter pages.

This module keeps semantic manifest/trace truth separate from delivery-layer
polish. Only explicit workflow/page/consumer activation entries participate in
ordinary-path cached polish.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .polish_store import load_polish_cache, save_polish_cache
from .polisher import compute_config_hash, polish_view
from .schemas import ViewPayload

logger = logging.getLogger(__name__)

AUTO_STYLE_ACTIVATIONS: dict[tuple[str, str, str], str] = {
    (
        "anxiety_of_influence_thematic_single_thinker",
        "aoi_thematic_analysis",
        "aoi-canary",
    ): "explanatory_narrative",
}


def collect_view_keys(views: list[ViewPayload]) -> list[str]:
    keys: list[str] = []
    for view in views:
        keys.append(view.view_key)
        keys.extend(collect_view_keys(view.children or []))
    return keys


def resolve_page_style_school(
    *,
    workflow_key: str,
    root_view_key: str,
    consumer_key: str,
) -> str:
    return AUTO_STYLE_ACTIVATIONS.get((workflow_key, root_view_key, consumer_key), "")


def apply_cached_polish_to_views(
    *,
    job_id: str,
    consumer_key: str,
    style_school: str,
    views: list[ViewPayload],
) -> tuple[list[ViewPayload], str]:
    copied = [view.model_copy(deep=True) for view in views]
    if not style_school:
        return copied, "raw"

    total_views = 0
    polished_views = 0

    def _walk(nodes: list[ViewPayload]) -> None:
        nonlocal total_views, polished_views
        for node in nodes:
            total_views += 1
            expected_hash = compute_config_hash(node.renderer_config or {})
            cached = load_polish_cache(
                job_id=job_id,
                view_key=node.view_key,
                consumer_key=consumer_key,
                style_school=style_school,
                expected_config_hash=expected_hash,
            )
            if cached is not None:
                polished_views += 1
                node.renderer_config = _merge_cached_polish_into_config(
                    base_config=node.renderer_config,
                    polished_payload=cached["polished_data"],
                )
            if node.children:
                _walk(node.children)

    _walk(copied)
    return copied, _derive_polish_state(total_views=total_views, polished_views=polished_views)


def seed_polish_cache_for_page(
    *,
    job_id: str,
    consumer_key: str,
    force: bool = False,
) -> dict[str, Any]:
    from .presentation_api import assemble_page
    from .presentation_api import _resolve_workflow_key
    from src.executor.job_manager import get_job

    page = assemble_page(job_id, consumer_key=consumer_key, slim=True)
    job = get_job(job_id)
    workflow_key = _resolve_workflow_key(job) if job is not None else ""
    root_view_key = page.views[0].view_key if page.views else ""
    style_school = resolve_page_style_school(
        workflow_key=workflow_key,
        root_view_key=root_view_key,
        consumer_key=consumer_key,
    )
    if not style_school:
        return {
            "activated": False,
            "style_school": "",
            "polished": 0,
            "cached": 0,
            "failed": 0,
            "total_views": 0,
        }

    result = seed_polish_cache_for_views(
        job_id=job_id,
        consumer_key=consumer_key,
        view_keys=collect_view_keys(page.views),
        style_school=style_school,
        force=force,
    )
    result["activated"] = True
    return result


def seed_polish_cache_for_views(
    *,
    job_id: str,
    consumer_key: str,
    view_keys: list[str],
    style_school: Optional[str] = None,
    force: bool = False,
) -> dict[str, Any]:
    from .presentation_api import assemble_single_view

    polished = 0
    cached_hits = 0
    failed = 0
    resolved_schools: list[str] = []

    for view_key in view_keys:
        payload = assemble_single_view(job_id, view_key, consumer_key=consumer_key)
        if payload is None:
            failed += 1
            continue

        config_hash = compute_config_hash(payload.renderer_config or {})
        cached = None
        if not force:
            cached = load_polish_cache(
                job_id=job_id,
                view_key=view_key,
                consumer_key=consumer_key,
                style_school=style_school,
                expected_config_hash=config_hash,
            )
        if cached is not None:
            cached_hits += 1
            resolved_schools.append(cached["style_school"])
            continue

        try:
            result = polish_view(
                payload=payload,
                engine_key=payload.engine_key,
                style_school=style_school,
            )
            save_polish_cache(
                job_id=job_id,
                view_key=view_key,
                consumer_key=consumer_key,
                style_school=result.style_school,
                polished_data=result.polished_payload.model_dump(),
                config_hash=config_hash,
                model_used=result.model_used,
                tokens_used=result.tokens_used,
            )
            resolved_schools.append(result.style_school)
            polished += 1
        except Exception as exc:
            failed += 1
            logger.warning(
                "[delivery-style] Failed to seed polish for %s/%s/%s: %s",
                job_id,
                consumer_key,
                view_key,
                exc,
            )

    return {
        "activated": bool(style_school),
        "style_school": style_school or (resolved_schools[0] if resolved_schools else ""),
        "polished": polished,
        "cached": cached_hits,
        "failed": failed,
        "total_views": len(view_keys),
    }


def _merge_cached_polish_into_config(
    *,
    base_config: Optional[dict[str, Any]],
    polished_payload: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(polished_payload.get("polished_renderer_config") or base_config or {})
    style_overrides = polished_payload.get("style_overrides") or {}
    section_descriptions = polished_payload.get("section_descriptions") or {}
    if style_overrides:
        merged["_style_overrides"] = style_overrides
    if section_descriptions:
        merged["_section_descriptions"] = section_descriptions
    return merged


def _derive_polish_state(*, total_views: int, polished_views: int) -> str:
    if polished_views <= 0:
        return "raw"
    if polished_views >= total_views:
        return "polished"
    return "partial"
