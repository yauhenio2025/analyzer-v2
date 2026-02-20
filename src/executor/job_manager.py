"""Job lifecycle management for the executor.

Handles:
- Job creation and DB persistence
- Progress updates (for frontend polling)
- Cancellation (flag-based, checked during execution)
- Job status queries

Uses the database for persistence — no in-memory state.
Cancellation flags are tracked in-memory (per process) since
they need to be checked at high frequency during streaming.

Ported from The Critic's job management with DB-first design.
"""

import logging
import threading
import uuid
from datetime import datetime
from typing import Optional

from src.executor.db import execute, _json_dumps, _json_loads

logger = logging.getLogger(__name__)

# In-memory cancellation flags (per job_id)
# Checked at high frequency during LLM streaming
_cancellation_flags: dict[str, bool] = {}
_flags_lock = threading.Lock()


def create_job(
    job_id: str,
    plan_id: str,
    plan_data: Optional[dict] = None,
    document_ids: Optional[dict[str, str]] = None,
) -> dict:
    """Create a new executor job in the database.

    Args:
        plan_data: Full serialized plan (for resume after instance recycle).
        document_ids: Mapping of work titles to document IDs.

    Returns the job record as a dict (includes cancel_token).
    """
    now = datetime.utcnow().isoformat()
    cancel_token = uuid.uuid4().hex
    progress = _json_dumps({
        "current_phase": 0,
        "total_phases": 5,
        "phase_name": "",
        "detail": "Waiting to start",
        "completed_phases": [],
        "phase_statuses": {},
    })

    execute(
        """INSERT INTO executor_jobs
           (job_id, plan_id, status, progress, phase_results, error,
            total_llm_calls, total_input_tokens, total_output_tokens,
            plan_data, document_ids, cancel_token, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (job_id, plan_id, "pending", progress, "{}", None, 0, 0, 0,
         _json_dumps(plan_data) if plan_data else None,
         _json_dumps(document_ids or {}), cancel_token, now),
    )

    logger.info(f"Created job {job_id} for plan {plan_id}")

    return {
        "job_id": job_id,
        "plan_id": plan_id,
        "status": "pending",
        "cancel_token": cancel_token,
        "created_at": now,
    }


def _normalize_timestamps(row: dict) -> dict:
    """Convert datetime objects to ISO strings (Postgres returns datetimes for TIMESTAMP columns)."""
    for key in ("created_at", "started_at", "completed_at"):
        val = row.get(key)
        if val is not None and isinstance(val, datetime):
            row[key] = val.isoformat()
    return row


def get_job(job_id: str) -> Optional[dict]:
    """Get a job record by ID."""
    row = execute(
        "SELECT * FROM executor_jobs WHERE job_id = %s",
        (job_id,),
        fetch="one",
    )
    if row is None:
        return None

    # Parse JSON fields
    if isinstance(row.get("progress"), str):
        row["progress"] = _json_loads(row["progress"])
    if isinstance(row.get("phase_results"), str):
        row["phase_results"] = _json_loads(row["phase_results"])
    if isinstance(row.get("plan_data"), str):
        row["plan_data"] = _json_loads(row["plan_data"])
    if isinstance(row.get("document_ids"), str):
        row["document_ids"] = _json_loads(row["document_ids"])

    # Normalize timestamps (Postgres returns datetime objects, schemas expect strings)
    _normalize_timestamps(row)

    return row


def update_job_plan_id(job_id: str, plan_id: str) -> None:
    """Update the plan_id on an existing job (used by async pipeline)."""
    execute(
        "UPDATE executor_jobs SET plan_id = %s WHERE job_id = %s",
        (plan_id, job_id),
    )
    logger.info(f"Job {job_id} plan_id → {plan_id}")


def update_job_status(
    job_id: str,
    status: str,
    error: Optional[str] = None,
) -> None:
    """Update job status and timestamps."""
    now = datetime.utcnow().isoformat()

    if status == "running":
        execute(
            """UPDATE executor_jobs
               SET status = %s, started_at = %s
               WHERE job_id = %s""",
            (status, now, job_id),
        )
    elif status in ("completed", "failed", "cancelled"):
        execute(
            """UPDATE executor_jobs
               SET status = %s, completed_at = %s, error = %s
               WHERE job_id = %s""",
            (status, now, error, job_id),
        )
    else:
        execute(
            """UPDATE executor_jobs
               SET status = %s WHERE job_id = %s""",
            (status, job_id),
        )

    logger.info(f"Job {job_id} status → {status}" + (f" (error: {error})" if error else ""))


def update_job_progress(
    job_id: str,
    current_phase: float,
    phase_name: str,
    detail: str = "",
    completed_phases: Optional[list[str]] = None,
    phase_statuses: Optional[dict[str, str]] = None,
    total_phases: int = 5,
    structured_detail: Optional[dict] = None,
) -> None:
    """Update job progress for frontend polling."""
    progress = {
        "current_phase": current_phase,
        "total_phases": total_phases,
        "phase_name": phase_name,
        "detail": detail,
        "completed_phases": completed_phases or [],
        "phase_statuses": phase_statuses or {},
    }
    if structured_detail:
        progress["structured_detail"] = structured_detail

    execute(
        """UPDATE executor_jobs
           SET progress = %s WHERE job_id = %s""",
        (_json_dumps(progress), job_id),
    )


def update_job_tokens(
    job_id: str,
    llm_calls: int = 0,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    """Increment job-level token counters."""
    execute(
        """UPDATE executor_jobs
           SET total_llm_calls = total_llm_calls + %s,
               total_input_tokens = total_input_tokens + %s,
               total_output_tokens = total_output_tokens + %s
           WHERE job_id = %s""",
        (llm_calls, input_tokens, output_tokens, job_id),
    )


def save_phase_result(
    job_id: str,
    phase_number: float,
    result_data: dict,
) -> None:
    """Save a phase result into the job's phase_results JSON.

    Since Postgres and SQLite handle JSON updates differently,
    we read-modify-write.
    """
    job = get_job(job_id)
    if job is None:
        logger.error(f"Cannot save phase result: job {job_id} not found")
        return

    phase_results = job.get("phase_results", {})
    if isinstance(phase_results, str):
        phase_results = _json_loads(phase_results)

    phase_results[str(phase_number)] = result_data

    execute(
        """UPDATE executor_jobs
           SET phase_results = %s WHERE job_id = %s""",
        (_json_dumps(phase_results), job_id),
    )


def list_jobs(
    status: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """List jobs, optionally filtered by status."""
    if status:
        rows = execute(
            """SELECT job_id, plan_id, status, progress, error,
                      total_llm_calls, total_input_tokens, total_output_tokens,
                      created_at, started_at, completed_at
               FROM executor_jobs WHERE status = %s
               ORDER BY created_at DESC LIMIT %s""",
            (status, limit),
            fetch="all",
        )
    else:
        rows = execute(
            """SELECT job_id, plan_id, status, progress, error,
                      total_llm_calls, total_input_tokens, total_output_tokens,
                      created_at, started_at, completed_at
               FROM executor_jobs
               ORDER BY created_at DESC LIMIT %s""",
            (limit,),
            fetch="all",
        )

    for row in rows:
        if isinstance(row.get("progress"), str):
            row["progress"] = _json_loads(row["progress"])
        _normalize_timestamps(row)

    return rows


# --- Cancellation ---

def request_cancellation(job_id: str, cancel_token: Optional[str] = None) -> tuple[bool, str]:
    """Request cancellation of a running job.

    Sets both the in-memory flag (for fast checking during streaming)
    and the DB status.

    Args:
        cancel_token: Required. Must match the token issued at job creation.

    Returns (success: bool, message: str).
    """
    job = get_job(job_id)
    if job is None:
        return (False, "Job not found")

    if job["status"] not in ("pending", "running"):
        return (False, f"Cannot cancel job in status: {job['status']}")

    # Verify cancel token
    stored_token = job.get("cancel_token")
    if stored_token and cancel_token != stored_token:
        logger.warning(
            f"Cancel REJECTED for job {job_id}: invalid token "
            f"(got {cancel_token!r}, expected {stored_token!r})"
        )
        return (False, "Invalid cancel_token. Only the session that created this job can cancel it.")

    # Set in-memory flag
    with _flags_lock:
        _cancellation_flags[job_id] = True

    # Update DB status
    update_job_status(job_id, "cancelled")
    logger.info(f"Cancellation requested for job {job_id} (token verified)")
    return (True, "Cancelled")


def is_cancelled(job_id: str) -> bool:
    """Check if a job has been cancelled.

    This is the fast-path check used during LLM streaming.
    Checks in-memory flag first, falls back to DB.
    """
    with _flags_lock:
        if _cancellation_flags.get(job_id):
            return True

    # Fallback: check DB (handles cross-process cancellation)
    job = get_job(job_id)
    if job and job["status"] == "cancelled":
        with _flags_lock:
            _cancellation_flags[job_id] = True
        return True

    return False


def clear_cancellation(job_id: str) -> None:
    """Clear cancellation flag (for job cleanup)."""
    with _flags_lock:
        _cancellation_flags.pop(job_id, None)


RECOVERY_GRACE_PERIOD_SECONDS = 300  # 5 minutes — plan generation takes ~2 min


def recover_orphaned_jobs() -> tuple[int, int, int]:
    """Resume orphaned running jobs or mark them as failed on startup.

    When Render recycles an instance, daemon execution threads die silently.
    The DB still shows status='running' but nothing is actually executing.

    This function:
    1. Finds orphaned running/pending jobs
    2. For jobs WITH full plan_data: resume them (spawn new execution thread)
    3. For jobs WITH request_snapshot: regenerate plan + resume (spawn thread)
    4. For jobs WITHOUT plan_data:
       - If created < 5 min ago: skip (grace period — old instance may still be running)
       - If older: mark as failed

    Returns (resumed_count, failed_count, skipped_count).
    """
    from src.executor.output_store import get_completed_phases

    # Find orphaned running jobs
    running_jobs = execute(
        """SELECT job_id, plan_id, status, started_at, created_at,
                  plan_data, document_ids
           FROM executor_jobs
           WHERE status IN ('running', 'pending')""",
        fetch="all",
    )

    if not running_jobs:
        return (0, 0, 0)

    resumed = 0
    failed = 0
    skipped = 0
    now = datetime.utcnow().isoformat()

    for job in running_jobs:
        job_id = job["job_id"]
        plan_data = job.get("plan_data")
        document_ids_raw = job.get("document_ids")

        # Parse plan_data and document_ids
        if isinstance(plan_data, str):
            try:
                plan_data = _json_loads(plan_data)
            except Exception:
                plan_data = None
        if isinstance(document_ids_raw, str):
            try:
                document_ids_raw = _json_loads(document_ids_raw)
            except Exception:
                document_ids_raw = {}

        # Empty dict is falsy for our purposes — treat as no plan_data
        if isinstance(plan_data, dict) and not plan_data:
            plan_data = None

        if plan_data and plan_data.get("_type") == "request_snapshot":
            # Has request snapshot — regenerate plan and resume
            logger.info(
                f"REGENERATE: Orphaned job {job_id} has request snapshot — "
                f"spawning plan regeneration + execution thread"
            )

            # Reset status to pending
            execute(
                """UPDATE executor_jobs
                   SET status = 'pending',
                       error = NULL,
                       completed_at = NULL
                   WHERE job_id = %s""",
                (job_id,),
            )
            clear_cancellation(job_id)

            # Spawn regeneration + execution thread
            _spawn_regeneration_thread(
                job_id=job_id,
                snapshot=plan_data,
                document_ids=document_ids_raw or {},
            )

            resumed += 1
            logger.warning(
                f"Recovered orphaned job {job_id} (was {job['status']}) → "
                f"regenerating plan from snapshot"
            )

        elif plan_data:
            # Has full plan data — can resume directly
            completed = get_completed_phases(job_id)
            logger.info(
                f"RESUME: Orphaned job {job_id} has plan_data and "
                f"{len(completed)} completed phases — scheduling resume"
            )

            # Reset status to pending (execution thread will set to running)
            execute(
                """UPDATE executor_jobs
                   SET status = 'pending',
                       error = NULL,
                       completed_at = NULL
                   WHERE job_id = %s""",
                (job_id,),
            )
            clear_cancellation(job_id)

            # Spawn resume thread (import here to avoid circular)
            from src.executor.workflow_runner import start_resume_thread
            start_resume_thread(
                job_id=job_id,
                plan_data=plan_data,
                document_ids=document_ids_raw or {},
            )

            resumed += 1
            logger.warning(
                f"Recovered orphaned job {job_id} (was {job['status']}) → resuming"
            )
        else:
            # No plan data — check grace period before failing
            created_at = job.get("created_at")
            age_seconds = _get_job_age_seconds(created_at)

            if age_seconds is not None and age_seconds < RECOVERY_GRACE_PERIOD_SECONDS:
                # Job is too new — old instance may still be generating the plan
                skipped += 1
                logger.warning(
                    f"SKIP: Orphaned job {job_id} created {age_seconds:.0f}s ago "
                    f"(within {RECOVERY_GRACE_PERIOD_SECONDS}s grace period) — "
                    f"old instance may still be running. Will be caught by stale check."
                )
            else:
                # Old job with no plan data — can't resume, mark as failed
                execute(
                    """UPDATE executor_jobs
                       SET status = 'failed',
                           completed_at = %s,
                           error = %s
                       WHERE job_id = %s AND status IN ('running', 'pending')""",
                    (
                        now,
                        "Process terminated unexpectedly (instance recycled). "
                        "No plan_data stored — cannot resume. Please retry the analysis.",
                        job_id,
                    ),
                )
                clear_cancellation(job_id)
                failed += 1
                logger.warning(
                    f"Recovered orphaned job {job_id} (was {job['status']}) → "
                    f"failed (no plan_data, age={age_seconds:.0f}s)"
                )

    logger.info(
        f"Startup recovery: {resumed} resumed, {failed} failed, {skipped} skipped (grace period)"
    )
    return (resumed, failed, skipped)


def _get_job_age_seconds(created_at) -> Optional[float]:
    """Get the age of a job in seconds from its created_at timestamp."""
    if created_at is None:
        return None
    if isinstance(created_at, str):
        try:
            created_dt = datetime.fromisoformat(created_at)
        except (ValueError, TypeError):
            return None
    elif isinstance(created_at, datetime):
        created_dt = created_at
    else:
        return None
    return (datetime.utcnow() - created_dt).total_seconds()


def _spawn_regeneration_thread(
    job_id: str,
    snapshot: dict,
    document_ids: dict[str, str],
) -> None:
    """Spawn a background thread to regenerate a plan from a request snapshot and execute.

    Called during recovery when we have the plan request params but not the
    completed plan (instance died during plan generation).
    """
    def _regen_and_execute():
        try:
            from src.orchestrator.planner import generate_plan
            from src.orchestrator.schemas import OrchestratorPlanRequest
            from src.executor.workflow_runner import execute_plan

            plan_request = OrchestratorPlanRequest(**snapshot["plan_request"])
            logger.info(f"REGEN: Regenerating plan for job {job_id}...")

            plan = generate_plan(plan_request)
            logger.info(
                f"REGEN: Plan {plan.plan_id} regenerated for job {job_id} — "
                f"{len(plan.phases)} phases, {plan.estimated_llm_calls} calls"
            )

            # Store the full plan + update plan_id
            from src.executor.db import _json_dumps as jdumps
            execute(
                """UPDATE executor_jobs
                   SET plan_data = %s, plan_id = %s
                   WHERE job_id = %s""",
                (jdumps(plan.model_dump()), plan.plan_id, job_id),
            )

            # Execute the plan (we're already in a background thread)
            execute_plan(
                job_id=job_id,
                plan_id=plan.plan_id,
                document_ids=document_ids,
                plan_object=plan,
            )

        except Exception as e:
            logger.error(f"REGEN: Failed for job {job_id}: {e}", exc_info=True)
            update_job_status(job_id, "failed", error=f"Plan regeneration failed: {e}")

    thread = threading.Thread(
        target=_regen_and_execute,
        name=f"regen-{job_id}",
        daemon=True,
    )
    thread.start()
    logger.info(f"REGEN: Spawned regeneration thread for job {job_id}")


MAX_JOB_RUNTIME_SECONDS = 3 * 60 * 60  # 3 hours — no single job should run this long


def check_stale_job(job: dict) -> Optional[dict]:
    """Check if a running job is stale and mark it as failed.

    A job is considered stale if it has been running for more than
    MAX_JOB_RUNTIME_SECONDS without completing. This catches:
    - Daemon threads that died due to unhandled exceptions
    - Orphaned jobs on instances that didn't run startup recovery
    - Jobs stuck in infinite loops

    Called from the polling endpoint — belt-and-suspenders alongside
    startup recovery.

    Returns the updated job dict if stale (or None if not stale).
    """
    if job["status"] not in ("running", "pending"):
        return None

    started = job.get("started_at") or job.get("created_at")
    if not started:
        return None

    # Parse the timestamp
    if isinstance(started, str):
        try:
            started_dt = datetime.fromisoformat(started)
        except (ValueError, TypeError):
            return None
    elif isinstance(started, datetime):
        started_dt = started
    else:
        return None

    elapsed = (datetime.utcnow() - started_dt).total_seconds()
    if elapsed < MAX_JOB_RUNTIME_SECONDS:
        return None

    # Job is stale — mark as failed
    job_id = job["job_id"]
    hours = elapsed / 3600
    error_msg = (
        f"Job exceeded maximum runtime ({hours:.1f}h > {MAX_JOB_RUNTIME_SECONDS/3600:.0f}h). "
        f"The execution thread likely crashed. Please retry the analysis."
    )
    update_job_status(job_id, "failed", error=error_msg)
    clear_cancellation(job_id)
    logger.warning(f"Marked stale job {job_id} as failed ({hours:.1f}h elapsed)")

    # Re-read to return updated job
    return get_job(job_id)


def delete_job(job_id: str) -> bool:
    """Delete a job and all its outputs.

    Only allowed for completed/failed/cancelled jobs.
    """
    from src.executor.output_store import delete_job_outputs

    job = get_job(job_id)
    if job is None:
        return False

    if job["status"] in ("pending", "running"):
        logger.warning(f"Cannot delete running job {job_id}")
        return False

    # Delete outputs first (foreign key constraint)
    delete_job_outputs(job_id)

    # Delete job
    execute("DELETE FROM executor_jobs WHERE job_id = %s", (job_id,))
    clear_cancellation(job_id)

    logger.info(f"Deleted job {job_id}")
    return True
