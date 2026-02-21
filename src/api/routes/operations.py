"""API routes for analytical stances / operations."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.operations.registry import StanceRegistry
from src.operations.schemas import AnalyticalStance, RendererAffinity, StanceSummary

router = APIRouter(prefix="/v1/operations", tags=["operations"])

_registry: StanceRegistry | None = None


def init_registry(registry: StanceRegistry) -> None:
    global _registry
    _registry = registry


def _get_registry() -> StanceRegistry:
    if _registry is None:
        raise HTTPException(status_code=503, detail="Stance registry not initialized")
    return _registry


# ── List endpoints ───────────────────────────────────────


@router.get("/stances", response_model=list[StanceSummary])
async def list_stances(
    type: Optional[str] = Query(
        None,
        description="Filter by stance type: 'analytical' or 'presentation'",
    ),
):
    """List stances (summaries). Filter by type=analytical or type=presentation."""
    return _get_registry().list_summaries(stance_type=type)


@router.get("/stances/full", response_model=list[AnalyticalStance])
async def list_stances_full(
    type: Optional[str] = Query(
        None,
        description="Filter by stance type: 'analytical' or 'presentation'",
    ),
):
    """List all stances with full prose descriptions."""
    return _get_registry().list_all(stance_type=type)


# ── Detail endpoints ─────────────────────────────────────


@router.get("/stances/{key}", response_model=AnalyticalStance)
async def get_stance(key: str):
    """Get a single stance by key."""
    reg = _get_registry()
    stance = reg.get(key)
    if not stance:
        raise HTTPException(
            status_code=404,
            detail=f"Stance '{key}' not found. Available: {[s.key for s in reg.list_all()]}",
        )
    return stance


@router.get("/stances/{key}/text", response_model=str)
async def get_stance_text(key: str):
    """Get just the stance prose (for prompt injection)."""
    reg = _get_registry()
    text = reg.get_stance_text(key)
    if text is None:
        raise HTTPException(status_code=404, detail=f"Stance '{key}' not found")
    return text


# ── Filter endpoints ─────────────────────────────────────


@router.get("/stances/{key}/renderers", response_model=list[RendererAffinity])
async def get_stance_renderers(key: str):
    """Get preferred renderers for a presentation stance.

    Returns the renderer affinities defined on the stance, sorted by
    affinity score (highest first). Only meaningful for presentation stances.
    """
    reg = _get_registry()
    stance = reg.get(key)
    if not stance:
        raise HTTPException(
            status_code=404,
            detail=f"Stance '{key}' not found. Available: {[s.key for s in reg.list_all()]}",
        )
    # Sort by affinity descending
    return sorted(stance.preferred_renderers, key=lambda r: r.affinity, reverse=True)


@router.get("/stances/position/{position}", response_model=list[StanceSummary])
async def get_stances_by_position(position: str):
    """Get stances suitable for a given pass position (early/middle/late)."""
    reg = _get_registry()
    stances = reg.get_by_position(position)
    return [
        StanceSummary(
            key=s.key,
            name=s.name,
            cognitive_mode=s.cognitive_mode,
            typical_position=s.typical_position,
        )
        for s in stances
    ]
