"""Database layer for the executor.

Supports two backends:
- PostgreSQL (production, set DATABASE_URL env var)
- SQLite (local development, default)

Uses raw SQL via psycopg2 (Postgres) or sqlite3 (SQLite) for simplicity.
No ORM — keeps the dependency footprint minimal.

Thread-safety: Postgres uses a ThreadedConnectionPool for efficient
connection reuse. SQLite uses per-call connections with check_same_thread=False.
"""

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Database URL: postgres://... for Postgres, or empty/sqlite for SQLite
DATABASE_URL = os.environ.get("EXECUTOR_DATABASE_URL", "")

# SQLite default path
SQLITE_PATH = Path(__file__).parent / "executor.db"

_initialized = False
_pg_pool = None


def _is_postgres() -> bool:
    """Check if we're using Postgres."""
    return DATABASE_URL.startswith("postgres")


def _get_pg_pool():
    """Get or create the Postgres connection pool (lazy singleton)."""
    global _pg_pool
    if _pg_pool is None:
        import psycopg2.pool
        _pg_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            dsn=DATABASE_URL,
        )
        logger.info("PostgreSQL connection pool initialized (1-5 connections)")
    return _pg_pool


@contextmanager
def get_connection():
    """Get a database connection (Postgres or SQLite).

    For Postgres, uses a connection pool to avoid the overhead of
    TCP + SSL + auth on every query (~700ms per connection cross-region).

    Usage:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(...)
            conn.commit()
    """
    if _is_postgres():
        pool = _get_pg_pool()
        conn = pool.getconn()
        try:
            yield conn
        finally:
            pool.putconn(conn)
    else:
        conn = sqlite3.connect(str(SQLITE_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            conn.close()


def _json_dumps(data: Any) -> str:
    """Serialize data to JSON string for storage."""
    if data is None:
        return "{}"
    return json.dumps(data, ensure_ascii=False, default=str)


def _json_loads(text: str) -> Any:
    """Deserialize JSON string from storage."""
    if not text:
        return {}
    if isinstance(text, dict):
        return text  # Already parsed (Postgres JSONB)
    return json.loads(text)


def execute(sql: str, params: tuple = (), fetch: str = "none") -> Any:
    """Execute a SQL statement.

    Args:
        sql: SQL statement (use %s for Postgres, ? for SQLite placeholders)
        params: Parameters tuple
        fetch: "none", "one", "all"

    Returns:
        None for "none", dict for "one", list[dict] for "all"
    """
    # Adapt placeholder style
    if _is_postgres():
        # Postgres uses %s
        adapted_sql = sql
    else:
        # SQLite uses ?
        adapted_sql = sql.replace("%s", "?")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(adapted_sql, params)

        if fetch == "none":
            conn.commit()
            return None
        elif fetch == "one":
            row = cursor.fetchone()
            if row is None:
                return None
            if _is_postgres():
                import psycopg2.extras
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            else:
                return dict(row)
        elif fetch == "all":
            rows = cursor.fetchall()
            if _is_postgres():
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
            else:
                return [dict(row) for row in rows]

        conn.commit()
        return None


def init_db():
    """Create tables if they don't exist."""
    global _initialized
    if _initialized:
        return

    if _is_postgres():
        _init_postgres()
        _migrate_postgres()
    else:
        _init_sqlite()

    _initialized = True
    backend = "PostgreSQL" if _is_postgres() else f"SQLite ({SQLITE_PATH})"
    logger.info(f"Executor database initialized: {backend}")


def _migrate_postgres():
    """Add columns that may be missing from existing tables."""
    migrations = [
        "ALTER TABLE executor_jobs ADD COLUMN IF NOT EXISTS plan_data JSONB",
        "ALTER TABLE executor_jobs ADD COLUMN IF NOT EXISTS document_ids JSONB DEFAULT '{}'",
        "ALTER TABLE executor_jobs ADD COLUMN IF NOT EXISTS cancel_token VARCHAR(64)",
        "ALTER TABLE executor_jobs ADD COLUMN IF NOT EXISTS workflow_key VARCHAR(100) DEFAULT 'intellectual_genealogy'",
        "ALTER TABLE presentation_cache ALTER COLUMN section TYPE VARCHAR(200)",
    ]
    with get_connection() as conn:
        cursor = conn.cursor()
        for sql in migrations:
            try:
                cursor.execute(sql)
            except Exception as e:
                logger.debug(f"Migration skipped (already applied?): {e}")
        conn.commit()


def _init_postgres():
    """Create Postgres tables."""
    ddl = """
    CREATE TABLE IF NOT EXISTS executor_jobs (
        job_id VARCHAR(100) PRIMARY KEY,
        plan_id VARCHAR(100) NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'pending',
        progress JSONB DEFAULT '{}',
        phase_results JSONB DEFAULT '{}',
        error TEXT,
        total_llm_calls INTEGER DEFAULT 0,
        total_input_tokens INTEGER DEFAULT 0,
        total_output_tokens INTEGER DEFAULT 0,
        plan_data JSONB,
        document_ids JSONB DEFAULT '{}',
        cancel_token VARCHAR(64),
        workflow_key VARCHAR(100) DEFAULT 'intellectual_genealogy',
        created_at TIMESTAMP DEFAULT NOW(),
        started_at TIMESTAMP,
        completed_at TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS phase_outputs (
        id VARCHAR(100) PRIMARY KEY,
        job_id VARCHAR(100) NOT NULL REFERENCES executor_jobs(job_id),
        phase_number FLOAT NOT NULL,
        engine_key VARCHAR(100) NOT NULL,
        pass_number INTEGER NOT NULL DEFAULT 1,
        work_key VARCHAR(200) DEFAULT '',
        stance_key VARCHAR(50) DEFAULT '',
        role VARCHAR(30) NOT NULL DEFAULT 'extraction',
        content TEXT NOT NULL,
        model_used VARCHAR(100),
        input_tokens INTEGER DEFAULT 0,
        output_tokens INTEGER DEFAULT 0,
        parent_id VARCHAR(100),
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_phase_outputs_job
        ON phase_outputs(job_id, phase_number);
    CREATE INDEX IF NOT EXISTS idx_phase_outputs_engine
        ON phase_outputs(job_id, engine_key);

    CREATE TABLE IF NOT EXISTS presentation_cache (
        id SERIAL PRIMARY KEY,
        output_id VARCHAR(100) NOT NULL,
        section VARCHAR(200) NOT NULL,
        source_hash VARCHAR(64) NOT NULL,
        structured_data JSONB NOT NULL,
        model_used VARCHAR(100),
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(output_id, section)
    );

    CREATE TABLE IF NOT EXISTS executor_documents (
        doc_id VARCHAR(100) PRIMARY KEY,
        title VARCHAR(500) NOT NULL,
        author VARCHAR(200),
        role VARCHAR(20) NOT NULL DEFAULT 'target',
        text TEXT NOT NULL,
        char_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS view_refinements (
        id SERIAL PRIMARY KEY,
        job_id VARCHAR(100) NOT NULL UNIQUE,
        plan_id VARCHAR(100) NOT NULL,
        refined_views JSONB NOT NULL DEFAULT '[]',
        changes_summary TEXT DEFAULT '',
        model_used VARCHAR(100),
        tokens_used INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS polish_cache (
        id SERIAL PRIMARY KEY,
        job_id VARCHAR(100) NOT NULL,
        view_key VARCHAR(100) NOT NULL,
        style_school VARCHAR(100) DEFAULT '',
        config_hash VARCHAR(64) DEFAULT '',
        polished_data JSONB NOT NULL,
        model_used VARCHAR(100),
        tokens_used INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(job_id, view_key, style_school)
    );
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(ddl)
        conn.commit()


def _init_sqlite():
    """Create SQLite tables."""
    ddl = """
    CREATE TABLE IF NOT EXISTS executor_jobs (
        job_id TEXT PRIMARY KEY,
        plan_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        progress TEXT DEFAULT '{}',
        phase_results TEXT DEFAULT '{}',
        error TEXT,
        total_llm_calls INTEGER DEFAULT 0,
        total_input_tokens INTEGER DEFAULT 0,
        total_output_tokens INTEGER DEFAULT 0,
        plan_data TEXT,
        document_ids TEXT DEFAULT '{}',
        cancel_token TEXT,
        workflow_key TEXT DEFAULT 'intellectual_genealogy',
        created_at TEXT,
        started_at TEXT,
        completed_at TEXT
    );

    CREATE TABLE IF NOT EXISTS phase_outputs (
        id TEXT PRIMARY KEY,
        job_id TEXT NOT NULL REFERENCES executor_jobs(job_id),
        phase_number REAL NOT NULL,
        engine_key TEXT NOT NULL,
        pass_number INTEGER NOT NULL DEFAULT 1,
        work_key TEXT DEFAULT '',
        stance_key TEXT DEFAULT '',
        role TEXT NOT NULL DEFAULT 'extraction',
        content TEXT NOT NULL,
        model_used TEXT,
        input_tokens INTEGER DEFAULT 0,
        output_tokens INTEGER DEFAULT 0,
        parent_id TEXT,
        metadata TEXT DEFAULT '{}',
        created_at TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_phase_outputs_job
        ON phase_outputs(job_id, phase_number);
    CREATE INDEX IF NOT EXISTS idx_phase_outputs_engine
        ON phase_outputs(job_id, engine_key);

    CREATE TABLE IF NOT EXISTS presentation_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        output_id TEXT NOT NULL,
        section TEXT NOT NULL,
        source_hash TEXT NOT NULL,
        structured_data TEXT NOT NULL,
        model_used TEXT,
        created_at TEXT,
        UNIQUE(output_id, section)
    );

    CREATE TABLE IF NOT EXISTS executor_documents (
        doc_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        author TEXT,
        role TEXT NOT NULL DEFAULT 'target',
        text TEXT NOT NULL,
        char_count INTEGER DEFAULT 0,
        created_at TEXT
    );

    CREATE TABLE IF NOT EXISTS view_refinements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL UNIQUE,
        plan_id TEXT NOT NULL,
        refined_views TEXT NOT NULL DEFAULT '[]',
        changes_summary TEXT DEFAULT '',
        model_used TEXT,
        tokens_used INTEGER DEFAULT 0,
        created_at TEXT
    );

    CREATE TABLE IF NOT EXISTS polish_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL,
        view_key TEXT NOT NULL,
        style_school TEXT DEFAULT '',
        config_hash TEXT DEFAULT '',
        polished_data TEXT NOT NULL,
        model_used TEXT,
        tokens_used INTEGER DEFAULT 0,
        created_at TEXT,
        UNIQUE(job_id, view_key, style_school)
    );
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.executescript(ddl)
        conn.commit()
