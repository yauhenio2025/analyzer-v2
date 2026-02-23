"""LLM-powered view definition generation from patterns.

Given a view pattern + engine + workflow context, generates a complete
ViewDefinition that composes correctly into existing page trees.

Uses engine canonical_schema to map fields to renderer config,
and existing page views for position/structure context.
"""

import json
import logging
from typing import Any, Optional

from pydantic import BaseModel, Field

from src.engines.schemas import EngineDefinition
from src.renderers.schemas import RendererDefinition
from src.views.pattern_schemas import ViewPattern
from src.views.schemas import ViewDefinition

logger = logging.getLogger(__name__)


class ViewGenerateRequest(BaseModel):
    """Request to generate a view definition from a pattern."""

    pattern_key: str = Field(
        ..., description="View pattern to instantiate (one of 6)"
    )
    engine_key: str = Field(
        ..., description="Engine producing the data"
    )

    # Workflow context
    workflow_key: str = Field(
        default="", description="Workflow key for data_source"
    )
    phase_number: float = Field(
        default=1.0, description="Phase number for data_source"
    )
    chain_key: Optional[str] = Field(
        default=None, description="Chain key if this is a chain output"
    )
    scope: str = Field(
        default="aggregated",
        description="'aggregated' (single result) or 'per_item'",
    )

    # Target location
    target_app: str = Field(
        default="the-critic", description="Consumer app"
    )
    target_page: str = Field(
        default="", description="Page within the app"
    )

    # Optional overrides
    parent_view_key: Optional[str] = Field(
        default=None, description="Parent view for nesting"
    )
    position: float = Field(
        default=0, description="Sort order within page"
    )
    presentation_stance: Optional[str] = Field(
        default=None, description="Presentation stance override"
    )

    # Generation options
    description: str = Field(
        default="", description="Additional context for generation"
    )
    transformation_template_key: Optional[str] = Field(
        default=None,
        description="Existing transformation template to wire into the view",
    )
    save: bool = Field(
        default=False, description="Whether to save to disk"
    )


class ViewGenerateResponse(BaseModel):
    """Response from view generation."""

    view: ViewDefinition
    transformation_generated: bool = False
    notes: str = ""


def _build_page_context(
    existing_views: list[ViewDefinition],
) -> str:
    """Build context about existing views on the target page."""
    if not existing_views:
        return "No existing views on this page — this will be the first."

    lines = ["Existing views on this page (for position/nesting context):"]
    for v in sorted(existing_views, key=lambda x: x.position):
        parent = f", parent={v.parent_view_key}" if v.parent_view_key else ""
        lines.append(
            f"  - {v.view_key} (pos={v.position}, "
            f"renderer={v.renderer_type}{parent})"
        )
    return "\n".join(lines)


def _build_view_generation_prompt(
    pattern: ViewPattern,
    engine: EngineDefinition,
    renderer: RendererDefinition,
    request: ViewGenerateRequest,
    existing_views: list[ViewDefinition],
) -> str:
    """Build prompt for view generation."""

    # Pattern template
    pattern_dump = pattern.model_dump()
    pattern_text = json.dumps(pattern_dump, indent=2)

    # Engine schema (abbreviated)
    schema_str = json.dumps(engine.canonical_schema, indent=2)
    if len(schema_str) > 3000:
        schema_str = schema_str[:3000] + "\n... (truncated)"

    # Engine key fields
    key_fields_text = ""
    kf = engine.stage_context.extraction.key_fields
    if kf:
        key_fields_text = "Engine Key Fields:\n"
        for field, desc in kf.items():
            key_fields_text += f"  - {field}: {desc}\n"

    # Renderer config schema
    config_schema_text = ""
    if renderer.config_schema:
        config_schema_text = json.dumps(
            renderer.config_schema, indent=2
        )
        if len(config_schema_text) > 2000:
            config_schema_text = config_schema_text[:2000] + "\n..."

    # Page context
    page_ctx = _build_page_context(existing_views)

    # Data source info
    data_source = {
        "workflow_key": request.workflow_key or None,
        "phase_number": request.phase_number,
        "engine_key": request.engine_key,
        "chain_key": request.chain_key,
        "scope": request.scope,
    }

    return f"""You are a view definition engineer. Generate a ViewDefinition JSON that instantiates a view pattern for a specific engine's output.

## VIEW PATTERN (template to instantiate)
{pattern_text}

## ENGINE (data source)
Engine: {engine.engine_key} — {engine.engine_name}
Description: {engine.description}
Extraction Focus: {', '.join(engine.extraction_focus) if engine.extraction_focus else 'N/A'}
Output Schema:
{schema_str}
{key_fields_text}

## RENDERER CONFIG SCHEMA
{config_schema_text}

## TARGET CONTEXT
App: {request.target_app}
Page: {request.target_page}
Parent View: {request.parent_view_key or "none (top-level)"}
Position: {request.position}
Presentation Stance: {request.presentation_stance or "auto"}

{page_ctx}

## DATA SOURCE (pre-filled — use exactly)
{json.dumps(data_source, indent=2)}

## INSTANTIATION HINTS FROM PATTERN
{pattern.instantiation_hints}

## ADDITIONAL CONTEXT
{request.description if request.description else "Generate a general-purpose view."}

## YOUR TASK

Generate a complete ViewDefinition JSON:

1. **view_key**: Use format `{{target_page}}_{{engine_short_name}}` (snake_case, max 60 chars)
2. **view_name**: Human-readable display name
3. **description**: 1-2 sentences about what this view shows
4. **target_app**: "{request.target_app}"
5. **target_page**: "{request.target_page}"
6. **renderer_type**: "{pattern.renderer_type}"
7. **renderer_config**: Fill in the pattern's default_renderer_config:
   - Map section keys/titles to engine output fields
   - Assign appropriate sub-renderers based on field data shapes
   - Use engine's key_fields for title_field, description_field mappings
8. **data_source**: Use the pre-filled data source above exactly
9. **presentation_stance**: {f'"{request.presentation_stance}"' if request.presentation_stance else "choose based on engine type"}
10. **position**: {request.position}
11. **parent_view_key**: {f'"{request.parent_view_key}"' if request.parent_view_key else "null"}
12. **visibility**: "if_data_exists"
13. **planner_hint**: Brief guidance for when to recommend this view
14. **planner_eligible**: true
15. **status**: "draft"
16. **tags**: relevant tags

Return ONLY valid JSON. No markdown fences."""


async def generate_view(
    request: ViewGenerateRequest,
) -> ViewGenerateResponse:
    """Generate a ViewDefinition from a pattern + engine context.

    Steps:
    1. Load pattern, engine, renderer
    2. Load existing views for same target_page (for context)
    3. Build prompt with pattern template + engine schema + page context
    4. Call Claude Sonnet
    5. Validate, force generation_mode/status
    6. Wire transformation if specified
    7. Optionally save
    """
    from src.llm.client import (
        GENERATION_MODEL,
        get_anthropic_client,
        parse_llm_json_response,
    )
    from src.views.pattern_registry import get_pattern_registry
    from src.views.registry import get_view_registry
    from src.engines.registry import get_engine_registry
    from src.renderers.registry import get_renderer_registry

    client = get_anthropic_client()
    if client is None:
        raise RuntimeError("LLM service unavailable. Set ANTHROPIC_API_KEY.")

    # Load entities
    pattern_registry = get_pattern_registry()
    pattern = pattern_registry.get(request.pattern_key)
    if pattern is None:
        keys = pattern_registry.list_keys()
        raise ValueError(
            f"Pattern '{request.pattern_key}' not found. "
            f"Available: {keys}"
        )

    engine_registry = get_engine_registry()
    engine = engine_registry.get(request.engine_key)
    if engine is None:
        raise ValueError(f"Engine '{request.engine_key}' not found")

    renderer_registry = get_renderer_registry()
    renderer = renderer_registry.get(pattern.renderer_type)
    if renderer is None:
        raise ValueError(
            f"Renderer '{pattern.renderer_type}' not found "
            f"(referenced by pattern '{request.pattern_key}')"
        )

    # Get existing page views for context
    view_registry = get_view_registry()
    existing_views = [
        v
        for v in view_registry.list_all()
        if v.target_app == request.target_app
        and v.target_page == request.target_page
    ]
    logger.info(
        f"View generation: pattern={request.pattern_key}, "
        f"engine={request.engine_key}, "
        f"page={request.target_app}/{request.target_page}, "
        f"existing_views={len(existing_views)}"
    )

    # Build and call LLM
    prompt = _build_view_generation_prompt(
        pattern, engine, renderer, request, existing_views
    )
    logger.info(f"View generation prompt: {len(prompt)} chars")

    response = client.messages.create(
        model=GENERATION_MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw_text = response.content[0].text
    logger.info(
        f"LLM response: {len(raw_text)} chars, "
        f"model={response.model}, "
        f"input_tokens={response.usage.input_tokens}, "
        f"output_tokens={response.usage.output_tokens}"
    )

    parsed = parse_llm_json_response(raw_text)

    # Force provenance fields
    parsed["generation_mode"] = "generated"
    parsed["status"] = "draft"
    parsed.setdefault("source_project", "auto-generated")

    view = ViewDefinition.model_validate(parsed)

    # Wire transformation if specified
    transformation_generated = False
    if request.transformation_template_key:
        from src.transformations.registry import get_transformation_registry
        from src.views.schemas import TransformationSpec

        tmpl_registry = get_transformation_registry()
        tmpl = tmpl_registry.get(request.transformation_template_key)
        if tmpl:
            view.transformation = TransformationSpec(
                type=tmpl.transformation_type,
                field_mapping=tmpl.field_mapping,
                llm_extraction_schema=tmpl.llm_extraction_schema,
                llm_prompt_template=tmpl.llm_prompt_template,
                stance_key=tmpl.stance_key,
            )
            transformation_generated = True
            logger.info(
                f"Wired transformation '{request.transformation_template_key}' "
                f"into view '{view.view_key}'"
            )

    # Validate parent_view_key exists if set
    if view.parent_view_key:
        parent = view_registry.get(view.parent_view_key)
        if parent is None:
            logger.warning(
                f"Generated view '{view.view_key}' references "
                f"non-existent parent '{view.parent_view_key}'"
            )

    # Check for view_key collision
    if view_registry.get(view.view_key) is not None:
        original_key = view.view_key
        view.view_key = f"{original_key}_gen"
        logger.info(
            f"View key collision: '{original_key}' exists, "
            f"using '{view.view_key}'"
        )

    # Save if requested
    if request.save:
        success = view_registry.save(view.view_key, view)
        if not success:
            raise RuntimeError(
                f"Failed to save generated view '{view.view_key}'"
            )
        logger.info(f"Saved generated view: {view.view_key}")
    else:
        logger.info(f"Generated view (not saved): {view.view_key}")

    return ViewGenerateResponse(
        view=view,
        transformation_generated=transformation_generated,
        notes=(
            f"Generated from pattern '{pattern.pattern_key}' "
            f"for engine '{engine.engine_key}'. "
            f"Renderer: {pattern.renderer_type}."
        ),
    )
