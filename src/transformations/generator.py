"""LLM-powered transformation template generation.

Uses rich engine metadata (canonical_schema, extraction_focus, key_fields)
+ renderer specs (ideal_data_shapes, config_schema) + existing templates
as few-shot exemplars to generate high-quality transformation templates.

This replaces the shallow generation logic that only used engine name/description.
"""

import json
import logging
from typing import Any, Optional

from src.engines.schemas import EngineDefinition
from src.renderers.schemas import RendererDefinition
from src.transformations.schemas import TransformationTemplate

logger = logging.getLogger(__name__)


def _select_exemplars(
    engine: EngineDefinition,
    renderer: RendererDefinition,
    max_exemplars: int = 3,
) -> list[TransformationTemplate]:
    """Select the most relevant existing templates as few-shot exemplars.

    Scoring priority:
    1. Same renderer_type (+3)
    2. Compatible data_shape_out (+2)
    3. Has pattern_type (+1)
    4. Same domain as engine category (+1)
    """
    from src.transformations.registry import get_transformation_registry

    registry = get_transformation_registry()
    all_templates = registry.list_all()

    scored: list[tuple[int, TransformationTemplate]] = []
    for t in all_templates:
        if t.status == "deprecated":
            continue
        score = 0
        if renderer.renderer_key in t.applicable_renderer_types:
            score += 3
        if t.data_shape_out and t.data_shape_out in renderer.ideal_data_shapes:
            score += 2
        if t.pattern_type:
            score += 1
        # Prefer templates that actually have LLM extraction
        if t.transformation_type == "llm_extract" and t.llm_extraction_schema:
            score += 1
        scored.append((score, t))

    scored.sort(key=lambda x: -x[0])
    return [t for _, t in scored[:max_exemplars]]


def _build_engine_context(engine: EngineDefinition) -> str:
    """Build rich engine context from all available metadata."""
    lines = [
        f"Engine: {engine.engine_key} — {engine.engine_name}",
        f"Description: {engine.description}",
        f"Category: {engine.category.value}",
        f"Kind: {engine.kind.value}",
    ]

    if engine.extraction_focus:
        lines.append(f"Extraction Focus: {', '.join(engine.extraction_focus)}")

    # Canonical schema — the definitive output structure
    schema_str = json.dumps(engine.canonical_schema, indent=2)
    # Cap at 4000 chars to leave room for other context
    if len(schema_str) > 4000:
        schema_str = schema_str[:4000] + "\n... (truncated)"
    lines.append(f"Canonical Output Schema:\n{schema_str}")

    # Stage context extraction details
    sc = engine.stage_context
    ex = sc.extraction

    lines.append(f"Core Analytical Question: {ex.core_question}")
    lines.append(f"ID Field Convention: {ex.id_field}")

    if ex.key_fields:
        lines.append("Key Output Fields:")
        for field, desc in ex.key_fields.items():
            lines.append(f"  - {field}: {desc}")

    if ex.extraction_steps:
        lines.append("Extraction Steps (what the engine looks for):")
        for i, step in enumerate(ex.extraction_steps[:5], 1):
            lines.append(f"  {i}. {step[:200]}")

    if ex.key_relationships:
        lines.append(f"Key Relationships: {', '.join(ex.key_relationships)}")

    if ex.special_instructions:
        lines.append(f"Special Instructions: {ex.special_instructions[:300]}")

    return "\n".join(lines)


def _build_renderer_context(renderer: RendererDefinition) -> str:
    """Build renderer context including data shape and config requirements."""
    lines = [
        f"Renderer: {renderer.renderer_key} — {renderer.renderer_name}",
        f"Category: {renderer.category}",
        f"Ideal Data Shapes: {', '.join(renderer.ideal_data_shapes)}",
    ]

    if renderer.input_data_schema:
        schema_str = json.dumps(renderer.input_data_schema, indent=2)
        if len(schema_str) > 2000:
            schema_str = schema_str[:2000] + "\n... (truncated)"
        lines.append(f"Input Data Schema:\n{schema_str}")

    if renderer.config_schema:
        config_props = renderer.config_schema.get("properties", {})
        if config_props:
            lines.append("Configuration Keys (what field names the renderer expects):")
            for key, spec in config_props.items():
                desc = spec.get("description", spec.get("type", ""))
                lines.append(f"  - {key}: {desc}")

    if renderer.available_section_renderers:
        lines.append(
            f"Available Sub-Renderers: {', '.join(renderer.available_section_renderers)}"
        )

    return "\n".join(lines)


def _build_exemplar_text(exemplars: list[TransformationTemplate]) -> str:
    """Format exemplar templates for few-shot prompting."""
    if not exemplars:
        return "No existing templates available as reference."

    lines = ["Here are existing high-quality templates for reference. Study their structure:"]
    for i, t in enumerate(exemplars, 1):
        lines.append(f"\n--- Exemplar {i}: {t.template_key} ---")
        lines.append(f"Engines: {', '.join(t.applicable_engines)}")
        lines.append(f"Renderers: {', '.join(t.applicable_renderer_types)}")
        lines.append(f"Pattern Type: {t.pattern_type}")
        lines.append(f"Data Shape Out: {t.data_shape_out}")

        if t.llm_extraction_schema:
            schema_str = json.dumps(t.llm_extraction_schema, indent=2)
            if len(schema_str) > 3000:
                schema_str = schema_str[:3000] + "\n... (truncated)"
            lines.append(f"Extraction Schema:\n{schema_str}")

        if t.llm_prompt_template:
            prompt_preview = t.llm_prompt_template[:500]
            if len(t.llm_prompt_template) > 500:
                prompt_preview += "... (truncated)"
            lines.append(f"Prompt Template:\n{prompt_preview}")

    return "\n".join(lines)


def _infer_data_shape(renderer: RendererDefinition) -> str:
    """Infer the best data_shape_out based on renderer's ideal shapes."""
    # Map renderer data shapes to transformation output shapes
    shape_map = {
        "object_array": "object_array",
        "flat_list": "object_array",
        "nested_sections": "nested_sections",
        "timeline_data": "timeline_data",
        "key_value_pairs": "key_value_pairs",
        "prose_text": "prose_text",
    }
    for shape in renderer.ideal_data_shapes:
        if shape in shape_map:
            return shape_map[shape]
    return "object_array"  # Safe default


def _infer_pattern_type(data_shape: str) -> str:
    """Infer pattern_type from data_shape_out."""
    pattern_map = {
        "object_array": "card_extraction",
        "nested_sections": "section_extraction",
        "timeline_data": "timeline_extraction",
        "key_value_pairs": "table_extraction",
        "prose_text": "narrative_extraction",
    }
    return pattern_map.get(data_shape, "section_extraction")


def _build_generation_prompt(
    engine: EngineDefinition,
    renderer: RendererDefinition,
    exemplars: list[TransformationTemplate],
    description: str = "",
    domain: str = "generic",
) -> str:
    """Build the complete generation prompt."""
    engine_ctx = _build_engine_context(engine)
    renderer_ctx = _build_renderer_context(renderer)
    exemplar_text = _build_exemplar_text(exemplars)

    data_shape = _infer_data_shape(renderer)
    pattern_type = _infer_pattern_type(data_shape)

    return f"""You are a transformation template engineer for an analytical visualization system.

TASK: Generate a TransformationTemplate that extracts structured data from an engine's PROSE output into a format suitable for a specific renderer.

The engine produces free-form analytical prose (5-25K words). Your template will instruct Claude Haiku to extract structured JSON from that prose.

## SOURCE: Engine (what data looks like)

{engine_ctx}

## TARGET: Renderer (what shape it needs)

{renderer_ctx}

## EXEMPLARS: Existing High-Quality Templates (learn from these)

{exemplar_text}

## ADDITIONAL CONTEXT
{description if description else "Generate a general-purpose extraction template."}
Domain: {domain}

## OUTPUT REQUIREMENTS

Generate a complete TransformationTemplate JSON with these fields:

1. **template_key**: `{engine.engine_key}_{renderer.renderer_key}_extraction`
2. **template_name**: Human-readable name
3. **description**: 1-2 sentences describing what's extracted
4. **version**: 1
5. **transformation_type**: "llm_extract"
6. **llm_extraction_schema**: JSON schema that:
   - Maps the engine's canonical_schema fields to the renderer's expected data shape
   - For "{data_shape}" shape: follow the exemplar patterns above
   - Use the engine's key_fields as primary extraction targets
   - Include appropriate enum values from the engine's extraction_focus
   - Use the engine's id_field convention for IDs (e.g., "{engine.stage_context.extraction.id_field}")
7. **llm_prompt_template**: System prompt that:
   - Instructs extraction of ALL items (not just first few)
   - Specifies exact enum values and field constraints
   - Includes a numbered RULES section
   - Uses sequential IDs matching the engine's convention
   - Says "Return ONLY JSON — no markdown fences, no commentary"
8. **applicable_renderer_types**: ["{renderer.renderer_key}"]
9. **applicable_engines**: ["{engine.engine_key}"]
10. **domain**: "{domain}"
11. **pattern_type**: "{pattern_type}"
12. **data_shape_out**: "{data_shape}"
13. **compatible_sub_renderers**: [] (add relevant ones if the renderer is a container)
14. **tags**: relevant tags
15. **status**: "draft"
16. **model**: "claude-haiku-4-5-20251001"
17. **model_fallback**: "claude-sonnet-4-6"
18. **max_tokens**: 8000

Return ONLY valid JSON. No markdown fences. No commentary outside the JSON."""


async def generate_transformation_template(
    engine: EngineDefinition,
    renderer: RendererDefinition,
    description: str = "",
    domain: str = "generic",
    save: bool = False,
) -> TransformationTemplate:
    """Generate a transformation template using rich engine + renderer metadata.

    Steps:
    1. Select 2-3 most relevant existing templates as exemplars
    2. Build rich context from engine canonical_schema, extraction_focus, key_fields
    3. Build renderer context from ideal_data_shapes, config_schema
    4. Call Claude Sonnet with few-shot exemplars + full context
    5. Validate output against TransformationTemplate schema
    6. Optionally save to disk

    Returns validated TransformationTemplate.
    """
    from src.llm.client import (
        GENERATION_MODEL,
        get_anthropic_client,
        parse_llm_json_response,
    )

    client = get_anthropic_client()
    if client is None:
        raise RuntimeError("LLM service unavailable. Set ANTHROPIC_API_KEY.")

    # Step 1: Select exemplars
    exemplars = _select_exemplars(engine, renderer)
    logger.info(
        f"Selected {len(exemplars)} exemplars for "
        f"{engine.engine_key} -> {renderer.renderer_key}: "
        f"{[e.template_key for e in exemplars]}"
    )

    # Step 2-3: Build prompt
    prompt = _build_generation_prompt(
        engine, renderer, exemplars, description, domain
    )
    logger.info(
        f"Generation prompt: {len(prompt)} chars "
        f"({len(prompt.split())} words)"
    )

    # Step 4: Call LLM
    response = client.messages.create(
        model=GENERATION_MODEL,
        max_tokens=12000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw_text = response.content[0].text
    logger.info(
        f"LLM response: {len(raw_text)} chars, "
        f"model={response.model}, "
        f"input_tokens={response.usage.input_tokens}, "
        f"output_tokens={response.usage.output_tokens}"
    )

    # Step 5: Parse and validate
    parsed = parse_llm_json_response(raw_text)

    # Force provenance fields
    parsed["generation_mode"] = "generated"
    parsed["status"] = "draft"

    template = TransformationTemplate.model_validate(parsed)

    # Step 6: Optionally save
    if save:
        from src.transformations.registry import get_transformation_registry

        registry = get_transformation_registry()
        success = registry.save(template.template_key, template)
        if not success:
            raise RuntimeError(
                f"Failed to save generated template '{template.template_key}'"
            )
        logger.info(f"Saved generated template: {template.template_key}")
    else:
        logger.info(
            f"Generated template (not saved): {template.template_key}"
        )

    return template
