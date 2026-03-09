"""Tests for Tier 3b variant store (persistence layer)."""

import os
import pytest
from unittest.mock import patch

from src.presenter.variant_store import (
    delete_for_job,
    delete_variant_set,
    list_variant_sets,
    load_selections,
    load_variant_set,
    save_selection,
    save_variant,
    save_variant_set,
    summarize_selections,
)


@pytest.fixture(autouse=True)
def use_sqlite_db(tmp_path):
    """Set up a temporary SQLite database for each test."""
    db_path = tmp_path / "test.db"
    import src.executor.db as db_mod
    original_db_path = db_mod.SQLITE_PATH
    original_db_url = db_mod.DATABASE_URL
    original_initialized = db_mod._initialized

    db_mod.SQLITE_PATH = db_path
    db_mod.DATABASE_URL = ""  # Force SQLite
    db_mod._initialized = False

    db_mod.init_db()
    yield

    db_mod.SQLITE_PATH = original_db_path
    db_mod.DATABASE_URL = original_db_url
    db_mod._initialized = original_initialized


class TestSaveAndLoadVariantSet:
    def test_save_and_load_roundtrip(self):
        save_variant_set(
            variant_set_id="vs-test-001",
            job_id="job-1",
            view_key="tactics",
            dimension="renderer_type",
            base_renderer="accordion",
            variant_count=2,
            metadata={"reason": "test"},
        )
        save_variant(
            variant_id="vs-test-001-v0",
            variant_set_id="vs-test-001",
            variant_index=0,
            is_control=True,
            renderer_type="accordion",
            renderer_config={"key": "value"},
            rationale="Control",
            compatibility_score=1.0,
        )
        save_variant(
            variant_id="vs-test-001-v1",
            variant_set_id="vs-test-001",
            variant_index=1,
            is_control=False,
            renderer_type="card_grid",
            rationale="Alternative",
            compatibility_score=0.8,
        )

        result = load_variant_set("vs-test-001")
        assert result is not None
        assert result["variant_set_id"] == "vs-test-001"
        assert result["job_id"] == "job-1"
        assert result["dimension"] == "renderer_type"
        assert result["variant_count"] == 2
        assert result["metadata"] == {"reason": "test"}
        assert len(result["variants"]) == 2

        control = result["variants"][0]
        assert control["is_control"] is True
        assert control["renderer_type"] == "accordion"
        assert control["renderer_config"] == {"key": "value"}

        alt = result["variants"][1]
        assert alt["is_control"] is False
        assert alt["renderer_type"] == "card_grid"

    def test_load_nonexistent(self):
        assert load_variant_set("vs-nonexistent") is None


class TestListVariantSets:
    def test_list_by_job_and_view(self):
        save_variant_set("vs-a", "job-1", "view_a", "renderer_type", "accordion", variant_count=1)
        save_variant_set("vs-b", "job-1", "view_a", "sub_renderer_strategy", "accordion", variant_count=1)
        save_variant_set("vs-c", "job-1", "view_b", "renderer_type", "accordion", variant_count=1)

        sets = list_variant_sets("job-1", "view_a")
        assert len(sets) == 2
        set_ids = {s["variant_set_id"] for s in sets}
        assert set_ids == {"vs-a", "vs-b"}


class TestDeleteVariantSet:
    def test_delete_cascades(self):
        save_variant_set("vs-del", "job-1", "view_a", "renderer_type", "accordion", variant_count=1)
        save_variant("vs-del-v0", "vs-del", 0, True, "accordion")
        save_selection("vs-del", "vs-del-v0", "job-1", "view_a")

        deleted = delete_variant_set("vs-del")
        assert deleted == 3  # 1 selection + 1 variant + 1 set

        assert load_variant_set("vs-del") is None


class TestSelections:
    def test_save_and_load_selection(self):
        save_variant_set("vs-sel", "job-1", "view_a", "renderer_type", "accordion", variant_count=2)

        ts = save_selection("vs-sel", "vs-sel-v1", "job-1", "view_a", project_id="proj-1")
        assert ts  # Returns timestamp

        selections = load_selections("job-1", "view_a")
        assert len(selections) == 1
        assert selections[0]["selected_variant_id"] == "vs-sel-v1"

    def test_upsert_replaces_selection(self):
        save_variant_set("vs-up", "job-1", "view_a", "renderer_type", "accordion", variant_count=2)

        save_selection("vs-up", "vs-up-v0", "job-1", "view_a")
        save_selection("vs-up", "vs-up-v1", "job-1", "view_a")  # Change mind

        selections = load_selections("job-1", "view_a")
        assert len(selections) == 1
        assert selections[0]["selected_variant_id"] == "vs-up-v1"

    def test_empty_selections(self):
        selections = load_selections("job-nonexistent", "view_a")
        assert selections == []


class TestSummarizeSelections:
    def test_summary_grouped(self):
        save_variant_set("vs-s1", "job-1", "view_a", "renderer_type", "accordion", variant_count=2)
        save_variant("vs-s1-v0", "vs-s1", 0, True, "accordion")
        save_variant("vs-s1-v1", "vs-s1", 1, False, "card_grid")
        save_selection("vs-s1", "vs-s1-v1", "job-1", "view_a", project_id="proj-1")

        summary = summarize_selections("proj-1")
        assert len(summary) == 1
        assert summary[0]["selected_renderer"] == "card_grid"
        assert summary[0]["selection_count"] == 1


class TestDeleteForJob:
    def test_deletes_all_variant_data(self):
        save_variant_set("vs-j1", "job-del", "view_a", "renderer_type", "accordion", variant_count=2)
        save_variant("vs-j1-v0", "vs-j1", 0, True, "accordion")
        save_variant("vs-j1-v1", "vs-j1", 1, False, "card_grid")
        save_selection("vs-j1", "vs-j1-v0", "job-del", "view_a")

        counts = delete_for_job("job-del")
        assert "variant_selections" in counts
        assert "variants" in counts
        assert "variant_sets" in counts

        assert load_variant_set("vs-j1") is None

    def test_delete_nonexistent_job(self):
        counts = delete_for_job("job-nonexistent")
        assert counts == {}
