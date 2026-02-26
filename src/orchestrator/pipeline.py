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
from src.objectives.registry import get_objective
from src.orchestrator.adaptive_planner import generate_adaptive_plan
from src.orchestrator.planner import generate_plan
from src.orchestrator.sampler import sample_all_books
from src.orchestrator.schemas import (
    OrchestratorPlanRequest,
    PriorWork,
    TargetWork,
    WorkflowExecutionPlan,
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

    if request.objective_key:
        # Adaptive mode: sample books → plan with objectives
        plan = _generate_adaptive(request, plan_request)
    else:
        # Legacy mode: fixed pipeline
        plan = generate_plan(plan_request)

    # Apply execution_model to plan if specified
    if request.execution_model:
        plan.execution_model = request.execution_model

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
    workflow_key = request.workflow_key or "intellectual_genealogy"
    job_record = create_job(job_id, plan_id="(generating)", workflow_key=workflow_key)

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

    Recovery support:
    - After doc upload, stores a "request snapshot" to plan_data so that
      if the instance dies during plan generation, the new instance can
      regenerate the plan from the snapshot.
    - After plan generation, overwrites plan_data with the full plan.
    """
    try:
        # ── Stage 1: Upload documents ──
        chapter_count = len(request.target_work_chapters)
        base_doc_count = 1 + len(request.prior_works)
        chapter_note = f" + {chapter_count} chapters" if chapter_count else ""
        update_job_progress(
            job_id,
            current_phase=0,
            phase_name="Uploading Documents",
            detail=f"Uploading {base_doc_count} documents{chapter_note}...",
        )

        document_ids = _upload_documents(request)
        logger.info(f"[Pipeline {job_id}] Uploaded {len(document_ids)} documents")

        # ── Stage 1.5: Store request snapshot for recovery ──
        # If the instance dies during plan generation (~2 min), the new
        # instance can regenerate the plan from this snapshot.
        plan_request = _build_plan_request(request)
        _store_request_snapshot(job_id, plan_request, document_ids)

        # ── Stage 2: Generate plan ──
        planning_model_name = request.planning_model or "claude-opus-4-6"
        update_job_progress(
            job_id,
            current_phase=0,
            phase_name="Generating Analysis Plan",
            detail=f"{planning_model_name} analyzing thinker context and generating execution plan...",
        )

        if request.objective_key:
            # Adaptive mode: sample books → plan with objectives
            plan = _generate_adaptive(request, plan_request)
        else:
            # Legacy mode: fixed pipeline
            plan = generate_plan(plan_request)

        # Apply execution_model to plan if specified
        if request.execution_model:
            plan.execution_model = request.execution_model

        logger.info(
            f"[Pipeline {job_id}] Generated plan {plan.plan_id} — "
            f"{len(plan.phases)} phases, {plan.estimated_llm_calls} estimated calls"
        )

        # ── Stage 2.5: Pre-execution plan revision ──
        # If adaptive mode with objective, run plan self-critique using the planning model
        if request.objective_key and not request.skip_plan_revision:
            revision_model = request.planning_model or "claude-opus-4-6"
            update_job_progress(
                job_id,
                current_phase=0,
                phase_name="Reviewing Plan",
                detail=f"{revision_model} reviewing plan for gaps before execution...",
            )
            try:
                plan = _run_pre_execution_revision(plan, request)
            except Exception as e:
                logger.warning(f"[Pipeline {job_id}] Pre-execution revision failed (continuing): {e}")

        # Update job with plan_id and full plan_data (overwrites snapshot)
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
    """Upload all works + their chapters to the document store.

    Returns a dict mapping role/title -> doc_id.
    Keys:
      - "target" for the target work (whole document)
      - "chapter:target:{chapter_id}" for target work chapters
      - prior work title for each prior work (whole document)
      - "chapter:{prior_work_title}:{chapter_id}" for prior work chapters

    Chapters are optional — uploading them makes them available for
    chapter-targeted execution but doesn't force their use.
    """
    document_ids: dict[str, str] = {}

    # Upload target work (whole document)
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

    # Upload target work chapters (if provided)
    _upload_chapters(
        chapters=request.target_work_chapters,
        work_title=request.target_work.title,
        work_key="target",
        author=request.target_work.author,
        document_ids=document_ids,
    )

    # Upload prior works + their chapters
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

        # Upload prior work chapters (if provided)
        _upload_chapters(
            chapters=pw.chapters,
            work_title=pw.title,
            work_key=pw.title,
            author=pw.author,
            document_ids=document_ids,
        )

    return document_ids


def _upload_chapters(
    chapters: list,
    work_title: str,
    work_key: str,
    author: str | None,
    document_ids: dict[str, str],
) -> None:
    """Upload pre-split chapters for a work.

    Stores each chapter as a separate document with role="chapter".
    Keys in document_ids: "chapter:{work_key}:{chapter_id}".
    """
    if not chapters:
        return

    for ch in chapters:
        ch_display_title = f"{work_title} — {ch.title or ch.chapter_id}"
        ch_doc_id = store_document(
            title=ch_display_title,
            text=ch.text,
            author=author,
            role="chapter",
        )
        doc_key = f"chapter:{work_key}:{ch.chapter_id}"
        document_ids[doc_key] = ch_doc_id
        logger.info(
            f"Uploaded chapter: '{ch.chapter_id}' ({ch.title}) -> {ch_doc_id} "
            f"({len(ch.text):,} chars)"
        )

    logger.info(
        f"Uploaded {len(chapters)} chapters for '{work_title}'"
    )


def _store_request_snapshot(
    job_id: str,
    plan_request,
    document_ids: dict[str, str],
) -> None:
    """Store a request snapshot to the job record BEFORE plan generation.

    This allows recovery if the instance dies during plan generation (~2 min).
    The snapshot contains the plan request params + document_ids mapping.
    Recovery detects the _type marker and regenerates the plan.
    """
    snapshot = {
        "_type": "request_snapshot",
        "plan_request": plan_request.model_dump(),
    }
    try:
        execute(
            """UPDATE executor_jobs
               SET plan_data = %s, document_ids = %s
               WHERE job_id = %s""",
            (_json_dumps(snapshot), _json_dumps(document_ids), job_id),
        )
        logger.info(
            f"[Pipeline {job_id}] Stored request snapshot + document_ids "
            f"for recovery support"
        )
    except Exception as e:
        logger.error(f"[Pipeline {job_id}] Failed to store request snapshot: {e}")


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


def _generate_adaptive(
    request: AnalyzeRequest,
    plan_request: OrchestratorPlanRequest,
) -> WorkflowExecutionPlan:
    """Generate an adaptive plan: sample books → load objective → plan.

    Returns a WorkflowExecutionPlan with adaptive fields populated.
    """
    objective = get_objective(request.objective_key)
    if objective is None:
        raise ValueError(
            f"Unknown objective_key: '{request.objective_key}'. "
            f"Valid keys: genealogical, logical"
        )

    logger.info(
        f"Adaptive mode: sampling {1 + len(request.prior_works)} books "
        f"for objective '{request.objective_key}'"
    )

    # Sample books — include chapter metadata when available
    prior_works_for_sampling = []
    for pw in request.prior_works:
        pw_entry: dict = {"title": pw.title, "text": pw.text}
        if pw.chapters:
            pw_entry["chapters"] = [
                {"chapter_id": ch.chapter_id, "title": ch.title, "char_count": len(ch.text)}
                for ch in pw.chapters
            ]
        prior_works_for_sampling.append(pw_entry)

    # Pass pre-uploaded chapter metadata so the sampler uses it
    # instead of running regex detection
    target_chapters = None
    if request.target_work_chapters:
        target_chapters = [
            {
                "chapter_id": ch.chapter_id,
                "title": ch.title,
                "char_count": len(ch.text),
            }
            for ch in request.target_work_chapters
        ]

    book_samples = sample_all_books(
        target_work_text=request.target_work_text,
        target_work_title=request.target_work.title,
        prior_works=prior_works_for_sampling,
        target_chapters=target_chapters,
    )

    logger.info(f"Sampled {len(book_samples)} books, generating adaptive plan...")

    # Generate adaptive plan
    plan = generate_adaptive_plan(
        request=plan_request,
        book_samples=book_samples,
        objective=objective,
        planning_model=request.planning_model,
    )

    return plan


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
        workflow_key=request.workflow_key,
    )


def _run_pre_execution_revision(
    plan: WorkflowExecutionPlan,
    request: AnalyzeRequest,
) -> WorkflowExecutionPlan:
    """Run pre-execution plan revision and apply changes if needed.

    Returns the (possibly revised) plan.
    """
    from src.orchestrator.plan_revision import (
        apply_revision_to_plan,
        revise_plan_pre_execution,
    )

    # Get objective text for the revision prompt
    objective_text = ""
    if request.objective_key:
        objective = get_objective(request.objective_key)
        if objective:
            objective_text = getattr(objective, "planner_strategy", "") or ""

    revision_model = request.planning_model or "claude-opus-4-6"
    plan_dict = plan.model_dump()
    result = revise_plan_pre_execution(
        plan_dict=plan_dict,
        book_samples=plan_dict.get("book_samples", []),
        objective_text=objective_text,
        model=revision_model,
    )

    if result is None:
        return plan  # No revision needed

    # Apply revision
    revised_dict = apply_revision_to_plan(
        plan_dict=plan_dict,
        revision_result=result,
        completed_phases=set(),
    )

    # Rebuild the plan object from the revised dict
    revised_plan = WorkflowExecutionPlan(**revised_dict)
    logger.info(
        f"Pre-execution revision applied: {result['revision']['changes_summary']}"
    )
    return revised_plan
