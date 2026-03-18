"""Stage 4 run contract tests: live-run discovery and by-job detail."""

from types import SimpleNamespace
from uuid import uuid4

from src.analysis_products import result_contract as result_contract_module
from src.analysis_products.run_contract import build_run_detail, build_run_discovery
from src.aoi.constants import AOI_WORKFLOW_KEY
from src.executor.db import execute, init_db
from src.executor.job_manager import create_job, update_job_progress, update_job_status
from src.presenter.preparation_store import save_presentation_run


def _aoi_plan_data(source_thinker_id: str = "otto_neurath") -> dict:
    return {
        "workflow_key": AOI_WORKFLOW_KEY,
        "objective_key": "influence_thematic",
        "selected_source_thinker_id": source_thinker_id,
        "selected_source_thinker_name": source_thinker_id.replace("_", " ").title(),
        "target_work": {"title": "Beyond Capitalism", "author": "Aaron Benanav"},
        "prior_works": [],
    }


def _cleanup(job_ids: list[str]) -> None:
    for job_id in job_ids:
        execute("DELETE FROM presentation_runs WHERE job_id = %s", (job_id,))
        execute("DELETE FROM analysis_artifacts WHERE job_id = %s", (job_id,))
        execute("DELETE FROM analysis_corpora WHERE corpus_ref IN (SELECT corpus_ref FROM executor_jobs WHERE job_id = %s)", (job_id,))
        execute("DELETE FROM executor_jobs WHERE job_id = %s", (job_id,))


def test_run_detail_exposes_progress_aliases(monkeypatch):
    init_db()
    job_id = f"job-run-detail-{uuid4().hex[:8]}"

    try:
        create_job(
            job_id=job_id,
            plan_id="plan-run-detail",
            plan_data=_aoi_plan_data(),
            document_ids={"target": "doc-target-run-detail"},
            workflow_key=AOI_WORKFLOW_KEY,
            project_id="proj-run-detail",
        )
        update_job_progress(
            job_id,
            current_phase=2.5,
            phase_name="Relationship Extraction",
            detail="Processing relationship cards",
            completed_phases=["1.0", "1.5", "2.0"],
            phase_statuses={"1.0": "completed", "1.5": "completed", "2.0": "completed", "2.5": "running"},
            total_phases=5,
            structured_detail={"engine_key": "relationship_extraction", "work_key": "work-1"},
        )
        save_presentation_run(job_id, "running", detail="Preparing presentation")

        monkeypatch.setattr(
            "src.analysis_products.run_contract.lookup_job_corpus",
            lambda _job_id: "corp-run-detail",
        )
        monkeypatch.setattr(
            "src.analysis_products.run_contract.summarize_jobs_artifacts",
            lambda job_ids, jobs_by_id=None, preparation_statuses=None, ensure_corpus=False: {
                jid: [] for jid in job_ids
            },
        )
        monkeypatch.setattr(
            "src.analysis_products.run_contract.load_effective_plan_context",
            lambda _job_id, plan_id=None: SimpleNamespace(plan=object(), source="job_plan_data"),
        )

        detail = build_run_detail(job_id)

        assert detail.job_id == job_id
        assert detail.progress.current_phase == 2.5
        assert detail.progress.current_pass == 2.5
        assert detail.progress.total_passes == 5
        assert detail.progress.current_pass_name == "Relationship Extraction"
        assert detail.progress.structured_detail == {
            "engine_key": "relationship_extraction",
            "work_key": "work-1",
        }
        assert detail.presentation_status == "running"
        assert detail.result_state == "preparing"
        assert detail.restore_available is False
    finally:
        _cleanup([job_id])


def test_run_discovery_filters_active_jobs_and_selected_source_thinker(monkeypatch):
    init_db()
    job_ids: list[str] = []

    try:
        matching_job = f"job-run-match-{uuid4().hex[:8]}"
        other_project = f"job-run-other-project-{uuid4().hex[:8]}"
        other_thinker = f"job-run-other-thinker-{uuid4().hex[:8]}"
        completed_job = f"job-run-completed-{uuid4().hex[:8]}"
        job_ids.extend([matching_job, other_project, other_thinker, completed_job])

        create_job(
            matching_job,
            "plan-run-match",
            plan_data=_aoi_plan_data("otto_neurath"),
            workflow_key=AOI_WORKFLOW_KEY,
            project_id="proj-active",
        )
        create_job(
            other_project,
            "plan-run-other-project",
            plan_data=_aoi_plan_data("otto_neurath"),
            workflow_key=AOI_WORKFLOW_KEY,
            project_id="proj-other",
        )
        create_job(
            other_thinker,
            "plan-run-other-thinker",
            plan_data=_aoi_plan_data("karl_popper"),
            workflow_key=AOI_WORKFLOW_KEY,
            project_id="proj-active",
        )
        create_job(
            completed_job,
            "plan-run-completed",
            plan_data=_aoi_plan_data("otto_neurath"),
            workflow_key=AOI_WORKFLOW_KEY,
            project_id="proj-active",
        )

        update_job_status(matching_job, "running")
        update_job_status(other_project, "running")
        update_job_status(other_thinker, "running")
        update_job_status(completed_job, "completed")

        monkeypatch.setattr(
            "src.analysis_products.run_contract.lookup_job_corpora",
            lambda job_ids: {jid: f"corp-{jid}" for jid in job_ids},
        )
        monkeypatch.setattr(
            "src.analysis_products.run_contract.summarize_jobs_artifacts",
            lambda job_ids, jobs_by_id=None, preparation_statuses=None, ensure_corpus=False: {
                jid: [] for jid in job_ids
            },
        )
        monkeypatch.setattr(
            "src.analysis_products.run_contract.load_effective_plan_context",
            lambda _job_id, plan_id=None: SimpleNamespace(plan=object(), source="job_plan_data"),
        )

        active = build_run_discovery(
            project_id="proj-active",
            workflow_key=AOI_WORKFLOW_KEY,
            scope="active",
            selected_source_thinker_id="otto_neurath",
        )

        assert [summary.job_id for summary in active] == [matching_job]
        assert active[0].selected_source_thinker_id == "otto_neurath"

        recent = build_run_discovery(
            project_id="proj-active",
            workflow_key=AOI_WORKFLOW_KEY,
            scope="recent",
        )

        assert [summary.job_id for summary in recent] == [completed_job]
        assert recent[0].status == "completed"
    finally:
        _cleanup(job_ids)


def test_run_discovery_uses_batch_derivation_not_result_manifest_loop(monkeypatch):
    init_db()
    job_id = f"job-run-batch-{uuid4().hex[:8]}"

    try:
        create_job(
            job_id,
            "plan-run-batch",
            plan_data=_aoi_plan_data(),
            workflow_key=AOI_WORKFLOW_KEY,
            project_id="proj-batch",
        )
        update_job_status(job_id, "running")

        monkeypatch.setattr(
            result_contract_module,
            "build_result_manifest",
            lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("result manifest loop should not be used")),
        )
        monkeypatch.setattr(
            "src.analysis_products.run_contract.lookup_job_corpora",
            lambda job_ids: {jid: f"corp-{jid}" for jid in job_ids},
        )
        monkeypatch.setattr(
            "src.analysis_products.run_contract.summarize_jobs_artifacts",
            lambda job_ids, jobs_by_id=None, preparation_statuses=None, ensure_corpus=False: {
                jid: [] for jid in job_ids
            },
        )
        monkeypatch.setattr(
            "src.analysis_products.run_contract.load_effective_plan_context",
            lambda _job_id, plan_id=None: SimpleNamespace(plan=object(), source="job_plan_data"),
        )

        discovered = build_run_discovery(
            project_id="proj-batch",
            workflow_key=AOI_WORKFLOW_KEY,
            scope="active",
        )

        assert len(discovered) == 1
        assert discovered[0].job_id == job_id
        assert discovered[0].result_state == "preparing"
    finally:
        _cleanup([job_id])
