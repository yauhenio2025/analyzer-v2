"""Workflow API routes."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.workflows.registry import get_workflow_registry
from src.workflows.schemas import (
    WorkflowCategory,
    WorkflowDefinition,
    WorkflowPass,
    WorkflowSummary,
)

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("", response_model=list[WorkflowSummary])
async def list_workflows(
    category: Optional[WorkflowCategory] = Query(
        None, description="Filter by category"
    ),
) -> list[WorkflowSummary]:
    """List all workflows with optional filtering."""
    registry = get_workflow_registry()

    if category:
        return registry.list_by_category(category)
    return registry.list_all()


@router.get("/keys", response_model=list[str])
async def list_workflow_keys() -> list[str]:
    """List all workflow keys."""
    registry = get_workflow_registry()
    return registry.get_workflow_keys()


@router.get("/count")
async def get_workflow_count() -> dict[str, int]:
    """Get total number of workflows."""
    registry = get_workflow_registry()
    return {"count": registry.count()}


@router.get("/category/{category}", response_model=list[WorkflowSummary])
async def list_workflows_by_category(category: WorkflowCategory) -> list[WorkflowSummary]:
    """List workflows in a specific category."""
    registry = get_workflow_registry()
    return registry.list_by_category(category)


@router.get("/{workflow_key}", response_model=WorkflowDefinition)
async def get_workflow(workflow_key: str) -> WorkflowDefinition:
    """Get full workflow definition."""
    registry = get_workflow_registry()
    workflow = registry.get(workflow_key)
    if workflow is None:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow not found: {workflow_key}",
        )
    return workflow


@router.get("/{workflow_key}/passes", response_model=list[WorkflowPass])
async def get_workflow_passes(workflow_key: str) -> list[WorkflowPass]:
    """Get just the passes for a workflow."""
    registry = get_workflow_registry()
    workflow = registry.get(workflow_key)
    if workflow is None:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow not found: {workflow_key}",
        )
    return workflow.passes
