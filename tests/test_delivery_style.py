from types import SimpleNamespace

import pytest

from src.presenter.delivery_style import apply_cached_polish_to_views
from src.presenter.polish_store import (
    _normalize_polished_data_for_storage,
    load_polish_cache,
    save_polish_cache,
)
from src.presenter.schemas import ViewPayload


@pytest.fixture(autouse=True)
def use_sqlite_db(tmp_path):
    """Set up a temporary SQLite database for each test."""
    db_path = tmp_path / "test.db"
    import src.executor.db as db_mod
    import src.presenter.polish_store as store_mod

    original_db_path = db_mod.SQLITE_PATH
    original_db_url = db_mod.DATABASE_URL
    original_initialized = db_mod._initialized
    original_migration_done = store_mod._migration_done

    db_mod.SQLITE_PATH = db_path
    db_mod.DATABASE_URL = ""
    db_mod._initialized = False
    store_mod._migration_done = False

    db_mod.init_db()
    yield

    db_mod.SQLITE_PATH = original_db_path
    db_mod.DATABASE_URL = original_db_url
    db_mod._initialized = original_initialized
    store_mod._migration_done = original_migration_done


def _payload() -> ViewPayload:
    return ViewPayload(
        view_key="aoi_by_theme",
        view_name="By Theme",
        description="",
        renderer_type="accordion",
        renderer_config={"expand_first": True},
        presentation_stance="comparison",
        priority="primary",
        rationale="",
        data_quality="rich",
        top_level_group=None,
        source_parent_view_key=None,
        promoted_to_top_level=False,
        selection_priority="primary",
        navigation_state="normal",
        semantic_scaffold_type=None,
        scaffold_hosting_mode=None,
        phase_number=3.0,
        engine_key="aoi_sin_findings",
        chain_key=None,
        scope="aggregated",
        has_structured_data=True,
        structured_data={"theme_one": {"overview": "Theme overview"}},
        reading_scaffold=None,
        raw_prose=None,
        prose_ref_view_key=None,
        items=None,
        tab_count=None,
        visibility="if_data_exists",
        position=1.2,
        children=[],
    )


def test_polish_cache_is_consumer_scoped_and_config_hash_aware():
    save_polish_cache(
        job_id="job-aoi",
        view_key="aoi_by_theme",
        consumer_key="aoi-canary",
        style_school="explanatory_narrative",
        polished_data={"polished_renderer_config": {"expand_first": False}},
        config_hash="cfg-a",
    )

    assert load_polish_cache(
        job_id="job-aoi",
        view_key="aoi_by_theme",
        consumer_key="aoi-canary",
        style_school="explanatory_narrative",
        expected_config_hash="cfg-a",
    ) is not None
    assert load_polish_cache(
        job_id="job-aoi",
        view_key="aoi_by_theme",
        consumer_key="the-critic",
        style_school="explanatory_narrative",
        expected_config_hash="cfg-a",
    ) is None
    assert load_polish_cache(
        job_id="job-aoi",
        view_key="aoi_by_theme",
        consumer_key="aoi-canary",
        style_school="explanatory_narrative",
        expected_config_hash="cfg-b",
    ) is None


def test_apply_cached_polish_to_views_merges_delivery_config_only():
    payload = _payload()
    save_polish_cache(
        job_id="job-aoi",
        view_key=payload.view_key,
        consumer_key="aoi-canary",
        style_school="explanatory_narrative",
        polished_data={
            "polished_renderer_config": {"expand_first": False},
            "style_overrides": {"accent_color": "#9f1239"},
            "section_descriptions": {"theme_one": "Polished section description"},
        },
        config_hash="cfg-a",
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("src.presenter.delivery_style.compute_config_hash", lambda config: "cfg-a")
        styled, polish_state = apply_cached_polish_to_views(
            job_id="job-aoi",
            consumer_key="aoi-canary",
            style_school="explanatory_narrative",
            views=[payload],
        )

    assert polish_state == "polished"
    assert payload.renderer_config == {"expand_first": True}
    assert styled[0].renderer_config["expand_first"] is False
    assert styled[0].renderer_config["_style_overrides"] == {"accent_color": "#9f1239"}
    assert styled[0].renderer_config["_section_descriptions"] == {
        "theme_one": "Polished section description"
    }


def test_normalize_polished_data_for_storage_handles_postgres_jsonb_objects():
    payload = {"polished_renderer_config": {"expand_first": False}}

    normalized = _normalize_polished_data_for_storage(payload)

    assert isinstance(normalized, str)
    assert '"expand_first":false' in normalized.replace(" ", "")
    assert _normalize_polished_data_for_storage(normalized) == normalized
