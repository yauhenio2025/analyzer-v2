"""Persistence helpers for derived presentation artifacts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Optional

from src.executor.db import _json_dumps, _json_loads, execute, init_db


def save_presentation_artifact(
    job_id: str,
    view_key: str,
    artifact_kind: str,
    artifact_version: int,
    prompt_version: str,
    input_hash: str,
    content: dict[str, Any],
    *,
    model_used: str = "",
) -> bool:
    """Persist a derived presentation artifact."""
    init_db()
    now = datetime.now(UTC).isoformat()

    try:
        execute(
            """DELETE FROM presentation_artifacts
               WHERE job_id = %s
                 AND view_key = %s
                 AND artifact_kind = %s
                 AND artifact_version = %s
                 AND prompt_version = %s
                 AND input_hash = %s""",
            (job_id, view_key, artifact_kind, artifact_version, prompt_version, input_hash),
        )
        execute(
            """INSERT INTO presentation_artifacts
               (job_id, view_key, artifact_kind, artifact_version, prompt_version,
                input_hash, content, model_used, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                job_id,
                view_key,
                artifact_kind,
                artifact_version,
                prompt_version,
                input_hash,
                _json_dumps(content),
                model_used,
                now,
            ),
        )
        return True
    except Exception:
        return False


def load_presentation_artifact(
    job_id: str,
    view_key: str,
    artifact_kind: str,
    artifact_version: int,
    prompt_version: str,
    input_hash: str,
) -> Optional[dict[str, Any]]:
    """Load an exact artifact match."""
    init_db()
    row = execute(
        """SELECT content
           FROM presentation_artifacts
           WHERE job_id = %s
             AND view_key = %s
             AND artifact_kind = %s
             AND artifact_version = %s
             AND prompt_version = %s
             AND input_hash = %s
           ORDER BY created_at DESC, id DESC
           LIMIT 1""",
        (job_id, view_key, artifact_kind, artifact_version, prompt_version, input_hash),
        fetch="one",
    )
    if row is None:
        return None

    content = row["content"]
    if isinstance(content, str):
        content = _json_loads(content)
    return content


def load_presentation_artifact_batch(
    job_id: str,
    artifact_kind: str,
) -> dict[tuple[str, int, str, str], dict[str, Any]]:
    """Load all artifacts of a kind for a job keyed by version/prompt/hash."""
    init_db()
    rows = execute(
        """SELECT view_key, artifact_version, prompt_version, input_hash, content
           FROM presentation_artifacts
           WHERE job_id = %s AND artifact_kind = %s
           ORDER BY created_at DESC, id DESC""",
        (job_id, artifact_kind),
        fetch="all",
    )

    result: dict[tuple[str, int, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (
            row["view_key"],
            int(row.get("artifact_version") or 1),
            row.get("prompt_version") or "",
            row["input_hash"],
        )
        if key in result:
            continue
        content = row["content"]
        if isinstance(content, str):
            content = _json_loads(content)
        result[key] = content
    return result


def load_presentation_artifact_fingerprint_batch(
    job_id: str,
    artifact_kind: str,
) -> dict[tuple[str, int, str, str], str]:
    """Load artifact fingerprint metadata without hydrating full JSON content."""
    init_db()
    rows = execute(
        """SELECT view_key, artifact_version, prompt_version, input_hash
           FROM presentation_artifacts
           WHERE job_id = %s AND artifact_kind = %s
           ORDER BY created_at DESC, id DESC""",
        (job_id, artifact_kind),
        fetch="all",
    )

    result: dict[tuple[str, int, str, str], str] = {}
    for row in rows:
        key = (
            row["view_key"],
            int(row.get("artifact_version") or 1),
            row.get("prompt_version") or "",
            row["input_hash"],
        )
        result.setdefault(key, row["input_hash"])
    return result
