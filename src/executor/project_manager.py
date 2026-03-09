"""Project lifecycle management for the executor.

Handles:
- Project CRUD (create, list, get, update)
- Lifecycle transitions (archive, revive, delete)
- Presentation artifact cleanup on archive
- Full data cleanup on delete
- Auto-archive of stale projects
- Activity tracking (touch on meaningful writes)

Projects are ephemeral workspaces that group jobs together.
They follow a lifecycle: active -> archived -> [deleted].
Archived projects retain engine outputs but release presentation resources.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from src.executor.db import execute, execute_write, execute_transaction, _json_dumps, _json_loads

logger = logging.getLogger(__name__)


# --- CRUD ---


def create_project(
    name: str,
    description: str = "",
    auto_archive_days: Optional[int] = 30,
    metadata: Optional[dict] = None,
) -> dict:
    """Create a new project. Returns the project record."""
    project_id = f"proj-{uuid.uuid4().hex[:12]}"
    now = datetime.utcnow().isoformat()

    execute(
        """INSERT INTO projects
           (project_id, name, description, status, auto_archive_days,
            created_at, last_activity_at, metadata)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (project_id, name, description, "active", auto_archive_days,
         now, now, _json_dumps(metadata or {})),
    )

    logger.info(f"Created project {project_id}: {name}")

    return {
        "project_id": project_id,
        "name": name,
        "description": description,
        "status": "active",
        "auto_archive_days": auto_archive_days,
        "created_at": now,
        "last_activity_at": now,
        "archived_at": None,
        "metadata": metadata or {},
        "job_count": 0,
        "active_job_count": 0,
    }


def get_project(project_id: str) -> Optional[dict]:
    """Get a project by ID, including job counts."""
    row = execute(
        "SELECT * FROM projects WHERE project_id = %s",
        (project_id,),
        fetch="one",
    )
    if row is None:
        return None

    # Normalize timestamps
    for key in ("created_at", "last_activity_at", "archived_at"):
        val = row.get(key)
        if val is not None and isinstance(val, datetime):
            row[key] = val.isoformat()

    # Parse metadata
    if isinstance(row.get("metadata"), str):
        row["metadata"] = _json_loads(row["metadata"])

    # Job counts
    counts = execute(
        """SELECT
               COUNT(*) as total,
               COUNT(CASE WHEN status IN ('pending', 'running') THEN 1 END) as active
           FROM executor_jobs WHERE project_id = %s""",
        (project_id,),
        fetch="one",
    )
    row["job_count"] = counts["total"] if counts else 0
    row["active_job_count"] = counts["active"] if counts else 0

    return row


def list_projects(status: Optional[str] = None, limit: int = 50) -> list[dict]:
    """List projects, optionally filtered by status."""
    if status:
        rows = execute(
            """SELECT p.*,
                      (SELECT COUNT(*) FROM executor_jobs WHERE project_id = p.project_id) as job_count,
                      (SELECT COUNT(*) FROM executor_jobs
                       WHERE project_id = p.project_id AND status IN ('pending', 'running')) as active_job_count
               FROM projects p WHERE p.status = %s
               ORDER BY p.last_activity_at DESC LIMIT %s""",
            (status, limit),
            fetch="all",
        )
    else:
        rows = execute(
            """SELECT p.*,
                      (SELECT COUNT(*) FROM executor_jobs WHERE project_id = p.project_id) as job_count,
                      (SELECT COUNT(*) FROM executor_jobs
                       WHERE project_id = p.project_id AND status IN ('pending', 'running')) as active_job_count
               FROM projects p
               ORDER BY p.last_activity_at DESC LIMIT %s""",
            (limit,),
            fetch="all",
        )

    for row in rows:
        for key in ("created_at", "last_activity_at", "archived_at"):
            val = row.get(key)
            if val is not None and isinstance(val, datetime):
                row[key] = val.isoformat()
        if isinstance(row.get("metadata"), str):
            row["metadata"] = _json_loads(row["metadata"])

    return rows


def update_project(project_id: str, **kwargs) -> Optional[dict]:
    """Update project metadata fields. Returns updated project or None if not found."""
    project = get_project(project_id)
    if project is None:
        return None

    updates = []
    params = []
    for field in ("name", "description", "auto_archive_days"):
        if field in kwargs and kwargs[field] is not None:
            updates.append(f"{field} = %s")
            params.append(kwargs[field])

    if not updates:
        return project

    # Also touch activity
    updates.append("last_activity_at = %s")
    params.append(datetime.utcnow().isoformat())

    params.append(project_id)
    execute(
        f"UPDATE projects SET {', '.join(updates)} WHERE project_id = %s",
        tuple(params),
    )

    return get_project(project_id)


# --- Activity tracking ---


def touch_project_activity(project_id: str) -> None:
    """Update last_activity_at for a project. Called on meaningful writes."""
    execute(
        "UPDATE projects SET last_activity_at = %s WHERE project_id = %s",
        (datetime.utcnow().isoformat(), project_id),
    )


def touch_project_activity_for_job(job_id: str) -> None:
    """Look up project_id from a job and touch activity if non-NULL.

    Convenience wrapper for presenter routes that only have job_id.
    """
    row = execute(
        "SELECT project_id FROM executor_jobs WHERE job_id = %s",
        (job_id,),
        fetch="one",
    )
    if row and row.get("project_id"):
        touch_project_activity(row["project_id"])


# --- Lifecycle transitions ---


def _has_active_jobs(project_id: str) -> bool:
    """Check if a project has running or pending jobs."""
    row = execute(
        """SELECT COUNT(*) as cnt FROM executor_jobs
           WHERE project_id = %s AND status IN ('pending', 'running')""",
        (project_id,),
        fetch="one",
    )
    return (row["cnt"] if row else 0) > 0


def _cleanup_presentation_artifacts(project_id: str) -> dict:
    """Archive cleanup: delete presentation artifacts atomically, retain engine outputs.

    Uses execute_transaction() so all three deletes are atomic.
    Returns {table: rows_deleted} for observability.
    """
    table_names = [
        "variant_selections", "variants", "variant_sets",
        "polish_cache", "view_refinements", "presentation_cache",
    ]
    statements = [
        (
            "DELETE FROM variant_selections WHERE variant_set_id IN "
            "(SELECT variant_set_id FROM variant_sets WHERE job_id IN "
            "(SELECT job_id FROM executor_jobs WHERE project_id = %s))",
            (project_id,),
        ),
        (
            "DELETE FROM variants WHERE variant_set_id IN "
            "(SELECT variant_set_id FROM variant_sets WHERE job_id IN "
            "(SELECT job_id FROM executor_jobs WHERE project_id = %s))",
            (project_id,),
        ),
        (
            "DELETE FROM variant_sets WHERE job_id IN "
            "(SELECT job_id FROM executor_jobs WHERE project_id = %s)",
            (project_id,),
        ),
        (
            "DELETE FROM polish_cache WHERE job_id IN "
            "(SELECT job_id FROM executor_jobs WHERE project_id = %s)",
            (project_id,),
        ),
        (
            "DELETE FROM view_refinements WHERE job_id IN "
            "(SELECT job_id FROM executor_jobs WHERE project_id = %s)",
            (project_id,),
        ),
        (
            "DELETE FROM presentation_cache WHERE output_id IN "
            "(SELECT po.id FROM phase_outputs po "
            "JOIN executor_jobs ej ON po.job_id = ej.job_id "
            "WHERE ej.project_id = %s)",
            (project_id,),
        ),
    ]

    rowcounts = execute_transaction(statements)

    return {name: count for name, count in zip(table_names, rowcounts) if count > 0}


def _cleanup_all_project_data(project_id: str) -> dict:
    """Delete cleanup: remove ALL data for a project atomically.

    Uses execute_transaction() so the entire cascade is atomic —
    if any step fails, nothing is deleted (no orphaned rows).

    Returns {table: rows_deleted} for observability.
    """
    # Order matters: presentation_cache references phase_outputs,
    # phase_outputs references executor_jobs, so delete leaf tables first.
    table_names = [
        "variant_selections",
        "variants",
        "variant_sets",
        "feedback_events",
        "polish_cache",
        "view_refinements",
        "presentation_cache",
        "phase_outputs",
        "executor_jobs",
        "projects",
    ]
    statements = [
        (
            "DELETE FROM variant_selections WHERE variant_set_id IN "
            "(SELECT variant_set_id FROM variant_sets WHERE job_id IN "
            "(SELECT job_id FROM executor_jobs WHERE project_id = %s))",
            (project_id,),
        ),
        (
            "DELETE FROM variants WHERE variant_set_id IN "
            "(SELECT variant_set_id FROM variant_sets WHERE job_id IN "
            "(SELECT job_id FROM executor_jobs WHERE project_id = %s))",
            (project_id,),
        ),
        (
            "DELETE FROM variant_sets WHERE job_id IN "
            "(SELECT job_id FROM executor_jobs WHERE project_id = %s)",
            (project_id,),
        ),
        (
            "DELETE FROM feedback_events "
            "WHERE job_id IN (SELECT job_id FROM executor_jobs WHERE project_id = %s) "
            "OR project_id = %s",
            (project_id, project_id),
        ),
        (
            "DELETE FROM polish_cache WHERE job_id IN "
            "(SELECT job_id FROM executor_jobs WHERE project_id = %s)",
            (project_id,),
        ),
        (
            "DELETE FROM view_refinements WHERE job_id IN "
            "(SELECT job_id FROM executor_jobs WHERE project_id = %s)",
            (project_id,),
        ),
        (
            "DELETE FROM presentation_cache WHERE output_id IN "
            "(SELECT po.id FROM phase_outputs po "
            "JOIN executor_jobs ej ON po.job_id = ej.job_id "
            "WHERE ej.project_id = %s)",
            (project_id,),
        ),
        (
            "DELETE FROM phase_outputs WHERE job_id IN "
            "(SELECT job_id FROM executor_jobs WHERE project_id = %s)",
            (project_id,),
        ),
        (
            "DELETE FROM executor_jobs WHERE project_id = %s",
            (project_id,),
        ),
        (
            "DELETE FROM projects WHERE project_id = %s",
            (project_id,),
        ),
    ]

    rowcounts = execute_transaction(statements)

    counts = {name: count for name, count in zip(table_names, rowcounts) if count > 0}
    return counts


def archive_project(project_id: str) -> dict:
    """Archive a project: delete presentation artifacts, retain engine outputs.

    Uses optimistic locking: UPDATE ... WHERE status='active'.
    Only one instance wins in multi-worker setups.

    Returns LifecycleActionResponse dict.
    """
    project = get_project(project_id)
    if project is None:
        raise ValueError(f"Project not found: {project_id}")

    # Already archived — idempotent
    if project["status"] == "archived":
        return {
            "project_id": project_id,
            "action": "already_archived",
            "artifacts_removed": {},
        }

    # Guard: no active jobs
    if _has_active_jobs(project_id):
        raise RuntimeError(
            f"Cannot archive project {project_id}: has running/pending jobs"
        )

    # Optimistic lock: only one instance wins
    affected = execute_write(
        "UPDATE projects SET status = %s, archived_at = %s WHERE project_id = %s AND status = %s",
        ("archived", datetime.utcnow().isoformat(), project_id, "active"),
    )

    if affected == 0:
        # Another instance already archived it
        return {
            "project_id": project_id,
            "action": "already_archived",
            "artifacts_removed": {},
        }

    # Cleanup presentation artifacts
    artifacts = _cleanup_presentation_artifacts(project_id)

    logger.info(f"Archived project {project_id}: {artifacts}")

    return {
        "project_id": project_id,
        "action": "archived",
        "artifacts_removed": artifacts,
    }


def revive_project(project_id: str) -> dict:
    """Revive an archived project: flip status back to active.

    Presentation is regenerated lazily on demand (via presenter endpoints).

    Returns LifecycleActionResponse dict.
    """
    project = get_project(project_id)
    if project is None:
        raise ValueError(f"Project not found: {project_id}")

    # Already active — idempotent
    if project["status"] == "active":
        return {
            "project_id": project_id,
            "action": "already_active",
            "artifacts_removed": {},
        }

    # Optimistic lock
    now = datetime.utcnow().isoformat()
    affected = execute_write(
        "UPDATE projects SET status = %s, archived_at = NULL, last_activity_at = %s "
        "WHERE project_id = %s AND status = %s",
        ("active", now, project_id, "archived"),
    )

    if affected == 0:
        return {
            "project_id": project_id,
            "action": "already_active",
            "artifacts_removed": {},
        }

    logger.info(f"Revived project {project_id}")

    return {
        "project_id": project_id,
        "action": "revived",
        "artifacts_removed": {},
    }


def delete_project(project_id: str) -> dict:
    """Hard-delete a project and ALL associated data.

    Returns LifecycleActionResponse dict.
    """
    project = get_project(project_id)
    if project is None:
        raise ValueError(f"Project not found: {project_id}")

    # Guard: no active jobs
    if _has_active_jobs(project_id):
        raise RuntimeError(
            f"Cannot delete project {project_id}: has running/pending jobs"
        )

    # Full cleanup
    artifacts = _cleanup_all_project_data(project_id)

    logger.info(f"Deleted project {project_id}: {artifacts}")

    return {
        "project_id": project_id,
        "action": "deleted",
        "artifacts_removed": artifacts,
    }


# --- Auto-archive ---


def run_auto_archive() -> dict:
    """Find and archive stale projects.

    Called periodically from the auto-archive background task.

    Returns {checked: N, archived: M, skipped_active_jobs: K, skipped_exempt: J}.
    """
    now = datetime.utcnow()

    # Find active projects with auto_archive_days set
    candidates = execute(
        """SELECT project_id, name, auto_archive_days, last_activity_at
           FROM projects
           WHERE status = 'active' AND auto_archive_days IS NOT NULL""",
        fetch="all",
    )

    result = {"checked": len(candidates), "archived": 0, "skipped_active_jobs": 0, "skipped_exempt": 0}

    for proj in candidates:
        auto_days = proj.get("auto_archive_days")
        if auto_days is None:
            result["skipped_exempt"] += 1
            continue

        last_activity = proj.get("last_activity_at")
        if last_activity is None:
            continue

        # Parse timestamp
        if isinstance(last_activity, str):
            try:
                last_dt = datetime.fromisoformat(last_activity)
            except (ValueError, TypeError):
                continue
        elif isinstance(last_activity, datetime):
            last_dt = last_activity
        else:
            continue

        days_inactive = (now - last_dt).total_seconds() / 86400
        if days_inactive < auto_days:
            continue

        # Check for active jobs
        if _has_active_jobs(proj["project_id"]):
            result["skipped_active_jobs"] += 1
            logger.info(
                f"[auto-archive] Skipping {proj['project_id']} ({proj['name']}): "
                f"has active jobs"
            )
            continue

        try:
            action = archive_project(proj["project_id"])
            if action["action"] == "archived":
                result["archived"] += 1
                logger.info(
                    f"[auto-archive] Archived {proj['project_id']} ({proj['name']}): "
                    f"inactive {days_inactive:.0f} days > {auto_days} day threshold"
                )
        except Exception as e:
            logger.error(f"[auto-archive] Failed to archive {proj['project_id']}: {e}")

    return result
