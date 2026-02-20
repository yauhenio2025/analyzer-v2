"""Persist phase outputs to the database.

Each LLM call produces a prose output that gets stored with full lineage
tracking (parent_id links to the output this one built upon).

Follows incremental persistence: each output is committed immediately
after generation, not batched at the end.
"""

import hashlib
import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from src.executor.db import execute, _json_dumps, _json_loads

logger = logging.getLogger(__name__)


def save_output(
    job_id: str,
    phase_number: float,
    engine_key: str,
    pass_number: int,
    content: str,
    *,
    work_key: str = "",
    stance_key: str = "",
    role: str = "extraction",
    model_used: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
    parent_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> str:
    """Save a prose analysis output to the database.

    Returns the generated output_id.
    """
    output_id = f"po-{uuid.uuid4().hex[:12]}"
    now = datetime.utcnow().isoformat()

    execute(
        """INSERT INTO phase_outputs
           (id, job_id, phase_number, engine_key, pass_number, work_key,
            stance_key, role, content, model_used, input_tokens, output_tokens,
            parent_id, metadata, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            output_id, job_id, phase_number, engine_key, pass_number,
            work_key, stance_key, role, content, model_used,
            input_tokens, output_tokens, parent_id,
            _json_dumps(metadata or {}), now,
        ),
    )

    logger.info(
        f"Saved output {output_id}: phase={phase_number}, engine={engine_key}, "
        f"pass={pass_number}, work={work_key or 'N/A'}, "
        f"tokens={input_tokens}+{output_tokens}, chars={len(content)}"
    )
    return output_id


def load_phase_outputs(
    job_id: str,
    phase_number: Optional[float] = None,
    engine_key: Optional[str] = None,
    work_key: Optional[str] = None,
) -> list[dict]:
    """Load prose outputs for a job, optionally filtered.

    Returns list of dicts with all columns, sorted by phase_number then pass_number.
    """
    conditions = ["job_id = %s"]
    params: list = [job_id]

    if phase_number is not None:
        conditions.append("phase_number = %s")
        params.append(phase_number)
    if engine_key is not None:
        conditions.append("engine_key = %s")
        params.append(engine_key)
    if work_key is not None:
        conditions.append("work_key = %s")
        params.append(work_key)

    where = " AND ".join(conditions)
    rows = execute(
        f"SELECT * FROM phase_outputs WHERE {where} ORDER BY phase_number, pass_number",
        tuple(params),
        fetch="all",
    )

    # Parse metadata JSON for SQLite
    for row in rows:
        if isinstance(row.get("metadata"), str):
            row["metadata"] = _json_loads(row["metadata"])

    return rows


def load_outputs_for_context(
    job_id: str,
    phase_numbers: Optional[list[float]] = None,
    engine_keys: Optional[list[str]] = None,
) -> list[dict]:
    """Load outputs suitable for context assembly.

    Returns outputs sorted by phase_number, pass_number for predictable
    context ordering. Only returns the 'content' and metadata fields
    needed by the context broker.
    """
    conditions = ["job_id = %s"]
    params: list = [job_id]

    if phase_numbers:
        placeholders = ", ".join(["%s"] * len(phase_numbers))
        conditions.append(f"phase_number IN ({placeholders})")
        params.extend(phase_numbers)

    if engine_keys:
        placeholders = ", ".join(["%s"] * len(engine_keys))
        conditions.append(f"engine_key IN ({placeholders})")
        params.extend(engine_keys)

    where = " AND ".join(conditions)
    rows = execute(
        f"""SELECT id, phase_number, engine_key, pass_number, work_key,
                   stance_key, role, content, model_used, metadata
            FROM phase_outputs
            WHERE {where}
            ORDER BY phase_number, pass_number""",
        tuple(params),
        fetch="all",
    )

    for row in rows:
        if isinstance(row.get("metadata"), str):
            row["metadata"] = _json_loads(row["metadata"])

    return rows


def get_latest_output_for_phase(
    job_id: str,
    phase_number: float,
    work_key: str = "",
) -> Optional[str]:
    """Get the final prose output for a phase (last engine's last pass).

    For context threading: upstream phases provide their final output
    as context for downstream phases.
    """
    row = execute(
        """SELECT content FROM phase_outputs
           WHERE job_id = %s AND phase_number = %s AND work_key = %s
           ORDER BY pass_number DESC LIMIT 1""",
        (job_id, phase_number, work_key),
        fetch="one",
    )
    return row["content"] if row else None


def count_outputs(job_id: str) -> int:
    """Count total outputs for a job."""
    row = execute(
        "SELECT COUNT(*) as cnt FROM phase_outputs WHERE job_id = %s",
        (job_id,),
        fetch="one",
    )
    return row["cnt"] if row else 0


def get_completed_passes(job_id: str) -> set[tuple]:
    """Get the set of (phase_number, engine_key, pass_number, work_key) already saved.

    Used by the resume system: before running an engine pass, check if it's
    already in phase_outputs. If yes, skip it and load the saved content.
    """
    rows = execute(
        """SELECT DISTINCT phase_number, engine_key, pass_number, work_key
           FROM phase_outputs WHERE job_id = %s""",
        (job_id,),
        fetch="all",
    )
    return {
        (r["phase_number"], r["engine_key"], r["pass_number"], r["work_key"] or "")
        for r in rows
    }


def get_completed_phases(job_id: str) -> set[float]:
    """Get phase numbers that have at least one output saved.

    Used by the resume system to identify phases that have partial
    or complete work.
    """
    rows = execute(
        """SELECT DISTINCT phase_number FROM phase_outputs WHERE job_id = %s""",
        (job_id,),
        fetch="all",
    )
    return {r["phase_number"] for r in rows}


def load_pass_content(
    job_id: str,
    phase_number: float,
    engine_key: str,
    pass_number: int,
    work_key: str = "",
) -> Optional[str]:
    """Load the saved content for a specific pass.

    Used by the resume system to restore context threading for
    already-completed passes.
    """
    row = execute(
        """SELECT content FROM phase_outputs
           WHERE job_id = %s AND phase_number = %s AND engine_key = %s
                 AND pass_number = %s AND work_key = %s
           LIMIT 1""",
        (job_id, phase_number, engine_key, pass_number, work_key),
        fetch="one",
    )
    return row["content"] if row else None


def load_engine_last_pass_content(
    job_id: str,
    phase_number: float,
    engine_key: str,
    work_key: str = "",
) -> Optional[str]:
    """Load the last pass output for an engine (for chain context threading).

    When resuming a chain, we need the last pass output of the previous
    engine to provide as context to the next engine.
    """
    row = execute(
        """SELECT content FROM phase_outputs
           WHERE job_id = %s AND phase_number = %s AND engine_key = %s
                 AND work_key = %s
           ORDER BY pass_number DESC LIMIT 1""",
        (job_id, phase_number, engine_key, work_key),
        fetch="one",
    )
    return row["content"] if row else None


def delete_job_outputs(job_id: str) -> int:
    """Delete all outputs for a job. Returns count deleted."""
    row = execute(
        "SELECT COUNT(*) as cnt FROM phase_outputs WHERE job_id = %s",
        (job_id,),
        fetch="one",
    )
    count = row["cnt"] if row else 0
    execute("DELETE FROM phase_outputs WHERE job_id = %s", (job_id,))
    logger.info(f"Deleted {count} outputs for job {job_id}")
    return count


# --- Presentation Cache ---

def save_presentation_cache(
    output_id: str,
    section: str,
    structured_data: dict,
    source_content: str,
    model_used: str = "",
) -> bool:
    """Save extracted structured data from prose output.

    Uses source_hash for invalidation: if the source prose changes,
    the cached extraction is stale.
    """
    source_hash = hashlib.sha256(source_content.encode()).hexdigest()
    now = datetime.utcnow().isoformat()

    try:
        # Upsert: replace if exists
        execute(
            "DELETE FROM presentation_cache WHERE output_id = %s AND section = %s",
            (output_id, section),
        )
        execute(
            """INSERT INTO presentation_cache
               (output_id, section, source_hash, structured_data, model_used, created_at)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (output_id, section, source_hash, _json_dumps(structured_data), model_used, now),
        )
        logger.info(f"Cached presentation: output={output_id}, section={section}")
        return True
    except Exception as e:
        logger.error(f"Failed to cache presentation: {e}")
        return False


def load_presentation_cache(
    output_id: str,
    section: str,
    source_content: Optional[str] = None,
) -> Optional[dict]:
    """Load cached structured extraction, optionally verifying freshness.

    If source_content is provided, checks that the source hasn't changed.
    Returns None if cache miss or stale.
    """
    row = execute(
        """SELECT structured_data, source_hash FROM presentation_cache
           WHERE output_id = %s AND section = %s""",
        (output_id, section),
        fetch="one",
    )

    if row is None:
        return None

    # Check freshness
    if source_content is not None:
        current_hash = hashlib.sha256(source_content.encode()).hexdigest()
        if current_hash != row["source_hash"]:
            logger.info(f"Stale presentation cache: output={output_id}, section={section}")
            return None

    data = row["structured_data"]
    if isinstance(data, str):
        data = _json_loads(data)
    return data
