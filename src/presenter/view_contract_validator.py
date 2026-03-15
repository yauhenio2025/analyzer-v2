"""Catalog-level validation for curated view/template contracts.

This catches a class of UI failures where a view definition references fields
or section keys that the paired extraction template never emits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from src.transformations.registry import get_transformation_registry
from src.views.registry import get_view_registry

from .composition_resolver import find_applicable_template, resolve_effective_render_contract
from .view_hierarchy import is_chain_container_view


@dataclass
class ShapeNode:
    kind: str
    fields: dict[str, "ShapeNode"] = field(default_factory=dict)
    item: Optional["ShapeNode"] = None


@dataclass
class ContractIssue:
    path: str
    message: str


@dataclass
class ViewContractValidation:
    view_key: str
    template_key: Optional[str]
    renderer_type: str
    valid: bool
    issues: list[ContractIssue] = field(default_factory=list)
    skipped_reason: Optional[str] = None


FIELD_CONFIG_KEYS = (
    "source_field",
    "target_field",
    "from_field",
    "to_field",
    "status_field",
    "type_field",
    "title_field",
    "subtitle_field",
    "badge_field",
    "secondary_badge_field",
    "description_field",
    "detail_field",
    "significance_field",
    "chips_field",
    "flag_field",
    "group_field",
    "intensity_field",
    "count_field",
    "key_field",
    "value_field",
    "label_field",
    "stages_field",
    "left_field",
    "right_field",
    "left_key",
    "right_key",
    "left_title_field",
    "right_title_field",
    "left_description_field",
    "right_description_field",
    "mode_field",
    "phases_field",
)


def validate_view_template_contract(view_def, template, view_registry=None) -> ViewContractValidation:
    """Validate a single curated view/template pair."""
    view_registry = view_registry or get_view_registry()
    composition = resolve_effective_render_contract(
        view_def=view_def,
        rec={"view_key": view_def.view_key},
        consumer_key="the-critic",
        view_registry=view_registry,
    )
    renderer_type = composition.renderer_type
    renderer_config = composition.renderer_config or {}

    root_node = _infer_shape(template.llm_extraction_schema)
    binding = _resolve_binding_node(view_def, template, root_node, view_registry)
    if binding is None:
        return ViewContractValidation(
            view_key=view_def.view_key,
            template_key=template.template_key,
            renderer_type=renderer_type,
            valid=False,
            issues=[ContractIssue(path="root", message="Could not resolve template output shape for view")],
        )

    issues = _validate_renderer_contract(
        renderer_type=renderer_type,
        renderer_config=renderer_config,
        node=binding,
        path=view_def.view_key,
    )

    return ViewContractValidation(
        view_key=view_def.view_key,
        template_key=template.template_key,
        renderer_type=renderer_type,
        valid=not issues,
        issues=issues,
    )


def validate_registered_view_contracts(
    *,
    target_page: Optional[str] = None,
    view_key_prefix: Optional[str] = None,
) -> dict[str, Any]:
    """Validate all active registered view/template pairs with curated templates."""
    view_registry = get_view_registry()
    transform_registry = get_transformation_registry()

    validations: list[ViewContractValidation] = []
    skipped = 0
    for view_def in view_registry.list_all():
        if getattr(view_def, "status", "active") != "active":
            continue
        if target_page and view_def.target_page != target_page:
            continue
        if view_key_prefix and not view_def.view_key.startswith(view_key_prefix):
            continue
        if is_chain_container_view(view_def, view_registry):
            skipped += 1
            continue

        composition = resolve_effective_render_contract(
            view_def=view_def,
            rec={"view_key": view_def.view_key},
            consumer_key="the-critic",
            view_registry=view_registry,
        )
        template = (
            transform_registry.get(composition.template_key)
            if composition.template_key
            else find_applicable_template(view_def=view_def, renderer_type=composition.renderer_type)
        )
        if template is None or template.generation_mode != "curated":
            skipped += 1
            continue

        validations.append(validate_view_template_contract(view_def, template, view_registry=view_registry))

    return {
        "total": len(validations),
        "valid": sum(1 for item in validations if item.valid),
        "invalid": sum(1 for item in validations if not item.valid),
        "skipped": skipped,
        "details": validations,
    }


def _infer_shape(sample: Any) -> ShapeNode:
    if isinstance(sample, list):
        item = _infer_shape(sample[0]) if sample else ShapeNode(kind="unknown")
        return ShapeNode(kind="array", item=item)
    if isinstance(sample, dict):
        return ShapeNode(
            kind="object",
            fields={key: _infer_shape(value) for key, value in sample.items()},
        )
    return ShapeNode(kind="scalar")


def _resolve_binding_node(view_def, template, root_node: ShapeNode, view_registry) -> Optional[ShapeNode]:
    binding = None
    from .view_hierarchy import resolve_parent_section_binding

    binding = resolve_parent_section_binding(view_def, view_registry)
    if binding is not None:
        bound = _resolve_shape_path(root_node, binding["section_key"])
        if bound is not None:
            return bound

    result_path = getattr(getattr(view_def, "data_source", None), "result_path", "") or ""
    return _resolve_shape_path(root_node, result_path)


def _resolve_shape_path(node: Optional[ShapeNode], result_path: str) -> Optional[ShapeNode]:
    if node is None or not result_path:
        return node

    current = node
    for segment in result_path.split("."):
        if current is None:
            return None
        if current.kind == "array" and segment.isdigit():
            current = current.item
            continue
        if current.kind != "object":
            return None
        current = current.fields.get(segment)
    return current


def _validate_renderer_contract(
    *,
    renderer_type: str,
    renderer_config: dict[str, Any],
    node: Optional[ShapeNode],
    path: str,
) -> list[ContractIssue]:
    issues: list[ContractIssue] = []

    if node is None:
        return [ContractIssue(path=path, message="No data shape available for renderer contract")]

    if renderer_type in {"accordion", "tab"}:
        sections = renderer_config.get("sections") or []
        if node.kind != "object":
            issues.append(ContractIssue(path=path, message=f"{renderer_type} expects object-shaped data"))
            return issues

        section_renderers = renderer_config.get("section_renderers") or {}
        for section in sections:
            section_key = section.get("key")
            if not section_key:
                continue
            section_node = node.fields.get(section_key)
            if section_node is None:
                issues.append(
                    ContractIssue(
                        path=f"{path}.{section_key}",
                        message="Section key is not present in extraction schema",
                    )
                )
                continue
            renderer_hint = section_renderers.get(section_key) or {}
            sub_renderer = renderer_hint.get("renderer_type")
            if sub_renderer:
                issues.extend(
                    _validate_renderer_contract(
                        renderer_type=sub_renderer,
                        renderer_config=renderer_hint.get("config") or renderer_hint,
                        node=section_node,
                        path=f"{path}.{section_key}",
                    )
                )
        return issues

    if renderer_type == "nested_sections":
        if node.kind != "object":
            issues.append(ContractIssue(path=path, message="nested_sections expects object-shaped data"))
            return issues
        sub_renderers = renderer_config.get("sub_renderers") or {}
        for child_key, renderer_hint in sub_renderers.items():
            child_node = node.fields.get(child_key)
            if child_node is None:
                issues.append(
                    ContractIssue(
                        path=f"{path}.{child_key}",
                        message="Nested section key is not present in extraction schema",
                    )
                )
                continue
            issues.extend(
                _validate_renderer_contract(
                    renderer_type=renderer_hint.get("renderer_type"),
                    renderer_config=renderer_hint.get("config") or {},
                    node=child_node,
                    path=f"{path}.{child_key}",
                )
            )
        return issues

    issues.extend(_validate_shape_expectation(renderer_type, node, path))
    issues.extend(_validate_field_references(renderer_config, node, path))
    return issues


def _validate_shape_expectation(renderer_type: str, node: ShapeNode, path: str) -> list[ContractIssue]:
    array_renderers = {
        "mini_card_list",
        "concept_dossier_cards",
        "rich_description_list",
        "dimension_analysis_cards",
        "move_repertoire",
        "intensity_matrix",
        "chip_grid",
        "timeline_strip",
        "ordered_flow",
        "dependency_matrix",
        "directional_transfer_list",
    }
    object_or_array_renderers = {"key_value_table", "dialectical_pair", "comparison_panel"}
    object_renderers = {"phase_timeline", "nested_sections"}
    prose_renderers = {"annotated_prose", "prose_block"}

    if renderer_type in array_renderers and node.kind != "array":
        return [ContractIssue(path=path, message=f"{renderer_type} expects an array-shaped section")]
    if renderer_type in object_or_array_renderers and node.kind not in {"array", "object"}:
        return [ContractIssue(path=path, message=f"{renderer_type} expects object- or array-shaped data")]
    if renderer_type in object_renderers and node.kind != "object":
        return [ContractIssue(path=path, message=f"{renderer_type} expects object-shaped data")]
    if renderer_type in prose_renderers and node.kind not in {"scalar", "object"}:
        return [ContractIssue(path=path, message=f"{renderer_type} expects prose text or object data")]
    return []


def _validate_field_references(renderer_config: dict[str, Any], node: ShapeNode, path: str) -> list[ContractIssue]:
    if node.kind == "object" and "phases_field" in renderer_config:
        return _validate_phase_timeline_fields(renderer_config, node, path)
    if node.kind == "object" and "left_key" in renderer_config and "right_key" in renderer_config:
        return _validate_dialectical_pair_fields(renderer_config, node, path)

    issues: list[ContractIssue] = []
    target = _field_target_node(node)
    if target is None:
        return issues

    declared_derived = set(renderer_config.get("derived_fields") or [])

    for key in FIELD_CONFIG_KEYS:
        field_name = renderer_config.get(key)
        if not isinstance(field_name, str) or not field_name or field_name in declared_derived:
            continue
        if field_name.startswith("_"):
            continue
        if field_name not in target.fields:
            issues.append(
                ContractIssue(
                    path=f"{path}.{key}",
                    message=f"Field '{field_name}' is not present in the extracted shape",
                )
            )

    badge_fields = renderer_config.get("badge_fields") or []
    if isinstance(badge_fields, list):
        for field_name in badge_fields:
            if not isinstance(field_name, str) or not field_name or field_name in declared_derived:
                continue
            if field_name not in target.fields:
                issues.append(
                    ContractIssue(
                        path=f"{path}.badge_fields",
                        message=f"Field '{field_name}' is not present in the extracted shape",
                    )
                )

    return issues


def _validate_phase_timeline_fields(
    renderer_config: dict[str, Any],
    node: ShapeNode,
    path: str,
) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    phases_field = renderer_config.get("phases_field")
    if not isinstance(phases_field, str) or phases_field not in node.fields:
        return [ContractIssue(path=f"{path}.phases_field", message="Field is not present in the extracted shape")]

    phase_node = node.fields[phases_field]
    if phase_node.kind != "array" or phase_node.item is None or phase_node.item.kind != "object":
        return [ContractIssue(path=f"{path}.phases_field", message="Field does not resolve to an array of objects")]

    phase_item = phase_node.item
    mode_field = renderer_config.get("mode_field")
    if isinstance(mode_field, str) and mode_field and mode_field not in node.fields:
        issues.append(ContractIssue(path=f"{path}.mode_field", message=f"Field '{mode_field}' is not present in the extracted shape"))

    for key in ("label_field", "description_field"):
        field_name = renderer_config.get(key)
        if isinstance(field_name, str) and field_name and field_name not in phase_item.fields:
            issues.append(ContractIssue(path=f"{path}.{key}", message=f"Field '{field_name}' is not present in the extracted phase shape"))

    return issues


def _validate_dialectical_pair_fields(
    renderer_config: dict[str, Any],
    node: ShapeNode,
    path: str,
) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    left_key = renderer_config.get("left_key")
    right_key = renderer_config.get("right_key")

    for key_name, field_name in (("left_key", left_key), ("right_key", right_key)):
        if isinstance(field_name, str) and field_name and field_name not in node.fields:
            issues.append(ContractIssue(path=f"{path}.{key_name}", message=f"Field '{field_name}' is not present in the extracted shape"))

    if issues:
        return issues

    left_node = node.fields.get(left_key) if isinstance(left_key, str) else None
    right_node = node.fields.get(right_key) if isinstance(right_key, str) else None

    if _is_array_object_node(left_node) and _is_array_object_node(right_node):
        left_item = left_node.item
        right_item = right_node.item
        for key_name, field_name in (
            ("left_title_field", renderer_config.get("left_title_field")),
            ("left_description_field", renderer_config.get("left_description_field")),
        ):
            if isinstance(field_name, str) and field_name and field_name not in left_item.fields:
                issues.append(ContractIssue(path=f"{path}.{key_name}", message=f"Field '{field_name}' is not present in the left-side extracted shape"))
        for key_name, field_name in (
            ("right_title_field", renderer_config.get("right_title_field")),
            ("right_description_field", renderer_config.get("right_description_field")),
        ):
            if isinstance(field_name, str) and field_name and field_name not in right_item.fields:
                issues.append(ContractIssue(path=f"{path}.{key_name}", message=f"Field '{field_name}' is not present in the right-side extracted shape"))
        return issues

    return _validate_generic_object_fields(
        renderer_config=renderer_config,
        node=node,
        path=path,
    )


def _validate_generic_object_fields(
    *,
    renderer_config: dict[str, Any],
    node: ShapeNode,
    path: str,
) -> list[ContractIssue]:
    target = _field_target_node(node)
    if target is None:
        return []

    issues: list[ContractIssue] = []
    declared_derived = set(renderer_config.get("derived_fields") or [])
    for key in FIELD_CONFIG_KEYS:
        field_name = renderer_config.get(key)
        if not isinstance(field_name, str) or not field_name or field_name in declared_derived:
            continue
        if field_name.startswith("_"):
            continue
        if field_name not in target.fields:
            issues.append(
                ContractIssue(
                    path=f"{path}.{key}",
                    message=f"Field '{field_name}' is not present in the extracted shape",
                )
            )

    badge_fields = renderer_config.get("badge_fields") or []
    if isinstance(badge_fields, list):
        for field_name in badge_fields:
            if not isinstance(field_name, str) or not field_name or field_name in declared_derived:
                continue
            if field_name not in target.fields:
                issues.append(
                    ContractIssue(
                        path=f"{path}.badge_fields",
                        message=f"Field '{field_name}' is not present in the extracted shape",
                    )
                )
    return issues


def _field_target_node(node: ShapeNode) -> Optional[ShapeNode]:
    if node.kind == "array":
        return node.item if node.item and node.item.kind == "object" else None
    if node.kind == "object":
        return node
    return None


def _is_array_object_node(node: Optional[ShapeNode]) -> bool:
    return bool(node and node.kind == "array" and node.item and node.item.kind == "object")
