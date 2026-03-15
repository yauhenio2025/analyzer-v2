"""Persistence for view polish results.

Uses the executor DB layer (same Postgres/SQLite backend).
Supports both view-level polish (section_key='') and per-section polish.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Optional

from src.executor.db import (
    _is_postgres,
    _json_dumps,
    _json_loads,
    execute,
    get_connection,
    init_db,
)

logger = logging.getLogger(__name__)

_migration_done = False
_POLISH_IDENTITY = ("job_id", "view_key", "consumer_key", "style_school", "section_key")


def _ensure_polish_cache_schema() -> None:
    """Ensure polish_cache has the current identity shape on both backends."""
    global _migration_done
    if _migration_done:
        return

    init_db()

    with get_connection() as conn:
        cursor = conn.cursor()
        columns = _polish_cache_columns(cursor)
        if not _has_expected_identity(cursor) or {"consumer_key", "section_key"} - columns:
            logger.info("[polish-cache] Rebuilding polish_cache schema for consumer + section scoping")
            _rebuild_polish_cache(cursor, columns)
            conn.commit()

    _migration_done = True


def _polish_cache_columns(cursor) -> set[str]:
    if _is_postgres():
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'polish_cache'
            """
        )
        return {row[0] for row in cursor.fetchall()}

    cursor.execute("PRAGMA table_info(polish_cache)")
    return {row[1] for row in cursor.fetchall()}


def _has_expected_identity(cursor) -> bool:
    expected = list(_POLISH_IDENTITY)

    if _is_postgres():
        cursor.execute(
            """
            SELECT indexdef
            FROM pg_indexes
            WHERE tablename = 'polish_cache'
            """
        )
        for (indexdef,) in cursor.fetchall():
            normalized = "".join(indexdef.lower().split())
            if "unique" not in normalized:
                continue
            if ",".join(expected) in normalized:
                return True
        return False

    cursor.execute("PRAGMA index_list(polish_cache)")
    indexes = cursor.fetchall()
    for index in indexes:
        # sqlite pragma: seq, name, unique, origin, partial
        if len(index) < 3 or not index[2]:
            continue
        cursor.execute(f"PRAGMA index_info('{index[1]}')")
        columns = [row[2] for row in cursor.fetchall()]
        if columns == expected:
            return True
    return False


def _rebuild_polish_cache(cursor, columns: set[str]) -> None:
    legacy_table = "polish_cache_legacy_tmp"
    cursor.execute(f"DROP TABLE IF EXISTS {legacy_table}")
    cursor.execute(f"ALTER TABLE polish_cache RENAME TO {legacy_table}")
    _create_polish_cache(cursor)

    select_exprs = [
        "job_id",
        "view_key",
        "consumer_key" if "consumer_key" in columns else "'' AS consumer_key",
        "style_school" if "style_school" in columns else "'' AS style_school",
        "section_key" if "section_key" in columns else "'' AS section_key",
        "config_hash" if "config_hash" in columns else "'' AS config_hash",
        "polished_data",
        "model_used",
        "tokens_used",
        "created_at",
    ]
    cursor.execute(
        f"SELECT {', '.join(select_exprs)} FROM {legacy_table} ORDER BY created_at ASC"
    )
    rows = cursor.fetchall()

    if _is_postgres():
        insert_sql = """
            INSERT INTO polish_cache (
                job_id, view_key, consumer_key, style_school, section_key,
                config_hash, polished_data, model_used, tokens_used, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (job_id, view_key, consumer_key, style_school, section_key)
            DO UPDATE SET
                config_hash = EXCLUDED.config_hash,
                polished_data = EXCLUDED.polished_data,
                model_used = EXCLUDED.model_used,
                tokens_used = EXCLUDED.tokens_used,
                created_at = EXCLUDED.created_at
        """
    else:
        insert_sql = """
            INSERT OR REPLACE INTO polish_cache (
                job_id, view_key, consumer_key, style_school, section_key,
                config_hash, polished_data, model_used, tokens_used, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

    for row in rows:
        cursor.execute(insert_sql, tuple(row))

    cursor.execute(f"DROP TABLE {legacy_table}")


def _create_polish_cache(cursor) -> None:
    if _is_postgres():
        cursor.execute(
            """
            CREATE TABLE polish_cache (
                id SERIAL PRIMARY KEY,
                job_id VARCHAR(100) NOT NULL,
                view_key VARCHAR(100) NOT NULL,
                consumer_key VARCHAR(100) DEFAULT '',
                style_school VARCHAR(100) DEFAULT '',
                section_key VARCHAR(100) DEFAULT '',
                config_hash VARCHAR(64) DEFAULT '',
                polished_data JSONB NOT NULL,
                model_used VARCHAR(100),
                tokens_used INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(job_id, view_key, consumer_key, style_school, section_key)
            )
            """
        )
        return

    cursor.execute(
        """
        CREATE TABLE polish_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            view_key TEXT NOT NULL,
            consumer_key TEXT DEFAULT '',
            style_school TEXT DEFAULT '',
            section_key TEXT DEFAULT '',
            config_hash TEXT DEFAULT '',
            polished_data TEXT NOT NULL,
            model_used TEXT,
            tokens_used INTEGER DEFAULT 0,
            created_at TEXT,
            UNIQUE(job_id, view_key, consumer_key, style_school, section_key)
        )
        """
    )


def save_polish_cache(
    job_id: str,
    view_key: str,
    consumer_key: str,
    style_school: str,
    polished_data: dict[str, Any],
    config_hash: str = "",
    model_used: str = "",
    tokens_used: int = 0,
    section_key: str = "",
) -> bool:
    """Save or update polished view/section data."""
    _ensure_polish_cache_schema()
    now = datetime.now(UTC).isoformat()
    try:
        execute(
            "DELETE FROM polish_cache WHERE job_id = %s AND view_key = %s "
            "AND consumer_key = %s AND style_school = %s AND section_key = %s",
            (job_id, view_key, consumer_key, style_school, section_key),
        )
        execute(
            """INSERT INTO polish_cache
               (job_id, view_key, consumer_key, style_school, section_key, config_hash,
                polished_data, model_used, tokens_used, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                job_id,
                view_key,
                consumer_key,
                style_school,
                section_key,
                config_hash,
                _json_dumps(polished_data),
                model_used,
                tokens_used,
                now,
            ),
        )
        section_label = f" section={section_key}" if section_key else ""
        logger.info(
            "[polish-cache] Saved polish for job=%s consumer=%s view=%s school=%s%s",
            job_id,
            consumer_key,
            view_key,
            style_school,
            section_label,
        )
        return True
    except Exception as e:
        logger.error(
            "[polish-cache] Failed to save for %s/%s/%s: %s",
            job_id,
            consumer_key,
            view_key,
            e,
        )
        return False


def delete_polish_cache(job_id: str) -> int:
    """Delete all polish cache entries for a job."""
    _ensure_polish_cache_schema()
    try:
        row = execute(
            "SELECT COUNT(*) AS cnt FROM polish_cache WHERE job_id = %s",
            (job_id,),
            fetch="one",
        )
        count = row["cnt"] if row else 0
        execute(
            "DELETE FROM polish_cache WHERE job_id = %s",
            (job_id,),
        )
        logger.info("[polish-cache] Deleted %s entries for job=%s", count, job_id)
        return count
    except Exception as e:
        logger.error(f"[polish-cache] Failed to delete for {job_id}: {e}")
        return 0


def load_polish_cache(
    job_id: str,
    view_key: str,
    *,
    consumer_key: str = "",
    style_school: Optional[str] = None,
    section_key: Optional[str] = None,
    expected_config_hash: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Load cached polish result for a view or section."""
    _ensure_polish_cache_schema()
    sk = section_key if section_key is not None else ""

    params: tuple[Any, ...]
    sql = """
        SELECT polished_data, model_used, tokens_used, style_school, config_hash, created_at
        FROM polish_cache
        WHERE job_id = %s AND view_key = %s AND consumer_key = %s AND section_key = %s
    """
    params = (job_id, view_key, consumer_key, sk)

    if style_school is not None:
        sql += " AND style_school = %s"
        params += (style_school,)
    else:
        sql += " ORDER BY created_at DESC"

    row = execute(sql, params, fetch="one")
    if row is None:
        return None

    if expected_config_hash is not None and (row.get("config_hash") or "") != expected_config_hash:
        return None

    polished = row["polished_data"]
    if isinstance(polished, str):
        polished = _json_loads(polished)

    return {
        "polished_data": polished,
        "model_used": row["model_used"],
        "tokens_used": row["tokens_used"],
        "style_school": row["style_school"],
        "config_hash": row.get("config_hash") or "",
        "created_at": row["created_at"],
    }
