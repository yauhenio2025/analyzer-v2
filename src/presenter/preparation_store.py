"""Persistent status tracking for presentation preparation jobs."""

from datetime import datetime
from typing import Optional

from src.executor.db import _json_dumps, _json_loads, execute


def _is_missing_relation_error(error: Exception, relation: str) -> bool:
    message = str(error).lower()
    return relation.lower() in message and "does not exist" in message


def load_presentation_run(job_id: str) -> Optional[dict]:
    """Load persisted presentation-preparation status for a job."""
    try:
        row = execute(
            """SELECT job_id, status, detail, stats, error,
                      started_at, updated_at, completed_at
               FROM presentation_runs
               WHERE job_id = %s""",
            (job_id,),
            fetch="one",
        )
    except Exception as error:
        if _is_missing_relation_error(error, "presentation_runs"):
            return None
        raise
    if row is None:
        return None
    if isinstance(row.get("stats"), str):
        row["stats"] = _json_loads(row["stats"])
    elif row.get("stats") is None:
        row["stats"] = {}
    return row


def load_presentation_runs(job_ids: list[str]) -> dict[str, dict]:
    """Load persisted presentation-preparation state for multiple jobs."""
    if not job_ids:
        return {}

    placeholders = ", ".join(["%s"] * len(job_ids))
    try:
        rows = execute(
            f"""SELECT job_id, status, detail, stats, error,
                       started_at, updated_at, completed_at
                FROM presentation_runs
                WHERE job_id IN ({placeholders})""",
            tuple(job_ids),
            fetch="all",
        )
    except Exception as error:
        if _is_missing_relation_error(error, "presentation_runs"):
            return {}
        raise

    result: dict[str, dict] = {}
    for row in rows:
        if isinstance(row.get("stats"), str):
            row["stats"] = _json_loads(row["stats"])
        elif row.get("stats") is None:
            row["stats"] = {}
        result[row["job_id"]] = row
    return result


def save_presentation_run(
    job_id: str,
    status: str,
    detail: str = "",
    stats: Optional[dict] = None,
    error: Optional[str] = None,
) -> dict:
    """Insert or update presentation-preparation status for a job."""
    now = datetime.utcnow().isoformat()
    existing = load_presentation_run(job_id)
    stats_json = _json_dumps(stats or {})

    if existing is None:
        started_at = now if status == "running" else None
        completed_at = now if status in {"completed", "failed"} else None
        execute(
            """INSERT INTO presentation_runs
               (job_id, status, detail, stats, error, started_at, updated_at, completed_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (job_id, status, detail, stats_json, error, started_at, now, completed_at),
        )
    else:
        started_at = existing.get("started_at")
        completed_at = existing.get("completed_at")
        if status == "running":
            started_at = now
            completed_at = None
        elif status in {"completed", "failed"}:
            completed_at = now
            if not started_at:
                started_at = now

        execute(
            """UPDATE presentation_runs
               SET status = %s,
                   detail = %s,
                   stats = %s,
                   error = %s,
                   started_at = %s,
                   updated_at = %s,
                   completed_at = %s
               WHERE job_id = %s""",
            (status, detail, stats_json, error, started_at, now, completed_at, job_id),
        )

    return load_presentation_run(job_id) or {
        "job_id": job_id,
        "status": status,
        "detail": detail,
        "stats": stats or {},
        "error": error,
        "started_at": None,
        "updated_at": now,
        "completed_at": None,
    }
