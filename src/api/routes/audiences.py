"""Audience API routes.

Provides CRUD operations for audience definitions and utility endpoints
for guidance generation, vocabulary translation, and engine weighting.
"""

from fastapi import APIRouter, HTTPException

from src.audiences.registry import get_audience_registry
from src.audiences.schemas import (
    AudienceDefinition,
    AudienceIdentity,
    AudienceSummary,
    CurationGuidance,
    EngineAffinities,
    PatternDiscoveryConfig,
    StrategistGuidance,
    TextualStyleConfig,
    VisualStyleConfig,
    VocabularyConfig,
)

router = APIRouter(prefix="/audiences", tags=["audiences"])


# -------------------------------------------------------------------------
# List / Read
# -------------------------------------------------------------------------

@router.get("", response_model=list[AudienceSummary])
async def list_audiences() -> list[AudienceSummary]:
    """List all audience summaries."""
    registry = get_audience_registry()
    return registry.list_summaries()


@router.get("/keys", response_model=list[str])
async def list_audience_keys() -> list[str]:
    """List all audience keys."""
    registry = get_audience_registry()
    return registry.get_keys()


@router.get("/count")
async def get_audience_count() -> dict[str, int]:
    """Get total number of audiences."""
    registry = get_audience_registry()
    return {"count": registry.count()}


@router.get("/{audience_key}", response_model=AudienceDefinition)
async def get_audience(audience_key: str) -> AudienceDefinition:
    """Get full audience definition."""
    registry = get_audience_registry()
    audience = registry.get(audience_key)
    if audience is None:
        raise HTTPException(
            status_code=404,
            detail=f"Audience not found: {audience_key}",
        )
    return audience


# -------------------------------------------------------------------------
# Per-section getters (for individual tab loading)
# -------------------------------------------------------------------------

@router.get("/{audience_key}/identity", response_model=AudienceIdentity)
async def get_audience_identity(audience_key: str) -> AudienceIdentity:
    """Get audience identity/profile tab."""
    audience = _get_or_404(audience_key)
    return audience.identity


@router.get("/{audience_key}/engine-affinities", response_model=EngineAffinities)
async def get_audience_engine_affinities(audience_key: str) -> EngineAffinities:
    """Get audience engine affinities tab."""
    audience = _get_or_404(audience_key)
    return audience.engine_affinities


@router.get("/{audience_key}/visual-style", response_model=VisualStyleConfig)
async def get_audience_visual_style(audience_key: str) -> VisualStyleConfig:
    """Get audience visual style tab."""
    audience = _get_or_404(audience_key)
    return audience.visual_style


@router.get("/{audience_key}/textual-style", response_model=TextualStyleConfig)
async def get_audience_textual_style(audience_key: str) -> TextualStyleConfig:
    """Get audience textual style tab."""
    audience = _get_or_404(audience_key)
    return audience.textual_style


@router.get("/{audience_key}/curation", response_model=CurationGuidance)
async def get_audience_curation(audience_key: str) -> CurationGuidance:
    """Get audience curation guidance tab."""
    audience = _get_or_404(audience_key)
    return audience.curation


@router.get("/{audience_key}/strategist", response_model=StrategistGuidance)
async def get_audience_strategist(audience_key: str) -> StrategistGuidance:
    """Get audience strategist guidance tab."""
    audience = _get_or_404(audience_key)
    return audience.strategist


@router.get("/{audience_key}/pattern-discovery", response_model=PatternDiscoveryConfig)
async def get_audience_pattern_discovery(audience_key: str) -> PatternDiscoveryConfig:
    """Get audience pattern discovery tab."""
    audience = _get_or_404(audience_key)
    return audience.pattern_discovery


@router.get("/{audience_key}/vocabulary", response_model=VocabularyConfig)
async def get_audience_vocabulary(audience_key: str) -> VocabularyConfig:
    """Get audience vocabulary translations tab."""
    audience = _get_or_404(audience_key)
    return audience.vocabulary


# -------------------------------------------------------------------------
# Utility endpoints
# -------------------------------------------------------------------------

@router.get("/{audience_key}/guidance")
async def get_audience_guidance(audience_key: str) -> dict:
    """Get composed guidance block for prompt injection.

    Returns a ready-to-inject guidance block that combines identity,
    priorities, curation emphasis, and vocabulary guidance.
    """
    registry = get_audience_registry()
    guidance = registry.generate_guidance(audience_key)
    if guidance is None:
        raise HTTPException(
            status_code=404,
            detail=f"Audience not found: {audience_key}",
        )

    vocab_guidance = registry.get_vocabulary_guidance(audience_key)

    return {
        "audience_key": audience_key,
        "guidance": guidance,
        "vocabulary_guidance": vocab_guidance,
    }


@router.get("/{audience_key}/engine-weight/{engine_key}")
async def get_engine_weight(
    audience_key: str,
    engine_key: str,
    engine_category: str = "general",
) -> dict:
    """Calculate audience-specific weight for an engine.

    Returns a 0.4-1.6 multiplier based on category weights
    and engine-specific affinities.
    """
    _get_or_404(audience_key)
    registry = get_audience_registry()
    weight = registry.get_engine_weight(engine_key, engine_category, audience_key)
    return {
        "audience_key": audience_key,
        "engine_key": engine_key,
        "engine_category": engine_category,
        "weight": weight,
    }


@router.get("/{audience_key}/translate/{term}")
async def translate_term(audience_key: str, term: str) -> dict:
    """Translate a technical term for a specific audience."""
    _get_or_404(audience_key)
    registry = get_audience_registry()
    translation = registry.translate_term(term, audience_key)
    return {
        "audience_key": audience_key,
        "term": term,
        "translation": translation,
        "changed": term != translation,
    }


# -------------------------------------------------------------------------
# CRUD: Create / Update / Delete
# -------------------------------------------------------------------------

@router.post("", response_model=AudienceDefinition)
async def create_audience(definition: AudienceDefinition) -> AudienceDefinition:
    """Create a new audience definition."""
    registry = get_audience_registry()

    existing = registry.get(definition.audience_key)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Audience already exists: {definition.audience_key}",
        )

    success = registry.save(definition.audience_key, definition)
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create audience: {definition.audience_key}",
        )

    return definition


@router.put("/{audience_key}", response_model=AudienceDefinition)
async def update_audience(
    audience_key: str, definition: AudienceDefinition
) -> AudienceDefinition:
    """Update an existing audience definition."""
    if audience_key != definition.audience_key:
        raise HTTPException(
            status_code=400,
            detail="URL audience_key must match definition's audience_key",
        )

    registry = get_audience_registry()

    existing = registry.get(audience_key)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail=f"Audience not found: {audience_key}",
        )

    success = registry.save(audience_key, definition)
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update audience: {audience_key}",
        )

    return definition


@router.delete("/{audience_key}")
async def delete_audience(audience_key: str) -> dict:
    """Delete an audience definition."""
    registry = get_audience_registry()

    existing = registry.get(audience_key)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail=f"Audience not found: {audience_key}",
        )

    success = registry.delete(audience_key)
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete audience: {audience_key}",
        )

    return {"status": "deleted", "audience_key": audience_key}


@router.post("/reload")
async def reload_audiences() -> dict:
    """Force reload all audience definitions from disk."""
    registry = get_audience_registry()
    registry.reload()
    return {"status": "reloaded", "count": registry.count()}


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def _get_or_404(audience_key: str) -> AudienceDefinition:
    """Get audience or raise 404."""
    registry = get_audience_registry()
    audience = registry.get(audience_key)
    if audience is None:
        raise HTTPException(
            status_code=404,
            detail=f"Audience not found: {audience_key}",
        )
    return audience
