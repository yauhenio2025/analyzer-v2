"""
Style API routes for managing visual style definitions and affinities.

Includes:
- Style school CRUD and listing
- Affinity mappings (engine, format, audience)
- Design token generation and caching (LLM-powered)
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from typing import Optional

from ...styles.schemas import (
    StyleSchool,
    StyleGuide,
    StyleGuideSummary,
    AffinitySet,
    EngineStyleMapping,
    StyleRecommendRequest,
    StyleRecommendResponse,
)
from ...styles.token_schema import DesignTokenSet
from ...styles.token_generator import (
    generate_design_tokens,
    clear_token_cache,
    tokens_to_css,
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
    for engine in engine_registry.list_summaries():
        # Check if engine has semantic visual intent
        full_engine = engine_registry.get(engine.engine_key)
        has_semantic = False
        visual_patterns = []

        if full_engine and full_engine.stage_context and full_engine.stage_context.concretization:
            has_semantic = full_engine.stage_context.concretization.semantic_visual_intent is not None
            visual_patterns = full_engine.stage_context.concretization.recommended_visual_patterns or []

        mapping = style_registry.get_engine_style_mapping(
            engine_key=engine.engine_key,
            engine_name=engine.engine_name,
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

    engine = engine_registry.get(engine_key)
    if not engine:
        raise HTTPException(status_code=404, detail=f"Engine '{engine_key}' not found")

    has_semantic = False
    visual_patterns = []
    if engine.stage_context and engine.stage_context.concretization:
        has_semantic = engine.stage_context.concretization.semantic_visual_intent is not None
        visual_patterns = engine.stage_context.concretization.recommended_visual_patterns or []

    return style_registry.get_engine_style_mapping(
        engine_key=engine_key,
        engine_name=engine.name,
        has_semantic_intent=has_semantic,
        recommended_visual_patterns=visual_patterns,
    )


@router.post("/recommend", response_model=StyleRecommendResponse)
async def recommend_styles(request: StyleRecommendRequest):
    """Recommend style schools based on combined context signals.

    Accepts engine keys, renderer types, and/or audience, and returns
    a ranked list of style schools with scores and reasoning.
    """
    registry = get_style_registry()
    return registry.recommend_styles(
        engine_keys=request.engine_keys,
        renderer_types=request.renderer_types,
        audience=request.audience,
        limit=request.limit,
    )


@router.post("/reload")
async def reload_styles():
    """Reload all style definitions from disk."""
    registry = get_style_registry()
    registry.reload()
    return {"status": "reloaded", "stats": registry.get_stats()}


# ---------------------------------------------------------------------------
# Design Token Endpoints
# ---------------------------------------------------------------------------

@router.get("/tokens/{school_key}", response_model=DesignTokenSet)
async def get_design_tokens(school_key: StyleSchool):
    """Get complete design token set for a style school.

    Returns cached tokens if available (in-memory or DB).
    Generates via LLM if not cached (~10-20 seconds).
    Cache is invalidated when the school JSON definition changes.
    """
    try:
        return await generate_design_tokens(school_key.value)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/tokens/{school_key}/regenerate", response_model=DesignTokenSet)
async def regenerate_design_tokens(school_key: StyleSchool):
    """Force-regenerate design tokens (clears cache first).

    Use this when you want a fresh LLM generation, e.g., after
    updating the prompt template or wanting a different variation.
    """
    try:
        await clear_token_cache(school_key.value)
        return await generate_design_tokens(school_key.value)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/tokens/{school_key}/css")
async def get_design_tokens_css(school_key: StyleSchool):
    """Get design tokens as CSS custom properties.

    Returns Content-Type: text/css with all tokens as
    --token-name: value custom properties in a :root selector.
    """
    try:
        tokens = await generate_design_tokens(school_key.value)
        css = tokens_to_css(tokens)
        return Response(content=css, media_type="text/css")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
