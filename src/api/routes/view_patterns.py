"""API routes for view patterns.

View patterns are reusable templates for common view configurations.
They capture renderer + config + sub-renderer combinations that work
well for classes of analytical output. An LLM orchestrator instantiates
patterns rather than copying specific views.
"""

import logging

from fastapi import APIRouter, HTTPException

from src.api.routes.meta import mark_definitions_modified
from src.views.pattern_registry import get_pattern_registry
from src.views.pattern_schemas import (
    ViewPattern,
    ViewPatternSummary,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/views/patterns", tags=["view-patterns"])


def _get_or_404(pattern_key: str) -> ViewPattern:
    """Get a view pattern by key or raise 404."""
    registry = get_pattern_registry()
    pattern = registry.get(pattern_key)
    if pattern is None:
        available = registry.list_keys()
        raise HTTPException(
            status_code=404,
            detail=f"View pattern '{pattern_key}' not found. Available: {available}",
        )
    return pattern


# -- List endpoints --


@router.get("", response_model=list[ViewPatternSummary])
async def list_view_patterns():
    """List all view patterns (summaries)."""
    registry = get_pattern_registry()
    return registry.list_summaries()


# -- Query endpoints --


@router.get("/for-renderer/{renderer_type}", response_model=list[ViewPatternSummary])
async def patterns_for_renderer(renderer_type: str):
    """Get patterns that use a specific renderer type."""
    registry = get_pattern_registry()
    patterns = registry.for_renderer(renderer_type)
    return [
        ViewPatternSummary(
            pattern_key=p.pattern_key,
            pattern_name=p.pattern_name,
            description=p.description,
            renderer_type=p.renderer_type,
            ideal_for=p.ideal_for,
            data_shape_in=p.data_shape_in,
            example_views=p.example_views,
            status=p.status,
        )
        for p in patterns
    ]


@router.get("/for-data-shape/{shape}", response_model=list[ViewPatternSummary])
async def patterns_for_data_shape(shape: str):
    """Get patterns that expect a given data shape."""
    registry = get_pattern_registry()
    patterns = registry.for_data_shape(shape)
    return [
        ViewPatternSummary(
            pattern_key=p.pattern_key,
            pattern_name=p.pattern_name,
            description=p.description,
            renderer_type=p.renderer_type,
            ideal_for=p.ideal_for,
            data_shape_in=p.data_shape_in,
            example_views=p.example_views,
            status=p.status,
        )
        for p in patterns
    ]


# -- Detail endpoint --


@router.get("/{pattern_key}", response_model=ViewPattern)
async def get_view_pattern(pattern_key: str):
    """Get a single view pattern by key."""
    return _get_or_404(pattern_key)


# -- CRUD --


@router.post("", response_model=ViewPattern, status_code=201)
async def create_view_pattern(pattern: ViewPattern):
    """Create a new view pattern."""
    registry = get_pattern_registry()

    if registry.get(pattern.pattern_key) is not None:
        raise HTTPException(
            status_code=409,
            detail=f"View pattern '{pattern.pattern_key}' already exists",
        )

    success = registry.save(pattern.pattern_key, pattern)
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save view pattern '{pattern.pattern_key}'",
        )

    mark_definitions_modified()
    logger.info(f"Created view pattern: {pattern.pattern_key}")
    return pattern


@router.put("/{pattern_key}", response_model=ViewPattern)
async def update_view_pattern(pattern_key: str, pattern: ViewPattern):
    """Update an existing view pattern."""
    registry = get_pattern_registry()

    if registry.get(pattern_key) is None:
        raise HTTPException(
            status_code=404,
            detail=f"View pattern '{pattern_key}' not found",
        )

    if pattern.pattern_key != pattern_key:
        raise HTTPException(
            status_code=400,
            detail=f"pattern_key in body ('{pattern.pattern_key}') "
            f"must match URL ('{pattern_key}')",
        )

    success = registry.save(pattern_key, pattern)
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save view pattern '{pattern_key}'",
        )

    mark_definitions_modified()
    logger.info(f"Updated view pattern: {pattern_key}")
    return pattern


@router.delete("/{pattern_key}")
async def delete_view_pattern(pattern_key: str):
    """Delete a view pattern."""
    registry = get_pattern_registry()

    success = registry.delete(pattern_key)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"View pattern '{pattern_key}' not found",
        )

    mark_definitions_modified()
    logger.info(f"Deleted view pattern: {pattern_key}")
    return {"deleted": pattern_key}


# -- Reload --


@router.post("/reload")
async def reload_view_patterns():
    """Force reload view pattern definitions from disk."""
    registry = get_pattern_registry()
    registry.reload()
    return {"reloaded": True, "count": registry.count()}
