"""Storage operations for Tier 3a feedback events."""

from datetime import datetime
from typing import Optional

from src.executor.db import execute, execute_write, _json_dumps, _json_loads
from src.feedback.schemas import FeedbackEventInput

ALLOWED_GROUP_COLUMNS = {
    "event_type": "event_type",
    "view_key": "view_key",
    "style_school": "style_school",
    "renderer_type": "renderer_type",
}


def _normalize_event_row(row: dict) -> dict:
    """Normalize DB row into API response shape."""
    normalized = dict(row)
    payload = normalized.get("payload")
    if isinstance(payload, str):
        normalized["payload"] = _json_loads(payload)
    elif payload is None:
        normalized["payload"] = {}

    for ts_key in ("created_at", "client_timestamp"):
        ts_val = normalized.get(ts_key)
        if isinstance(ts_val, datetime):
            normalized[ts_key] = ts_val.isoformat()
    return normalized


def _resolve_project_ids(job_ids: set[str]) -> dict[str, Optional[str]]:
    """Resolve project IDs for jobs for denormalization during ingest."""
    if not job_ids:
        return {}

    placeholders = ", ".join(["%s"] * len(job_ids))
    rows = execute(
        f"SELECT job_id, project_id FROM executor_jobs WHERE job_id IN ({placeholders})",
        tuple(job_ids),
        fetch="all",
    )
    mapping = {job_id: None for job_id in job_ids}
    for row in rows:
        mapping[row["job_id"]] = row.get("project_id")
    return mapping


def save_events(events: list[FeedbackEventInput]) -> tuple[int, int]:
    """Persist a batch of feedback events.

    Returns:
        (accepted, duplicates)
    """
    job_ids = {event.job_id for event in events if event.project_id is None}
    project_by_job = _resolve_project_ids(job_ids)

    accepted = 0
    duplicates = 0

    sql = (
        "INSERT INTO feedback_events "
        "(event_id, event_type, job_id, project_id, view_key, section_key, "
        "renderer_type, style_school, payload, client_timestamp, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "ON CONFLICT(event_id) DO NOTHING"
    )

    now = datetime.utcnow().isoformat()
    for event in events:
        project_id = event.project_id
        if project_id is None:
            project_id = project_by_job.get(event.job_id)

        rowcount = execute_write(
            sql,
            (
                event.event_id,
                event.event_type.value,
                event.job_id,
                project_id,
                event.view_key,
                event.section_key,
                event.renderer_type,
                event.style_school,
                _json_dumps(event.payload),
                event.client_timestamp,
                now,
            ),
        )
        if rowcount == 1:
            accepted += 1
        else:
            duplicates += 1

    return accepted, duplicates


def list_events(
    *,
    job_id: Optional[str] = None,
    project_id: Optional[str] = None,
    event_types: Optional[list[str]] = None,
    view_key: Optional[str] = None,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """List feedback events with filters and pagination."""
    if not job_id and not project_id:
        raise ValueError("At least one of job_id or project_id is required")

    conditions = []
    params: list = []

    if job_id:
        conditions.append("job_id = %s")
        params.append(job_id)
    if project_id:
        conditions.append("project_id = %s")
        params.append(project_id)
    if event_types:
        placeholders = ", ".join(["%s"] * len(event_types))
        conditions.append(f"event_type IN ({placeholders})")
        params.extend(event_types)
    if view_key:
        conditions.append("view_key = %s")
        params.append(view_key)
    if from_ts:
        conditions.append("created_at >= %s")
        params.append(from_ts)
    if to_ts:
        conditions.append("created_at <= %s")
        params.append(to_ts)

    where_clause = " AND ".join(conditions)

    rows = execute(
        f"SELECT * FROM feedback_events WHERE {where_clause} "
        "ORDER BY created_at DESC LIMIT %s OFFSET %s",
        tuple(params + [limit, offset]),
        fetch="all",
    )

    total_row = execute(
        f"SELECT COUNT(*) as cnt FROM feedback_events WHERE {where_clause}",
        tuple(params),
        fetch="one",
    )

    total = total_row["cnt"] if total_row else 0
    return [_normalize_event_row(row) for row in rows], total


def summarize_events(
    *,
    job_id: Optional[str] = None,
    project_id: Optional[str] = None,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
    group_by: Optional[list[str]] = None,
) -> tuple[list[dict], int]:
    """Aggregate feedback events by whitelisted columns."""
    if not job_id and not project_id:
        raise ValueError("At least one of job_id or project_id is required")

    group_by = group_by or ["event_type"]
    columns: list[str] = []
    for key in group_by:
        column = ALLOWED_GROUP_COLUMNS.get(key)
        if not column:
            raise ValueError(f"Invalid group_by field: {key}")
        columns.append(column)

    conditions = []
    params: list = []

    if job_id:
        conditions.append("job_id = %s")
        params.append(job_id)
    if project_id:
        conditions.append("project_id = %s")
        params.append(project_id)
    if from_ts:
        conditions.append("created_at >= %s")
        params.append(from_ts)
    if to_ts:
        conditions.append("created_at <= %s")
        params.append(to_ts)

    where_clause = " AND ".join(conditions)
    group_expr = ", ".join(columns)
    select_expr = ", ".join(columns + ["COUNT(*) as count"])

    rows = execute(
        f"SELECT {select_expr} FROM feedback_events WHERE {where_clause} "
        f"GROUP BY {group_expr} ORDER BY count DESC",
        tuple(params),
        fetch="all",
    )

    total_row = execute(
        f"SELECT COUNT(*) as cnt FROM feedback_events WHERE {where_clause}",
        tuple(params),
        fetch="one",
    )
    total = total_row["cnt"] if total_row else 0

    return rows, total


def delete_events_for_job(job_id: str) -> int:
    """Delete all feedback events for a job. Returns rows deleted."""
    return execute_write("DELETE FROM feedback_events WHERE job_id = %s", (job_id,))


def delete_events_for_project(project_id: str) -> int:
    """Delete all feedback events for a project.

    Includes rows with project_id NULL but job scoped to the project.
    """
    return execute_write(
        "DELETE FROM feedback_events "
        "WHERE job_id IN (SELECT job_id FROM executor_jobs WHERE project_id = %s) "
        "OR project_id = %s",
        (project_id, project_id),
    )
