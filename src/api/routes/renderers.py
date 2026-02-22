"""API routes for renderer definitions.

Renderer definitions declare HOW analytical output is visually presented.
Consumer apps fetch the catalog to discover available renderers,
their capabilities, and configuration schemas.
"""

import logging

from fastapi import APIRouter, HTTPException

from src.api.routes.meta import mark_definitions_modified
from src.renderers.registry import get_renderer_registry
from src.renderers.schemas import RendererDefinition, RendererSummary

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


# -- Reload --


@router.post("/reload")
async def reload_renderers():
    """Force reload renderer definitions from disk."""
    registry = get_renderer_registry()
    registry.reload()
    return {"reloaded": True, "count": registry.count()}
