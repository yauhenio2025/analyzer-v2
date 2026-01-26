"""Engine API routes."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.engines.registry import get_engine_registry
from src.engines.schemas import (
    EngineCategory,
    EngineDefinition,
    EnginePromptResponse,
    EngineSchemaResponse,
    EngineSummary,
)

router = APIRouter(prefix="/engines", tags=["engines"])


@router.get("", response_model=list[EngineSummary])
async def list_engines(
    category: Optional[EngineCategory] = Query(
        None, description="Filter by category"
    ),
    paradigm: Optional[str] = Query(
        None, description="Filter by associated paradigm key"
    ),
    search: Optional[str] = Query(
        None, description="Search in name and description"
    ),
) -> list[EngineSummary]:
    """List all engines with optional filtering."""
    registry = get_engine_registry()

    if search:
        engines = registry.search(search)
    elif category:
        engines = registry.list_by_category(category)
    elif paradigm:
        engines = registry.list_by_paradigm(paradigm)
    else:
        engines = registry.list_all()

    return [
        EngineSummary(
            engine_key=e.engine_key,
            engine_name=e.engine_name,
            description=e.description,
            category=e.category,
            kind=e.kind,
            version=e.version,
            paradigm_keys=e.paradigm_keys,
        )
        for e in engines
    ]


@router.get("/keys", response_model=list[str])
async def list_engine_keys() -> list[str]:
    """List all engine keys."""
    registry = get_engine_registry()
    return registry.list_keys()


@router.get("/count")
async def get_engine_count() -> dict[str, int]:
    """Get total number of engines."""
    registry = get_engine_registry()
    return {"count": registry.count()}


@router.get("/category/{category}", response_model=list[EngineSummary])
async def list_engines_by_category(
    category: EngineCategory,
) -> list[EngineSummary]:
    """List engines in a specific category."""
    registry = get_engine_registry()
    engines = registry.list_by_category(category)
    return [
        EngineSummary(
            engine_key=e.engine_key,
            engine_name=e.engine_name,
            description=e.description,
            category=e.category,
            kind=e.kind,
            version=e.version,
            paradigm_keys=e.paradigm_keys,
        )
        for e in engines
    ]


@router.get("/{engine_key}", response_model=EngineDefinition)
async def get_engine(engine_key: str) -> EngineDefinition:
    """Get full engine definition including prompts and schema."""
    registry = get_engine_registry()
    engine = registry.get(engine_key)
    if engine is None:
        raise HTTPException(
            status_code=404,
            detail=f"Engine not found: {engine_key}",
        )
    return engine


@router.get("/{engine_key}/extraction-prompt", response_model=EnginePromptResponse)
async def get_extraction_prompt(engine_key: str) -> EnginePromptResponse:
    """Get extraction prompt for an engine."""
    registry = get_engine_registry()
    engine = registry.get(engine_key)
    if engine is None:
        raise HTTPException(
            status_code=404,
            detail=f"Engine not found: {engine_key}",
        )
    return EnginePromptResponse(
        engine_key=engine_key,
        prompt_type="extraction",
        prompt=engine.extraction_prompt,
    )


@router.get("/{engine_key}/curation-prompt", response_model=EnginePromptResponse)
async def get_curation_prompt(engine_key: str) -> EnginePromptResponse:
    """Get curation prompt for an engine."""
    registry = get_engine_registry()
    engine = registry.get(engine_key)
    if engine is None:
        raise HTTPException(
            status_code=404,
            detail=f"Engine not found: {engine_key}",
        )
    return EnginePromptResponse(
        engine_key=engine_key,
        prompt_type="curation",
        prompt=engine.curation_prompt,
    )


@router.get(
    "/{engine_key}/concretization-prompt", response_model=EnginePromptResponse
)
async def get_concretization_prompt(engine_key: str) -> EnginePromptResponse:
    """Get concretization prompt for an engine (if available)."""
    registry = get_engine_registry()
    engine = registry.get(engine_key)
    if engine is None:
        raise HTTPException(
            status_code=404,
            detail=f"Engine not found: {engine_key}",
        )
    if engine.concretization_prompt is None:
        raise HTTPException(
            status_code=404,
            detail=f"Engine {engine_key} has no concretization prompt",
        )
    return EnginePromptResponse(
        engine_key=engine_key,
        prompt_type="concretization",
        prompt=engine.concretization_prompt,
    )


@router.get("/{engine_key}/schema", response_model=EngineSchemaResponse)
async def get_engine_schema(engine_key: str) -> EngineSchemaResponse:
    """Get canonical schema for an engine."""
    registry = get_engine_registry()
    engine = registry.get(engine_key)
    if engine is None:
        raise HTTPException(
            status_code=404,
            detail=f"Engine not found: {engine_key}",
        )
    return EngineSchemaResponse(
        engine_key=engine_key,
        canonical_schema=engine.canonical_schema,
    )


@router.post("/reload")
async def reload_engines() -> dict[str, str]:
    """Force reload all engine definitions from disk."""
    registry = get_engine_registry()
    registry.reload()
    return {"status": "reloaded", "count": str(registry.count())}
