"""Storage operations for Tier 3b variant sets, variants, and selections."""

import logging
from datetime import datetime
from typing import Optional

from src.executor.db import execute, execute_write, execute_transaction, _json_dumps, _json_loads

logger = logging.getLogger(__name__)


def _normalize_variant_set_row(row: dict) -> dict:
    """Normalize DB row into API response shape."""
    normalized = dict(row)
    metadata = normalized.get("metadata")
    if isinstance(metadata, str):
        normalized["metadata"] = _json_loads(metadata)
    elif metadata is None:
        normalized["metadata"] = {}

    for ts_key in ("created_at",):
        ts_val = normalized.get(ts_key)
        if isinstance(ts_val, datetime):
            normalized[ts_key] = ts_val.isoformat()
        elif ts_val is None:
            normalized[ts_key] = ""
    return normalized


def _normalize_variant_row(row: dict) -> dict:
    """Normalize a variant DB row."""
    normalized = dict(row)
    config = normalized.get("renderer_config")
    if isinstance(config, str):
        normalized["renderer_config"] = _json_loads(config)
    elif config is None:
        normalized["renderer_config"] = {}

    # SQLite stores booleans as integers
    is_control = normalized.get("is_control")
    if isinstance(is_control, int):
        normalized["is_control"] = bool(is_control)

    for ts_key in ("created_at",):
        ts_val = normalized.get(ts_key)
        if isinstance(ts_val, datetime):
            normalized[ts_key] = ts_val.isoformat()
    return normalized


def save_variant_set(
    variant_set_id: str,
    job_id: str,
    view_key: str,
    dimension: str,
    base_renderer: str,
    style_school: str = "",
    variant_count: int = 0,
    metadata: Optional[dict] = None,
) -> None:
    """Persist a variant set record."""
    now = datetime.utcnow().isoformat()
    execute_write(
        "INSERT INTO variant_sets "
        "(variant_set_id, job_id, view_key, dimension, base_renderer, "
        "style_school, variant_count, created_at, metadata) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "ON CONFLICT(variant_set_id) DO UPDATE SET "
        "variant_count = EXCLUDED.variant_count, metadata = EXCLUDED.metadata",
        (
            variant_set_id, job_id, view_key, dimension, base_renderer,
            style_school or "", variant_count, now,
            _json_dumps(metadata or {}),
        ),
    )


def save_variant(
    variant_id: str,
    variant_set_id: str,
    variant_index: int,
    is_control: bool,
    renderer_type: str,
    renderer_config: Optional[dict] = None,
    rationale: str = "",
    compatibility_score: float = 0.0,
) -> None:
    """Persist a single variant record."""
    now = datetime.utcnow().isoformat()
    execute_write(
        "INSERT INTO variants "
        "(variant_id, variant_set_id, variant_index, is_control, renderer_type, "
        "renderer_config, rationale, compatibility_score, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "ON CONFLICT(variant_id) DO UPDATE SET "
        "renderer_config = EXCLUDED.renderer_config, "
        "rationale = EXCLUDED.rationale, "
        "compatibility_score = EXCLUDED.compatibility_score",
        (
            variant_id, variant_set_id, variant_index, is_control,
            renderer_type, _json_dumps(renderer_config or {}),
            rationale, compatibility_score, now,
        ),
    )


def load_variant_set(variant_set_id: str) -> Optional[dict]:
    """Load a variant set with all its variants."""
    row = execute(
        "SELECT * FROM variant_sets WHERE variant_set_id = %s",
        (variant_set_id,),
        fetch="one",
    )
    if row is None:
        return None

    vs = _normalize_variant_set_row(row)

    variants = execute(
        "SELECT * FROM variants WHERE variant_set_id = %s ORDER BY variant_index",
        (variant_set_id,),
        fetch="all",
    )
    vs["variants"] = [_normalize_variant_row(v) for v in variants]
    return vs


def list_variant_sets(job_id: str, view_key: str) -> list[dict]:
    """List variant sets for a job+view combination."""
    rows = execute(
        "SELECT * FROM variant_sets WHERE job_id = %s AND view_key = %s "
        "ORDER BY created_at DESC",
        (job_id, view_key),
        fetch="all",
    )
    result = []
    for row in rows:
        vs = _normalize_variant_set_row(row)
        variants = execute(
            "SELECT * FROM variants WHERE variant_set_id = %s ORDER BY variant_index",
            (vs["variant_set_id"],),
            fetch="all",
        )
        vs["variants"] = [_normalize_variant_row(v) for v in variants]
        result.append(vs)
    return result


def delete_variant_set(variant_set_id: str) -> int:
    """Delete a variant set and its variants + selections. Returns total rows deleted."""
    statements = [
        (
            "DELETE FROM variant_selections WHERE variant_set_id = %s",
            (variant_set_id,),
        ),
        (
            "DELETE FROM variants WHERE variant_set_id = %s",
            (variant_set_id,),
        ),
        (
            "DELETE FROM variant_sets WHERE variant_set_id = %s",
            (variant_set_id,),
        ),
    ]
    rowcounts = execute_transaction(statements)
    total = sum(rowcounts)
    if total > 0:
        logger.info(f"Deleted variant set {variant_set_id}: {total} rows")
    return total


def save_selection(
    variant_set_id: str,
    variant_id: str,
    job_id: str,
    view_key: str,
    project_id: Optional[str] = None,
) -> str:
    """Upsert a variant selection. Returns the selected_at timestamp."""
    now = datetime.utcnow().isoformat()

    # Use upsert to handle re-selection (change of mind)
    execute_write(
        "INSERT INTO variant_selections "
        "(variant_set_id, variant_id, job_id, project_id, view_key, selected_at) "
        "VALUES (%s, %s, %s, %s, %s, %s) "
        "ON CONFLICT(variant_set_id, job_id) DO UPDATE SET "
        "variant_id = EXCLUDED.variant_id, selected_at = EXCLUDED.selected_at",
        (variant_set_id, variant_id, job_id, project_id, view_key, now),
    )
    return now


def load_selections(job_id: str, view_key: str) -> list[dict]:
    """Load current selections for a job+view."""
    rows = execute(
        "SELECT vs.*, vsel.variant_id as selected_variant_id, vsel.selected_at "
        "FROM variant_selections vsel "
        "JOIN variant_sets vs ON vsel.variant_set_id = vs.variant_set_id "
        "WHERE vsel.job_id = %s AND vsel.view_key = %s "
        "ORDER BY vsel.selected_at DESC",
        (job_id, view_key),
        fetch="all",
    )
    result = []
    for row in rows:
        normalized = dict(row)
        for ts_key in ("created_at", "selected_at"):
            ts_val = normalized.get(ts_key)
            if isinstance(ts_val, datetime):
                normalized[ts_key] = ts_val.isoformat()
        metadata = normalized.get("metadata")
        if isinstance(metadata, str):
            normalized["metadata"] = _json_loads(metadata)
        result.append(normalized)
    return result


def load_selected_variants(job_id: str, view_key: str) -> list[dict]:
    """Load the fully-resolved selected variants for a job+view.

    Joins selections -> variant_sets -> variants so the compose pipeline can
    apply the user's chosen renderer or sub-renderer strategy on later loads.
    """
    rows = execute(
        "SELECT vs.dimension, vs.base_renderer, vs.style_school, "
        "vsel.variant_set_id, vsel.variant_id, vsel.selected_at, "
        "v.renderer_type, v.renderer_config, v.compatibility_score, v.rationale "
        "FROM variant_selections vsel "
        "JOIN variant_sets vs ON vsel.variant_set_id = vs.variant_set_id "
        "JOIN variants v ON vsel.variant_id = v.variant_id "
        "WHERE vsel.job_id = %s AND vsel.view_key = %s "
        "ORDER BY vsel.selected_at DESC",
        (job_id, view_key),
        fetch="all",
    )
    result = []
    for row in rows:
        normalized = dict(row)
        config = normalized.get("renderer_config")
        if isinstance(config, str):
            normalized["renderer_config"] = _json_loads(config)
        elif config is None:
            normalized["renderer_config"] = {}

        ts_val = normalized.get("selected_at")
        if isinstance(ts_val, datetime):
            normalized["selected_at"] = ts_val.isoformat()

        result.append(normalized)
    return result


def summarize_selections(project_id: str) -> list[dict]:
    """Aggregate selection data grouped by dimension and view_key."""
    rows = execute(
        "SELECT vs.dimension, vs.view_key, vs.base_renderer, "
        "v.renderer_type as selected_renderer, COUNT(*) as selection_count "
        "FROM variant_selections vsel "
        "JOIN variant_sets vs ON vsel.variant_set_id = vs.variant_set_id "
        "JOIN variants v ON vsel.variant_id = v.variant_id "
        "WHERE vsel.project_id = %s "
        "GROUP BY vs.dimension, vs.view_key, vs.base_renderer, v.renderer_type "
        "ORDER BY selection_count DESC",
        (project_id,),
        fetch="all",
    )
    return [dict(r) for r in rows]


def delete_for_job(job_id: str) -> dict:
    """Delete all variant data for a job. Returns {table: rows_deleted}."""
    # Must cascade through variant_sets since variants table has no job_id
    statements = [
        (
            "DELETE FROM variant_selections WHERE variant_set_id IN "
            "(SELECT variant_set_id FROM variant_sets WHERE job_id = %s)",
            (job_id,),
        ),
        (
            "DELETE FROM variants WHERE variant_set_id IN "
            "(SELECT variant_set_id FROM variant_sets WHERE job_id = %s)",
            (job_id,),
        ),
        (
            "DELETE FROM variant_sets WHERE job_id = %s",
            (job_id,),
        ),
    ]
    table_names = ["variant_selections", "variants", "variant_sets"]
    rowcounts = execute_transaction(statements)
    counts = {name: count for name, count in zip(table_names, rowcounts) if count > 0}
    if counts:
        logger.info(f"Deleted variant data for job {job_id}: {counts}")
    return counts
