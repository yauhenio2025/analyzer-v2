"""Tests for Priority 6: Ephemeral Project Lifecycle.

Tests project CRUD, lifecycle transitions (archive/revive/delete),
cleanup cascades, guards, and auto-archive logic.

Uses direct function calls (not TestClient) to avoid the SIGTERM
handler limitation in lifespan (signal only works in main thread).
"""

import os
import tempfile
from pathlib import Path

import pytest

# Force SQLite for tests — use a temp directory to avoid conflicts
_test_db_dir = tempfile.mkdtemp(prefix="analyzer_v2_test_")
_test_db_path = Path(_test_db_dir) / "test_executor.db"
os.environ["EXECUTOR_DATABASE_URL"] = ""

import src.executor.db as db_mod

# Override the SQLite path BEFORE any imports that call init_db()
db_mod.SQLITE_PATH = _test_db_path

from src.executor.db import init_db, execute, execute_write, execute_transaction, _json_dumps
from src.executor.job_manager import create_job, update_job_status
from src.executor.project_manager import (
    archive_project,
    create_project,
    delete_project,
    get_project,
    list_projects,
    revive_project,
    run_auto_archive,
    touch_project_activity,
    touch_project_activity_for_job,
    update_project,
)


# Tables to truncate between tests (order: children before parents)
_TABLES = [
    "presentation_cache",
    "polish_cache",
    "view_refinements",
    "phase_outputs",
    "executor_jobs",
    "projects",
    "design_token_cache",
]


@pytest.fixture(autouse=True)
def fresh_db():
    """Ensure tables exist, then truncate all data between tests.

    Instead of deleting/recreating the SQLite file (which causes I/O errors
    if connections are still open), we init once and truncate between tests.
    """
    if not db_mod._initialized:
        init_db()
    else:
        # Truncate all tables — fast, no file I/O issues
        for table in _TABLES:
            try:
                execute(f"DELETE FROM {table}")
            except Exception:
                pass  # Table might not exist yet in some edge cases
    yield


# --- CRUD ---


class TestProjectCRUD:
    def test_create_project(self):
        project = create_project(name="Test Project", description="A test")
        assert project["project_id"].startswith("proj-")
        assert project["name"] == "Test Project"
        assert project["description"] == "A test"
        assert project["status"] == "active"
        assert project["auto_archive_days"] == 30
        assert project["job_count"] == 0

    def test_create_project_no_auto_archive(self):
        project = create_project(name="Permanent", auto_archive_days=None)
        assert project["auto_archive_days"] is None

    def test_get_project(self):
        created = create_project(name="Get Test")
        fetched = get_project(created["project_id"])
        assert fetched is not None
        assert fetched["name"] == "Get Test"
        assert fetched["job_count"] == 0
        assert fetched["active_job_count"] == 0

    def test_get_project_not_found(self):
        assert get_project("proj-nonexistent") is None

    def test_list_projects(self):
        create_project(name="P1")
        create_project(name="P2")
        projects = list_projects()
        assert len(projects) == 2

    def test_list_projects_filter_status(self):
        p1 = create_project(name="Active")
        p2 = create_project(name="To Archive")
        archive_project(p2["project_id"])

        active = list_projects(status="active")
        archived = list_projects(status="archived")
        assert len(active) == 1
        assert active[0]["name"] == "Active"
        assert len(archived) == 1
        assert archived[0]["name"] == "To Archive"

    def test_update_project(self):
        project = create_project(name="Old Name")
        updated = update_project(project["project_id"], name="New Name")
        assert updated["name"] == "New Name"

    def test_update_project_not_found(self):
        assert update_project("proj-nonexistent", name="X") is None

    def test_list_projects_with_job_counts(self):
        project = create_project(name="With Jobs")
        pid = project["project_id"]
        create_job("job-1", "plan-1", project_id=pid)
        create_job("job-2", "plan-2", project_id=pid)
        update_job_status("job-1", "completed")

        fetched = get_project(pid)
        assert fetched["job_count"] == 2
        assert fetched["active_job_count"] == 1  # job-2 is still pending


# --- Lifecycle ---


class TestArchive:
    def test_archive_project(self):
        project = create_project(name="Archive Me")
        result = archive_project(project["project_id"])
        assert result["action"] == "archived"
        fetched = get_project(project["project_id"])
        assert fetched["status"] == "archived"
        assert fetched["archived_at"] is not None

    def test_archive_idempotent(self):
        project = create_project(name="Archive Twice")
        archive_project(project["project_id"])
        result = archive_project(project["project_id"])
        assert result["action"] == "already_archived"

    def test_archive_rejects_active_jobs(self):
        project = create_project(name="Busy Project")
        create_job("job-active", "plan-1", project_id=project["project_id"])
        # job-active is in pending status (active)
        with pytest.raises(RuntimeError, match="running/pending jobs"):
            archive_project(project["project_id"])

    def test_archive_allows_completed_jobs(self):
        project = create_project(name="Done Project")
        create_job("job-done", "plan-1", project_id=project["project_id"])
        update_job_status("job-done", "completed")
        result = archive_project(project["project_id"])
        assert result["action"] == "archived"

    def test_archive_cleans_presentation_artifacts(self):
        project = create_project(name="Artifact Project")
        pid = project["project_id"]
        create_job("job-art", "plan-1", project_id=pid)
        update_job_status("job-art", "completed")

        # Insert some presentation artifacts
        execute(
            "INSERT INTO polish_cache (job_id, view_key, polished_data) VALUES (%s, %s, %s)",
            ("job-art", "view-1", "{}"),
        )
        execute(
            "INSERT INTO view_refinements (job_id, plan_id, refined_views) VALUES (%s, %s, %s)",
            ("job-art", "plan-1", "[]"),
        )

        result = archive_project(pid)
        assert result["action"] == "archived"
        assert result["artifacts_removed"].get("polish_cache", 0) == 1
        assert result["artifacts_removed"].get("view_refinements", 0) == 1

    def test_archive_retains_engine_outputs(self):
        project = create_project(name="Retain Outputs")
        pid = project["project_id"]
        create_job("job-retain", "plan-1", project_id=pid)
        update_job_status("job-retain", "completed")

        # Insert phase output (engine data)
        execute(
            """INSERT INTO phase_outputs (id, job_id, phase_number, engine_key, content)
               VALUES (%s, %s, %s, %s, %s)""",
            ("out-1", "job-retain", 1.0, "concept_evolution", "Engine prose..."),
        )

        archive_project(pid)

        # Verify engine output is retained
        row = execute(
            "SELECT * FROM phase_outputs WHERE id = %s", ("out-1",), fetch="one"
        )
        assert row is not None
        assert row["content"] == "Engine prose..."

    def test_archive_not_found(self):
        with pytest.raises(ValueError, match="not found"):
            archive_project("proj-nonexistent")


class TestRevive:
    def test_revive_project(self):
        project = create_project(name="Revive Me")
        archive_project(project["project_id"])
        result = revive_project(project["project_id"])
        assert result["action"] == "revived"

        fetched = get_project(project["project_id"])
        assert fetched["status"] == "active"
        assert fetched["archived_at"] is None

    def test_revive_idempotent(self):
        project = create_project(name="Already Active")
        result = revive_project(project["project_id"])
        assert result["action"] == "already_active"

    def test_revive_not_found(self):
        with pytest.raises(ValueError, match="not found"):
            revive_project("proj-nonexistent")


class TestDelete:
    def test_delete_project(self):
        project = create_project(name="Delete Me")
        result = delete_project(project["project_id"])
        assert result["action"] == "deleted"
        assert get_project(project["project_id"]) is None

    def test_delete_cascades_all_data(self):
        project = create_project(name="Cascade Delete")
        pid = project["project_id"]
        create_job("job-del", "plan-1", project_id=pid)
        update_job_status("job-del", "completed")

        # Insert data at every level
        execute(
            """INSERT INTO phase_outputs (id, job_id, phase_number, engine_key, content)
               VALUES (%s, %s, %s, %s, %s)""",
            ("out-del", "job-del", 1.0, "test_engine", "Output"),
        )
        execute(
            "INSERT INTO polish_cache (job_id, view_key, polished_data) VALUES (%s, %s, %s)",
            ("job-del", "v1", "{}"),
        )
        execute(
            "INSERT INTO view_refinements (job_id, plan_id, refined_views) VALUES (%s, %s, %s)",
            ("job-del", "plan-1", "[]"),
        )

        result = delete_project(pid)
        assert result["action"] == "deleted"
        assert result["artifacts_removed"]["executor_jobs"] == 1
        assert result["artifacts_removed"]["phase_outputs"] == 1
        assert result["artifacts_removed"]["polish_cache"] == 1

        # Verify everything is gone
        assert get_project(pid) is None
        assert execute("SELECT COUNT(*) as c FROM executor_jobs WHERE project_id = %s", (pid,), fetch="one")["c"] == 0
        assert execute("SELECT COUNT(*) as c FROM phase_outputs WHERE job_id = %s", ("job-del",), fetch="one")["c"] == 0

    def test_delete_rejects_active_jobs(self):
        project = create_project(name="Busy Delete")
        create_job("job-busy", "plan-1", project_id=project["project_id"])
        with pytest.raises(RuntimeError, match="running/pending jobs"):
            delete_project(project["project_id"])

    def test_delete_not_found(self):
        with pytest.raises(ValueError, match="not found"):
            delete_project("proj-nonexistent")


# --- Job integration ---


class TestJobIntegration:
    def test_create_job_with_project_id(self):
        project = create_project(name="Job Test")
        job = create_job("job-proj", "plan-1", project_id=project["project_id"])
        assert job["project_id"] == project["project_id"]

    def test_create_job_without_project_id(self):
        job = create_job("job-noproj", "plan-1")
        assert job.get("project_id") is None

    def test_create_job_touches_activity(self):
        project = create_project(name="Activity Test")
        pid = project["project_id"]
        original_activity = project["last_activity_at"]

        import time
        time.sleep(0.01)  # Ensure timestamp difference
        create_job("job-touch", "plan-1", project_id=pid)

        fetched = get_project(pid)
        assert fetched["last_activity_at"] >= original_activity

    def test_touch_project_activity_for_job(self):
        project = create_project(name="Touch Test")
        pid = project["project_id"]
        create_job("job-touch2", "plan-1", project_id=pid)

        import time
        time.sleep(0.01)
        touch_project_activity_for_job("job-touch2")

        fetched = get_project(pid)
        assert fetched["last_activity_at"] > project["last_activity_at"]

    def test_touch_for_job_without_project(self):
        """Touching activity for a job without project_id is a no-op."""
        create_job("job-noproj2", "plan-1")
        # Should not raise
        touch_project_activity_for_job("job-noproj2")


# --- Auto-archive ---


class TestAutoArchive:
    def test_auto_archive_stale_project(self):
        project = create_project(name="Stale Project", auto_archive_days=0)
        # Set last_activity to the past
        execute(
            "UPDATE projects SET last_activity_at = %s WHERE project_id = %s",
            ("2020-01-01T00:00:00", project["project_id"]),
        )

        result = run_auto_archive()
        assert result["archived"] == 1

        fetched = get_project(project["project_id"])
        assert fetched["status"] == "archived"

    def test_auto_archive_skips_recent(self):
        create_project(name="Recent Project", auto_archive_days=30)
        result = run_auto_archive()
        assert result["archived"] == 0

    def test_auto_archive_skips_exempt(self):
        create_project(name="Exempt Project", auto_archive_days=None)
        # Even if activity is old, NULL auto_archive_days means exempt
        result = run_auto_archive()
        assert result["skipped_exempt"] == 0  # Not even checked (filtered by SQL)
        assert result["archived"] == 0

    def test_auto_archive_skips_active_jobs(self):
        project = create_project(name="Busy Stale", auto_archive_days=0)
        create_job("job-busy-stale", "plan-1", project_id=project["project_id"])
        execute(
            "UPDATE projects SET last_activity_at = %s WHERE project_id = %s",
            ("2020-01-01T00:00:00", project["project_id"]),
        )

        result = run_auto_archive()
        assert result["skipped_active_jobs"] == 1
        assert result["archived"] == 0


# --- DB primitives ---


class TestDBPrimitives:
    def test_execute_write_returns_rowcount(self):
        project = create_project(name="Write Test")
        count = execute_write(
            "UPDATE projects SET name = %s WHERE project_id = %s",
            ("Updated", project["project_id"]),
        )
        assert count == 1

    def test_execute_write_zero_rows(self):
        count = execute_write(
            "UPDATE projects SET name = %s WHERE project_id = %s",
            ("X", "proj-nonexistent"),
        )
        assert count == 0

    def test_execute_transaction_atomic(self):
        create_project(name="TX Test 1")
        create_project(name="TX Test 2")
        rowcounts = execute_transaction([
            ("UPDATE projects SET description = %s WHERE name = %s", ("updated", "TX Test 1")),
            ("UPDATE projects SET description = %s WHERE name = %s", ("updated", "TX Test 2")),
        ])
        assert rowcounts == [1, 1]

    def test_execute_transaction_rollback(self):
        project = create_project(name="Rollback Test")
        pid = project["project_id"]

        with pytest.raises(Exception):
            execute_transaction([
                ("UPDATE projects SET name = %s WHERE project_id = %s", ("Should Rollback", pid)),
                ("INVALID SQL STATEMENT", ()),  # This will fail
            ])

        # Original name should be preserved (rollback)
        fetched = get_project(pid)
        assert fetched["name"] == "Rollback Test"
