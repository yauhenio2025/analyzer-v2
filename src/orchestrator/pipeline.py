"""All-in-one analysis pipeline: documents -> plan -> execution -> presentation.

This is the top-level entry point for autonomous analysis. It chains:
1. Document upload (store target + prior work texts)
2. Plan generation (LLM produces a WorkflowExecutionPlan)
3. Execution start (runs the plan through all phases)

The pipeline returns IMMEDIATELY after accepting the request — all heavy
work (document upload, plan generation, execution) runs in a background
thread. The client polls GET /v1/executor/jobs/{job_id} for progress.

Presentation runs automatically when execution completes (via workflow_runner's
auto-presentation trigger).
"""

import logging
import threading
import uuid
from typing import Optional

from src.executor.db import execute, _json_dumps
from src.executor.document_store import store_document
from src.executor.job_manager import (
    create_job,
    update_job_plan_id,
    update_job_progress,
    update_job_status,
)
from src.executor.workflow_runner import execute_plan
from src.orchestrator.planner import generate_plan
from src.orchestrator.schemas import (
    OrchestratorPlanRequest,
    PriorWork,
    TargetWork,
)

from .pipeline_schemas import AnalyzeRequest, AnalyzeResponse

logger = logging.getLogger(__name__)


def run_analysis_pipeline(request: AnalyzeRequest) -> AnalyzeResponse:
    """Start the analysis pipeline asynchronously.

    Creates a job immediately and returns the job_id. All heavy work
    (document upload, plan generation, execution) runs in a background
    thread. The client polls GET /v1/executor/jobs/{job_id} for progress.

    Progress updates flow through the job's progress field:
    - Phase 0: "Uploading documents..." / "Generating analysis plan..."
    - Phase 1.0+: Normal phase-by-phase execution progress

    If skip_plan_review is False, the pipeline runs synchronously up to
    plan generation and returns immediately with the plan_id (no execution).
    """
    logger.info(
        f"Starting analysis pipeline for {request.thinker_name} — "
        f"target: {request.target_work.title}, "
        f"{len(request.prior_works)} prior works, "
        f"autonomous={request.skip_plan_review}"
    )

    # Checkpoint mode: run synchronously (doc upload + plan gen only)
    if not request.skip_plan_review:
        return _run_checkpoint_mode(request)

    # Autonomous mode: return immediately, run everything in background
    return _run_autonomous_mode(request)


def _run_checkpoint_mode(request: AnalyzeRequest) -> AnalyzeResponse:
    """Synchronous path: upload docs + generate plan, return for review."""
    document_ids = _upload_documents(request)
    logger.info(f"Uploaded {len(document_ids)} documents: {list(document_ids.keys())}")

    plan_request = _build_plan_request(request)
    plan = generate_plan(plan_request)
    logger.info(
        f"Generated plan {plan.plan_id} — "
        f"{len(plan.phases)} phases, {plan.estimated_llm_calls} estimated calls"
    )

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


def _run_autonomous_mode(request: AnalyzeRequest) -> AnalyzeResponse:
    """Async path: create job, return immediately, run pipeline in background."""
    # Pre-generate job_id
    job_id = f"job-{uuid.uuid4().hex[:12]}"

    # Create job entry immediately so the client can start polling
    job_record = create_job(job_id, plan_id="(generating)")

    # Set initial progress: pipeline is starting
    update_job_progress(
        job_id,
        current_phase=0,
        phase_name="Pipeline Starting",
        detail=f"Uploading {1 + len(request.prior_works)} documents...",
    )

    # Spawn background thread for the full pipeline
    thread = threading.Thread(
        target=_pipeline_thread,
        args=(job_id, request),
        name=f"pipeline-{job_id}",
        daemon=True,
    )
    thread.start()
    logger.info(f"Pipeline thread started for job {job_id}")

    return AnalyzeResponse(
        job_id=job_id,
        plan_id=None,  # Not known yet — will be set by background thread
        document_ids={},  # Not known yet
        cancel_token=job_record.get("cancel_token"),
        status="executing",
        message=(
            f"Pipeline accepted. Poll GET /v1/executor/jobs/{job_id} for progress. "
            f"Document upload, plan generation, and execution run in background."
        ),
    )


def _pipeline_thread(job_id: str, request: AnalyzeRequest) -> None:
    """Background thread: upload docs → generate plan → execute.

    Updates job progress at each stage so the client can see what's happening.
    On failure at any stage, marks the job as failed with the error.
    """
    try:
        # ── Stage 1: Upload documents ──
        update_job_progress(
            job_id,
            current_phase=0,
            phase_name="Uploading Documents",
            detail=f"Uploading {1 + len(request.prior_works)} documents...",
        )

        document_ids = _upload_documents(request)
        logger.info(f"[Pipeline {job_id}] Uploaded {len(document_ids)} documents")

        # ── Stage 2: Generate plan ──
        update_job_progress(
            job_id,
            current_phase=0,
            phase_name="Generating Analysis Plan",
            detail="Claude Opus analyzing thinker context and generating execution plan...",
        )

        plan_request = _build_plan_request(request)
        plan = generate_plan(plan_request)
        logger.info(
            f"[Pipeline {job_id}] Generated plan {plan.plan_id} — "
            f"{len(plan.phases)} phases, {plan.estimated_llm_calls} estimated calls"
        )

        # Update job with plan_id and plan_data for resume support
        update_job_plan_id(job_id, plan.plan_id)
        _store_plan_and_docs(job_id, plan, document_ids)

        # ── Stage 3: Execute plan ──
        # This calls execute_plan() directly (we're already in a background thread).
        # execute_plan() handles: status → running, phase-by-phase progress,
        # status → completed/failed, and auto-presentation.
        update_job_progress(
            job_id,
            current_phase=0,
            phase_name="Starting Execution",
            detail=f"Executing plan with {plan.estimated_llm_calls} LLM calls...",
        )

        execute_plan(
            job_id=job_id,
            plan_id=plan.plan_id,
            document_ids=document_ids,
            plan_object=plan,
        )

        # execute_plan() sets final status (completed/failed/cancelled)

    except Exception as e:
        logger.error(f"[Pipeline {job_id}] Pipeline failed: {e}", exc_info=True)
        update_job_status(job_id, "failed", error=str(e))


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


def _store_plan_and_docs(job_id: str, plan, document_ids: dict[str, str]) -> None:
    """Store plan_data and document_ids in the job record for resume support.

    After plan generation, we persist the full plan + doc mapping into the
    executor_jobs row so that if the instance recycles, recover_orphaned_jobs()
    can resume from where we left off.
    """
    try:
        execute(
            """UPDATE executor_jobs
               SET plan_data = %s, document_ids = %s
               WHERE job_id = %s""",
            (_json_dumps(plan.model_dump()), _json_dumps(document_ids), job_id),
        )
        logger.info(f"[Pipeline {job_id}] Stored plan_data + document_ids for resume support")
    except Exception as e:
        logger.error(f"[Pipeline {job_id}] Failed to store plan_data: {e}")


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
