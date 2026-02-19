"""API routes for the context-driven orchestrator.

The orchestrator takes a thinker + corpus + research question and uses
an LLM to generate a WorkflowExecutionPlan — a concrete, contextualized
plan for executing the genealogy workflow.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.orchestrator.catalog import assemble_full_catalog, catalog_to_text
from src.orchestrator.planner import generate_plan, load_plan, list_plans, refine_plan
from src.orchestrator.schemas import (
    OrchestratorPlanRequest,
    PlanRefinementRequest,
    WorkflowExecutionPlan,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])


# ── Capability Catalog ──────────────────────────────────────


@router.get("/capability-catalog")
async def get_capability_catalog(
    format: Optional[str] = Query(
        None,
        description="Output format: 'raw' for structured JSON, 'text' for LLM-readable markdown. Default: raw",
    ),
):
    """Get the full capability catalog that the orchestrator uses for planning.

    This is the orchestrator's 'menu' — everything it can choose from:
    engines, chains, stances, workflows, views, operationalizations.

    Use format=text to get the LLM-readable markdown version.
    """
    catalog = assemble_full_catalog()
    if format == "text":
        return {"format": "text", "content": catalog_to_text(catalog)}
    return catalog


# ── Plan Generation ─────────────────────────────────────────


@router.post("/plan", response_model=WorkflowExecutionPlan)
async def create_plan(request: OrchestratorPlanRequest):
    """Generate a new WorkflowExecutionPlan for a thinker and corpus.

    Calls Claude Opus with the capability catalog + thinker context
    and returns a validated plan with per-phase depth, engine overrides,
    context emphasis, and view recommendations.

    This is a synchronous call — it blocks while the LLM generates the plan
    (typically 15-30 seconds).
    """
    try:
        plan = generate_plan(request)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Plan generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Plan generation failed: {e}",
        )

    logger.info(
        f"Generated plan {plan.plan_id} for {request.thinker_name} — "
        f"{len(plan.phases)} phases, {plan.estimated_llm_calls} estimated calls"
    )
    return plan


# ── Plan Listing ────────────────────────────────────────────


@router.get("/plans")
async def get_plans():
    """List all saved plans (summary view).

    Returns plan ID, thinker name, target work title, status,
    and estimated depth profile.
    """
    return list_plans()


# ── Plan Detail ─────────────────────────────────────────────


@router.get("/plans/{plan_id}", response_model=WorkflowExecutionPlan)
async def get_plan(plan_id: str):
    """Get a specific plan by ID."""
    plan = load_plan(plan_id)
    if plan is None:
        raise HTTPException(
            status_code=404,
            detail=f"Plan '{plan_id}' not found",
        )
    return plan


# ── Plan Update (manual edits) ──────────────────────────────


@router.put("/plans/{plan_id}", response_model=WorkflowExecutionPlan)
async def update_plan(plan_id: str, plan: WorkflowExecutionPlan):
    """Update a plan with manual edits.

    The user can adjust depth, skip phases, change focus dimensions, etc.
    This is a direct save — no LLM involved.
    """
    existing = load_plan(plan_id)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail=f"Plan '{plan_id}' not found",
        )

    if plan.plan_id != plan_id:
        raise HTTPException(
            status_code=400,
            detail=f"plan_id in body ('{plan.plan_id}') must match URL ('{plan_id}')",
        )

    # Save directly
    from src.orchestrator.planner import _save_plan
    _save_plan(plan)
    logger.info(f"Updated plan {plan_id} (manual edit)")
    return plan


# ── Plan Refinement (LLM-assisted) ─────────────────────────


@router.post("/plans/{plan_id}/refine", response_model=WorkflowExecutionPlan)
async def refine_plan_endpoint(plan_id: str, refinement: PlanRefinementRequest):
    """Refine an existing plan using LLM-assisted re-planning.

    Send feedback like "make phase 2 deeper" or "skip conditions analysis"
    and the LLM will produce an updated plan that addresses the feedback.
    """
    existing = load_plan(plan_id)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail=f"Plan '{plan_id}' not found",
        )

    try:
        updated = refine_plan(existing, refinement)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Plan refinement failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Plan refinement failed: {e}",
        )

    logger.info(f"Refined plan {plan_id}")
    return updated


# ── Plan Status ─────────────────────────────────────────────


@router.patch("/plans/{plan_id}/status")
async def update_plan_status(plan_id: str, status: str = Query(...)):
    """Update a plan's status (draft → approved → executing → completed).

    Used by the execution layer to track plan lifecycle.
    """
    plan = load_plan(plan_id)
    if plan is None:
        raise HTTPException(
            status_code=404,
            detail=f"Plan '{plan_id}' not found",
        )

    valid_statuses = {"draft", "approved", "executing", "completed"}
    if status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{status}'. Valid: {valid_statuses}",
        )

    plan.status = status

    from src.orchestrator.planner import _save_plan
    _save_plan(plan)
    logger.info(f"Plan {plan_id} status → {status}")
    return {"plan_id": plan_id, "status": status}
