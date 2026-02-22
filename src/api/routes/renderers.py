"""API routes for renderer definitions.

Renderer definitions declare HOW analytical output is visually presented.
Consumer apps fetch the catalog to discover available renderers,
their capabilities, and configuration schemas.
"""

import json
import logging

from fastapi import APIRouter, HTTPException

from src.api.routes.meta import mark_definitions_modified
from src.renderers.registry import get_renderer_registry
from src.renderers.schemas import (
    RendererDefinition,
    RendererRecommendRequest,
    RendererRecommendResponse,
    RendererSummary,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/renderers", tags=["renderers"])


def _get_or_404(renderer_key: str) -> RendererDefinition:
    """Get a renderer by key or raise 404."""
    registry = get_renderer_registry()
    renderer = registry.get(renderer_key)
    if renderer is None:
        available = registry.list_keys()
        raise HTTPException(
            status_code=404,
            detail=f"Renderer '{renderer_key}' not found. Available: {available}",
        )
    return renderer


# -- List endpoints --


@router.get("", response_model=list[RendererSummary])
async def list_renderers():
    """List all renderer definitions (summaries)."""
    registry = get_renderer_registry()
    return registry.list_summaries()


# -- Query endpoints --


@router.get("/for-stance/{stance_key}", response_model=list[RendererSummary])
async def renderers_for_stance(stance_key: str):
    """Get renderers sorted by affinity to a presentation stance.

    Returns renderers that have affinity > 0 for the given stance,
    sorted by affinity score (highest first).
    """
    registry = get_renderer_registry()
    renderers = registry.for_stance(stance_key)
    return [
        RendererSummary(
            renderer_key=r.renderer_key,
            renderer_name=r.renderer_name,
            description=r.description,
            category=r.category,
            stance_affinities=r.stance_affinities,
            supported_apps=r.supported_apps,
            status=r.status,
        )
        for r in renderers
    ]


@router.get("/for-app/{app}", response_model=list[RendererSummary])
async def renderers_for_app(app: str):
    """Get renderers supported by a consumer app."""
    registry = get_renderer_registry()
    renderers = registry.for_app(app)
    return [
        RendererSummary(
            renderer_key=r.renderer_key,
            renderer_name=r.renderer_name,
            description=r.description,
            category=r.category,
            stance_affinities=r.stance_affinities,
            supported_apps=r.supported_apps,
            status=r.status,
        )
        for r in renderers
    ]


@router.get("/for-primitive/{primitive_key}", response_model=list[RendererSummary])
async def renderers_for_primitive(primitive_key: str):
    """Get renderers suited for a given analytical primitive.

    Enables planner discovery: primitive -> renderer -> transformation.
    """
    registry = get_renderer_registry()
    renderers = registry.for_primitive(primitive_key)
    return [
        RendererSummary(
            renderer_key=r.renderer_key,
            renderer_name=r.renderer_name,
            description=r.description,
            category=r.category,
            stance_affinities=r.stance_affinities,
            supported_apps=r.supported_apps,
            status=r.status,
        )
        for r in renderers
    ]


# -- Detail endpoint --


@router.get("/{renderer_key}", response_model=RendererDefinition)
async def get_renderer(renderer_key: str):
    """Get a single renderer definition by key."""
    return _get_or_404(renderer_key)


# -- CRUD --


@router.post("", response_model=RendererDefinition, status_code=201)
async def create_renderer(renderer: RendererDefinition):
    """Create a new renderer definition."""
    registry = get_renderer_registry()

    if registry.get(renderer.renderer_key) is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Renderer '{renderer.renderer_key}' already exists",
        )

    success = registry.save(renderer.renderer_key, renderer)
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save renderer '{renderer.renderer_key}'",
        )

    mark_definitions_modified()
    logger.info(f"Created renderer: {renderer.renderer_key}")
    return renderer


@router.put("/{renderer_key}", response_model=RendererDefinition)
async def update_renderer(renderer_key: str, renderer: RendererDefinition):
    """Update an existing renderer definition."""
    registry = get_renderer_registry()

    if registry.get(renderer_key) is None:
        raise HTTPException(
            status_code=404,
            detail=f"Renderer '{renderer_key}' not found",
        )

    if renderer.renderer_key != renderer_key:
        raise HTTPException(
            status_code=400,
            detail=f"renderer_key in body ('{renderer.renderer_key}') "
            f"must match URL ('{renderer_key}')",
        )

    success = registry.save(renderer_key, renderer)
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save renderer '{renderer_key}'",
        )

    mark_definitions_modified()
    logger.info(f"Updated renderer: {renderer_key}")
    return renderer


@router.delete("/{renderer_key}")
async def delete_renderer(renderer_key: str):
    """Delete a renderer definition."""
    registry = get_renderer_registry()

    success = registry.delete(renderer_key)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Renderer '{renderer_key}' not found",
        )

    mark_definitions_modified()
    logger.info(f"Deleted renderer: {renderer_key}")
    return {"deleted": renderer_key}


# -- LLM Recommendation --


def _build_renderer_catalog_block() -> str:
    """Build a text block describing all renderers for the LLM prompt."""
    registry = get_renderer_registry()
    lines = []
    for r in registry.list_all():
        lines.append(f"## {r.renderer_key} — {r.renderer_name}")
        lines.append(f"Category: {r.category}")
        lines.append(f"Description: {r.description}")
        if r.ideal_data_shapes:
            lines.append(f"Ideal data shapes: {', '.join(r.ideal_data_shapes)}")
        if r.stance_affinities:
            affinities = ", ".join(
                f"{k}: {v}" for k, v in sorted(
                    r.stance_affinities.items(), key=lambda x: -x[1]
                )
            )
            lines.append(f"Stance affinities: {affinities}")
        if r.available_section_renderers:
            lines.append(
                f"Section sub-renderers: {', '.join(r.available_section_renderers)}"
            )
        if r.config_schema:
            schema_keys = list(r.config_schema.get("properties", {}).keys())
            if schema_keys:
                lines.append(f"Config keys: {', '.join(schema_keys)}")
        if r.variants:
            lines.append(f"Variants: {', '.join(r.variants.keys())}")
        if r.supported_apps:
            lines.append(f"Supported apps: {', '.join(r.supported_apps)}")
        lines.append("")
    return "\n".join(lines)


@router.post("/recommend", response_model=RendererRecommendResponse)
async def recommend_renderer(req: RendererRecommendRequest):
    """LLM-powered renderer recommendation for a view context.

    Analyzes the view's data shape, stance, children, and target app
    to recommend the best-fit renderers with reasoning and optional
    config migration hints.
    """
    from src.llm.client import (
        GENERATION_MODEL,
        get_anthropic_client,
        parse_llm_json_response,
    )

    client = get_anthropic_client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="LLM service unavailable. Set ANTHROPIC_API_KEY.",
        )

    catalog_block = _build_renderer_catalog_block()

    # Build view context section
    view_context_parts = []
    if req.view_name:
        view_context_parts.append(f"View name: {req.view_name}")
    if req.description:
        view_context_parts.append(f"Description: {req.description}")
    if req.presentation_stance:
        view_context_parts.append(f"Presentation stance: {req.presentation_stance}")
    if req.renderer_type:
        view_context_parts.append(f"Current renderer: {req.renderer_type}")
    if req.data_source:
        ds = req.data_source
        if ds.get("engine_key"):
            view_context_parts.append(f"Engine: {ds['engine_key']}")
        if ds.get("chain_key"):
            view_context_parts.append(f"Chain: {ds['chain_key']}")
        if ds.get("result_path"):
            view_context_parts.append(f"Result path: {ds['result_path']}")
        if ds.get("scope"):
            view_context_parts.append(f"Scope: {ds['scope']}")
    view_context_parts.append(
        f"Has children: {req.has_children} (count: {req.child_count})"
    )
    if req.parent_view_key:
        view_context_parts.append(f"Parent view: {req.parent_view_key}")
    view_context_parts.append(f"Target app: {req.target_app}")
    if req.renderer_config:
        view_context_parts.append(
            f"Current config keys: {list(req.renderer_config.keys())}"
        )
    view_context = "\n".join(view_context_parts)

    # Build migration section
    migration_section = ""
    if req.include_config_migration and req.migrate_from:
        migration_section = f"""

## Config Migration Request
The user is considering switching FROM "{req.migrate_from}" TO a new renderer.
Include a "config_migration" object in your response with:
- from_renderer: "{req.migrate_from}"
- to_renderer: your top recommendation
- fields_to_add: config keys the new renderer needs
- fields_to_remove: config keys from the old renderer that are irrelevant
- fields_to_transform: mapping of old keys to new keys/descriptions
- explanation: natural-language migration guide
"""

    prompt = f"""You are a renderer selection expert for an analytical visualization system.
Given a view's context and a catalog of available renderers, recommend the best renderers ranked by fit.

# View Context
{view_context}

# Renderer Catalog
{catalog_block}

# Container Logic
- If the view has children (has_children=true), it NEEDS a container renderer (category: "container")
- Container renderers: accordion, tab
- Non-container renderers should be penalized when the view has children
- If the view has NO children and is a leaf node, container renderers are less ideal
{migration_section}
# Instructions
1. Score each renderer 0.0–1.0 based on: stance fit, data shape fit, container need, app support
2. Return the top 5 renderers, ranked by score
3. For each, provide concise reasoning, stance_fit description, and data_shape_fit description
4. Provide an analysis_summary (2-3 sentences) explaining the overall recommendation

Return ONLY valid JSON (no markdown fences) matching this schema:
{{
  "recommendations": [
    {{
      "renderer_key": "string",
      "renderer_name": "string",
      "category": "string",
      "score": 0.0,
      "rank": 1,
      "reasoning": "string",
      "stance_fit": "string",
      "data_shape_fit": "string",
      "config_suggestions": {{}},
      "warnings": []
    }}
  ],
  "best_match": "renderer_key",
  "config_migration": null,
  "analysis_summary": "string"
}}"""

    try:
        response = client.messages.create(
            model=GENERATION_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = response.content[0].text
        parsed = parse_llm_json_response(raw_text)

        result = RendererRecommendResponse.model_validate(parsed)

        logger.info(
            f"Renderer recommendation for view='{req.view_name}': "
            f"best_match={result.best_match}, "
            f"tokens={response.usage.input_tokens + response.usage.output_tokens}"
        )
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"LLM returned invalid JSON: {e}",
        )
    except Exception as e:
        logger.error(f"Renderer recommendation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Recommendation failed: {e}",
        )


# -- Reload --


@router.post("/reload")
async def reload_renderers():
    """Force reload renderer definitions from disk."""
    registry = get_renderer_registry()
    registry.reload()
    return {"reloaded": True, "count": registry.count()}
