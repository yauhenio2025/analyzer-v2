"""Database layer for the executor.

Supports two backends:
- PostgreSQL (production, set DATABASE_URL env var)
- SQLite (local development, default)

Uses raw SQL via psycopg2 (Postgres) or sqlite3 (SQLite) for simplicity.
No ORM — keeps the dependency footprint minimal.

Thread-safety: Postgres uses a ThreadedConnectionPool for efficient
connection reuse. SQLite uses per-call connections with check_same_thread=False.
"""

import hashlib
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
        _migrate_sqlite()

    _initialized = True
    backend = "PostgreSQL" if _is_postgres() else f"SQLite ({SQLITE_PATH})"
    logger.info(f"Executor database initialized: {backend}")


def execute_write(sql: str, params: tuple = ()) -> int:
    """Execute a single write statement. Returns affected row count.

    Uses raw connection path — does NOT call execute() (which auto-commits
    per call and returns None for writes). Needed for:
    - Counting deleted rows in cleanup cascades
    - Optimistic locking checks (affected_rows == 0 means another instance won)
    """
    if _is_postgres():
        adapted_sql = sql
    else:
        adapted_sql = sql.replace("%s", "?")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(adapted_sql, params)
        rowcount = cursor.rowcount
        conn.commit()
        return rowcount


def execute_transaction(statements: list[tuple[str, tuple]]) -> list[int]:
    """Execute multiple statements atomically. Returns rowcounts.

    Rolls back ALL on any exception. Used for multi-table cascade
    deletes (archive/delete project) where partial cleanup is undesirable.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        rowcounts = []
        try:
            for sql, params in statements:
                if _is_postgres():
                    adapted_sql = sql
                else:
                    adapted_sql = sql.replace("%s", "?")
                cursor.execute(adapted_sql, params)
                rowcounts.append(cursor.rowcount)
            conn.commit()
            return rowcounts
        except Exception:
            conn.rollback()
            raise


def _migrate_postgres():
    """Add columns that may be missing from existing tables."""
    migrations = [
        "ALTER TABLE executor_jobs ADD COLUMN IF NOT EXISTS plan_data JSONB",
        "ALTER TABLE executor_jobs ADD COLUMN IF NOT EXISTS document_ids JSONB DEFAULT '{}'",
        "ALTER TABLE executor_jobs ADD COLUMN IF NOT EXISTS cancel_token VARCHAR(64)",
        "ALTER TABLE executor_jobs ADD COLUMN IF NOT EXISTS workflow_key VARCHAR(100) DEFAULT 'intellectual_genealogy'",
        "ALTER TABLE executor_jobs ADD COLUMN IF NOT EXISTS corpus_ref VARCHAR(100)",
        "ALTER TABLE phase_outputs ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64) DEFAULT ''",
        "ALTER TABLE executor_documents ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64) DEFAULT ''",
        "ALTER TABLE presentation_cache ALTER COLUMN section TYPE VARCHAR(200)",
        # Priority 6: Project lifecycle
        "ALTER TABLE executor_jobs ADD COLUMN IF NOT EXISTS project_id VARCHAR(100)",
        """CREATE TABLE IF NOT EXISTS external_document_bindings (
               consumer_key VARCHAR(100) NOT NULL,
               external_project_id VARCHAR(120) NOT NULL,
               external_doc_key VARCHAR(200) NOT NULL,
               parent_external_doc_key VARCHAR(200),
               doc_id VARCHAR(100) NOT NULL REFERENCES executor_documents(doc_id),
               binding_role VARCHAR(20) NOT NULL,
               title VARCHAR(500) NOT NULL,
               author VARCHAR(200),
               source_thinker_id VARCHAR(100),
               source_thinker_name VARCHAR(200),
               source_document_id VARCHAR(200),
               content_hash VARCHAR(64) NOT NULL DEFAULT '',
               created_at TIMESTAMP DEFAULT NOW(),
               updated_at TIMESTAMP DEFAULT NOW(),
               PRIMARY KEY (consumer_key, external_project_id, external_doc_key)
           )""",
        """CREATE TABLE IF NOT EXISTS analysis_corpora (
               corpus_ref VARCHAR(100) PRIMARY KEY,
               workflow_key VARCHAR(100) NOT NULL,
               objective_key VARCHAR(100),
               member_manifest JSONB NOT NULL DEFAULT '[]'::jsonb,
               qualifiers JSONB NOT NULL DEFAULT '{}'::jsonb,
               created_at TIMESTAMP DEFAULT NOW(),
               updated_at TIMESTAMP DEFAULT NOW()
           )""",
        """CREATE TABLE IF NOT EXISTS analysis_artifacts (
               artifact_ref VARCHAR(100) PRIMARY KEY,
               corpus_ref VARCHAR(100) NOT NULL REFERENCES analysis_corpora(corpus_ref),
               artifact_family VARCHAR(120) NOT NULL,
               artifact_slot VARCHAR(200) NOT NULL DEFAULT 'default',
               format VARCHAR(40) NOT NULL,
               payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
               payload_text TEXT DEFAULT '',
               depends_on JSONB NOT NULL DEFAULT '[]'::jsonb,
               job_id VARCHAR(100),
               engine_key VARCHAR(100) DEFAULT '',
               phase_number FLOAT,
               source_output_id VARCHAR(100) DEFAULT '',
               payload_hash VARCHAR(64) NOT NULL DEFAULT '',
               producer_fingerprint VARCHAR(120) NOT NULL DEFAULT '',
               state VARCHAR(20) NOT NULL DEFAULT 'ready',
               created_at TIMESTAMP DEFAULT NOW(),
               updated_at TIMESTAMP DEFAULT NOW()
           )""",
    ]
    with get_connection() as conn:
        cursor = conn.cursor()
        for sql in migrations:
            try:
                cursor.execute(sql)
            except Exception as e:
                logger.debug(f"Migration skipped (already applied?): {e}")
        # Index for project_id lookups
        try:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_executor_jobs_project "
                "ON executor_jobs(project_id)"
            )
        except Exception as e:
            logger.debug(f"Index creation skipped: {e}")
        try:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_executor_jobs_corpus "
                "ON executor_jobs(corpus_ref)"
            )
        except Exception as e:
            logger.debug(f"Corpus index creation skipped: {e}")
        try:
            cursor.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_analysis_artifacts_family_slot "
                "ON analysis_artifacts(corpus_ref, artifact_family, artifact_slot)"
            )
        except Exception as e:
            logger.debug(f"Artifact unique index creation skipped: {e}")
        try:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_analysis_artifacts_job "
                "ON analysis_artifacts(job_id)"
            )
        except Exception as e:
            logger.debug(f"Artifact job index creation skipped: {e}")
        try:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_external_document_bindings_project "
                "ON external_document_bindings(consumer_key, external_project_id)"
            )
        except Exception as e:
            logger.debug(f"External binding index creation skipped: {e}")
        try:
            cursor.execute(
                "SELECT id, content FROM phase_outputs "
                "WHERE content_hash IS NULL OR content_hash = ''"
            )
            rows = cursor.fetchall()
            for row in rows:
                output_id, content = row[0], row[1] or ""
                cursor.execute(
                    "UPDATE phase_outputs SET content_hash = %s WHERE id = %s",
                    (hashlib.sha256(content.encode()).hexdigest(), output_id),
                )
        except Exception as e:
            logger.debug(f"Phase output content_hash backfill skipped: {e}")
        try:
            cursor.execute(
                "SELECT doc_id, text FROM executor_documents "
                "WHERE content_hash IS NULL OR content_hash = ''"
            )
            rows = cursor.fetchall()
            for row in rows:
                doc_id, text = row[0], row[1] or ""
                cursor.execute(
                    "UPDATE executor_documents SET content_hash = %s WHERE doc_id = %s",
                    (hashlib.sha256(text.encode("utf-8")).hexdigest(), doc_id),
                )
        except Exception as e:
            logger.debug(f"Executor document content_hash backfill skipped: {e}")
        conn.commit()


def _migrate_sqlite():
    """Add columns that may be missing from existing SQLite tables."""
    migrations = [
        "ALTER TABLE executor_jobs ADD COLUMN project_id TEXT",
        "ALTER TABLE executor_jobs ADD COLUMN corpus_ref TEXT",
        "ALTER TABLE phase_outputs ADD COLUMN content_hash TEXT DEFAULT ''",
        "ALTER TABLE executor_documents ADD COLUMN content_hash TEXT DEFAULT ''",
        """CREATE TABLE IF NOT EXISTS external_document_bindings (
               consumer_key TEXT NOT NULL,
               external_project_id TEXT NOT NULL,
               external_doc_key TEXT NOT NULL,
               parent_external_doc_key TEXT,
               doc_id TEXT NOT NULL REFERENCES executor_documents(doc_id),
               binding_role TEXT NOT NULL,
               title TEXT NOT NULL,
               author TEXT,
               source_thinker_id TEXT,
               source_thinker_name TEXT,
               source_document_id TEXT,
               content_hash TEXT NOT NULL DEFAULT '',
               created_at TEXT,
               updated_at TEXT,
               PRIMARY KEY (consumer_key, external_project_id, external_doc_key)
           )""",
        """CREATE TABLE IF NOT EXISTS analysis_corpora (
               corpus_ref TEXT PRIMARY KEY,
               workflow_key TEXT NOT NULL,
               objective_key TEXT,
               member_manifest TEXT NOT NULL DEFAULT '[]',
               qualifiers TEXT NOT NULL DEFAULT '{}',
               created_at TEXT,
               updated_at TEXT
           )""",
        """CREATE TABLE IF NOT EXISTS analysis_artifacts (
               artifact_ref TEXT PRIMARY KEY,
               corpus_ref TEXT NOT NULL REFERENCES analysis_corpora(corpus_ref),
               artifact_family TEXT NOT NULL,
               artifact_slot TEXT NOT NULL DEFAULT 'default',
               format TEXT NOT NULL,
               payload_json TEXT NOT NULL DEFAULT '{}',
               payload_text TEXT DEFAULT '',
               depends_on TEXT NOT NULL DEFAULT '[]',
               job_id TEXT,
               engine_key TEXT DEFAULT '',
               phase_number REAL,
               source_output_id TEXT DEFAULT '',
               payload_hash TEXT NOT NULL DEFAULT '',
               producer_fingerprint TEXT NOT NULL DEFAULT '',
               state TEXT NOT NULL DEFAULT 'ready',
               created_at TEXT,
               updated_at TEXT
           )""",
    ]
    with get_connection() as conn:
        cursor = conn.cursor()
        for sql in migrations:
            try:
                cursor.execute(sql)
            except Exception as e:
                logger.debug(f"SQLite migration skipped (already applied?): {e}")
        try:
            cursor.execute(
                "SELECT id, content FROM phase_outputs "
                "WHERE content_hash IS NULL OR content_hash = ''"
            )
            rows = cursor.fetchall()
            for output_id, content in rows:
                cursor.execute(
                    "UPDATE phase_outputs SET content_hash = ? WHERE id = ?",
                    (hashlib.sha256((content or "").encode()).hexdigest(), output_id),
                )
        except Exception as e:
            logger.debug(f"SQLite phase output content_hash backfill skipped: {e}")
        try:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_executor_jobs_corpus "
                "ON executor_jobs(corpus_ref)"
            )
        except Exception as e:
            logger.debug(f"SQLite corpus index creation skipped: {e}")
        try:
            cursor.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_analysis_artifacts_family_slot "
                "ON analysis_artifacts(corpus_ref, artifact_family, artifact_slot)"
            )
        except Exception as e:
            logger.debug(f"SQLite artifact unique index creation skipped: {e}")
        try:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_analysis_artifacts_job "
                "ON analysis_artifacts(job_id)"
            )
        except Exception as e:
            logger.debug(f"SQLite artifact job index creation skipped: {e}")
        try:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_external_document_bindings_project "
                "ON external_document_bindings(consumer_key, external_project_id)"
            )
        except Exception as e:
            logger.debug(f"SQLite external binding index creation skipped: {e}")
        try:
            cursor.execute(
                "SELECT doc_id, text FROM executor_documents "
                "WHERE content_hash IS NULL OR content_hash = ''"
            )
            rows = cursor.fetchall()
            for doc_id, text in rows:
                cursor.execute(
                    "UPDATE executor_documents SET content_hash = ? WHERE doc_id = ?",
                    (hashlib.sha256((text or "").encode("utf-8")).hexdigest(), doc_id),
                )
        except Exception as e:
            logger.debug(f"SQLite executor document content_hash backfill skipped: {e}")
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
        corpus_ref VARCHAR(100),
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
        content_hash VARCHAR(64) DEFAULT '',
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

    CREATE TABLE IF NOT EXISTS presentation_artifacts (
        id SERIAL PRIMARY KEY,
        job_id VARCHAR(100) NOT NULL,
        view_key VARCHAR(100) NOT NULL,
        artifact_kind VARCHAR(100) NOT NULL,
        artifact_version INTEGER NOT NULL DEFAULT 1,
        prompt_version VARCHAR(100) DEFAULT '',
        input_hash VARCHAR(64) NOT NULL,
        content JSONB NOT NULL,
        model_used VARCHAR(100),
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(job_id, view_key, artifact_kind, artifact_version, prompt_version, input_hash)
    );

    CREATE INDEX IF NOT EXISTS idx_presentation_artifacts_job_kind
        ON presentation_artifacts(job_id, artifact_kind);

    CREATE TABLE IF NOT EXISTS executor_documents (
        doc_id VARCHAR(100) PRIMARY KEY,
        title VARCHAR(500) NOT NULL,
        author VARCHAR(200),
        role VARCHAR(20) NOT NULL DEFAULT 'target',
        text TEXT NOT NULL,
        char_count INTEGER DEFAULT 0,
        content_hash VARCHAR(64) DEFAULT '',
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS external_document_bindings (
        consumer_key VARCHAR(100) NOT NULL,
        external_project_id VARCHAR(120) NOT NULL,
        external_doc_key VARCHAR(200) NOT NULL,
        parent_external_doc_key VARCHAR(200),
        doc_id VARCHAR(100) NOT NULL REFERENCES executor_documents(doc_id),
        binding_role VARCHAR(20) NOT NULL,
        title VARCHAR(500) NOT NULL,
        author VARCHAR(200),
        source_thinker_id VARCHAR(100),
        source_thinker_name VARCHAR(200),
        source_document_id VARCHAR(200),
        content_hash VARCHAR(64) NOT NULL DEFAULT '',
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        PRIMARY KEY (consumer_key, external_project_id, external_doc_key)
    );
    CREATE INDEX IF NOT EXISTS idx_external_document_bindings_project
        ON external_document_bindings(consumer_key, external_project_id);

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

    CREATE TABLE IF NOT EXISTS presentation_runs (
        job_id VARCHAR(100) PRIMARY KEY REFERENCES executor_jobs(job_id),
        status VARCHAR(32) NOT NULL,
        detail TEXT DEFAULT '',
        stats JSONB DEFAULT '{}'::jsonb,
        error TEXT,
        started_at TIMESTAMP,
        updated_at TIMESTAMP,
        completed_at TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS analysis_corpora (
        corpus_ref VARCHAR(100) PRIMARY KEY,
        workflow_key VARCHAR(100) NOT NULL,
        objective_key VARCHAR(100),
        member_manifest JSONB NOT NULL DEFAULT '[]'::jsonb,
        qualifiers JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS analysis_artifacts (
        artifact_ref VARCHAR(100) PRIMARY KEY,
        corpus_ref VARCHAR(100) NOT NULL REFERENCES analysis_corpora(corpus_ref),
        artifact_family VARCHAR(120) NOT NULL,
        artifact_slot VARCHAR(200) NOT NULL DEFAULT 'default',
        format VARCHAR(40) NOT NULL,
        payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        payload_text TEXT DEFAULT '',
        depends_on JSONB NOT NULL DEFAULT '[]'::jsonb,
        job_id VARCHAR(100),
        engine_key VARCHAR(100) DEFAULT '',
        phase_number FLOAT,
        source_output_id VARCHAR(100) DEFAULT '',
        payload_hash VARCHAR(64) NOT NULL DEFAULT '',
        producer_fingerprint VARCHAR(120) NOT NULL DEFAULT '',
        state VARCHAR(20) NOT NULL DEFAULT 'ready',
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );

    CREATE UNIQUE INDEX IF NOT EXISTS idx_analysis_artifacts_family_slot
        ON analysis_artifacts(corpus_ref, artifact_family, artifact_slot);
    CREATE INDEX IF NOT EXISTS idx_analysis_artifacts_job
        ON analysis_artifacts(job_id);

    CREATE TABLE IF NOT EXISTS polish_cache (
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
    );

    CREATE TABLE IF NOT EXISTS design_token_cache (
        school_key VARCHAR(64) PRIMARY KEY,
        school_json_hash VARCHAR(64) NOT NULL,
        token_set JSONB NOT NULL,
        model_used VARCHAR(64),
        tokens_used INTEGER,
        generated_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS projects (
        project_id    VARCHAR(100) PRIMARY KEY,
        name          VARCHAR(500) NOT NULL,
        description   TEXT DEFAULT '',
        status        VARCHAR(20) NOT NULL DEFAULT 'active',
        auto_archive_days INTEGER DEFAULT 30,
        created_at    TIMESTAMPTZ DEFAULT NOW(),
        last_activity_at TIMESTAMPTZ DEFAULT NOW(),
        archived_at   TIMESTAMPTZ,
        metadata      JSONB DEFAULT '{}'
    );

    CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
    CREATE INDEX IF NOT EXISTS idx_projects_activity ON projects(last_activity_at);

    CREATE TABLE IF NOT EXISTS feedback_events (
        id               SERIAL PRIMARY KEY,
        event_id         VARCHAR(64) NOT NULL UNIQUE,
        event_type       VARCHAR(50) NOT NULL,
        job_id           VARCHAR(100) NOT NULL,
        project_id       VARCHAR(100),
        view_key         VARCHAR(100),
        section_key      VARCHAR(200),
        renderer_type    VARCHAR(50),
        style_school     VARCHAR(100),
        payload          JSONB DEFAULT '{}',
        client_timestamp TIMESTAMPTZ,
        created_at       TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_fb_job ON feedback_events(job_id);
    CREATE INDEX IF NOT EXISTS idx_fb_project ON feedback_events(project_id);
    CREATE INDEX IF NOT EXISTS idx_fb_type_created ON feedback_events(event_type, created_at);
    CREATE INDEX IF NOT EXISTS idx_fb_job_view ON feedback_events(job_id, view_key);

    CREATE TABLE IF NOT EXISTS variant_sets (
        variant_set_id  VARCHAR(100) PRIMARY KEY,
        job_id          VARCHAR(100) NOT NULL,
        view_key        VARCHAR(100) NOT NULL,
        dimension       VARCHAR(30) NOT NULL,
        base_renderer   VARCHAR(100) NOT NULL,
        style_school    VARCHAR(100) DEFAULT '',
        variant_count   INTEGER NOT NULL DEFAULT 0,
        created_at      TIMESTAMPTZ DEFAULT NOW(),
        metadata        JSONB DEFAULT '{}'
    );
    CREATE INDEX IF NOT EXISTS idx_vs_job_view ON variant_sets(job_id, view_key);

    CREATE TABLE IF NOT EXISTS variants (
        variant_id          VARCHAR(120) PRIMARY KEY,
        variant_set_id      VARCHAR(100) NOT NULL,
        variant_index       INTEGER NOT NULL,
        is_control          BOOLEAN NOT NULL DEFAULT FALSE,
        renderer_type       VARCHAR(100) NOT NULL,
        renderer_config     JSONB NOT NULL DEFAULT '{}',
        rationale           TEXT DEFAULT '',
        compatibility_score FLOAT DEFAULT 0.0,
        payload_snapshot    JSONB,
        created_at          TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_var_set ON variants(variant_set_id);

    CREATE TABLE IF NOT EXISTS variant_selections (
        id              SERIAL PRIMARY KEY,
        variant_set_id  VARCHAR(100) NOT NULL,
        variant_id      VARCHAR(120) NOT NULL,
        job_id          VARCHAR(100) NOT NULL,
        project_id      VARCHAR(100),
        view_key        VARCHAR(100) NOT NULL,
        selected_at     TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(variant_set_id, job_id)
    );
    CREATE INDEX IF NOT EXISTS idx_vsel_job ON variant_selections(job_id);
    CREATE INDEX IF NOT EXISTS idx_vsel_project ON variant_selections(project_id);
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
        corpus_ref TEXT,
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
        content_hash TEXT DEFAULT '',
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

    CREATE TABLE IF NOT EXISTS presentation_artifacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL,
        view_key TEXT NOT NULL,
        artifact_kind TEXT NOT NULL,
        artifact_version INTEGER NOT NULL DEFAULT 1,
        prompt_version TEXT DEFAULT '',
        input_hash TEXT NOT NULL,
        content TEXT NOT NULL,
        model_used TEXT,
        created_at TEXT,
        UNIQUE(job_id, view_key, artifact_kind, artifact_version, prompt_version, input_hash)
    );

    CREATE INDEX IF NOT EXISTS idx_presentation_artifacts_job_kind
        ON presentation_artifacts(job_id, artifact_kind);

    CREATE TABLE IF NOT EXISTS executor_documents (
        doc_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        author TEXT,
        role TEXT NOT NULL DEFAULT 'target',
        text TEXT NOT NULL,
        char_count INTEGER DEFAULT 0,
        content_hash TEXT DEFAULT '',
        created_at TEXT
    );

    CREATE TABLE IF NOT EXISTS external_document_bindings (
        consumer_key TEXT NOT NULL,
        external_project_id TEXT NOT NULL,
        external_doc_key TEXT NOT NULL,
        parent_external_doc_key TEXT,
        doc_id TEXT NOT NULL REFERENCES executor_documents(doc_id),
        binding_role TEXT NOT NULL,
        title TEXT NOT NULL,
        author TEXT,
        source_thinker_id TEXT,
        source_thinker_name TEXT,
        source_document_id TEXT,
        content_hash TEXT NOT NULL DEFAULT '',
        created_at TEXT,
        updated_at TEXT,
        PRIMARY KEY (consumer_key, external_project_id, external_doc_key)
    );
    CREATE INDEX IF NOT EXISTS idx_external_document_bindings_project
        ON external_document_bindings(consumer_key, external_project_id);

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

    CREATE TABLE IF NOT EXISTS presentation_runs (
        job_id TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        detail TEXT DEFAULT '',
        stats TEXT DEFAULT '{}',
        error TEXT,
        started_at TEXT,
        updated_at TEXT,
        completed_at TEXT
    );

    CREATE TABLE IF NOT EXISTS analysis_corpora (
        corpus_ref TEXT PRIMARY KEY,
        workflow_key TEXT NOT NULL,
        objective_key TEXT,
        member_manifest TEXT NOT NULL DEFAULT '[]',
        qualifiers TEXT NOT NULL DEFAULT '{}',
        created_at TEXT,
        updated_at TEXT
    );

    CREATE TABLE IF NOT EXISTS analysis_artifacts (
        artifact_ref TEXT PRIMARY KEY,
        corpus_ref TEXT NOT NULL REFERENCES analysis_corpora(corpus_ref),
        artifact_family TEXT NOT NULL,
        artifact_slot TEXT NOT NULL DEFAULT 'default',
        format TEXT NOT NULL,
        payload_json TEXT NOT NULL DEFAULT '{}',
        payload_text TEXT DEFAULT '',
        depends_on TEXT NOT NULL DEFAULT '[]',
        job_id TEXT,
        engine_key TEXT DEFAULT '',
        phase_number REAL,
        source_output_id TEXT DEFAULT '',
        payload_hash TEXT NOT NULL DEFAULT '',
        producer_fingerprint TEXT NOT NULL DEFAULT '',
        state TEXT NOT NULL DEFAULT 'ready',
        created_at TEXT,
        updated_at TEXT
    );

    CREATE UNIQUE INDEX IF NOT EXISTS idx_analysis_artifacts_family_slot
        ON analysis_artifacts(corpus_ref, artifact_family, artifact_slot);
    CREATE INDEX IF NOT EXISTS idx_analysis_artifacts_job
        ON analysis_artifacts(job_id);

    CREATE TABLE IF NOT EXISTS polish_cache (
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
    );

    CREATE TABLE IF NOT EXISTS design_token_cache (
        school_key TEXT PRIMARY KEY,
        school_json_hash TEXT NOT NULL,
        token_set TEXT NOT NULL,
        model_used TEXT,
        tokens_used INTEGER,
        generated_at TEXT
    );

    CREATE TABLE IF NOT EXISTS projects (
        project_id    TEXT PRIMARY KEY,
        name          TEXT NOT NULL,
        description   TEXT DEFAULT '',
        status        TEXT NOT NULL DEFAULT 'active',
        auto_archive_days INTEGER DEFAULT 30,
        created_at    TEXT,
        last_activity_at TEXT,
        archived_at   TEXT,
        metadata      TEXT DEFAULT '{}'
    );

    CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
    CREATE INDEX IF NOT EXISTS idx_projects_activity ON projects(last_activity_at);

    CREATE TABLE IF NOT EXISTS feedback_events (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id         TEXT NOT NULL UNIQUE,
        event_type       TEXT NOT NULL,
        job_id           TEXT NOT NULL,
        project_id       TEXT,
        view_key         TEXT,
        section_key      TEXT,
        renderer_type    TEXT,
        style_school     TEXT,
        payload          TEXT DEFAULT '{}',
        client_timestamp TEXT,
        created_at       TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_fb_job ON feedback_events(job_id);
    CREATE INDEX IF NOT EXISTS idx_fb_project ON feedback_events(project_id);
    CREATE INDEX IF NOT EXISTS idx_fb_type_created ON feedback_events(event_type, created_at);
    CREATE INDEX IF NOT EXISTS idx_fb_job_view ON feedback_events(job_id, view_key);

    CREATE TABLE IF NOT EXISTS variant_sets (
        variant_set_id  TEXT PRIMARY KEY,
        job_id          TEXT NOT NULL,
        view_key        TEXT NOT NULL,
        dimension       TEXT NOT NULL,
        base_renderer   TEXT NOT NULL,
        style_school    TEXT DEFAULT '',
        variant_count   INTEGER NOT NULL DEFAULT 0,
        created_at      TEXT,
        metadata        TEXT DEFAULT '{}'
    );
    CREATE INDEX IF NOT EXISTS idx_vs_job_view ON variant_sets(job_id, view_key);

    CREATE TABLE IF NOT EXISTS variants (
        variant_id          TEXT PRIMARY KEY,
        variant_set_id      TEXT NOT NULL,
        variant_index       INTEGER NOT NULL,
        is_control          INTEGER NOT NULL DEFAULT 0,
        renderer_type       TEXT NOT NULL,
        renderer_config     TEXT NOT NULL DEFAULT '{}',
        rationale           TEXT DEFAULT '',
        compatibility_score REAL DEFAULT 0.0,
        payload_snapshot    TEXT,
        created_at          TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_var_set ON variants(variant_set_id);

    CREATE TABLE IF NOT EXISTS variant_selections (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        variant_set_id  TEXT NOT NULL,
        variant_id      TEXT NOT NULL,
        job_id          TEXT NOT NULL,
        project_id      TEXT,
        view_key        TEXT NOT NULL,
        selected_at     TEXT,
        UNIQUE(variant_set_id, job_id)
    );
    CREATE INDEX IF NOT EXISTS idx_vsel_job ON variant_selections(job_id);
    CREATE INDEX IF NOT EXISTS idx_vsel_project ON variant_selections(project_id);
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.executescript(ddl)
        conn.commit()
        # SQLite migration: add project_id column if missing
        cursor.execute("PRAGMA table_info(executor_jobs)")
        columns = [row[1] for row in cursor.fetchall()]
        if "project_id" not in columns:
            cursor.execute("ALTER TABLE executor_jobs ADD COLUMN project_id TEXT")
            conn.commit()
            logger.info("SQLite migration: added project_id column to executor_jobs")
