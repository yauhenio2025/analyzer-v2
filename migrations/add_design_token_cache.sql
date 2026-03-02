-- Design Token Cache table
-- Stores LLM-generated design token sets per style school,
-- keyed by school_key with hash-based cache invalidation.
--
-- Run manually against Postgres:
--   psql $DATABASE_URL -f migrations/add_design_token_cache.sql
--
-- Also auto-created by init_db() on startup.

CREATE TABLE IF NOT EXISTS design_token_cache (
    school_key VARCHAR(64) PRIMARY KEY,
    school_json_hash VARCHAR(64) NOT NULL,
    token_set JSONB NOT NULL,
    model_used VARCHAR(64),
    tokens_used INTEGER,
    generated_at TIMESTAMPTZ DEFAULT NOW()
);
