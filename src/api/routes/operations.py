"""API routes for analytical stances / operations."""

from fastapi import APIRouter, HTTPException

from src.operations.registry import StanceRegistry
from src.operations.schemas import AnalyticalStance, StanceSummary

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
async def list_stances():
    """List all analytical stances (summaries)."""
    return _get_registry().list_summaries()


@router.get("/stances/full", response_model=list[AnalyticalStance])
async def list_stances_full():
    """List all stances with full prose descriptions."""
    return _get_registry().list_all()


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
