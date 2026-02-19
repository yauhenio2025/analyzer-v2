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
) -> dict:
    """Create a new executor job in the database.

    Returns the job record as a dict.
    """
    now = datetime.utcnow().isoformat()
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
            created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (job_id, plan_id, "pending", progress, "{}", None, 0, 0, 0, now),
    )

    logger.info(f"Created job {job_id} for plan {plan_id}")

    return {
        "job_id": job_id,
        "plan_id": plan_id,
        "status": "pending",
        "created_at": now,
    }


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

    return row


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

    return rows


# --- Cancellation ---

def request_cancellation(job_id: str) -> bool:
    """Request cancellation of a running job.

    Sets both the in-memory flag (for fast checking during streaming)
    and the DB status.

    Returns True if the job was running and is now being cancelled.
    """
    job = get_job(job_id)
    if job is None:
        return False

    if job["status"] not in ("pending", "running"):
        logger.warning(
            f"Cannot cancel job {job_id}: status is {job['status']}"
        )
        return False

    # Set in-memory flag
    with _flags_lock:
        _cancellation_flags[job_id] = True

    # Update DB status
    update_job_status(job_id, "cancelled")
    logger.info(f"Cancellation requested for job {job_id}")
    return True


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
