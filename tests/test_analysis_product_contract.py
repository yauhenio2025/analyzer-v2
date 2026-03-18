from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.analysis_products.result_contract import (
    ConflictError,
    attach_project_to_job,
    build_discovery_summaries,
    build_result_manifest,
    get_result_presentation,
)
from src.analysis_products.schemas import AnalysisResultManifest
from src.analysis_products.store import (
    build_corpus_registration,
    load_aoi_normalized_artifact,
    record_aoi_artifact_from_metadata,
    register_job_corpus,
)
from src.aoi.constants import AOI_WORKFLOW_KEY
from src.executor.db import execute, init_db
from src.executor.job_manager import create_job
from src.executor.output_store import load_all_job_outputs, save_output
from src.presenter.schemas import PagePresentation


def _aoi_plan_data() -> dict:
    return {
        "workflow_key": AOI_WORKFLOW_KEY,
        "objective_key": "influence_thematic",
        "selected_source_thinker_id": "otto_neurath",
        "selected_source_thinker_name": "Otto Neurath",
        "target_work": {
            "title": "Beyond Capitalism",
            "author": "Aaron Benanav",
        },
        "prior_works": [
            {
                "title": "International Planning for Freedom",
                "author": "Otto Neurath",
                "year": 1942,
                "source_thinker_id": "otto_neurath",
                "source_thinker_name": "Otto Neurath",
                "source_document_id": "international_planning_for_freedom",
            }
        ],
    }


def test_build_corpus_registration_for_aoi_is_deterministic():
    registration = build_corpus_registration(
        plan_data=_aoi_plan_data(),
        document_ids={
            "target": "doc-target-1",
            "International Planning for Freedom": "doc-source-1",
        },
    )

    assert registration is not None
    assert registration["workflow_key"] == AOI_WORKFLOW_KEY
    assert registration["qualifiers"]["selected_source_thinker_id"] == "otto_neurath"
    assert any(
        member.get("source_document_id") == "international_planning_for_freedom"
        for member in registration["member_manifest"]
    )
    assert registration["corpus_ref"].startswith("corp-")


def test_corpus_registration_ignores_upload_time_doc_ids_and_input_order(monkeypatch):
    content_hashes = {
        "doc-target-a": "hash-target",
        "doc-target-b": "hash-target",
        "doc-source-a": "hash-source",
        "doc-source-b": "hash-source",
        "doc-prior-1a": "hash-prior-1",
        "doc-prior-1b": "hash-prior-1",
        "doc-prior-2a": "hash-prior-2",
        "doc-prior-2b": "hash-prior-2",
    }
    monkeypatch.setattr(
        "src.analysis_products.store._load_document_content_hash",
        lambda document_id: content_hashes[document_id],
    )

    aoi_plan = _aoi_plan_data()
    first = build_corpus_registration(
        plan_data=aoi_plan,
        document_ids={
            "target": "doc-target-a",
            "International Planning for Freedom": "doc-source-a",
        },
    )
    second = build_corpus_registration(
        plan_data=aoi_plan,
        document_ids={
            "target": "doc-target-b",
            "International Planning for Freedom": "doc-source-b",
        },
    )

    genealogy_plan = {
        "workflow_key": "intellectual_genealogy",
        "target_work": {"title": "Target", "author": "Author"},
        "prior_works": [
            {"title": "Prior B", "author": "Author B", "year": 1999},
            {"title": "Prior A", "author": "Author A", "year": 1991},
        ],
    }
    genealogy_first = build_corpus_registration(
        plan_data=genealogy_plan,
        document_ids={
            "target": "doc-target-a",
            "Prior B": "doc-prior-2a",
            "Prior A": "doc-prior-1a",
        },
    )
    genealogy_second = build_corpus_registration(
        plan_data={
            **genealogy_plan,
            "prior_works": list(reversed(genealogy_plan["prior_works"])),
        },
        document_ids={
            "target": "doc-target-b",
            "Prior A": "doc-prior-1b",
            "Prior B": "doc-prior-2b",
        },
    )

    assert first is not None and second is not None
    assert first["corpus_ref"] == second["corpus_ref"]
    assert genealogy_first is not None and genealogy_second is not None
    assert genealogy_first["corpus_ref"] == genealogy_second["corpus_ref"]


def test_aoi_stage1_artifact_round_trip_uses_registered_corpus():
    init_db()
    job_id = f"job-test-aoi-{uuid4().hex[:8]}"
    plan_data = _aoi_plan_data()
    document_ids = {
        "target": "doc-target-2",
        "International Planning for Freedom": "doc-source-2",
    }

    try:
        create_job(
            job_id=job_id,
            plan_id="plan-test-aoi",
            plan_data=plan_data,
            document_ids=document_ids,
            workflow_key=AOI_WORKFLOW_KEY,
        )
        corpus_ref = register_job_corpus(
            job_id,
            plan_data=plan_data,
            document_ids=document_ids,
            workflow_key=AOI_WORKFLOW_KEY,
            objective_key="influence_thematic",
        )

        assert corpus_ref is not None

        record_aoi_artifact_from_metadata(
            job_id=job_id,
            phase_number=1.0,
            engine_key="aoi_thematic_synthesis",
            source_output_id="po-aoi-source",
            output_metadata={
                "normalized": {
                    "themes": [{"theme_id": "theme_1", "theme_name": "Theme 1"}],
                    "source_documents": [],
                }
            },
        )

        loaded = load_aoi_normalized_artifact(job_id, "aoi_thematic_synthesis")
        assert loaded == {
            "themes": [{"theme_id": "theme_1", "theme_name": "Theme 1"}],
            "source_documents": [],
        }
    finally:
        execute("DELETE FROM analysis_artifacts WHERE job_id = %s", (job_id,))
        execute("DELETE FROM executor_jobs WHERE job_id = %s", (job_id,))


def test_slim_output_load_preserves_content_hash_for_manifest_freshness():
    init_db()
    job_id = f"job-test-slim-{uuid4().hex[:8]}"

    try:
        create_job(
            job_id=job_id,
            plan_id="plan-test-slim",
            plan_data=_aoi_plan_data(),
            document_ids={"target": "doc-target-slim"},
            workflow_key=AOI_WORKFLOW_KEY,
        )
        output_id = save_output(
            job_id=job_id,
            phase_number=1.0,
            engine_key="aoi_thematic_synthesis",
            pass_number=1,
            content="Fresh prose that should influence manifest freshness",
            metadata={"normalized": {"themes": []}},
        )

        rows = load_all_job_outputs(job_id, include_content=False)

        assert len(rows) == 1
        assert rows[0]["id"] == output_id
        assert rows[0]["content"] == ""
        assert rows[0]["content_hash"]
    finally:
        execute("DELETE FROM phase_outputs WHERE job_id = %s", (job_id,))
        execute("DELETE FROM executor_jobs WHERE job_id = %s", (job_id,))


def test_result_manifest_exposes_freshness_fields_and_slot_summaries(monkeypatch):
    monkeypatch.setattr(
        "src.analysis_products.result_contract.get_job",
        lambda job_id: {
            "job_id": job_id,
            "plan_id": "plan-1",
            "workflow_key": "intellectual_genealogy",
            "status": "completed",
        },
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.lookup_job_corpus",
        lambda job_id: "corp-genealogy-1",
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.load_effective_plan_context",
        lambda job_id, plan_id=None: SimpleNamespace(plan=object(), source="job_plan_data"),
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.get_preparation_state",
        lambda job_id: {
            "status": "completed",
            "detail": "Presentation ready",
            "active": False,
        },
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.build_presentation_manifest",
        lambda job_id, consumer_key, slim=True, read_only=True: SimpleNamespace(
            presentation_contract_version=1,
            presentation_hash="hash-1",
            presentation_content_hash="content-1",
            prepared_at="2026-03-16T10:00:00+00:00",
            artifacts_ready=True,
        ),
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.summarize_job_artifacts",
        lambda job_id, preparation_status=None, ensure_corpus=False: [
            {
                "artifact_family": "genealogy.relationship_classification",
                "state": "pending",
                "format": "annotated_prose",
                "total_slots": 3,
                "ready_slots": 2,
                "pending_slots": 1,
                "stale_slots": 0,
                "unavailable_slots": 0,
                "slots": [
                    {"slot": "work_a", "state": "ready"},
                    {"slot": "work_b", "state": "ready"},
                    {"slot": "work_c", "state": "pending"},
                ],
            }
        ],
    )

    manifest = build_result_manifest("job-1", consumer_key="the-critic")

    assert manifest.result_id.startswith("result-")
    assert manifest.result_state == "stale"
    assert manifest.presentation_contract_version == 1
    assert manifest.presentation_hash != "hash-1"
    assert manifest.presentation_content_hash != "content-1"
    assert manifest.artifacts_ready is False
    assert "artifacts_not_ready" in manifest.staleness_reasons
    assert manifest.artifact_families[0].total_slots == 3
    assert manifest.artifact_families[0].pending_slots == 1
    assert manifest.restore_available is False
    assert manifest.restore_reason == "presentation_stale"
    assert manifest.links.presentation_url.endswith(
        "/v1/results/by-job/job-1/presentation?consumer_key=the-critic"
    )
    assert manifest.links.refresh_presentation_url.endswith(
        "/v1/results/by-job/job-1/refresh-presentation?consumer_key=the-critic"
    )


def test_result_manifest_treats_stale_artifacts_as_freshness_change(monkeypatch):
    monkeypatch.setattr(
        "src.analysis_products.result_contract.get_job",
        lambda job_id: {
            "job_id": job_id,
            "plan_id": "plan-1",
            "workflow_key": "intellectual_genealogy",
            "status": "completed",
        },
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.lookup_job_corpus",
        lambda job_id: "corp-genealogy-1",
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.load_effective_plan_context",
        lambda job_id, plan_id=None: SimpleNamespace(plan=object(), source="job_plan_data"),
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.get_preparation_state",
        lambda job_id: {
            "status": "completed",
            "detail": "Presentation ready",
            "active": False,
        },
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.build_presentation_manifest",
        lambda job_id, consumer_key, slim=True, read_only=True: SimpleNamespace(
            presentation_contract_version=1,
            presentation_hash="hash-1",
            presentation_content_hash="content-1",
            prepared_at="2026-03-16T10:00:00+00:00",
            artifacts_ready=True,
        ),
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.summarize_job_artifacts",
        lambda job_id, preparation_status=None, ensure_corpus=False: [
            {
                "artifact_family": "genealogy.relationship_classification",
                "state": "stale",
                "format": "annotated_prose",
                "total_slots": 2,
                "ready_slots": 1,
                "pending_slots": 0,
                "stale_slots": 1,
                "unavailable_slots": 0,
                "slots": [
                    {"slot": "work_a", "state": "ready"},
                    {"slot": "work_b", "state": "stale"},
                ],
            }
        ],
    )

    manifest = build_result_manifest("job-1", consumer_key="the-critic")

    assert manifest.artifacts_ready is False
    assert manifest.result_state == "stale"
    assert manifest.restore_available is False
    assert manifest.restore_reason == "presentation_stale"
    assert "artifact_producer_drift" in manifest.staleness_reasons
    assert manifest.presentation_hash != "hash-1"
    assert manifest.presentation_content_hash != "content-1"


def test_result_manifest_marks_legacy_imports_without_corpus_as_untracked(monkeypatch):
    monkeypatch.setattr(
        "src.analysis_products.result_contract.get_job",
        lambda job_id: {
            "job_id": job_id,
            "plan_id": "plan-legacy",
            "workflow_key": "intellectual_genealogy",
            "status": "completed",
            "document_ids": {},
        },
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.lookup_job_corpus",
        lambda job_id: None,
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.load_effective_plan_context",
        lambda job_id, plan_id=None: SimpleNamespace(plan=None, source="missing"),
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.get_preparation_state",
        lambda job_id: {
            "status": "completed",
            "detail": "Legacy imported result",
            "active": False,
            "stats": {},
        },
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.build_presentation_manifest",
        lambda job_id, consumer_key, slim=True, read_only=True: SimpleNamespace(
            presentation_contract_version=1,
            presentation_hash="hash-legacy",
            presentation_content_hash="content-legacy",
            prepared_at="2026-03-16T10:00:00+00:00",
            artifacts_ready=False,
        ),
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.summarize_job_artifacts",
        lambda job_id, preparation_status=None, ensure_corpus=False: [],
    )

    manifest = build_result_manifest("job-legacy", consumer_key="the-critic")

    assert manifest.result_state == "legacy_untracked"
    assert manifest.restore_available is False
    assert manifest.restore_reason == "legacy_untracked"
    assert "missing_corpus_ref" in manifest.staleness_reasons
    assert "missing_plan_context" in manifest.staleness_reasons
    assert "legacy_imported_job" in manifest.product_warnings


def test_result_manifest_marks_ready_presentations_as_restorable(monkeypatch):
    monkeypatch.setattr(
        "src.analysis_products.result_contract.get_job",
        lambda job_id: {
            "job_id": job_id,
            "plan_id": "plan-ready",
            "workflow_key": "intellectual_genealogy",
            "status": "completed",
            "document_ids": {"target": "doc-target-1"},
        },
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.lookup_job_corpus",
        lambda job_id: "corp-ready-1",
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.load_effective_plan_context",
        lambda job_id, plan_id=None: SimpleNamespace(plan=object(), source="job_plan_data"),
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.get_preparation_state",
        lambda job_id: {
            "status": "completed",
            "detail": "Presentation ready",
            "active": False,
            "stats": {},
        },
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.build_presentation_manifest",
        lambda job_id, consumer_key, slim=True, read_only=True: SimpleNamespace(
            presentation_contract_version=1,
            presentation_hash="hash-ready",
            presentation_content_hash="content-ready",
            prepared_at="2026-03-16T10:00:00+00:00",
            artifacts_ready=True,
        ),
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.summarize_job_artifacts",
        lambda job_id, preparation_status=None, ensure_corpus=False: [],
    )

    manifest = build_result_manifest("job-ready", consumer_key="the-critic")

    assert manifest.result_state == "ready"
    assert manifest.restore_available is True
    assert manifest.restore_reason == "presentation_ready"


def test_build_discovery_summaries_filters_and_avoids_page_assembly(monkeypatch):
    jobs = [
        {
            "job_id": "job-newer",
            "plan_id": "plan-2",
            "project_id": "project-1",
            "workflow_key": AOI_WORKFLOW_KEY,
            "status": "completed",
            "plan_data": {
                "selected_source_thinker_id": "otto_neurath",
                "selected_source_thinker_name": "Otto Neurath",
            },
            "created_at": "2026-03-16T09:30:00+00:00",
            "completed_at": "2026-03-16T11:00:00+00:00",
            "document_ids": {"target": "doc-target-2"},
        },
        {
            "job_id": "job-other-thinker",
            "plan_id": "plan-3",
            "project_id": "project-1",
            "workflow_key": AOI_WORKFLOW_KEY,
            "status": "completed",
            "plan_data": {
                "selected_source_thinker_id": "john_dewey",
                "selected_source_thinker_name": "John Dewey",
            },
            "created_at": "2026-03-16T08:30:00+00:00",
            "completed_at": "2026-03-16T10:30:00+00:00",
            "document_ids": {"target": "doc-target-3"},
        },
        {
            "job_id": "job-older",
            "plan_id": "plan-1",
            "project_id": "project-1",
            "workflow_key": AOI_WORKFLOW_KEY,
            "status": "completed",
            "plan_data": {
                "selected_source_thinker_id": "otto_neurath",
                "selected_source_thinker_name": "Otto Neurath",
            },
            "created_at": "2026-03-16T07:30:00+00:00",
            "completed_at": "2026-03-16T09:00:00+00:00",
            "document_ids": {"target": "doc-target-4"},
        },
    ]
    jobs_by_id = {job["job_id"]: job for job in jobs}
    captured: dict[str, object] = {}

    def _list_completed_jobs(*, project_id=None, workflow_key=None, limit=50):
        captured["project_id"] = project_id
        captured["workflow_key"] = workflow_key
        captured["limit"] = limit
        return jobs

    monkeypatch.setattr(
        "src.executor.job_manager.list_completed_jobs",
        _list_completed_jobs,
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.get_job",
        lambda job_id: jobs_by_id[job_id],
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.lookup_job_corpus",
        lambda job_id: f"corp-{job_id}",
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.load_effective_plan_context",
        lambda job_id, plan_id=None: SimpleNamespace(plan=object(), source="job_plan_data"),
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.get_preparation_state",
        lambda job_id: {
            "status": "completed",
            "detail": "Presentation ready",
            "active": False,
            "stats": {},
        },
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.build_presentation_manifest",
        lambda job_id, consumer_key, slim=True, read_only=True: SimpleNamespace(
            presentation_contract_version=1,
            presentation_hash=f"hash-{job_id}",
            presentation_content_hash=f"content-{job_id}",
            prepared_at=jobs_by_id[job_id]["completed_at"],
            artifacts_ready=True,
        ),
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.summarize_job_artifacts",
        lambda job_id, preparation_status=None, ensure_corpus=False: [],
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.assemble_page",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("discovery must not assemble pages")),
    )

    summaries = build_discovery_summaries(
        project_id="project-1",
        workflow_key=AOI_WORKFLOW_KEY,
        consumer_key="the-critic",
        selected_source_thinker_id="otto_neurath",
        limit=2,
    )

    assert captured == {
        "project_id": "project-1",
        "workflow_key": AOI_WORKFLOW_KEY,
        "limit": 200,
    }
    assert [summary.job_id for summary in summaries] == ["job-newer", "job-older"]
    assert all(summary.project_id == "project-1" for summary in summaries)
    assert all(summary.mode == "v2_presentation" for summary in summaries)
    assert summaries[0].completed_at == "2026-03-16T11:00:00+00:00"


def test_build_discovery_summaries_requires_project_id():
    with pytest.raises(ValueError, match="project_id is required"):
        build_discovery_summaries(project_id="  ")


def test_build_discovery_summaries_keeps_generic_jobs_discoverable(monkeypatch):
    jobs = [
        {
            "job_id": "job-generic",
            "plan_id": "plan-generic",
            "project_id": "project-2",
            "workflow_key": "custom_workflow",
            "status": "completed",
            "plan_data": {"workflow_key": "custom_workflow"},
            "created_at": "2026-03-16T08:00:00+00:00",
            "completed_at": "2026-03-16T08:30:00+00:00",
            "document_ids": {"target": "doc-target-5"},
        }
    ]
    job = jobs[0]

    monkeypatch.setattr(
        "src.executor.job_manager.list_completed_jobs",
        lambda *, project_id=None, workflow_key=None, limit=50: jobs,
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.get_job",
        lambda job_id: job,
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.lookup_job_corpus",
        lambda job_id: None,
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.load_effective_plan_context",
        lambda job_id, plan_id=None: SimpleNamespace(plan=object(), source="job_plan_data"),
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.get_preparation_state",
        lambda job_id: {
            "status": "completed",
            "detail": "Presentation ready but missing corpus registration",
            "active": False,
            "stats": {},
        },
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.build_presentation_manifest",
        lambda job_id, consumer_key, slim=True, read_only=True: SimpleNamespace(
            presentation_contract_version=1,
            presentation_hash="hash-generic",
            presentation_content_hash="content-generic",
            prepared_at="2026-03-16T08:30:00+00:00",
            artifacts_ready=True,
        ),
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.summarize_job_artifacts",
        lambda job_id, preparation_status=None, ensure_corpus=False: [],
    )

    summaries = build_discovery_summaries(
        project_id="project-2",
        workflow_key="custom_workflow",
        consumer_key="the-critic",
        limit=10,
    )

    assert len(summaries) == 1
    assert summaries[0].job_id == "job-generic"
    assert summaries[0].restore_available is False
    assert summaries[0].restore_reason == "presentation_stale"
    assert summaries[0].selected_source_thinker_id is None


def test_attach_project_to_job_is_idempotent_and_detects_conflicts(monkeypatch):
    updated: list[tuple[str, str]] = []
    jobs = {
        "job-free": {"job_id": "job-free", "project_id": None},
        "job-same": {"job_id": "job-same", "project_id": "project-1"},
        "job-other": {"job_id": "job-other", "project_id": "project-2"},
    }

    monkeypatch.setattr("src.executor.job_manager.get_job", lambda job_id: jobs.get(job_id))
    monkeypatch.setattr(
        "src.executor.job_manager.set_job_project_id",
        lambda job_id, project_id: updated.append((job_id, project_id)),
    )

    attached = attach_project_to_job("job-free", "project-1")
    idempotent = attach_project_to_job("job-same", "project-1")

    assert attached.attached is True
    assert attached.idempotent is False
    assert idempotent.attached is False
    assert idempotent.idempotent is True
    assert updated == [("job-free", "project-1")]

    with pytest.raises(ConflictError, match="already attached"):
        attach_project_to_job("job-other", "project-1")


def test_get_result_presentation_is_read_only_and_skips_unprepared_jobs(monkeypatch):
    manifest = {
        "job_id": "job-1",
        "plan_id": "plan-1",
        "workflow_key": "intellectual_genealogy",
        "consumer_key": "the-critic",
        "result_id": "result-1",
        "result_state": "preparing",
        "corpus_ref": None,
        "status": "completed",
        "presentation_contract_version": 1,
        "presentation_hash": "",
        "presentation_content_hash": "",
        "prepared_at": "",
        "artifacts_ready": False,
        "presentation_status": "not_started",
        "preparation_detail": "",
        "presentation_active": False,
        "staleness_reasons": ["preparation_not_run"],
        "product_warnings": [],
        "links": {"page_url": "", "presentation_url": "", "manifest_url": "", "trace_url": "", "refresh_presentation_url": ""},
        "artifact_families": [],
    }
    monkeypatch.setattr(
        "src.analysis_products.result_contract.build_result_manifest",
        lambda job_id, consumer_key="the-critic": AnalysisResultManifest(**manifest),
    )
    assemble_calls: list[tuple] = []
    monkeypatch.setattr(
        "src.analysis_products.result_contract.assemble_page",
        lambda *args, **kwargs: assemble_calls.append((args, kwargs)),
    )

    response = get_result_presentation("job-1", consumer_key="the-critic")

    assert response.manifest.job_id == "job-1"
    assert response.presentation is None
    assert assemble_calls == []


def test_get_result_presentation_assembles_read_only_when_prepared(monkeypatch):
    manifest = {
        "job_id": "job-1",
        "plan_id": "plan-1",
        "workflow_key": "intellectual_genealogy",
        "consumer_key": "the-critic",
        "result_id": "result-1",
        "result_state": "ready",
        "corpus_ref": "corp-1",
        "status": "completed",
        "presentation_contract_version": 2,
        "presentation_hash": "manifest-hash",
        "presentation_content_hash": "manifest-content",
        "prepared_at": "2026-03-16T12:00:00+00:00",
        "artifacts_ready": True,
        "presentation_status": "completed",
        "preparation_detail": "",
        "presentation_active": False,
        "restore_available": True,
        "restore_reason": "presentation_ready",
        "staleness_reasons": [],
        "product_warnings": [],
        "links": {"page_url": "", "presentation_url": "", "manifest_url": "", "trace_url": "", "refresh_presentation_url": ""},
        "artifact_families": [],
    }
    page = PagePresentation(
        job_id="job-1",
        plan_id="plan-1",
        consumer_key="the-critic",
        views=[],
    )
    monkeypatch.setattr(
        "src.analysis_products.result_contract.build_result_manifest",
        lambda job_id, consumer_key="the-critic": AnalysisResultManifest(**manifest),
    )
    captured: dict[str, object] = {}

    def _assemble_page(job_id, *, consumer_key, read_only=False, slim=False):
        captured["job_id"] = job_id
        captured["consumer_key"] = consumer_key
        captured["read_only"] = read_only
        return page

    monkeypatch.setattr("src.analysis_products.result_contract.assemble_page", _assemble_page)

    response = get_result_presentation("job-1", consumer_key="the-critic")

    assert captured["job_id"] == "job-1"
    assert captured["consumer_key"] == "the-critic"
    assert captured["read_only"] is True
    assert response.presentation is not None
    assert response.presentation.presentation_hash == "manifest-hash"
