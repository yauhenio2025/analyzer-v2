"""Shared scaffold-contract resolution and validation.

This module keeps scaffold eligibility logic centralized so scaffold generation,
attachment, and freshness computation all consume the same effective contract.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from src.views.registry import get_view_registry

logger = logging.getLogger(__name__)

DECLARED_SCAFFOLD_TYPES = frozenset({"argument_map", "concept_atlas"})
DERIVED_SCAFFOLD_TYPES = frozenset({"composite_overview"})
SUPPORTED_SCAFFOLD_TYPES = DECLARED_SCAFFOLD_TYPES | DERIVED_SCAFFOLD_TYPES

_LEGACY_DECLARED_SCAFFOLD_KEYS = {
    "genealogy_tp_inferential_commitments": "argument_map",
    "genealogy_tp_conceptual_framework": "concept_atlas",
    "genealogy_tp_semantic_constellation": "concept_atlas",
}


@dataclass
class ScaffoldContractIssue:
    view_key: str
    message: str


@dataclass
class ScaffoldContractValidationResult:
    total_declared: int
    valid: int
    invalid: int
    issues: list[ScaffoldContractIssue] = field(default_factory=list)


def resolve_declared_scaffold_type(view_def: Any) -> Optional[str]:
    """Resolve the declared scaffold contract for a view definition.

    During the transition away from generic surface hints, allow legacy
    `surface_archetype` values for declared leaf scaffold types, but treat the
    explicit `scaffold_contract` as the authoritative source.
    """

    if view_def is None:
        return None

    contract = getattr(view_def, "scaffold_contract", None)
    contract_type = getattr(contract, "type", None)
    if contract_type in DECLARED_SCAFFOLD_TYPES:
        return contract_type

    archetype = getattr(view_def, "surface_archetype", None)
    if archetype in DECLARED_SCAFFOLD_TYPES:
        return archetype

    return None


def resolve_effective_scaffold_type(
    *,
    view_def: Any,
    has_logical_children: bool,
    chain_key: Optional[str],
    density_ok: bool,
) -> Optional[str]:
    """Resolve the effective scaffold type for a view.

    Phase 1 scope is intentionally narrow:
    - declared `scaffold_contract` for leaf scaffold types
    - derived `composite_overview` for dense parent surfaces
    """

    declared = resolve_declared_scaffold_type(view_def)
    if declared and density_ok:
        return declared

    if has_logical_children and (bool(chain_key) or density_ok):
        return "composite_overview"

    return None


def resolve_effective_scaffold_type_for_payload(
    payload: Any,
    payload_by_key: dict[str, Any],
    *,
    density_ok: bool,
) -> Optional[str]:
    """Resolve scaffold type for an assembled payload tree."""

    view_def = get_view_registry().get(payload.view_key)
    has_logical_children = any(
        getattr(child, "source_parent_view_key", None) == payload.view_key
        for child in payload_by_key.values()
    )
    return resolve_effective_scaffold_type(
        view_def=view_def,
        has_logical_children=has_logical_children,
        chain_key=getattr(payload, "chain_key", None),
        density_ok=density_ok,
    )


def validate_registered_scaffold_contracts() -> ScaffoldContractValidationResult:
    """Validate declared scaffold contracts and rollout coverage.

    Invalid scaffold metadata should fail fast at startup. During the migration
    away from legacy hard-coded key lists, also require the previously covered
    curated views to carry an explicit declared scaffold contract.
    """

    from .scaffold_generator import SCAFFOLD_PROMPT_VERSIONS

    issues: list[ScaffoldContractIssue] = []
    registry = get_view_registry()
    views = registry.list_all()
    declared_total = 0

    for view_def in views:
        contract = getattr(view_def, "scaffold_contract", None)
        contract_type = getattr(contract, "type", None)
        if contract_type is None:
            continue
        declared_total += 1
        if contract_type not in DECLARED_SCAFFOLD_TYPES:
            issues.append(
                ScaffoldContractIssue(
                    view_key=view_def.view_key,
                    message=f"Unknown declared scaffold_contract.type '{contract_type}'",
                )
            )
            continue
        if contract_type not in SCAFFOLD_PROMPT_VERSIONS:
            issues.append(
                ScaffoldContractIssue(
                    view_key=view_def.view_key,
                    message=f"No scaffold prompt family registered for '{contract_type}'",
                )
            )

    for view_key, expected_type in _LEGACY_DECLARED_SCAFFOLD_KEYS.items():
        view_def = registry.get(view_key)
        if view_def is None:
            issues.append(
                ScaffoldContractIssue(
                    view_key=view_key,
                    message="Expected scaffolded view is not registered",
                )
            )
            continue
        contract_type = getattr(getattr(view_def, "scaffold_contract", None), "type", None)
        if contract_type != expected_type:
            issues.append(
                ScaffoldContractIssue(
                    view_key=view_key,
                    message=(
                        f"Expected scaffold_contract.type='{expected_type}' "
                        f"for migrated scaffolded view"
                    ),
                )
            )

    return ScaffoldContractValidationResult(
        total_declared=declared_total,
        valid=max(declared_total - len([issue for issue in issues if issue.view_key not in _LEGACY_DECLARED_SCAFFOLD_KEYS]), 0),
        invalid=len(issues),
        issues=issues,
    )
