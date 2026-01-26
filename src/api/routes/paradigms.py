"""Paradigm API routes."""

from fastapi import APIRouter, HTTPException

from src.paradigms.registry import get_paradigm_registry
from src.paradigms.schemas import (
    CritiquePattern,
    ParadigmCritiquePatternsResponse,
    ParadigmDefinition,
    ParadigmEnginesResponse,
    ParadigmPrimerResponse,
    ParadigmSummary,
)

router = APIRouter(prefix="/paradigms", tags=["paradigms"])


@router.get("", response_model=list[ParadigmSummary])
async def list_paradigms(active_only: bool = False) -> list[ParadigmSummary]:
    """List all paradigms."""
    registry = get_paradigm_registry()

    if active_only:
        paradigms = registry.list_active()
    else:
        paradigms = registry.list_all()

    return [
        ParadigmSummary(
            paradigm_key=p.paradigm_key,
            paradigm_name=p.paradigm_name,
            description=p.description,
            version=p.version,
            status=p.status,
            guiding_thinkers=p.guiding_thinkers,
            active_traits=p.active_traits,
        )
        for p in paradigms
    ]


@router.get("/keys", response_model=list[str])
async def list_paradigm_keys() -> list[str]:
    """List all paradigm keys."""
    registry = get_paradigm_registry()
    return registry.list_keys()


@router.get("/count")
async def get_paradigm_count() -> dict[str, int]:
    """Get total number of paradigms."""
    registry = get_paradigm_registry()
    return {"count": registry.count()}


@router.get("/{paradigm_key}", response_model=ParadigmDefinition)
async def get_paradigm(paradigm_key: str) -> ParadigmDefinition:
    """Get full paradigm definition including 4-layer ontology."""
    registry = get_paradigm_registry()
    paradigm = registry.get(paradigm_key)
    if paradigm is None:
        raise HTTPException(
            status_code=404,
            detail=f"Paradigm not found: {paradigm_key}",
        )
    return paradigm


@router.get("/{paradigm_key}/primer", response_model=ParadigmPrimerResponse)
async def get_paradigm_primer(paradigm_key: str) -> ParadigmPrimerResponse:
    """Get LLM-ready primer text for a paradigm."""
    registry = get_paradigm_registry()

    try:
        primer_text = registry.generate_primer(paradigm_key)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return ParadigmPrimerResponse(
        paradigm_key=paradigm_key,
        primer_text=primer_text,
    )


@router.get("/{paradigm_key}/engines", response_model=ParadigmEnginesResponse)
async def get_paradigm_engines(paradigm_key: str) -> ParadigmEnginesResponse:
    """Get engines associated with a paradigm."""
    registry = get_paradigm_registry()
    paradigm = registry.get(paradigm_key)
    if paradigm is None:
        raise HTTPException(
            status_code=404,
            detail=f"Paradigm not found: {paradigm_key}",
        )
    return ParadigmEnginesResponse(
        paradigm_key=paradigm_key,
        primary_engines=paradigm.primary_engines,
        compatible_engines=paradigm.compatible_engines,
    )


@router.get(
    "/{paradigm_key}/critique-patterns",
    response_model=ParadigmCritiquePatternsResponse,
)
async def get_paradigm_critique_patterns(
    paradigm_key: str,
) -> ParadigmCritiquePatternsResponse:
    """Get critique patterns for a paradigm."""
    registry = get_paradigm_registry()
    paradigm = registry.get(paradigm_key)
    if paradigm is None:
        raise HTTPException(
            status_code=404,
            detail=f"Paradigm not found: {paradigm_key}",
        )
    return ParadigmCritiquePatternsResponse(
        paradigm_key=paradigm_key,
        critique_patterns=paradigm.critique_patterns,
    )


@router.post("/reload")
async def reload_paradigms() -> dict[str, str]:
    """Force reload all paradigm definitions from disk."""
    registry = get_paradigm_registry()
    registry.reload()
    return {"status": "reloaded", "count": str(registry.count())}
