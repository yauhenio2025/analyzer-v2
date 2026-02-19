"""All-in-one analysis pipeline: documents -> plan -> execution -> presentation.

This is the top-level entry point for autonomous analysis. It chains:
1. Document upload (store target + prior work texts)
2. Plan generation (LLM produces a WorkflowExecutionPlan)
3. Execution start (background thread runs the plan)

Presentation runs automatically when execution completes (via workflow_runner's
auto-presentation trigger).

The pipeline returns immediately after step 3 — the client polls
GET /v1/executor/jobs/{job_id} for progress.
"""

import logging
from typing import Optional

from src.executor.document_store import store_document
from src.executor.job_manager import create_job
from src.executor.schemas import ExecutorJob
from src.executor.workflow_runner import start_execution_thread
from src.orchestrator.planner import generate_plan
from src.orchestrator.schemas import (
    OrchestratorPlanRequest,
    PriorWork,
    TargetWork,
)

from .pipeline_schemas import AnalyzeRequest, AnalyzeResponse

logger = logging.getLogger(__name__)


def run_analysis_pipeline(request: AnalyzeRequest) -> AnalyzeResponse:
    """Execute the full analysis pipeline.

    Steps:
        1. Upload documents to the document store
        2. Generate an execution plan via the orchestrator
        3. If autonomous mode: start execution immediately
        4. Return job_id + plan_id for polling

    If skip_plan_review is False, only steps 1-2 run and the client
    gets back a plan_id to review before manually starting execution.

    Raises:
        RuntimeError: If plan generation fails (LLM unavailable, etc.)
        ValueError: If request validation fails
    """
    logger.info(
        f"Starting analysis pipeline for {request.thinker_name} — "
        f"target: {request.target_work.title}, "
        f"{len(request.prior_works)} prior works, "
        f"autonomous={request.skip_plan_review}"
    )

    # Step 1: Upload documents
    document_ids = _upload_documents(request)
    logger.info(f"Uploaded {len(document_ids)} documents: {list(document_ids.keys())}")

    # Step 2: Generate plan
    plan_request = _build_plan_request(request)
    plan = generate_plan(plan_request)
    logger.info(
        f"Generated plan {plan.plan_id} — "
        f"{len(plan.phases)} phases, {plan.estimated_llm_calls} estimated calls"
    )

    # Step 3: If checkpoint mode, stop here
    if not request.skip_plan_review:
        return AnalyzeResponse(
            job_id=None,
            plan_id=plan.plan_id,
            document_ids=document_ids,
            status="plan_generated",
            message=(
                f"Plan generated with {len(plan.phases)} phases and "
                f"{plan.estimated_llm_calls} estimated LLM calls. "
                f"Review at GET /v1/orchestrator/plans/{plan.plan_id}, "
                f"then start execution with POST /v1/executor/jobs."
            ),
        )

    # Step 4: Start execution
    job = ExecutorJob(plan_id=plan.plan_id)
    create_job(job.job_id, plan.plan_id)
    start_execution_thread(
        job_id=job.job_id,
        plan_id=plan.plan_id,
        document_ids=document_ids,
    )

    logger.info(f"Started execution job {job.job_id} for plan {plan.plan_id}")

    return AnalyzeResponse(
        job_id=job.job_id,
        plan_id=plan.plan_id,
        document_ids=document_ids,
        status="executing",
        message=(
            f"Pipeline started: plan {plan.plan_id}, job {job.job_id}. "
            f"Poll GET /v1/executor/jobs/{job.job_id} for progress. "
            f"On completion, GET /v1/presenter/page/{job.job_id} for results."
        ),
    )


def _upload_documents(request: AnalyzeRequest) -> dict[str, str]:
    """Upload target work + prior work texts to the document store.

    Returns a dict mapping role/title -> doc_id.
    Keys: "target" for the target work, prior work titles for prior works.
    """
    document_ids: dict[str, str] = {}

    # Upload target work
    target_doc_id = store_document(
        title=request.target_work.title,
        text=request.target_work_text,
        author=request.target_work.author,
        role="target",
    )
    document_ids["target"] = target_doc_id
    logger.info(
        f"Uploaded target: '{request.target_work.title}' -> {target_doc_id} "
        f"({len(request.target_work_text):,} chars)"
    )

    # Upload prior works
    for pw in request.prior_works:
        pw_doc_id = store_document(
            title=pw.title,
            text=pw.text,
            author=pw.author,
            role="prior_work",
        )
        document_ids[pw.title] = pw_doc_id
        logger.info(
            f"Uploaded prior work: '{pw.title}' -> {pw_doc_id} "
            f"({len(pw.text):,} chars)"
        )

    return document_ids


def _build_plan_request(request: AnalyzeRequest) -> OrchestratorPlanRequest:
    """Convert AnalyzeRequest to OrchestratorPlanRequest (stripping text)."""
    prior_works = [
        PriorWork(
            title=pw.title,
            author=pw.author,
            year=pw.year,
            description=pw.description,
            relationship_hint=pw.relationship_hint,
        )
        for pw in request.prior_works
    ]

    return OrchestratorPlanRequest(
        thinker_name=request.thinker_name,
        target_work=request.target_work,
        prior_works=prior_works,
        research_question=request.research_question,
        depth_preference=request.depth_preference,
        focus_hint=request.focus_hint,
    )
