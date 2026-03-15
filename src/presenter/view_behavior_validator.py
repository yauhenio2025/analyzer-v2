"""Raw registered-view behavior validation for renderer policy defaults.

This validator intentionally inspects raw registered view definitions rather than
effective/composed render contracts. The goal is to catch missing explicit
declarations in the registry itself before runtime composition papers over them.

Scope for this tranche:
- active registered `card_grid` views only
- explicit outer-card behavior in raw renderer_config

Residual risk:
- runtime refinement and selected-variant paths can still switch a different
  renderer into `card_grid` after registry load; that is intentionally out of
  scope for this validator and should be treated as a follow-on policy gate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from src.views.registry import get_view_registry


@dataclass(frozen=True)
class ViewBehaviorIssue:
    view_key: str
    path: str
    message: str


CARD_GRID_SCOPE = "raw_registered_views_only"
CARD_GRID_RESIDUAL_RISK = (
    "runtime refinement and variant overrides can still switch a non-card_grid "
    "view into card_grid after registry load"
)


def validate_registered_card_grid_behavior_policies() -> dict[str, Any]:
    """Validate raw registered card-grid behavior declarations."""
    issues: list[ViewBehaviorIssue] = []
    total = 0

    for view_def in get_view_registry().list_all():
        if getattr(view_def, "status", "active") != "active":
            continue
        if view_def.renderer_type != "card_grid":
            continue

        total += 1
        issues.extend(_validate_card_grid_behavior(view_def))

    failing_views = {issue.view_key for issue in issues}
    return {
        "scope": CARD_GRID_SCOPE,
        "residual_risk": CARD_GRID_RESIDUAL_RISK,
        "total": total,
        "valid": total - len(failing_views),
        "invalid": len(failing_views),
        "issues": [asdict(issue) for issue in issues],
    }


def _validate_card_grid_behavior(view_def: Any) -> list[ViewBehaviorIssue]:
    renderer_config = getattr(view_def, "renderer_config", None) or {}
    issues: list[ViewBehaviorIssue] = []

    if "expandable" not in renderer_config or not isinstance(renderer_config.get("expandable"), bool):
        issues.append(
            ViewBehaviorIssue(
                view_key=view_def.view_key,
                path="renderer_config.expandable",
                message="card_grid views must declare expandable explicitly as a boolean",
            )
        )

    group_by = renderer_config.get("group_by")
    has_explicit_group_by = isinstance(group_by, str) and bool(group_by.strip())
    if "group_style_map" in renderer_config and not has_explicit_group_by:
        issues.append(
            ViewBehaviorIssue(
                view_key=view_def.view_key,
                path="renderer_config.group_style_map",
                message="group_style_map requires an explicit non-empty group_by in raw view config",
            )
        )

    return issues
