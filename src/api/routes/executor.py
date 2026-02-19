"""Executor API routes for job management, execution, and results.

Endpoints:
    POST /v1/executor/jobs                           Start execution from plan_id
    GET  /v1/executor/jobs                           List jobs
    GET  /v1/executor/jobs/{job_id}                  Poll status + progress
    POST /v1/executor/jobs/{job_id}/cancel           Cancel running job
    GET  /v1/executor/jobs/{job_id}/results          All phase outputs (summaries)
    GET  /v1/executor/jobs/{job_id}/phases/{phase}   Specific phase outputs (full prose)
    DELETE /v1/executor/jobs/{job_id}                Delete a completed job

    POST /v1/executor/documents                      Upload document text
    GET  /v1/executor/documents                      List documents
    GET  /v1/executor/documents/{doc_id}             Retrieve document
    DELETE /v1/executor/documents/{doc_id}           Delete document
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException

from src.executor.db import init_db
from src.executor.document_store import (
    delete_document,
    get_document,
    list_documents,
    store_document,
)
from src.executor.job_manager import (
    create_job,
    delete_job,
    get_job,
    list_jobs,
    request_cancellation,
)
from src.executor.output_store import (
    count_outputs,
    load_outputs_for_context,
    load_phase_outputs,
)
from src.executor.schemas import (
    DocumentRecord,
    DocumentUpload,
    ExecutorJob,
    JobStatusResponse,
    PhaseOutputSummary,
    StartJobRequest,
)
from src.executor.workflow_runner import start_execution_thread

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/executor", tags=["executor"])


# --- Job endpoints ---


@router.post("/jobs")
async def start_job(request: StartJobRequest):
    """Start executing a plan.

    Creates a new job, spawns a background thread for execution,
    and returns the job ID for polling.
    """
    from src.orchestrator.planner import load_plan

    # Validate plan exists
    plan = load_plan(request.plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan not found: {request.plan_id}")

    # Create job
    job = ExecutorJob(plan_id=request.plan_id)
    create_job(job.job_id, request.plan_id)

    # Spawn execution thread
    start_execution_thread(
        job_id=job.job_id,
        plan_id=request.plan_id,
        document_ids=request.document_ids,
    )

    logger.info(f"Started job {job.job_id} for plan {request.plan_id}")

    return {
        "job_id": job.job_id,
        "plan_id": request.plan_id,
        "status": "pending",
        "message": "Execution started. Poll GET /v1/executor/jobs/{job_id} for progress.",
    }


@router.get("/jobs")
async def list_all_jobs(status: Optional[str] = None, limit: int = 20):
    """List all executor jobs."""
    jobs = list_jobs(status=status, limit=limit)
    return {"jobs": jobs, "count": len(jobs)}


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get job status and progress.

    This is the primary polling endpoint for the frontend.
    """
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return JobStatusResponse(
        job_id=job["job_id"],
        plan_id=job["plan_id"],
        status=job["status"],
        progress=job.get("progress", {}),
        error=job.get("error"),
        created_at=job.get("created_at", ""),
        started_at=job.get("started_at"),
        completed_at=job.get("completed_at"),
        total_llm_calls=job.get("total_llm_calls", 0),
        total_input_tokens=job.get("total_input_tokens", 0),
        total_output_tokens=job.get("total_output_tokens", 0),
    )


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel a running job."""
    success = request_cancellation(job_id)
    if not success:
        job = get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job in status: {job['status']}",
        )
    return {"job_id": job_id, "status": "cancelled", "message": "Cancellation requested"}


@router.get("/jobs/{job_id}/results")
async def get_job_results(job_id: str):
    """Get all phase outputs as summaries.

    Returns high-level info for each phase without full prose text.
    Use the /phases/{phase} endpoint for full prose.
    """
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    # Get phase results from job record
    phase_results = job.get("phase_results", {})
    if isinstance(phase_results, str):
        import json
        phase_results = json.loads(phase_results)

    output_count = count_outputs(job_id)

    return {
        "job_id": job_id,
        "status": job["status"],
        "phase_results": phase_results,
        "total_outputs": output_count,
        "total_llm_calls": job.get("total_llm_calls", 0),
        "total_input_tokens": job.get("total_input_tokens", 0),
        "total_output_tokens": job.get("total_output_tokens", 0),
    }


@router.get("/jobs/{job_id}/phases/{phase_number}")
async def get_phase_outputs(job_id: str, phase_number: float):
    """Get full prose outputs for a specific phase.

    Returns all engine/pass outputs for the given phase number.
    """
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    outputs = load_phase_outputs(job_id, phase_number=phase_number)
    if not outputs:
        raise HTTPException(
            status_code=404,
            detail=f"No outputs found for phase {phase_number}",
        )

    return {
        "job_id": job_id,
        "phase_number": phase_number,
        "outputs": [
            {
                "id": o.get("id"),
                "engine_key": o.get("engine_key"),
                "pass_number": o.get("pass_number"),
                "work_key": o.get("work_key"),
                "stance_key": o.get("stance_key"),
                "role": o.get("role"),
                "content": o.get("content"),
                "model_used": o.get("model_used"),
                "input_tokens": o.get("input_tokens"),
                "output_tokens": o.get("output_tokens"),
            }
            for o in outputs
        ],
        "count": len(outputs),
    }


@router.delete("/jobs/{job_id}")
async def remove_job(job_id: str):
    """Delete a completed/failed/cancelled job and all its outputs."""
    success = delete_job(job_id)
    if not success:
        job = get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete job in status: {job['status']}",
        )
    return {"job_id": job_id, "deleted": True}


# --- Document endpoints ---


@router.post("/documents")
async def upload_document(doc: DocumentUpload):
    """Upload a document text for analysis."""
    doc_id = store_document(
        title=doc.title,
        text=doc.text,
        author=doc.author,
        role=doc.role,
    )
    return {
        "doc_id": doc_id,
        "title": doc.title,
        "char_count": len(doc.text),
        "role": doc.role,
    }


@router.get("/documents")
async def list_all_documents(role: Optional[str] = None):
    """List all stored documents (without full text)."""
    docs = list_documents(role=role)
    return {"documents": docs, "count": len(docs)}


@router.get("/documents/{doc_id}")
async def get_document_by_id(doc_id: str):
    """Get a document by ID (includes full text)."""
    doc = get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")
    return doc


@router.delete("/documents/{doc_id}")
async def remove_document(doc_id: str):
    """Delete a document."""
    success = delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")
    return {"doc_id": doc_id, "deleted": True}
