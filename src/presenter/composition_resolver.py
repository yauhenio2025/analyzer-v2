"""Resolve effective presentation settings for a view.

Combines:
- static view defaults
- refinement overrides
- transformation template presets
- user-selected A/B variants

This keeps assembly and transformation task planning in sync so dynamic
composition choices are applied consistently across the presenter.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Optional
from types import SimpleNamespace

from src.chains.registry import get_chain_registry
from src.transformations.registry import get_transformation_registry

from .runtime_override_validator import validate_runtime_overrides, validate_variant_patch
from .view_hierarchy import resolve_parent_section_binding
from .variant_store import load_selected_variants


@dataclass
class EffectiveComposition:
    renderer_type: str
    renderer_config: dict[str, Any] = field(default_factory=dict)
    presentation_stance: Optional[str] = None
    data_quality: str = "standard"
    template_key: Optional[str] = None
    template_selection_reason: Optional[str] = None
    dropped_overrides: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class TemplateSelection:
    template: Any
    reason: str


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge dicts. Lists/scalars replace the base value."""
    result = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _fill_missing(base: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    """Recursively fill missing keys from defaults without overwriting existing values."""
    result = deepcopy(base)
    for key, value in defaults.items():
        if key not in result:
            result[key] = deepcopy(value)
        elif isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _fill_missing(result[key], value)
    return result


def _template_priority_key(template: Any, *, renderer_type: str) -> tuple[int, int, int, int, str]:
    preset = (getattr(template, "renderer_config_presets", None) or {}).get(renderer_type) or {}
    preset_rank = 1 if preset else 0
    generation_mode = getattr(template, "generation_mode", "generated")
    generation_rank = {
        "curated": 2,
        "hybrid": 1,
        "generated": 0,
    }.get(generation_mode, 0)
    version = int(getattr(template, "version", 0) or 0)
    selection_priority = int(getattr(template, "selection_priority", 0) or 0)
    template_key = getattr(template, "template_key", "")
    return (selection_priority, preset_rank, generation_rank, version, template_key)


def select_applicable_template(view_def, renderer_type: Optional[str] = None) -> Optional[TemplateSelection]:
    """Select an applicable template deterministically.

    For chain-backed views, preserve chain engine order and rank only within each
    engine bucket. For single-engine views, rank within that single bucket.
    """
    target_renderer = renderer_type or view_def.renderer_type
    ds = view_def.data_source
    engine_key = ds.engine_key
    chain_key = ds.chain_key

    search_engine_keys: list[str] = []
    if engine_key:
        search_engine_keys = [engine_key]
    elif chain_key:
        chain = get_chain_registry().get(chain_key)
        if chain:
            search_engine_keys = list(chain.engine_keys)

    registry = get_transformation_registry()
    for candidate_engine in search_engine_keys:
        applicable = [
            template
            for template in registry.for_engine(candidate_engine)
            if target_renderer in template.applicable_renderer_types
        ]
        if not applicable:
            continue
        ranked = sorted(
            applicable,
            key=lambda template: _template_priority_key(template, renderer_type=target_renderer),
            reverse=True,
        )
        selected = ranked[0]
        preset = (getattr(selected, "renderer_config_presets", None) or {}).get(target_renderer) or {}
        return TemplateSelection(
            template=selected,
            reason=(
                f"template_key={getattr(selected, 'template_key', '')};"
                f"engine_bucket={candidate_engine};selection_priority="
                f"{int(getattr(selected, 'selection_priority', 0) or 0)};"
                f"preset_match={'yes' if preset else 'no'};"
                f"generation_mode={getattr(selected, 'generation_mode', 'generated')};"
                f"version={int(getattr(selected, 'version', 0) or 0)}"
            ),
        )
    return None


def find_applicable_template(view_def, renderer_type: Optional[str] = None):
    """Back-compat wrapper returning only the selected template."""
    selection = select_applicable_template(view_def, renderer_type=renderer_type)
    return selection.template if selection else None


def resolve_effective_composition(
    view_def,
    rec: Optional[dict] = None,
    consumer_key: str = "the-critic",
    job_id: Optional[str] = None,
) -> EffectiveComposition:
    """Resolve the effective renderer/config/stance for a view."""
    rec = rec or {}
    validation = validate_runtime_overrides(
        view_def=view_def,
        rec=rec,
        consumer_key=consumer_key,
    )

    refined_renderer = validation.renderer_type_override or view_def.renderer_type
    selected_variants = load_selected_variants(job_id, view_def.view_key) if job_id else []
    selection_by_dimension: dict[str, dict[str, Any]] = {}
    for row in selected_variants:
        selection_by_dimension.setdefault(row["dimension"], row)

    renderer_variant = selection_by_dimension.get("renderer_type")
    sub_renderer_variant = selection_by_dimension.get("sub_renderer_strategy")
    dropped_overrides = [
        {
            "field": dropped.field,
            "value": dropped.value,
            "reason": dropped.reason,
        }
        for dropped in validation.dropped_overrides
    ]

    renderer_variant_validation = None
    if renderer_variant:
        renderer_variant_validation = validate_variant_patch(
            view_def=view_def,
            renderer_type_override=renderer_variant.get("renderer_type"),
            renderer_config_overrides=renderer_variant.get("renderer_config") or {},
            consumer_key=consumer_key,
        )
        dropped_overrides.extend(
            {
                "field": dropped.field,
                "value": dropped.value,
                "reason": dropped.reason,
            }
            for dropped in renderer_variant_validation.dropped_overrides
        )

    final_renderer = (
        renderer_variant_validation.renderer_type_override
        if renderer_variant and renderer_variant_validation and renderer_variant_validation.renderer_type_override
        else refined_renderer
    )

    renderer_switched = final_renderer != view_def.renderer_type
    if renderer_switched:
        base_config: dict[str, Any] = {}
    else:
        base_config = deepcopy(view_def.renderer_config)

    template_selection = select_applicable_template(view_def, final_renderer)
    template = template_selection.template if template_selection else None
    preset = {}
    if template and template.renderer_config_presets:
        preset = deepcopy(template.renderer_config_presets.get(final_renderer) or {})

    if renderer_switched:
        resolved_config = _deep_merge(base_config, preset)
    else:
        resolved_config = _fill_missing(base_config, preset)

    refinement_overrides = validation.renderer_config_overrides
    if refinement_overrides:
        resolved_config = _deep_merge(resolved_config, refinement_overrides)

    if renderer_variant and renderer_variant_validation and renderer_variant_validation.renderer_type_override:
        resolved_config = _deep_merge(
            resolved_config,
            renderer_variant_validation.renderer_config_overrides,
        )

    if sub_renderer_variant:
        sub_renderer_validation = validate_variant_patch(
            view_def=SimpleNamespace(renderer_type=final_renderer),
            renderer_type_override=None,
            renderer_config_overrides=sub_renderer_variant.get("renderer_config") or {},
            consumer_key=consumer_key,
        )
        dropped_overrides.extend(
            {
                "field": dropped.field,
                "value": dropped.value,
                "reason": dropped.reason,
            }
            for dropped in sub_renderer_validation.dropped_overrides
        )
        resolved_config = _deep_merge(
            resolved_config,
            sub_renderer_validation.renderer_config_overrides,
        )

    return EffectiveComposition(
        renderer_type=final_renderer,
        renderer_config=resolved_config,
        presentation_stance=rec.get("presentation_stance_override") or view_def.presentation_stance,
        data_quality=rec.get("data_quality_assessment", "standard"),
        template_key=template.template_key if template else None,
        template_selection_reason=template_selection.reason if template_selection else None,
        dropped_overrides=dropped_overrides,
    )


def resolve_effective_render_contract(
    view_def,
    rec: Optional[dict] = None,
    consumer_key: str = "the-critic",
    job_id: Optional[str] = None,
    view_registry=None,
) -> EffectiveComposition:
    """Resolve the effective renderer contract for a view.

    This starts from the normal composition resolution and then, when a child
    view represents a named parent section, inherits that parent section's
    richer renderer contract by default.
    """
    composition = resolve_effective_composition(
        view_def=view_def,
        rec=rec,
        consumer_key=consumer_key,
        job_id=job_id,
    )
    if view_registry is None:
        return composition

    section_binding = resolve_parent_section_binding(view_def, view_registry)
    if not section_binding:
        return composition

    renderer_hint = section_binding.get("renderer_hint") or {}
    inherited_renderer = renderer_hint.get("renderer_type")
    if not isinstance(inherited_renderer, str) or not inherited_renderer:
        return composition

    # Preserve explicit child section surfaces. Parent section renderer hints are
    # useful for lightweight detail tabs, but they should not silently replace a
    # child view that already declares its own sectioned container contract.
    child_sections = composition.renderer_config.get("sections")
    if (
        inherited_renderer != composition.renderer_type
        and isinstance(child_sections, list)
        and len(child_sections) > 0
    ):
        return composition

    inherited_config = renderer_hint.get("config") or {}
    resolved_config = _deep_merge(composition.renderer_config, inherited_config)
    resolved_config.setdefault("_parentSectionKey", section_binding["section_key"])
    resolved_config.setdefault("_parentSectionTitle", section_binding["section_title"])
    resolved_config.setdefault("_sourceParentViewKey", section_binding["parent_view_key"])

    template_selection = select_applicable_template(view_def=view_def, renderer_type=inherited_renderer)
    template = template_selection.template if template_selection else None
    if template and template.renderer_config_presets:
        preset = deepcopy(template.renderer_config_presets.get(inherited_renderer) or {})
        resolved_config = _fill_missing(resolved_config, preset)

    return EffectiveComposition(
        renderer_type=inherited_renderer,
        renderer_config=resolved_config,
        presentation_stance=composition.presentation_stance,
        data_quality=composition.data_quality,
        template_key=template.template_key if template else composition.template_key,
        template_selection_reason=(
            template_selection.reason if template_selection else composition.template_selection_reason
        ),
        dropped_overrides=list(composition.dropped_overrides),
    )
