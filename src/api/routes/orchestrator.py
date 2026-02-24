"""API routes for the context-driven orchestrator.

The orchestrator takes a thinker + corpus + research question and uses
an LLM to generate a WorkflowExecutionPlan — a concrete, contextualized
plan for executing the genealogy workflow.
"""

import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.orchestrator.catalog import assemble_full_catalog, catalog_to_text
from src.orchestrator.pipeline import run_analysis_pipeline
from src.orchestrator.pipeline_schemas import AnalyzeRequest, AnalyzeResponse
from src.orchestrator.planner import generate_plan, load_plan, list_plans, refine_plan
from src.orchestrator.schemas import (
    OrchestratorPlanRequest,
    PlanRefinementRequest,
    WorkflowExecutionPlan,
)
from src.orchestrator.visualization import assemble_pipeline_visualization

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])


# ── Capability Catalog ──────────────────────────────────────


@router.get("/capability-catalog")
async def get_capability_catalog(
    format: Optional[str] = Query(
        None,
        description="Output format: 'raw' for structured JSON, 'text' for LLM-readable markdown. Default: raw",
    ),
    app: Optional[str] = Query(None, description="Filter views by consumer app"),
    page: Optional[str] = Query(None, description="Filter views by page"),
    workflow_key: Optional[str] = Query(None, description="Filter by workflow key"),
):
    """Get the full capability catalog that the orchestrator uses for planning.

    This is the orchestrator's 'menu' — everything it can choose from:
    engines, chains, stances, workflows, views, sub-renderers, view patterns,
    and operationalizations.

    Supports filtering by app, page, and workflow_key.
    Use format=text to get the LLM-readable markdown version.
    """
    catalog = assemble_full_catalog(app=app, page=page, workflow_key=workflow_key)
    if format == "text":
        workflow_name = None
        if catalog.get("workflow"):
            workflow_name = catalog["workflow"][0].get("workflow_name")
        return {"format": "text", "content": catalog_to_text(catalog, workflow_name=workflow_name)}
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


# ── Pipeline Visualization ─────────────────────────────────


@router.get("/plans/{plan_id}/pipeline-visualization")
async def get_pipeline_visualization(plan_id: str):
    """Get the full pipeline tree for a plan, suitable for rendering a visualization.

    Assembles data from multiple registries (workflow, chains, engines,
    operationalizations, stances) into a hierarchical tree showing
    phases → chains → engines → passes → stances → dimensions.

    No LLM calls — reads only from in-memory registries loaded from JSON/YAML.
    """
    try:
        return assemble_pipeline_visualization(plan_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Pipeline visualization failed for {plan_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline visualization assembly failed: {e}",
        )


# ── Decision Trace ─────────────────────────────────────────


@router.get("/plans/{plan_id}/decision-trace")
async def get_decision_trace(plan_id: str):
    """Get the decision trace for an adaptive plan.

    Returns the structured reasoning that drove pipeline composition:
    sampling insights, objective alignment, phase decisions, and catalog coverage.
    """
    plan = load_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")
    if plan.decision_trace is None:
        return {"plan_id": plan_id, "has_decision_trace": False, "decision_trace": None}
    return {
        "plan_id": plan_id,
        "has_decision_trace": True,
        "decision_trace": plan.decision_trace.model_dump(),
    }


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


# ── All-in-One Analysis Pipeline ──────────────────────────────


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    """All-in-one analysis: documents + plan + execution + presentation.

    Accepts inline document texts + thinker context and runs the full pipeline:
    1. Upload documents to the document store
    2. Generate a WorkflowExecutionPlan (Claude Opus, 15-30s)
    3. Start execution (background thread, 5-60+ minutes)

    Returns immediately after step 3 with {job_id, plan_id} for polling.
    Presentation runs automatically when execution completes.

    Set skip_plan_review=false to stop after step 2 (returns plan_id
    for review; manually start execution later with POST /v1/executor/jobs).
    """
    # Fail-fast: validate model API keys are available before starting background work
    for model_field, label in [
        (request.planning_model, "planning"),
        (request.execution_model, "execution"),
    ]:
        if model_field and model_field.startswith("gemini"):
            if not os.environ.get("GEMINI_API_KEY"):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Gemini model '{model_field}' selected for {label} "
                        f"but GEMINI_API_KEY is not configured on the server. "
                        f"Please select a Claude model instead, or ask the admin "
                        f"to set the GEMINI_API_KEY environment variable."
                    ),
                )

    try:
        result = run_analysis_pipeline(request)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Analysis pipeline failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Analysis pipeline failed: {e}",
        )

    logger.info(
        f"Analysis pipeline initiated for {request.thinker_name}: "
        f"plan={result.plan_id}, job={result.job_id}, status={result.status}"
    )
    return result


@router.get("/analyze/{job_id}")
async def get_analysis(job_id: str):
    """Convenience endpoint: combines job status + PagePresentation.

    - If job is running: returns job status with progress
    - If job is completed: returns PagePresentation (render-ready)
    - If job is failed/cancelled: returns job status with error + partial PagePresentation
    """
    from src.executor.job_manager import get_job
    from src.executor.schemas import JobStatusResponse

    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    status = job.get("status", "unknown")

    # Running or pending: return progress
    if status in ("pending", "running"):
        return {
            "job_id": job_id,
            "plan_id": job.get("plan_id", ""),
            "status": status,
            "progress": job.get("progress", {}),
            "total_llm_calls": job.get("total_llm_calls", 0),
            "total_input_tokens": job.get("total_input_tokens", 0),
            "total_output_tokens": job.get("total_output_tokens", 0),
        }

    # Completed: return PagePresentation
    if status == "completed":
        try:
            from src.presenter.presentation_api import assemble_page
            page = assemble_page(job_id)
            return {
                "job_id": job_id,
                "plan_id": job.get("plan_id", ""),
                "status": "completed",
                "presentation": page.model_dump(),
            }
        except Exception as e:
            logger.warning(f"Page assembly failed for completed job {job_id}: {e}")
            return {
                "job_id": job_id,
                "plan_id": job.get("plan_id", ""),
                "status": "completed",
                "presentation": None,
                "presentation_error": str(e),
            }

    # Failed/cancelled: return status + try partial presentation
    result = {
        "job_id": job_id,
        "plan_id": job.get("plan_id", ""),
        "status": status,
        "error": job.get("error"),
        "total_llm_calls": job.get("total_llm_calls", 0),
        "total_input_tokens": job.get("total_input_tokens", 0),
        "total_output_tokens": job.get("total_output_tokens", 0),
    }

    try:
        from src.presenter.presentation_api import assemble_page
        page = assemble_page(job_id)
        result["presentation"] = page.model_dump()
    except Exception:
        result["presentation"] = None

    return result


# ── Book Sampling ──────────────────────────────────────────


@router.post("/sample")
async def sample_books(request: AnalyzeRequest):
    """Sample books to understand their nature before planning.

    Returns BookSample profiles for the target work and all prior works,
    with genre, domain, reasoning modes, and engine category affinities.

    This is a diagnostic/preview endpoint — the full pipeline calls
    sampling automatically when objective_key is set.
    """
    from src.orchestrator.sampler import sample_all_books

    prior_works = [
        {"title": pw.title, "text": pw.text}
        for pw in request.prior_works
    ]

    samples = sample_all_books(
        target_work_text=request.target_work_text,
        target_work_title=request.target_work.title,
        prior_works=prior_works,
    )

    return {
        "samples": [s.model_dump() for s in samples],
        "count": len(samples),
    }


# ── Adaptive Planning ─────────────────────────────────────


@router.post("/plan/adaptive")
async def create_adaptive_plan(request: AnalyzeRequest):
    """Generate an adaptive plan from objective + book samples.

    This endpoint:
    1. Loads the analysis objective from objective_key
    2. Samples all books (target + prior works)
    3. Assembles the full capability catalog
    4. Calls Opus to generate a bespoke pipeline

    Requires objective_key to be set in the request.
    Synchronous call — blocks for 30-60 seconds.
    """
    if not request.objective_key:
        raise HTTPException(
            status_code=400,
            detail="objective_key is required for adaptive planning",
        )

    from src.objectives.registry import get_objective
    from src.orchestrator.sampler import sample_all_books
    from src.orchestrator.adaptive_planner import generate_adaptive_plan
    from src.orchestrator.schemas import OrchestratorPlanRequest, PriorWork

    objective = get_objective(request.objective_key)
    if objective is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown objective_key: '{request.objective_key}'",
        )

    # Sample books
    prior_works_data = [
        {"title": pw.title, "text": pw.text}
        for pw in request.prior_works
    ]
    book_samples = sample_all_books(
        target_work_text=request.target_work_text,
        target_work_title=request.target_work.title,
        prior_works=prior_works_data,
    )

    # Build plan request (metadata only, no texts)
    prior_works_meta = [
        PriorWork(
            title=pw.title,
            author=pw.author,
            year=pw.year,
            description=pw.description,
            relationship_hint=pw.relationship_hint,
        )
        for pw in request.prior_works
    ]
    plan_request = OrchestratorPlanRequest(
        thinker_name=request.thinker_name,
        target_work=request.target_work,
        prior_works=prior_works_meta,
        research_question=request.research_question,
        depth_preference=request.depth_preference,
        focus_hint=request.focus_hint,
    )

    try:
        plan = generate_adaptive_plan(
            request=plan_request,
            book_samples=book_samples,
            objective=objective,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Adaptive plan generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Adaptive plan generation failed: {e}",
        )

    return plan
