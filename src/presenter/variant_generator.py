"""Tier 3b variant generation — deterministic A/B alternatives for views.

Generates 2-3 presentation variants per view by varying exactly one dimension
(renderer_type or sub_renderer_strategy). All variants share the same
structured_data and raw_prose — only the presentation differs.
"""

import hashlib
import logging
from typing import Optional

from src.presenter.presentation_api import assemble_single_view
from src.presenter.variant_store import (
    delete_variant_set,
    load_variant_set,
    save_variant,
    save_variant_set,
)
from src.renderers.registry import get_renderer_registry
from src.renderers.schemas import RendererDefinition
from src.views.registry import get_view_registry

logger = logging.getLogger(__name__)

PHASE2_PARENT_TARGETS = {"genealogy_target_profile", "genealogy_text_profiling"}
PHASE2_EXTRA_TARGETS = {"genealogy_per_work_scan", "genealogy_conditions"}


def _compute_variant_set_id(
    job_id: str,
    view_key: str,
    dimension: str,
    base_renderer: str,
    style_school: str,
) -> str:
    """Deterministic variant set ID — same inputs → same ID."""
    hash_input = f"{job_id}|{view_key}|{dimension}|{base_renderer}|{style_school}"
    digest = hashlib.sha256(hash_input.encode()).hexdigest()[:8]
    vk_prefix = view_key[:20]
    jid_prefix = job_id[:8]
    return f"vs-{jid_prefix}-{vk_prefix}-{digest}"


def get_phase2_variant_target_keys() -> set[str]:
    """Return the Phase 2 steering target set including direct child closure."""
    registry = get_view_registry()
    direct_children = {
        view.view_key
        for view in registry.list_all()
        if getattr(view, "parent_view_key", None) in PHASE2_PARENT_TARGETS
    }
    return PHASE2_PARENT_TARGETS | PHASE2_EXTRA_TARGETS | direct_children


def is_phase2_variant_target(view_key: str) -> bool:
    return view_key in get_phase2_variant_target_keys()


def _score_candidate(
    candidate: RendererDefinition,
    base: RendererDefinition,
    base_stance: Optional[str],
) -> float:
    """Score a candidate renderer for compatibility with the base view.

    Combines data shape overlap and stance affinity into a 0.0-1.0 score.
    """
    # Data shape overlap (0.0-1.0)
    if not base.ideal_data_shapes:
        shape_score = 0.5  # Unknown shape = moderate compatibility
    else:
        overlap = set(candidate.ideal_data_shapes) & set(base.ideal_data_shapes)
        shape_score = len(overlap) / len(base.ideal_data_shapes) if base.ideal_data_shapes else 0.0

    # Stance affinity (0.0-1.0)
    if base_stance and base_stance in candidate.stance_affinities:
        stance_score = candidate.stance_affinities[base_stance]
    else:
        stance_score = 0.3  # Default modest score

    # Weighted combination
    return round(0.6 * shape_score + 0.4 * stance_score, 3)


def _validate_against_schema(
    candidate: RendererDefinition,
    structured_data: dict,
) -> bool:
    """Validate structured_data against a renderer's input_data_schema.

    Returns True if schema is absent (no constraint) or data passes validation.
    """
    if not candidate.input_data_schema:
        return True

    try:
        import jsonschema
        jsonschema.validate(structured_data, candidate.input_data_schema)
        return True
    except ImportError:
        # jsonschema not available — skip validation
        logger.warning("jsonschema not installed; skipping input schema validation")
        return True
    except jsonschema.ValidationError:
        return False
    except Exception as e:
        logger.warning(f"Schema validation error for {candidate.renderer_key}: {e}")
        return True  # Don't reject on unexpected errors


def _generate_renderer_type_variants(
    base_renderer: RendererDefinition,
    structured_data: dict,
    base_stance: Optional[str],
    max_variants: int,
    base_renderer_config: dict,
) -> list[dict]:
    """Generate alternative renderer_type variants.

    Finds renderers that handle the same data shapes and are supported
    by the target app (the-critic).
    """
    registry = get_renderer_registry()

    # Collect candidate renderers from all base data shapes
    candidates: dict[str, RendererDefinition] = {}
    for shape in base_renderer.ideal_data_shapes:
        for r in registry.for_data_shape(shape):
            if r.renderer_key != base_renderer.renderer_key:
                candidates[r.renderer_key] = r

    # Filter by app support
    app_renderers = {r.renderer_key for r in registry.for_app("the-critic")}
    candidates = {
        k: v for k, v in candidates.items()
        if k in app_renderers
    }

    # Validate against input_data_schema
    candidates = {
        k: v for k, v in candidates.items()
        if _validate_against_schema(v, structured_data)
    }

    if not candidates:
        logger.info(
            f"No compatible alternative renderers for {base_renderer.renderer_key} "
            f"(shapes: {base_renderer.ideal_data_shapes})"
        )
        return []

    # Score and rank
    scored = [
        (k, v, _score_candidate(v, base_renderer, base_stance))
        for k, v in candidates.items()
    ]
    scored.sort(key=lambda x: x[2], reverse=True)

    # Take top N-1 alternatives (slot 0 is control)
    alternatives = []
    for key, renderer_def, score in scored[: max_variants - 1]:
        alternatives.append({
            "renderer_type": key,
            "renderer_config": {},  # Fresh config for alternative renderer
            "rationale": (
                f"Alternative renderer '{renderer_def.renderer_name}' "
                f"(category: {renderer_def.category}) shares data shapes "
                f"{list(set(renderer_def.ideal_data_shapes) & set(base_renderer.ideal_data_shapes))} "
                f"with base '{base_renderer.renderer_name}'"
            ),
            "compatibility_score": score,
        })

    return alternatives


def _generate_sub_renderer_variants(
    base_renderer: RendererDefinition,
    base_renderer_config: dict,
    max_variants: int,
) -> list[dict]:
    """Generate alternative sub_renderer_strategy variants.

    Varies which section renderers are used within a container renderer.
    Only applies to renderers with available_section_renderers.
    """
    available = base_renderer.available_section_renderers
    if not available or len(available) < 2:
        logger.info(
            f"Renderer {base_renderer.renderer_key} has {len(available)} "
            f"section renderers — not enough for sub_renderer variants"
        )
        return []

    current_section_renderers = dict(base_renderer_config.get("section_renderers") or {})
    current_types = {
        spec.get("renderer_type")
        for spec in current_section_renderers.values()
        if isinstance(spec, dict)
    }

    # Find unused section renderers
    unused = [sr for sr in available if sr not in current_types]
    if not unused:
        # All section renderers already in use — swap some instead
        unused = available

    section_order = [
        section.get("key")
        for section in (base_renderer_config.get("sections") or [])
        if isinstance(section, dict) and section.get("key")
    ]
    if not section_order and current_section_renderers:
        section_order = sorted(current_section_renderers.keys())

    alternatives = []
    for i in range(min(max_variants - 1, len(unused))):
        swap_target = unused[i]
        target_section = None
        for section_key in section_order:
            current_spec = current_section_renderers.get(section_key) or {}
            if current_spec.get("renderer_type") != swap_target:
                target_section = section_key
                break
        if target_section is None and section_order:
            target_section = section_order[0]
        if target_section is None:
            target_section = "default"

        existing_spec = dict(current_section_renderers.get(target_section) or {})
        replacement_spec = {
            **existing_spec,
            "renderer_type": swap_target,
        }
        new_config = {
            "section_renderers": {
                target_section: replacement_spec,
            }
        }

        alternatives.append({
            "renderer_type": base_renderer.renderer_key,  # Same renderer
            "renderer_config": new_config,
            "rationale": (
                f"Sub-renderer strategy variant using '{swap_target}' "
                f"for section '{target_section}' (from available: {available})"
            ),
            "compatibility_score": 0.8,  # High compatibility — same base renderer
        })

    return alternatives


def generate_variant_set(
    job_id: str,
    view_key: str,
    dimension: str,
    max_variants: int = 3,
    style_school: Optional[str] = None,
    force: bool = False,
) -> dict:
    """Generate a variant set for a view.

    Returns a dict matching VariantSetResponse shape.
    """
    if not is_phase2_variant_target(view_key):
        raise ValueError(
            f"View '{view_key}' is outside the Phase 2 steering target set"
        )

    style_school_str = style_school or ""

    # Load the base view
    view_payload = assemble_single_view(job_id, view_key, consumer_key="the-critic")
    if view_payload is None:
        raise ValueError(f"View not found: {view_key} for job {job_id}")

    base_renderer_type = view_payload.renderer_type
    base_renderer_config = view_payload.renderer_config
    structured_data = view_payload.structured_data
    base_stance = view_payload.presentation_stance

    if not structured_data:
        raise ValueError(
            f"View '{view_key}' has no structured_data — "
            f"renderer_type and sub_renderer variants require structured data"
        )

    # Look up renderer definition
    registry = get_renderer_registry()
    base_renderer_def = registry.get(base_renderer_type)
    if base_renderer_def is None:
        raise ValueError(f"Renderer definition not found: {base_renderer_type}")

    # Compute deterministic ID
    variant_set_id = _compute_variant_set_id(
        job_id, view_key, dimension, base_renderer_type, style_school_str,
    )

    # Check cache unless forced
    if not force:
        existing = load_variant_set(variant_set_id)
        if existing is not None:
            logger.info(f"Returning cached variant set {variant_set_id}")
            return existing

    # Force: delete existing data for this set
    if force:
        delete_variant_set(variant_set_id)
        logger.info(f"Force regeneration: deleted existing variant set {variant_set_id}")

    # Generate alternatives based on dimension
    if dimension == "renderer_type":
        alternatives = _generate_renderer_type_variants(
            base_renderer=base_renderer_def,
            structured_data=structured_data,
            base_stance=base_stance,
            max_variants=max_variants,
            base_renderer_config=base_renderer_config,
        )
    elif dimension == "sub_renderer_strategy":
        alternatives = _generate_sub_renderer_variants(
            base_renderer=base_renderer_def,
            base_renderer_config=base_renderer_config,
            max_variants=max_variants,
        )
    else:
        raise ValueError(f"Unsupported dimension: {dimension}")

    # Build variant list: control (index 0) + alternatives
    variant_count = 1 + len(alternatives)

    metadata = {}
    if not alternatives:
        metadata["reason"] = "no_compatible_alternatives"

    # Persist variant set
    save_variant_set(
        variant_set_id=variant_set_id,
        job_id=job_id,
        view_key=view_key,
        dimension=dimension,
        base_renderer=base_renderer_type,
        style_school=style_school_str,
        variant_count=variant_count,
        metadata=metadata,
    )

    # Persist control variant (index 0)
    control_variant_id = f"{variant_set_id}-v0"
    save_variant(
        variant_id=control_variant_id,
        variant_set_id=variant_set_id,
        variant_index=0,
        is_control=True,
        renderer_type=base_renderer_type,
        renderer_config=base_renderer_config,
        rationale="Control variant — current configuration",
        compatibility_score=1.0,
    )

    # Persist alternative variants
    for i, alt in enumerate(alternatives, start=1):
        alt_variant_id = f"{variant_set_id}-v{i}"
        save_variant(
            variant_id=alt_variant_id,
            variant_set_id=variant_set_id,
            variant_index=i,
            is_control=False,
            renderer_type=alt["renderer_type"],
            renderer_config=alt.get("renderer_config", {}),
            rationale=alt.get("rationale", ""),
            compatibility_score=alt.get("compatibility_score", 0.0),
        )

    logger.info(
        f"Generated variant set {variant_set_id}: "
        f"{variant_count} variants (dimension={dimension}, "
        f"base={base_renderer_type})"
    )

    # Return the complete set
    return load_variant_set(variant_set_id)
