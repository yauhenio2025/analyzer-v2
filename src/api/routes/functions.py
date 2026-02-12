"""Function API routes."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.functions.registry import get_function_registry
from src.functions.schemas import (
    FunctionCategory,
    FunctionDefinition,
    FunctionImplementationsResponse,
    FunctionPromptsResponse,
    FunctionSummary,
    FunctionTier,
)

router = APIRouter(prefix="/functions", tags=["functions"])


@router.get("", response_model=list[FunctionSummary])
async def list_functions(
    category: Optional[FunctionCategory] = Query(
        None, description="Filter by category"
    ),
    tier: Optional[FunctionTier] = Query(
        None, description="Filter by model tier"
    ),
    project: Optional[str] = Query(
        None, description="Filter by source project"
    ),
    track: Optional[str] = Query(
        None, description="Filter by track (ideas, process, both)"
    ),
    search: Optional[str] = Query(
        None, description="Search in name, description, and tags"
    ),
) -> list[FunctionSummary]:
    """List all functions with optional filtering."""
    registry = get_function_registry()

    if search:
        functions = registry.search(search)
    elif category:
        functions = registry.list_by_category(category)
    elif tier:
        functions = registry.list_by_tier(tier)
    elif project:
        functions = registry.list_by_project(project)
    else:
        functions = registry.list_all()

    # Apply track filter
    if track:
        functions = [f for f in functions if f.track == track]

    return [
        FunctionSummary(
            function_key=f.function_key,
            function_name=f.function_name,
            description=f.description,
            category=f.category,
            tier=f.tier,
            invocation_pattern=f.invocation_pattern,
            source_projects=f.source_projects,
            implementation_count=len(f.implementations),
            track=f.track,
            tags=f.tags,
        )
        for f in functions
    ]


@router.get("/categories")
async def list_categories() -> dict[str, dict[str, int]]:
    """Get function counts by category."""
    registry = get_function_registry()
    counts: dict[str, int] = {}
    for func in registry.list_all():
        cat = func.category.value
        counts[cat] = counts.get(cat, 0) + 1
    return {"categories": counts}


@router.get("/projects", response_model=list[str])
async def list_projects() -> list[str]:
    """List all unique source project names."""
    registry = get_function_registry()
    return registry.list_projects()


@router.get("/project/{project}", response_model=list[FunctionSummary])
async def list_by_project(project: str) -> list[FunctionSummary]:
    """List all functions for a specific project."""
    registry = get_function_registry()
    functions = registry.list_by_project(project)
    return [
        FunctionSummary(
            function_key=f.function_key,
            function_name=f.function_name,
            description=f.description,
            category=f.category,
            tier=f.tier,
            invocation_pattern=f.invocation_pattern,
            source_projects=f.source_projects,
            implementation_count=len(f.implementations),
            track=f.track,
            tags=f.tags,
        )
        for f in functions
    ]


@router.get("/{function_key}", response_model=FunctionDefinition)
async def get_function(function_key: str) -> FunctionDefinition:
    """Get full function definition."""
    registry = get_function_registry()
    func = registry.get(function_key)
    if func is None:
        raise HTTPException(
            status_code=404,
            detail=f"Function not found: {function_key}",
        )
    return func


@router.get("/{function_key}/prompts", response_model=FunctionPromptsResponse)
async def get_function_prompts(function_key: str) -> FunctionPromptsResponse:
    """Get prompt templates for a function."""
    registry = get_function_registry()
    func = registry.get(function_key)
    if func is None:
        raise HTTPException(
            status_code=404,
            detail=f"Function not found: {function_key}",
        )
    return FunctionPromptsResponse(
        function_key=func.function_key,
        function_name=func.function_name,
        prompt_count=len(func.prompt_templates),
        prompts=func.prompt_templates,
    )


@router.get(
    "/{function_key}/implementations",
    response_model=FunctionImplementationsResponse,
)
async def get_function_implementations(
    function_key: str,
) -> FunctionImplementationsResponse:
    """Get implementation locations for a function."""
    registry = get_function_registry()
    func = registry.get(function_key)
    if func is None:
        raise HTTPException(
            status_code=404,
            detail=f"Function not found: {function_key}",
        )
    return FunctionImplementationsResponse(
        function_key=func.function_key,
        function_name=func.function_name,
        implementation_count=len(func.implementations),
        implementations=func.implementations,
    )


@router.post("/reload")
async def reload_functions() -> dict[str, str]:
    """Force reload all function definitions from disk."""
    registry = get_function_registry()
    registry.reload()
    return {"status": "reloaded", "count": str(registry.count())}
