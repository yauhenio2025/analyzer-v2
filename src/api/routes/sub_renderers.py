"""API routes for sub-renderer definitions.

Sub-renderer definitions declare atomic UI components within container
renderers (accordion, tab). Consumer apps and the orchestrator use
this catalog to discover and configure section-level rendering.
"""

import logging

from fastapi import APIRouter, HTTPException

from src.api.routes.meta import mark_definitions_modified
from src.sub_renderers.registry import get_sub_renderer_registry
from src.sub_renderers.schemas import (
    SubRendererDefinition,
    SubRendererSummary,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sub-renderers", tags=["sub-renderers"])


def _get_or_404(sub_renderer_key: str) -> SubRendererDefinition:
    """Get a sub-renderer by key or raise 404."""
    registry = get_sub_renderer_registry()
    sub_renderer = registry.get(sub_renderer_key)
    if sub_renderer is None:
        available = registry.list_keys()
        raise HTTPException(
            status_code=404,
            detail=f"Sub-renderer '{sub_renderer_key}' not found. Available: {available}",
        )
    return sub_renderer


@router.get("", response_model=list[SubRendererSummary])
async def list_sub_renderers():
    """List all sub-renderer definitions (summaries)."""
    registry = get_sub_renderer_registry()
    return registry.list_summaries()


@router.get("/for-parent/{renderer_type}", response_model=list[SubRendererSummary])
async def sub_renderers_for_parent(renderer_type: str):
    """Get sub-renderers compatible with a parent renderer type."""
    registry = get_sub_renderer_registry()
    sub_renderers = registry.for_parent(renderer_type)
    return [
        SubRendererSummary(
            sub_renderer_key=r.sub_renderer_key,
            sub_renderer_name=r.sub_renderer_name,
            description=r.description,
            category=r.category,
            ideal_data_shapes=r.ideal_data_shapes,
            stance_affinities=r.stance_affinities,
            parent_renderer_types=r.parent_renderer_types,
            status=r.status,
        )
        for r in sub_renderers
    ]


@router.get("/for-data-shape/{shape}", response_model=list[SubRendererSummary])
async def sub_renderers_for_data_shape(shape: str):
    """Get sub-renderers that handle a given data shape."""
    registry = get_sub_renderer_registry()
    sub_renderers = registry.for_data_shape(shape)
    return [
        SubRendererSummary(
            sub_renderer_key=r.sub_renderer_key,
            sub_renderer_name=r.sub_renderer_name,
            description=r.description,
            category=r.category,
            ideal_data_shapes=r.ideal_data_shapes,
            stance_affinities=r.stance_affinities,
            parent_renderer_types=r.parent_renderer_types,
            status=r.status,
        )
        for r in sub_renderers
    ]


@router.get("/{sub_renderer_key}", response_model=SubRendererDefinition)
async def get_sub_renderer(sub_renderer_key: str):
    """Get a single sub-renderer definition by key."""
    return _get_or_404(sub_renderer_key)


@router.post("", response_model=SubRendererDefinition, status_code=201)
async def create_sub_renderer(sub_renderer: SubRendererDefinition):
    """Create a new sub-renderer definition."""
    registry = get_sub_renderer_registry()
    if registry.get(sub_renderer.sub_renderer_key) is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Sub-renderer '{sub_renderer.sub_renderer_key}' already exists",
        )
    success = registry.save(sub_renderer.sub_renderer_key, sub_renderer)
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to save sub-renderer '{sub_renderer.sub_renderer_key}'")
    mark_definitions_modified()
    logger.info(f"Created sub-renderer: {sub_renderer.sub_renderer_key}")
    return sub_renderer


@router.put("/{sub_renderer_key}", response_model=SubRendererDefinition)
async def update_sub_renderer(sub_renderer_key: str, sub_renderer: SubRendererDefinition):
    """Update an existing sub-renderer definition."""
    registry = get_sub_renderer_registry()
    if registry.get(sub_renderer_key) is None:
        raise HTTPException(status_code=404, detail=f"Sub-renderer '{sub_renderer_key}' not found")
    if sub_renderer.sub_renderer_key != sub_renderer_key:
        raise HTTPException(status_code=400, detail=f"sub_renderer_key in body must match URL")
    success = registry.save(sub_renderer_key, sub_renderer)
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to save sub-renderer '{sub_renderer_key}'")
    mark_definitions_modified()
    logger.info(f"Updated sub-renderer: {sub_renderer_key}")
    return sub_renderer


@router.delete("/{sub_renderer_key}")
async def delete_sub_renderer(sub_renderer_key: str):
    """Delete a sub-renderer definition."""
    registry = get_sub_renderer_registry()
    success = registry.delete(sub_renderer_key)
    if not success:
        raise HTTPException(status_code=404, detail=f"Sub-renderer '{sub_renderer_key}' not found")
    mark_definitions_modified()
    logger.info(f"Deleted sub-renderer: {sub_renderer_key}")
    return {"deleted": sub_renderer_key}


@router.post("/reload")
async def reload_sub_renderers():
    """Force reload sub-renderer definitions from disk."""
    registry = get_sub_renderer_registry()
    registry.reload()
    return {"reloaded": True, "count": registry.count()}
