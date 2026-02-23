"""Persistence for view polish results.

Uses the executor DB layer (same Postgres/SQLite backend).
"""

import logging
from datetime import datetime
from typing import Any, Optional

from src.executor.db import execute, _json_dumps, _json_loads

logger = logging.getLogger(__name__)


def save_polish_cache(
    job_id: str,
    view_key: str,
    style_school: str,
    polished_data: dict[str, Any],
    config_hash: str = "",
    model_used: str = "",
    tokens_used: int = 0,
) -> bool:
    """Save or update polished view data.

    Uses upsert: deletes existing entry for this (job_id, view_key, style_school),
    then inserts.
    """
    now = datetime.utcnow().isoformat()
    try:
        execute(
            "DELETE FROM polish_cache WHERE job_id = %s AND view_key = %s AND style_school = %s",
            (job_id, view_key, style_school),
        )
        execute(
            """INSERT INTO polish_cache
               (job_id, view_key, style_school, config_hash, polished_data,
                model_used, tokens_used, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                job_id, view_key, style_school, config_hash,
                _json_dumps(polished_data), model_used, tokens_used, now,
            ),
        )
        logger.info(
            f"[polish-cache] Saved polish for job={job_id} view={view_key} "
            f"school={style_school}"
        )
        return True
    except Exception as e:
        logger.error(f"[polish-cache] Failed to save for {job_id}/{view_key}: {e}")
        return False


def load_polish_cache(
    job_id: str,
    view_key: str,
    style_school: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Load cached polish result for a view.

    If style_school is None, returns the most recent polish for this view
    regardless of school. Otherwise, matches exactly.
    """
    if style_school is not None:
        row = execute(
            """SELECT polished_data, model_used, tokens_used, style_school, created_at
               FROM polish_cache
               WHERE job_id = %s AND view_key = %s AND style_school = %s""",
            (job_id, view_key, style_school),
            fetch="one",
        )
    else:
        row = execute(
            """SELECT polished_data, model_used, tokens_used, style_school, created_at
               FROM polish_cache
               WHERE job_id = %s AND view_key = %s
               ORDER BY created_at DESC""",
            (job_id, view_key),
            fetch="one",
        )

    if row is None:
        return None

    polished = row["polished_data"]
    if isinstance(polished, str):
        polished = _json_loads(polished)

    return {
        "polished_data": polished,
        "model_used": row["model_used"],
        "tokens_used": row["tokens_used"],
        "style_school": row["style_school"],
        "created_at": row["created_at"],
    }
