"""Persistence for view refinements.

Uses the executor DB layer (same Postgres/SQLite backend).
"""

import logging
from datetime import datetime
from typing import Optional

from src.executor.db import execute, _json_dumps, _json_loads

logger = logging.getLogger(__name__)


def save_view_refinement(
    job_id: str,
    plan_id: str,
    refined_views: list[dict],
    changes_summary: str = "",
    model_used: str = "",
    tokens_used: int = 0,
) -> bool:
    """Save or update view refinement for a job.

    Uses upsert: deletes existing refinement for this job_id, then inserts.
    """
    now = datetime.utcnow().isoformat()
    try:
        execute("DELETE FROM view_refinements WHERE job_id = %s", (job_id,))
        execute(
            """INSERT INTO view_refinements
               (job_id, plan_id, refined_views, changes_summary,
                model_used, tokens_used, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                job_id, plan_id, _json_dumps(refined_views),
                changes_summary, model_used, tokens_used, now,
            ),
        )
        logger.info(f"Saved view refinement for job {job_id}: {len(refined_views)} views")
        return True
    except Exception as e:
        logger.error(f"Failed to save view refinement for {job_id}: {e}")
        return False


def delete_view_refinement(job_id: str) -> bool:
    """Delete view refinement for a job (used to clear bad refinements)."""
    try:
        execute("DELETE FROM view_refinements WHERE job_id = %s", (job_id,))
        logger.info(f"Deleted view refinement for job {job_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete view refinement for {job_id}: {e}")
        return False


def load_view_refinement(job_id: str) -> Optional[dict]:
    """Load view refinement for a job.

    Returns dict with refined_views, changes_summary, model_used, tokens_used
    or None if no refinement exists.
    """
    row = execute(
        """SELECT refined_views, changes_summary, model_used, tokens_used, created_at
           FROM view_refinements WHERE job_id = %s""",
        (job_id,),
        fetch="one",
    )
    if row is None:
        return None

    views = row["refined_views"]
    if isinstance(views, str):
        views = _json_loads(views)

    return {
        "refined_views": views,
        "changes_summary": row["changes_summary"],
        "model_used": row["model_used"],
        "tokens_used": row["tokens_used"],
        "created_at": row["created_at"],
    }
