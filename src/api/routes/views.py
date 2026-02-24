"""API routes for view definitions.

View definitions declare how analytical outputs become UI. Consumer apps
fetch view trees for their pages and dispatch to their component registries.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.api.routes.meta import mark_definitions_modified
from src.chains.registry import get_chain_registry
from src.views.registry import get_view_registry
from src.views.schemas import (
    ChainViewInfo,
    ComposedPageResponse,
    ViewDefinition,
    ViewSummary,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/views", tags=["views"])


def _get_or_404(view_key: str) -> ViewDefinition:
    """Get a view by key or raise 404."""
    registry = get_view_registry()
    view = registry.get(view_key)
    if view is None:
        available = registry.list_keys()
        raise HTTPException(
            status_code=404,
            detail=f"View '{view_key}' not found. Available: {available}",
        )
    return view


# ── List endpoints ───────────────────────────────────────


@router.get("", response_model=list[ViewSummary])
async def list_views(
    app: Optional[str] = Query(None, description="Filter by target app"),
    page: Optional[str] = Query(None, description="Filter by target page"),
):
    """List all view definitions (summaries) with optional app/page filters."""
    registry = get_view_registry()
    return registry.list_summaries(app=app, page=page)


# ── Composition endpoint ─────────────────────────────────


@router.get(
    "/compose/{app}/{page}",
    response_model=ComposedPageResponse,
)
async def compose_page_views(app: str, page: str):
    """Get the full tree of views for a specific app/page.

    This is the primary consumer endpoint. Returns top-level views
    sorted by position, with nested children resolved. Fetch once,
    render the whole page.

    Example: GET /v1/views/compose/the-critic/genealogy
    """
    registry = get_view_registry()
    return registry.compose_tree(app, page)


# ── Workflow lookup ──────────────────────────────────────


@router.get(
    "/for-workflow/{workflow_key}",
    response_model=list[ViewSummary],
)
async def views_for_workflow(workflow_key: str):
    """Get all views that reference a given workflow.

    Useful for understanding what UI a workflow produces.
    """
    registry = get_view_registry()
    views = registry.for_workflow(workflow_key)
    return [
        ViewSummary(
            view_key=v.view_key,
            view_name=v.view_name,
            description=v.description,
            target_app=v.target_app,
            target_page=v.target_page,
            renderer_type=v.renderer_type,
            presentation_stance=v.presentation_stance,
            position=v.position,
            parent_view_key=v.parent_view_key,
            visibility=v.visibility,
            status=v.status,
        )
        for v in sorted(views, key=lambda v: v.position)
    ]


# ── Chain lookup ──────────────────────────────────────────


@router.get(
    "/for-chain/{chain_key}",
    response_model=list[ChainViewInfo],
)
async def views_for_chain(chain_key: str):
    """Get all views connected to a chain, showing the full presentation pipeline.

    Returns views that reference this chain directly or reference engines
    within the chain. Each result includes data source details, renderer type,
    and sub-renderer breakdown — the complete chain → view → renderer → sub-renderer path.

    Views are returned as a tree: child views nested under their parents.
    """
    chain_registry = get_chain_registry()
    chain = chain_registry.get(chain_key)
    if chain is None:
        raise HTTPException(
            status_code=404,
            detail=f"Chain '{chain_key}' not found",
        )

    view_registry = get_view_registry()
    return view_registry.for_chain(chain_key, chain.engine_keys)


# ── Detail endpoint ──────────────────────────────────────


@router.get("/{view_key}", response_model=ViewDefinition)
async def get_view(view_key: str):
    """Get a single view definition by key."""
    return _get_or_404(view_key)


# ── CRUD ─────────────────────────────────────────────────


@router.post("", response_model=ViewDefinition, status_code=201)
async def create_view(view: ViewDefinition):
    """Create a new view definition."""
    registry = get_view_registry()

    if registry.get(view.view_key) is not None:
        raise HTTPException(
            status_code=409,
            detail=f"View '{view.view_key}' already exists",
        )

    success = registry.save(view.view_key, view)
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save view '{view.view_key}'",
        )

    mark_definitions_modified()
    logger.info(f"Created view: {view.view_key}")
    return view


@router.put("/{view_key}", response_model=ViewDefinition)
async def update_view(view_key: str, view: ViewDefinition):
    """Update an existing view definition."""
    registry = get_view_registry()

    if registry.get(view_key) is None:
        raise HTTPException(
            status_code=404,
            detail=f"View '{view_key}' not found",
        )

    if view.view_key != view_key:
        raise HTTPException(
            status_code=400,
            detail=f"view_key in body ('{view.view_key}') must match URL ('{view_key}')",
        )

    success = registry.save(view_key, view)
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save view '{view_key}'",
        )

    mark_definitions_modified()
    logger.info(f"Updated view: {view_key}")
    return view


@router.delete("/{view_key}")
async def delete_view(view_key: str):
    """Delete a view definition."""
    registry = get_view_registry()

    success = registry.delete(view_key)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"View '{view_key}' not found",
        )

    mark_definitions_modified()
    logger.info(f"Deleted view: {view_key}")
    return {"deleted": view_key}


# ── Reload ───────────────────────────────────────────────


@router.post("/reload")
async def reload_views():
    """Force reload view definitions from disk."""
    registry = get_view_registry()
    registry.reload()
    return {"reloaded": True, "count": registry.count()}


# ── Generate (LLM-powered view generation from patterns) ──


@router.post("/generate")
async def generate_view_endpoint(request: dict):
    """LLM-powered view definition generation from patterns.

    Given a pattern_key + engine_key + workflow context, generates
    a ViewDefinition that composes correctly into existing page trees.

    Required fields: pattern_key, engine_key
    Optional: workflow_key, phase_number, chain_key, scope, target_app,
              target_page, parent_view_key, position, presentation_stance,
              transformation_template_key, description, save
    """
    from src.views.generator import ViewGenerateRequest, ViewGenerateResponse, generate_view

    try:
        req = ViewGenerateRequest.model_validate(request)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid request: {e}",
        )

    try:
        result = await generate_view(req)
        if req.save:
            mark_definitions_modified()
        return result.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"View generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"View generation failed: {e}",
        )
