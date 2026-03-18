import threading
from types import SimpleNamespace
from unittest.mock import patch

from src.presenter.preparation_coordinator import (
    run_presentation_pipeline_sync,
    start_background_preparation,
    wait_for_preparation,
)


def test_start_background_preparation_dedupes_active_job():
    states = {}
    worker_started = threading.Event()
    release_worker = threading.Event()

    def _load(job_id):
        return states.get(job_id)

    def _save(job_id, status, detail="", stats=None, error=None):
        states[job_id] = {
            "job_id": job_id,
            "status": status,
            "detail": detail,
            "stats": stats or {},
            "error": error,
            "started_at": "2026-03-10T00:00:00",
            "updated_at": "2026-03-10T00:00:00",
            "completed_at": "2026-03-10T00:00:00" if status in {"completed", "failed"} else None,
        }
        return states[job_id]

    def _refine_views(*, job_id, plan_id, consumer_key):
        worker_started.set()
        release_worker.wait(timeout=2)
        return SimpleNamespace(refined_views=[{"view_key": "genealogy_target_profile"}], tokens_used=42)

    def _prepare(job_id, *, consumer_key, force=False):
        return SimpleNamespace(
            tasks_planned=3,
            tasks_completed=3,
            tasks_failed=0,
            tasks_skipped=1,
            cached_results=2,
            dynamic_extractions=0,
        )

    def _scaffold(job_id, *, consumer_key, force=False):
        return SimpleNamespace(
            artifacts_planned=2,
            artifacts_generated=1,
            artifacts_cached=1,
            artifacts_failed=0,
        )

    with patch("src.presenter.preparation_coordinator.load_presentation_run", side_effect=_load), patch(
        "src.presenter.preparation_coordinator.save_presentation_run",
        side_effect=_save,
    ), patch(
        "src.presenter.view_refiner.refine_views",
        side_effect=_refine_views,
    ), patch(
        "src.presenter.presentation_bridge.prepare_presentation",
        side_effect=_prepare,
    ), patch(
        "src.presenter.presentation_api.materialize_stage1_artifacts",
    ), patch(
        "src.presenter.scaffold_generator.generate_reading_scaffolds",
        side_effect=_scaffold,
    ), patch(
        "src.presenter.delivery_style.seed_polish_cache_for_page",
        return_value={"activated": False, "style_school": "", "polished": 0, "cached": 0, "failed": 0},
    ):
        first = start_background_preparation("job-1", "plan-1", consumer_key="the-critic")
        assert worker_started.wait(timeout=1)

        second = start_background_preparation("job-1", "plan-1", consumer_key="the-critic")

        assert first["status"] == "running"
        assert second["status"] == "running"
        assert second["active"] is True

        release_worker.set()
        final = wait_for_preparation("job-1", timeout_s=2)

    assert final["status"] == "completed"
    assert final["stats"]["tasks_completed"] == 3
    assert final["stats"]["scaffolds_generated"] == 1
    assert final["stats"]["polish_activation"] is False
    assert final["active"] is False


def test_run_presentation_pipeline_sync_uses_deterministic_refinement_when_skipping_llm_refiner():
    states = {}

    def _load(job_id):
        return states.get(job_id)

    def _save(job_id, status, detail="", stats=None, error=None):
        states[job_id] = {
            "job_id": job_id,
            "status": status,
            "detail": detail,
            "stats": stats or {},
            "error": error,
            "started_at": "2026-03-10T00:00:00",
            "updated_at": "2026-03-10T00:00:00",
            "completed_at": "2026-03-10T00:00:00" if status in {"completed", "failed"} else None,
        }
        return states[job_id]

    with patch("src.presenter.preparation_coordinator.load_presentation_run", side_effect=_load), patch(
        "src.presenter.preparation_coordinator.save_presentation_run",
        side_effect=_save,
    ), patch(
        "src.presenter.view_refiner.deterministic_refine_views",
        return_value=SimpleNamespace(refined_views=[{"view_key": "genealogy_target_profile"}], tokens_used=0),
    ) as deterministic_refiner, patch(
        "src.presenter.presentation_bridge.prepare_presentation",
        return_value=SimpleNamespace(
            tasks_planned=2,
            tasks_completed=2,
            tasks_failed=0,
            tasks_skipped=0,
            cached_results=2,
            dynamic_extractions=0,
        ),
    ), patch(
        "src.presenter.presentation_api.materialize_stage1_artifacts",
    ) as materialize_stage1_artifacts, patch(
        "src.presenter.scaffold_generator.generate_reading_scaffolds",
        return_value=SimpleNamespace(
            artifacts_planned=1,
            artifacts_generated=1,
            artifacts_cached=0,
            artifacts_failed=0,
        ),
    ), patch(
        "src.presenter.delivery_style.seed_polish_cache_for_page",
        return_value={"activated": True, "style_school": "explanatory_narrative", "polished": 2, "cached": 1, "failed": 0},
    ):
        final = run_presentation_pipeline_sync(
            "job-1",
            "plan-1",
            consumer_key="the-critic",
            skip_refinement=True,
            wait_if_active=True,
        )

    deterministic_refiner.assert_called_once_with(
        job_id="job-1",
        plan_id="plan-1",
        consumer_key="the-critic",
    )
    materialize_stage1_artifacts.assert_called_once_with("job-1")
    assert final["status"] == "completed"
    assert final["stats"]["tasks_completed"] == 2
    assert final["stats"]["scaffolds_generated"] == 1
    assert final["stats"]["polish_style_school"] == "explanatory_narrative"
    assert final["stats"]["polish_seeded"] == 2
    assert final["stats"]["stage1_artifacts_failed"] is False


def test_run_presentation_pipeline_sync_does_not_short_circuit_when_clear_refinement_is_requested():
    states = {
        "job-1": {
            "job_id": "job-1",
            "status": "completed",
            "detail": "Presentation ready",
            "stats": {},
            "error": None,
            "started_at": "2026-03-10T00:00:00",
            "updated_at": "2026-03-10T00:00:00",
            "completed_at": "2026-03-10T00:00:00",
        }
    }

    def _load(job_id):
        return states.get(job_id)

    def _save(job_id, status, detail="", stats=None, error=None):
        states[job_id] = {
            "job_id": job_id,
            "status": status,
            "detail": detail,
            "stats": stats or {},
            "error": error,
            "started_at": "2026-03-10T00:00:00",
            "updated_at": "2026-03-10T00:00:00",
            "completed_at": "2026-03-10T00:00:00" if status in {"completed", "failed"} else None,
        }
        return states[job_id]

    with patch("src.presenter.preparation_coordinator.load_presentation_run", side_effect=_load), patch(
        "src.presenter.preparation_coordinator.save_presentation_run",
        side_effect=_save,
    ), patch(
        "src.presenter.store.delete_view_refinement",
    ) as delete_refinement, patch(
        "src.presenter.view_refiner.deterministic_refine_views",
        return_value=SimpleNamespace(refined_views=[{"view_key": "genealogy_target_profile"}], tokens_used=0),
    ) as deterministic_refiner, patch(
        "src.presenter.presentation_bridge.prepare_presentation",
        return_value=SimpleNamespace(
            tasks_planned=1,
            tasks_completed=1,
            tasks_failed=0,
            tasks_skipped=0,
            cached_results=1,
            dynamic_extractions=0,
        ),
    ), patch(
        "src.presenter.presentation_api.materialize_stage1_artifacts",
    ), patch(
        "src.presenter.scaffold_generator.generate_reading_scaffolds",
        return_value=SimpleNamespace(
            artifacts_planned=1,
            artifacts_generated=0,
            artifacts_cached=1,
            artifacts_failed=0,
        ),
    ), patch(
        "src.presenter.delivery_style.seed_polish_cache_for_page",
        return_value={"activated": False, "style_school": "", "polished": 0, "cached": 0, "failed": 0},
    ):
        final = run_presentation_pipeline_sync(
            "job-1",
            "plan-1",
            consumer_key="the-critic",
            skip_refinement=True,
            clear_refinement=True,
            wait_if_active=True,
        )

    delete_refinement.assert_called_once_with("job-1")
    deterministic_refiner.assert_called_once_with(
        job_id="job-1",
        plan_id="plan-1",
        consumer_key="the-critic",
    )
    assert final["status"] == "completed"
    assert final["stats"]["scaffolds_cached"] == 1
