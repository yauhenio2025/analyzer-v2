"""Shared view-hierarchy helpers for composition and task planning."""

from __future__ import annotations

import re
from typing import Iterable


def iter_active_child_views(view_registry, parent_view_key: str) -> list:
    """Return active child view definitions for a parent."""
    return [
        view_def
        for view_def in view_registry.list_all()
        if getattr(view_def, "status", "active") == "active"
        and getattr(view_def, "parent_view_key", None) == parent_view_key
    ]


def has_active_child_views(view_registry, parent_view_key: str) -> bool:
    """True when the view acts as a container for active child views."""
    return any(iter_active_child_views(view_registry, parent_view_key))


def is_chain_container_view(view_def, view_registry) -> bool:
    """True when a view is a chain-backed analytical container."""
    ds = getattr(view_def, "data_source", None)
    if ds is None:
        return False
    return (
        getattr(ds, "chain_key", None)
        and not getattr(ds, "engine_key", None)
        and getattr(ds, "scope", None) == "aggregated"
        and getattr(getattr(view_def, "transformation", None), "type", "none") == "none"
        and has_active_child_views(view_registry, view_def.view_key)
    )


def match_container_sections_to_children(parent_view_def, child_views: Iterable) -> dict[str, object]:
    """Match parent section keys to the most likely child views.

    Uses conservative identifier matching so chain-backed container views can
    synthesize section data from child payloads without hardcoding genealogy-
    specific names.
    """
    sections = getattr(parent_view_def, "renderer_config", {}).get("sections", []) or []
    remaining_children = list(child_views)
    matches: dict[str, object] = {}

    for section in sections:
        section_key = section.get("key")
        if not section_key:
            continue

        scored = []
        for child_view in remaining_children:
            score = _score_child_for_section(section_key, child_view)
            if score > 0:
                scored.append((score, child_view))

        if not scored:
            continue

        scored.sort(key=lambda item: item[0], reverse=True)
        best_child = scored[0][1]
        matches[section_key] = best_child
        remaining_children = [child for child in remaining_children if child != best_child]

    return matches


def resolve_parent_section_binding(view_def, view_registry) -> dict[str, object] | None:
    """Resolve the parent section metadata for a nested child view.

    This lets the presenter treat standalone child tabs as first-class views of
    the same section contract already declared on the parent container.
    """
    parent_key = getattr(view_def, "parent_view_key", None)
    if not parent_key:
        return None

    parent_view = view_registry.get(parent_key)
    if parent_view is None:
        return None

    parent_config = getattr(parent_view, "renderer_config", {}) or {}
    sections = parent_config.get("sections", []) or []
    section_renderers = parent_config.get("section_renderers", {}) or {}
    if not sections:
        return None

    section_by_key = {
        section.get("key"): section
        for section in sections
        if isinstance(section, dict) and section.get("key")
    }
    candidate_keys: list[str] = []

    result_path = getattr(getattr(view_def, "data_source", None), "result_path", "") or ""
    if result_path:
        candidate_keys.append(result_path)

    child_views = iter_active_child_views(view_registry, parent_key)
    matches = match_container_sections_to_children(parent_view, child_views)
    for section_key, child_view in matches.items():
        if getattr(child_view, "view_key", None) == getattr(view_def, "view_key", None):
            candidate_keys.append(section_key)

    seen: set[str] = set()
    for section_key in candidate_keys:
        if not section_key or section_key in seen:
            continue
        seen.add(section_key)

        section = section_by_key.get(section_key)
        if section is None:
            continue

        return {
            "parent_view_key": parent_key,
            "parent_view_name": getattr(parent_view, "view_name", ""),
            "section_key": section_key,
            "section_title": section.get("title") or section_key.replace("_", " ").title(),
            "renderer_hint": section_renderers.get(section_key) or {},
        }

    return None


def _normalize_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")


def _score_child_for_section(section_key: str, child_view) -> int:
    section_norm = _normalize_identifier(section_key)
    if not section_norm:
        return 0

    view_key_norm = _normalize_identifier(getattr(child_view, "view_key", ""))
    view_name_norm = _normalize_identifier(getattr(child_view, "view_name", ""))
    candidates = [view_key_norm, view_name_norm]

    best = 0
    section_tokens = [token for token in section_norm.split("_") if token]

    for candidate in candidates:
        if not candidate:
            continue
        if candidate == section_norm:
            best = max(best, 600 + len(section_norm))
        if candidate.endswith(section_norm):
            best = max(best, 500 + len(section_norm))
        if f"_{section_norm}_" in f"_{candidate}_":
            best = max(best, 450 + len(section_norm))
        if section_norm in candidate:
            best = max(best, 350 + len(section_norm))

        candidate_tokens = [token for token in candidate.split("_") if token]
        if section_tokens and all(token in candidate_tokens for token in section_tokens):
            best = max(best, 300 + len(section_tokens))

    return best
