"""
Primitives API routes - analytical primitives that bridge engines and visuals.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional

from ...primitives.schemas import (
    AnalyticalPrimitive,
    PrimitiveSummary,
    EnginePrimitiveMapping,
)
from ...primitives.registry import get_primitives_registry

router = APIRouter(prefix="/primitives", tags=["primitives"])


@router.get("", response_model=list[PrimitiveSummary])
async def list_primitives():
    """List all analytical primitives."""
    registry = get_primitives_registry()
    return registry.list_primitives()


@router.get("/stats")
async def get_primitives_stats():
    """Get primitives registry statistics."""
    registry = get_primitives_registry()
    return registry.get_stats()


@router.get("/all", response_model=list[AnalyticalPrimitive])
async def get_all_primitives():
    """Get all primitives with full details."""
    registry = get_primitives_registry()
    return list(registry._primitives.values())


@router.get("/engine-mappings", response_model=list[EnginePrimitiveMapping])
async def get_engine_mappings():
    """Get primitive mappings for all engines."""
    registry = get_primitives_registry()
    return registry.get_all_engine_mappings()


@router.get("/{key}", response_model=AnalyticalPrimitive)
async def get_primitive(key: str):
    """Get a specific primitive by key."""
    registry = get_primitives_registry()
    primitive = registry.get_primitive(key)
    if not primitive:
        raise HTTPException(status_code=404, detail=f"Primitive '{key}' not found")
    return primitive


@router.get("/for-engine/{engine_key}", response_model=list[AnalyticalPrimitive])
async def get_primitives_for_engine(engine_key: str):
    """Get primitives associated with an engine."""
    registry = get_primitives_registry()
    return registry.get_primitives_for_engine(engine_key)


@router.get("/for-engine/{engine_key}/guidance")
async def get_guidance_for_engine(engine_key: str):
    """Get Gemini guidance text for an engine's primitives.

    This is the text that should be passed to Gemini to help it
    understand what visual approaches tend to work for this engine.
    """
    registry = get_primitives_registry()
    guidance = registry.get_guidance_for_engine(engine_key)

    primitives = registry.get_primitives_for_engine(engine_key)

    return {
        "engine_key": engine_key,
        "has_guidance": guidance is not None,
        "primitive_count": len(primitives),
        "primitive_keys": [p.key for p in primitives],
        "gemini_guidance": guidance,
    }


@router.post("/reload")
async def reload_primitives():
    """Reload primitives from disk."""
    registry = get_primitives_registry()
    registry.reload()
    return {"status": "reloaded", "stats": registry.get_stats()}
