"""Baseline view recommendations when a plan does not carry recommended_views.

Older or imported jobs may have workflow execution plans without any
presentation recommendations. In that case we synthesize a bounded default
from the workflow's target page rather than falling back to every active
view in the workflow.
"""

from __future__ import annotations

from typing import Any


def _fallback_page_for_workflow(workflow_key: str) -> str:
    from src.workflows.registry import get_workflow_registry

    workflow = get_workflow_registry().get(workflow_key)
    if workflow and getattr(workflow, "target_page", ""):
        return workflow.target_page
    return workflow_key.replace("_", "-").removeprefix("intellectual-") or "genealogy"


def _flatten_composed_views(views: list[Any], *, depth: int = 0) -> list[dict]:
    rows: list[dict] = []
    for view in views:
        priority = "primary" if depth == 0 and getattr(view, "visibility", "default") == "default" else "secondary"
        rows.append(
            {
                "view_key": view.view_key,
                "priority": priority,
                "rationale": "Workflow page default",
            }
        )
        rows.extend(_flatten_composed_views(getattr(view, "children", []), depth=depth + 1))
    return rows


def get_default_recommendations_for_workflow(
    workflow_key: str,
    *,
    consumer_key: str = "the-critic",
) -> list[dict]:
    from src.views.registry import get_view_registry

    page = _fallback_page_for_workflow(workflow_key)
    composed = get_view_registry().compose_tree(consumer_key, page)
    return _flatten_composed_views(composed.views)
