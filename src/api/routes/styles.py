"""
Style API routes for managing visual style definitions and affinities.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional

from ...styles.schemas import (
    StyleSchool,
    StyleGuide,
    StyleGuideSummary,
    AffinitySet,
    EngineStyleMapping,
)
from ...styles.registry import get_style_registry
from ...engines.registry import get_engine_registry

router = APIRouter(prefix="/styles", tags=["styles"])


@router.get("", response_model=list[StyleGuideSummary])
async def list_styles():
    """List all available style schools with summaries."""
    registry = get_style_registry()
    return registry.list_styles()


@router.get("/stats")
async def get_style_stats():
    """Get style registry statistics."""
    registry = get_style_registry()
    return registry.get_stats()


@router.get("/schools/{key}", response_model=StyleGuide)
async def get_style(key: StyleSchool):
    """Get a specific style guide by key."""
    registry = get_style_registry()
    style = registry.get_style(key)
    if not style:
        raise HTTPException(status_code=404, detail=f"Style '{key}' not found")
    return style


@router.get("/affinities/engine", response_model=AffinitySet)
async def get_engine_affinities():
    """Get all engine-to-style affinity mappings."""
    registry = get_style_registry()
    return registry.get_engine_affinities()


@router.get("/affinities/format", response_model=AffinitySet)
async def get_format_affinities():
    """Get all format-to-style affinity mappings."""
    registry = get_style_registry()
    return registry.get_format_affinities()


@router.get("/affinities/audience", response_model=AffinitySet)
async def get_audience_affinities():
    """Get all audience-to-style affinity mappings."""
    registry = get_style_registry()
    return registry.get_audience_affinities()


@router.get("/for-engine/{engine_key}", response_model=list[StyleSchool])
async def get_styles_for_engine(engine_key: str):
    """Get preferred styles for a specific engine."""
    registry = get_style_registry()
    return registry.get_styles_for_engine(engine_key)


@router.get("/for-format/{format_key}", response_model=list[StyleSchool])
async def get_styles_for_format(format_key: str):
    """Get preferred styles for a specific visual format."""
    registry = get_style_registry()
    return registry.get_styles_for_format(format_key)


@router.get("/for-audience/{audience}", response_model=list[StyleSchool])
async def get_styles_for_audience(audience: str):
    """Get preferred styles for a specific audience type."""
    registry = get_style_registry()
    return registry.get_styles_for_audience(audience)


@router.get("/engine-mappings", response_model=list[EngineStyleMapping])
async def get_all_engine_style_mappings():
    """Get complete style mappings for all engines (for UI display)."""
    style_registry = get_style_registry()
    engine_registry = get_engine_registry()

    mappings = []
    for engine in engine_registry.list_engines():
        # Check if engine has semantic visual intent
        full_engine = engine_registry.get_engine(engine.key)
        has_semantic = False
        visual_patterns = []

        if full_engine:
            has_semantic = (
                full_engine.stage_context is not None
                and full_engine.stage_context.semantic_visual_intent is not None
            )
            visual_patterns = full_engine.recommended_visual_patterns or []

        mapping = style_registry.get_engine_style_mapping(
            engine_key=engine.key,
            engine_name=engine.name,
            has_semantic_intent=has_semantic,
            recommended_visual_patterns=visual_patterns,
        )
        mappings.append(mapping)

    return mappings


@router.get("/engine-mappings/{engine_key}", response_model=EngineStyleMapping)
async def get_engine_style_mapping(engine_key: str):
    """Get complete style mapping for a specific engine."""
    style_registry = get_style_registry()
    engine_registry = get_engine_registry()

    engine = engine_registry.get_engine(engine_key)
    if not engine:
        raise HTTPException(status_code=404, detail=f"Engine '{engine_key}' not found")

    has_semantic = (
        engine.stage_context is not None
        and engine.stage_context.semantic_visual_intent is not None
    )
    visual_patterns = engine.recommended_visual_patterns or []

    return style_registry.get_engine_style_mapping(
        engine_key=engine_key,
        engine_name=engine.name,
        has_semantic_intent=has_semantic,
        recommended_visual_patterns=visual_patterns,
    )


@router.post("/reload")
async def reload_styles():
    """Reload all style definitions from disk."""
    registry = get_style_registry()
    registry.reload()
    return {"status": "reloaded", "stats": registry.get_stats()}
