"""API routes for transformation templates and execution.

Transformation templates are named, reusable transformation specifications.
The execute endpoint applies a transformation (by template or inline spec)
to data and returns the result.
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.routes.meta import mark_definitions_modified
from src.transformations.executor import get_transformation_executor
from src.transformations.registry import get_transformation_registry
from src.transformations.schemas import (
    AggregateConfig,
    TransformationTemplate,
    TransformationTemplateSummary,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transformations", tags=["transformations"])


# ── Request/Response schemas ─────────────────────────────


class TransformationExecuteRequest(BaseModel):
    """Request to execute a transformation on data."""

    data: Any = Field(
        ..., description="The raw data to transform"
    )

    # Option A: reference a template
    template_key: Optional[str] = Field(
        default=None,
        description="Template key to use for transformation spec",
    )

    # Option B: inline spec
    transformation_type: Optional[str] = Field(
        default=None,
        description="Type: none/schema_map/llm_extract/llm_summarize/aggregate",
    )
    field_mapping: Optional[dict[str, str]] = Field(
        default=None,
        description="Field mapping for schema_map type",
    )
    llm_extraction_schema: Optional[dict[str, Any]] = Field(
        default=None,
        description="Extraction schema for llm_extract type",
    )
    llm_prompt_template: Optional[str] = Field(
        default=None,
        description="System prompt for LLM types",
    )
    stance_key: Optional[str] = Field(
        default=None,
        description="Stance key for LLM context",
    )
    aggregate_config: Optional[AggregateConfig] = Field(
        default=None,
        description="Aggregation config for aggregate type",
    )

    # Execution options
    cache_key: Optional[str] = Field(
        default=None,
        description="Optional cache key for result caching",
    )


class TransformationExecuteResponse(BaseModel):
    """Response from transformation execution."""

    success: bool
    data: Any = None
    error: Optional[str] = None
    transformation_type: str
    model_used: Optional[str] = None
    token_count: Optional[int] = None
    cached: bool = False
    execution_time_ms: int = 0


# ── Helper ───────────────────────────────────────────────


def _get_or_404(template_key: str) -> TransformationTemplate:
    """Get a template by key or raise 404."""
    registry = get_transformation_registry()
    template = registry.get(template_key)
    if template is None:
        available = registry.list_keys()
        raise HTTPException(
            status_code=404,
            detail=f"Transformation template '{template_key}' not found. "
            f"Available: {available}",
        )
    return template


# ── List endpoints ───────────────────────────────────────


@router.get("", response_model=list[TransformationTemplateSummary])
async def list_transformations(
    type: Optional[str] = Query(
        None, description="Filter by transformation type"
    ),
    tag: Optional[str] = Query(
        None, description="Filter by tag"
    ),
):
    """List all transformation templates with optional filters."""
    registry = get_transformation_registry()
    return registry.list_summaries(transformation_type=type, tag=tag)


# ── Lookup endpoints ─────────────────────────────────────


@router.get(
    "/for-engine/{engine_key}",
    response_model=list[TransformationTemplateSummary],
)
async def templates_for_engine(engine_key: str):
    """Get templates applicable to a specific engine."""
    registry = get_transformation_registry()
    templates = registry.for_engine(engine_key)
    return [
        TransformationTemplateSummary(
            template_key=t.template_key,
            template_name=t.template_name,
            description=t.description,
            transformation_type=t.transformation_type,
            applicable_renderer_types=t.applicable_renderer_types,
            tags=t.tags,
            status=t.status,
        )
        for t in templates
    ]


@router.get(
    "/for-renderer/{renderer_type}",
    response_model=list[TransformationTemplateSummary],
)
async def templates_for_renderer(renderer_type: str):
    """Get templates applicable to a specific renderer type."""
    registry = get_transformation_registry()
    templates = registry.for_renderer(renderer_type)
    return [
        TransformationTemplateSummary(
            template_key=t.template_key,
            template_name=t.template_name,
            description=t.description,
            transformation_type=t.transformation_type,
            applicable_renderer_types=t.applicable_renderer_types,
            tags=t.tags,
            status=t.status,
        )
        for t in templates
    ]


@router.get(
    "/for-primitive/{primitive_key}",
    response_model=list[TransformationTemplateSummary],
)
async def templates_for_primitive(primitive_key: str):
    """Get transformations that serve a given analytical primitive.

    Enables planner discovery: primitive -> renderer -> transformation.
    """
    registry = get_transformation_registry()
    templates = registry.for_primitive(primitive_key)
    return [
        TransformationTemplateSummary(
            template_key=t.template_key,
            template_name=t.template_name,
            description=t.description,
            transformation_type=t.transformation_type,
            applicable_renderer_types=t.applicable_renderer_types,
            tags=t.tags,
            status=t.status,
        )
        for t in templates
    ]


@router.get(
    "/for-pattern",
    response_model=list[TransformationTemplateSummary],
)
async def templates_for_pattern(
    data_shape: Optional[str] = Query(
        None, description="Output data shape: object_array, nested_sections, etc."
    ),
    renderer_type: Optional[str] = Query(
        None, description="Target renderer type"
    ),
    domain: Optional[str] = Query(
        None, description="Domain: generic, genealogy, rhetoric, policy"
    ),
):
    """Find templates by output data shape and/or target renderer, across domains.

    Enables cross-domain template discovery for the orchestrator.
    """
    registry = get_transformation_registry()
    templates = registry.for_pattern(
        data_shape=data_shape,
        renderer_type=renderer_type,
        domain=domain,
    )
    return [
        TransformationTemplateSummary(
            template_key=t.template_key,
            template_name=t.template_name,
            description=t.description,
            transformation_type=t.transformation_type,
            applicable_renderer_types=t.applicable_renderer_types,
            domain=t.domain,
            pattern_type=t.pattern_type,
            data_shape_out=t.data_shape_out,
            tags=t.tags,
            status=t.status,
        )
        for t in templates
    ]


# ── Detail endpoint ──────────────────────────────────────


@router.get("/{template_key}", response_model=TransformationTemplate)
async def get_transformation(template_key: str):
    """Get a single transformation template by key."""
    return _get_or_404(template_key)


# ── CRUD ─────────────────────────────────────────────────


@router.post("", response_model=TransformationTemplate, status_code=201)
async def create_transformation(template: TransformationTemplate):
    """Create a new transformation template."""
    registry = get_transformation_registry()

    if registry.get(template.template_key) is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Template '{template.template_key}' already exists",
        )

    success = registry.save(template.template_key, template)
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save template '{template.template_key}'",
        )

    mark_definitions_modified()
    logger.info(f"Created transformation template: {template.template_key}")
    return template


@router.put("/{template_key}", response_model=TransformationTemplate)
async def update_transformation(
    template_key: str, template: TransformationTemplate
):
    """Update an existing transformation template."""
    registry = get_transformation_registry()

    if registry.get(template_key) is None:
        raise HTTPException(
            status_code=404,
            detail=f"Template '{template_key}' not found",
        )

    if template.template_key != template_key:
        raise HTTPException(
            status_code=400,
            detail=f"template_key in body ('{template.template_key}') "
            f"must match URL ('{template_key}')",
        )

    success = registry.save(template_key, template)
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save template '{template_key}'",
        )

    mark_definitions_modified()
    logger.info(f"Updated transformation template: {template_key}")
    return template


@router.delete("/{template_key}")
async def delete_transformation(template_key: str):
    """Delete a transformation template."""
    registry = get_transformation_registry()

    success = registry.delete(template_key)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Template '{template_key}' not found",
        )

    mark_definitions_modified()
    logger.info(f"Deleted transformation template: {template_key}")
    return {"deleted": template_key}


# ── Reload ───────────────────────────────────────────────


@router.post("/reload")
async def reload_transformations():
    """Force reload transformation templates from disk."""
    registry = get_transformation_registry()
    registry.reload()
    return {"reloaded": True, "count": registry.count()}


# ── Execute ──────────────────────────────────────────────


@router.post("/execute", response_model=TransformationExecuteResponse)
async def execute_transformation(
    request: TransformationExecuteRequest,
):
    """Execute a transformation on data.

    Provide either a template_key (to use a saved template's spec)
    or inline spec fields (transformation_type, field_mapping, etc.).

    For LLM types (llm_extract, llm_summarize), requires ANTHROPIC_API_KEY.
    """
    executor = get_transformation_executor()

    # Resolve spec: template takes precedence
    if request.template_key:
        template = _get_or_404(request.template_key)
        result = await executor.execute(
            data=request.data,
            transformation_type=template.transformation_type,
            field_mapping=template.field_mapping,
            llm_extraction_schema=template.llm_extraction_schema,
            llm_prompt_template=template.llm_prompt_template,
            stance_key=template.stance_key or request.stance_key,
            aggregate_config=template.aggregate_config,
            model=template.model,
            model_fallback=template.model_fallback,
            max_tokens=template.max_tokens,
            cache_key=request.cache_key,
        )
    elif request.transformation_type:
        result = await executor.execute(
            data=request.data,
            transformation_type=request.transformation_type,
            field_mapping=request.field_mapping,
            llm_extraction_schema=request.llm_extraction_schema,
            llm_prompt_template=request.llm_prompt_template,
            stance_key=request.stance_key,
            aggregate_config=request.aggregate_config,
            cache_key=request.cache_key,
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either template_key or transformation_type",
        )

    if not result.success:
        # Still return 200 with success=false so consumers can handle it
        logger.warning(
            f"Transformation failed: {result.error} "
            f"(type={result.transformation_type})"
        )

    return TransformationExecuteResponse(
        success=result.success,
        data=result.data,
        error=result.error,
        transformation_type=result.transformation_type,
        model_used=result.model_used,
        token_count=result.token_count,
        cached=result.cached,
        execution_time_ms=result.execution_time_ms,
    )


# ── Generate (LLM-powered template creation) ─────────────


class TransformationGenerateRequest(BaseModel):
    """Request to generate a new transformation template via LLM."""

    engine_key: str = Field(
        ..., description="Engine whose output to transform"
    )
    renderer_type: str = Field(
        ..., description="Target renderer type for the output"
    )
    description: str = Field(
        default="",
        description="What the transformation should extract",
    )
    domain: str = Field(
        default="generic",
        description="Domain for the generated template",
    )
    save: bool = Field(
        default=False,
        description="Whether to save the generated template to disk",
    )


@router.post("/generate", response_model=TransformationTemplate)
async def generate_transformation(request: TransformationGenerateRequest):
    """LLM-powered transformation template generation.

    Given an engine key and target renderer type, generates an extraction
    prompt + schema that transforms the engine's prose output into
    structured data suitable for the renderer.

    Set save=true to persist the generated template.
    """
    from src.engines.registry import get_engine_registry
    from src.renderers.registry import get_renderer_registry

    # Validate engine and renderer exist
    engine_registry = get_engine_registry()
    engine = engine_registry.get(request.engine_key)
    if engine is None:
        raise HTTPException(
            status_code=404,
            detail=f"Engine '{request.engine_key}' not found",
        )

    renderer_registry = get_renderer_registry()
    renderer = renderer_registry.get(request.renderer_type)
    if renderer is None:
        raise HTTPException(
            status_code=404,
            detail=f"Renderer '{request.renderer_type}' not found",
        )

    # Get LLM client
    try:
        from src.llm.client import get_anthropic_client, GENERATION_MODEL, parse_llm_json_response
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="LLM client not available",
        )

    client = get_anthropic_client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="LLM service unavailable. Set ANTHROPIC_API_KEY.",
        )

    # Build prompt for template generation
    engine_info = f"Engine: {engine.engine_key} — {engine.engine_name}"
    if hasattr(engine, "description") and engine.description:
        engine_info += f"\nDescription: {engine.description}"

    renderer_info = (
        f"Renderer: {renderer.renderer_key} — {renderer.renderer_name}\n"
        f"Category: {renderer.category}\n"
        f"Ideal data shapes: {', '.join(renderer.ideal_data_shapes)}"
    )
    if renderer.config_schema:
        config_keys = list(renderer.config_schema.get("properties", {}).keys())
        renderer_info += f"\nConfig keys: {', '.join(config_keys)}"

    prompt = f"""You are a transformation template generator for an analytical visualization system.

Given an engine and a target renderer, generate a TransformationTemplate that extracts
structured data from the engine's prose output into a format the renderer can display.

{engine_info}

{renderer_info}

Additional context: {request.description}
Domain: {request.domain}

Generate a complete TransformationTemplate JSON with:
1. A descriptive template_key (snake_case, e.g. "{request.engine_key}_{request.renderer_type}_extraction")
2. An extraction schema matching the renderer's expected data shape
3. An llm_prompt_template that instructs an LLM to extract structured JSON from prose
4. Appropriate metadata fields

Return ONLY valid JSON (no markdown fences) matching this schema:
{{
  "template_key": "string",
  "template_name": "string",
  "description": "string",
  "version": 1,
  "transformation_type": "llm_extract",
  "llm_extraction_schema": {{}},
  "llm_prompt_template": "string",
  "applicable_renderer_types": ["{request.renderer_type}"],
  "applicable_engines": ["{request.engine_key}"],
  "domain": "{request.domain}",
  "pattern_type": "string (section_extraction|timeline_extraction|card_extraction|table_extraction|narrative_extraction)",
  "data_shape_out": "string (object_array|nested_sections|timeline_data|key_value_pairs|prose_text)",
  "compatible_sub_renderers": [],
  "tags": [],
  "status": "draft",
  "model": "claude-haiku-4-5-20251001",
  "model_fallback": "claude-sonnet-4-6",
  "max_tokens": 8000
}}"""

    try:
        response = client.messages.create(
            model=GENERATION_MODEL,
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = response.content[0].text
        parsed = parse_llm_json_response(raw_text)
        template = TransformationTemplate.model_validate(parsed)

        if request.save:
            registry = get_transformation_registry()
            success = registry.save(template.template_key, template)
            if not success:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to save generated template '{template.template_key}'",
                )
            mark_definitions_modified()
            logger.info(f"Generated and saved transformation template: {template.template_key}")
        else:
            logger.info(f"Generated transformation template (not saved): {template.template_key}")

        return template

    except Exception as e:
        logger.error(f"Transformation generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Template generation failed: {e}",
        )
