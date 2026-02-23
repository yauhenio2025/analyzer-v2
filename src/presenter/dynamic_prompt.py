"""Dynamic extraction prompt composer — template-free presentation.

When no curated transformation template exists for an engine + renderer
combination, this module composes an extraction prompt at runtime from:
1. Engine metadata (canonical_schema, extraction_focus, stage_context)
2. Renderer shape (ideal_data_shapes, config_schema fields)
3. Presentation stance prose

The composed prompt is passed to Haiku via the same TransformationExecutor
pipeline. Curated templates remain optional quality overrides.
"""

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def compose_dynamic_extraction_prompt(
    engine_key: str,
    renderer_type: str,
    stance_key: Optional[str] = None,
) -> dict[str, Any]:
    """Compose an extraction prompt from engine metadata + renderer shape + stance.

    Returns a dict with fields matching what TransformationExecutor.execute() needs:
        system_prompt, transformation_type, model, model_fallback, max_tokens,
        stance_key, source
    """
    engine_context = _build_engine_context(engine_key)
    renderer_context = _build_renderer_context(renderer_type)
    stance_text = _resolve_stance(stance_key) if stance_key else ""

    system_prompt = _compose_system_prompt(
        engine_context=engine_context,
        renderer_context=renderer_context,
        stance_text=stance_text,
    )

    # Adjust max_tokens based on renderer complexity
    max_tokens = 8000
    if renderer_context.get("category") == "container":
        max_tokens = 12000  # containers (accordion) produce more sections
    if renderer_context.get("ideal_data_shapes") and "nested_sections" in renderer_context["ideal_data_shapes"]:
        max_tokens = 16000

    result = {
        "system_prompt": system_prompt,
        "transformation_type": "llm_extract",
        "model": "claude-haiku-4-5-20251001",
        "model_fallback": "claude-sonnet-4-6",
        "max_tokens": max_tokens,
        "stance_key": stance_key,
        "source": "dynamic",
    }

    logger.info(
        f"[dynamic-prompt] Composed extraction prompt: "
        f"engine={engine_key}, renderer={renderer_type}, stance={stance_key}, "
        f"prompt_len={len(system_prompt)}, max_tokens={max_tokens}"
    )

    return result


def _build_engine_context(engine_key: str) -> dict[str, Any]:
    """Extract relevant metadata from an engine definition."""
    try:
        from src.engines.registry import get_engine_registry
        engine = get_engine_registry().get(engine_key)
    except Exception as e:
        logger.warning(f"[dynamic-prompt] Failed to load engine '{engine_key}': {e}")
        return {"engine_key": engine_key, "available": False}

    if engine is None:
        logger.warning(f"[dynamic-prompt] Engine not found: {engine_key}")
        return {"engine_key": engine_key, "available": False}

    context: dict[str, Any] = {
        "engine_key": engine_key,
        "available": True,
        "engine_name": engine.engine_name,
        "description": engine.description,
        "extraction_focus": engine.extraction_focus,
    }

    # Canonical schema — the definitive output structure
    # Cap at ~3000 chars to stay within prompt budget
    schema_str = json.dumps(engine.canonical_schema, indent=2, default=str)
    if len(schema_str) > 3000:
        schema_str = schema_str[:3000] + "\n  ... (truncated)"
    context["canonical_schema_text"] = schema_str

    # Stage context extraction fields
    extraction = engine.stage_context.extraction
    context["core_question"] = extraction.core_question
    context["key_fields"] = extraction.key_fields
    context["key_relationships"] = extraction.key_relationships
    context["id_field"] = extraction.id_field
    context["analysis_type"] = extraction.analysis_type

    return context


def _build_renderer_context(renderer_type: str) -> dict[str, Any]:
    """Extract relevant metadata from a renderer definition."""
    try:
        from src.renderers.registry import get_renderer_registry
        renderer = get_renderer_registry().get(renderer_type)
    except Exception as e:
        logger.warning(f"[dynamic-prompt] Failed to load renderer '{renderer_type}': {e}")
        return {"renderer_type": renderer_type, "available": False}

    if renderer is None:
        logger.warning(f"[dynamic-prompt] Renderer not found: {renderer_type}")
        return {"renderer_type": renderer_type, "available": False}

    context: dict[str, Any] = {
        "renderer_type": renderer_type,
        "available": True,
        "renderer_name": renderer.renderer_name,
        "category": renderer.category,
        "ideal_data_shapes": renderer.ideal_data_shapes,
        "available_section_renderers": renderer.available_section_renderers,
    }

    # Extract config field names from config_schema.properties
    props = renderer.config_schema.get("properties", {})
    context["config_fields"] = {
        k: v.get("description", "")
        for k, v in props.items()
    }

    # Input data schema if available
    if renderer.input_data_schema:
        context["input_data_schema"] = renderer.input_data_schema

    return context


def _resolve_stance(stance_key: str) -> str:
    """Resolve a stance key to its prose description."""
    try:
        from src.operations.registry import StanceRegistry
        reg = StanceRegistry()
        stance = reg.get(stance_key)
        if stance:
            return stance.stance
    except Exception as e:
        logger.warning(f"[dynamic-prompt] Failed to resolve stance '{stance_key}': {e}")
    return ""


def _compose_system_prompt(
    engine_context: dict[str, Any],
    renderer_context: dict[str, Any],
    stance_text: str,
) -> str:
    """Compose the system prompt for Haiku extraction.

    The prompt is LLM-native: guidance rather than rigid schema. It tells
    Haiku what the prose is about, what shape to produce, and what
    presentation posture to adopt.
    """
    parts = []

    parts.append(
        "You are a precise data extraction assistant. Your task is to read "
        "analytical prose and extract structured JSON suitable for rendering "
        "in a specific UI component. Return ONLY valid JSON — no markdown "
        "code fences, no commentary."
    )

    # --- Engine context ---
    if engine_context.get("available"):
        parts.append(f"\n## About the Analysis\n")
        parts.append(
            f"This prose was produced by the \"{engine_context['engine_name']}\" engine, "
            f"which performs {engine_context.get('analysis_type', 'analytical')} analysis."
        )
        if engine_context.get("core_question"):
            parts.append(f"Core question: {engine_context['core_question']}")
        if engine_context.get("extraction_focus"):
            focuses = ", ".join(engine_context["extraction_focus"][:8])
            parts.append(f"Analytical dimensions: {focuses}")
    else:
        parts.append(
            "\n## About the Analysis\n"
            "Extract structured data from the analytical prose below."
        )

    # --- Renderer context ---
    if renderer_context.get("available"):
        parts.append(f"\n## Target Rendering\n")
        parts.append(
            f"The extracted data will be rendered in a \"{renderer_context['renderer_name']}\" "
            f"({renderer_context.get('category', 'general')}) component."
        )

        shapes = renderer_context.get("ideal_data_shapes", [])
        if shapes:
            parts.append(f"This renderer expects data in one of these shapes: {', '.join(shapes)}.")

        # Tell Haiku about the specific fields the renderer consumes
        config_fields = renderer_context.get("config_fields", {})
        if config_fields:
            field_descriptions = []
            for field, desc in config_fields.items():
                if field in ("columns", "expand_first"):
                    continue  # layout config, not data fields
                field_descriptions.append(f"  - {field}: {desc}" if desc else f"  - {field}")
            if field_descriptions:
                parts.append(
                    "The renderer maps data using these field references:\n"
                    + "\n".join(field_descriptions)
                )

        # For container renderers, mention section structure
        section_renderers = renderer_context.get("available_section_renderers", [])
        if section_renderers:
            parts.append(
                f"This is a container renderer that organizes data into sections. "
                f"Each section can use sub-renderers like: {', '.join(section_renderers[:6])}."
            )
            parts.append(_get_shape_guidance_for_container(renderer_context))
        else:
            parts.append(_get_shape_guidance(renderer_context))

    # --- Stance ---
    if stance_text:
        parts.append(f"\n## Presentation Stance\n")
        # Take first ~500 chars of stance prose to keep prompt reasonable
        stance_excerpt = stance_text.strip()
        if len(stance_excerpt) > 500:
            stance_excerpt = stance_excerpt[:500] + "..."
        parts.append(stance_excerpt)

    # --- Canonical schema as reference ---
    if engine_context.get("canonical_schema_text"):
        parts.append(f"\n## Engine Output Structure (Reference)\n")
        parts.append(
            "The engine's canonical output includes these fields. Use this as a guide "
            "for what information is available in the prose — extract what matches "
            "the target renderer's shape:\n"
        )
        parts.append(engine_context["canonical_schema_text"])

    # --- Key fields ---
    key_fields = engine_context.get("key_fields", {})
    if key_fields:
        parts.append("\n## Key Fields\n")
        for field_name, field_desc in list(key_fields.items())[:10]:
            parts.append(f"- **{field_name}**: {field_desc}")

    return "\n".join(parts)


def _get_shape_guidance(renderer_context: dict[str, Any]) -> str:
    """Return JSON shape guidance for non-container renderers."""
    shapes = renderer_context.get("ideal_data_shapes", [])
    config_fields = renderer_context.get("config_fields", {})

    # Build field list from config
    data_fields = [f for f in config_fields.keys() if f not in ("columns", "expand_first")]

    if "object_array" in shapes:
        if data_fields:
            field_spec = ", ".join(f'"{f}": "..."' for f in data_fields[:4])
            return (
                f"\nReturn a JSON array of objects. Each object should have fields "
                f"like: {{{field_spec}}}. Include as many items as the prose supports."
            )
        return "\nReturn a JSON array of objects with descriptive fields."

    if "key_value_pairs" in shapes:
        return "\nReturn a JSON object with descriptive keys and string values."

    if "flat_list" in shapes:
        return "\nReturn a JSON array of strings or simple objects."

    if "prose_text" in shapes:
        return (
            '\nReturn a JSON object with "sections" array, each having '
            '"title" and "content" (rich prose) fields.'
        )

    if "timeline_data" in shapes:
        return (
            '\nReturn a JSON array of objects with "date"/"period", '
            '"title", "description" fields, ordered chronologically.'
        )

    if "comparison_pairs" in shapes:
        return (
            '\nReturn a JSON object with items to compare, each having '
            '"left" and "right" properties with matching dimensions.'
        )

    return "\nReturn well-structured JSON that captures the analytical content."


def _get_shape_guidance_for_container(renderer_context: dict[str, Any]) -> str:
    """Return JSON shape guidance for container renderers (accordion, tabs)."""
    return (
        '\n\nReturn a JSON object with a "sections" key containing an array of section objects. '
        'Each section should have:\n'
        '  - "key": a snake_case identifier\n'
        '  - "title": human-readable section title\n'
        '  - "items": array of objects with fields appropriate to the section content\n'
        '\nOrganize the analytical content into 3-8 thematic sections. '
        "Each section should group related findings."
    )
