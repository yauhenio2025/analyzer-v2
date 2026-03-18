import hashlib
import asyncio
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.aoi.constants import AOI_WORKFLOW_KEY
from src.analysis_products.store import _build_aoi_corpus_payload
from src.api.routes.executor import sync_documents as sync_documents_route
from src.api.routes.orchestrator import analyze_by_ref as analyze_by_ref_route
from src.executor.db import execute, init_db
from src.executor.job_manager import get_job
from src.executor.document_store import get_document, load_registered_documents, sync_external_documents
from src.executor.schemas import SyncDocumentsRequest
from src.orchestrator.by_ref import _build_plan_request, run_analysis_by_ref
from src.orchestrator.pipeline_schemas import AnalyzeByRefRequest
from src.orchestrator.schemas import PriorWork, TargetWork, WorkflowExecutionPlan


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cleanup_external_project(consumer_key: str, external_project_id: str) -> None:
    bindings = execute(
        """SELECT doc_id FROM external_document_bindings
           WHERE consumer_key = %s AND external_project_id = %s""",
        (consumer_key, external_project_id),
        fetch="all",
    )
    for row in bindings:
        execute(
            """DELETE FROM external_document_bindings
               WHERE consumer_key = %s AND external_project_id = %s AND doc_id = %s""",
            (consumer_key, external_project_id, row["doc_id"]),
        )
        execute("DELETE FROM executor_documents WHERE doc_id = %s", (row["doc_id"],))


def _fake_plan(plan_suffix: str = "registered") -> WorkflowExecutionPlan:
    return WorkflowExecutionPlan(
        plan_id=f"plan-{plan_suffix}-{uuid4().hex[:8]}",
        workflow_key="intellectual_genealogy",
        thinker_name="Aaron Benanav",
        target_work=TargetWork(
            title="Beyond Capitalism",
            author="Aaron Benanav",
            description="Target work",
        ),
        prior_works=[
            PriorWork(
                title="Automation and the Future of Work",
                author="Aaron Benanav",
                description="Prior work",
                relationship_hint="early formulation",
            )
        ],
        strategy_summary="summary",
        phases=[],
        recommended_views=[],
        estimated_llm_calls=3,
        estimated_depth_profile="standard",
    )


def _fake_aoi_plan(plan_suffix: str = "registered") -> WorkflowExecutionPlan:
    return WorkflowExecutionPlan(
        plan_id=f"plan-{plan_suffix}-{uuid4().hex[:8]}",
        workflow_key=AOI_WORKFLOW_KEY,
        thinker_name="Aaron Benanav",
        target_work=TargetWork(
            title="Beyond Capitalism",
            author="Aaron Benanav",
            description="Target work",
        ),
        prior_works=[
            PriorWork(
                title="International Planning for Freedom",
                author="Otto Neurath",
                description="Source work",
                relationship_hint="selected_source_thinker_corpus",
                source_thinker_id="otto_neurath",
                source_thinker_name="Otto Neurath",
                source_document_id="international_planning_for_freedom",
            )
        ],
        selected_source_thinker_id="otto_neurath",
        selected_source_thinker_name="Otto Neurath",
        strategy_summary="summary",
        phases=[],
        recommended_views=[],
        estimated_llm_calls=3,
        estimated_depth_profile="standard",
        objective_key="influence_thematic",
    )


def test_sync_external_documents_resolves_parent_across_full_batch():
    init_db()
    consumer_key = "test-consumer"
    external_project_id = f"proj-sync-{uuid4().hex[:8]}"

    try:
        synced = sync_external_documents(
            consumer_key=consumer_key,
            external_project_id=external_project_id,
            documents=[
                {
                    "external_doc_key": "chapter-1",
                    "parent_external_doc_key": "target-doc",
                    "binding_role": "chapter",
                    "title": "Chapter 1",
                    "author": "Aaron Benanav",
                    "text": "Chapter text",
                    "content_hash": _hash("Chapter text"),
                },
                {
                    "external_doc_key": "target-doc",
                    "binding_role": "target",
                    "title": "Beyond Capitalism",
                    "author": "Aaron Benanav",
                    "text": "Target text",
                    "content_hash": _hash("Target text"),
                },
            ],
        )

        assert [row["sync_status"] for row in synced] == ["created", "created"]

        resolved = load_registered_documents(
            consumer_key=consumer_key,
            external_project_id=external_project_id,
            external_doc_keys=["target-doc", "chapter-1"],
        )

        assert resolved["target-doc"]["binding_role"] == "target"
        assert resolved["chapter-1"]["binding_role"] == "chapter"
        assert resolved["chapter-1"]["parent_external_doc_key"] == "target-doc"
    finally:
        _cleanup_external_project(consumer_key, external_project_id)


def test_sync_documents_route_returns_400_on_hash_mismatch():
    init_db()
    request = SyncDocumentsRequest(
        consumer_key="test-consumer",
        external_project_id=f"proj-bad-hash-{uuid4().hex[:8]}",
        documents=[
            {
                "external_doc_key": "target-doc",
                "binding_role": "target",
                "title": "Beyond Capitalism",
                "author": "Aaron Benanav",
                "text": "Target text",
                "content_hash": "bad-hash",
            }
        ],
    )

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(sync_documents_route(request))

    assert excinfo.value.status_code == 400
    assert "content_hash mismatch" in str(excinfo.value.detail)


def test_sync_documents_route_returns_400_on_missing_parent():
    init_db()
    request = SyncDocumentsRequest(
        consumer_key="test-consumer",
        external_project_id=f"proj-missing-parent-{uuid4().hex[:8]}",
        documents=[
            {
                "external_doc_key": "chapter-1",
                "parent_external_doc_key": "missing-target",
                "binding_role": "chapter",
                "title": "Chapter 1",
                "author": "Aaron Benanav",
                "text": "Chapter text",
                "content_hash": _hash("Chapter text"),
            }
        ],
    )

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(sync_documents_route(request))

    assert excinfo.value.status_code == 400
    assert "Missing parent_external_doc_key" in str(excinfo.value.detail)


def test_sync_external_documents_is_atomic_on_batch_failure():
    init_db()
    consumer_key = "test-consumer"
    external_project_id = f"proj-atomic-{uuid4().hex[:8]}"

    try:
        with pytest.raises(ValueError, match="Missing parent_external_doc_key"):
            sync_external_documents(
                consumer_key=consumer_key,
                external_project_id=external_project_id,
                documents=[
                    {
                        "external_doc_key": "target-doc",
                        "binding_role": "target",
                        "title": "Beyond Capitalism",
                        "author": "Aaron Benanav",
                        "text": "Target text",
                        "content_hash": _hash("Target text"),
                    },
                    {
                        "external_doc_key": "chapter-1",
                        "parent_external_doc_key": "missing-target",
                        "binding_role": "chapter",
                        "title": "Chapter 1",
                        "author": "Aaron Benanav",
                        "text": "Chapter text",
                        "content_hash": _hash("Chapter text"),
                    },
                ],
            )

        resolved = load_registered_documents(
            consumer_key=consumer_key,
            external_project_id=external_project_id,
            external_doc_keys=["target-doc", "chapter-1"],
        )
        assert resolved == {}
    finally:
        _cleanup_external_project(consumer_key, external_project_id)


def test_sync_external_documents_updates_binding_with_new_doc_id_without_mutating_old_content():
    init_db()
    consumer_key = "test-consumer"
    external_project_id = f"proj-update-{uuid4().hex[:8]}"
    old_doc_id = None
    new_doc_id = None

    try:
        first = sync_external_documents(
            consumer_key=consumer_key,
            external_project_id=external_project_id,
            documents=[
                {
                    "external_doc_key": "target-doc",
                    "binding_role": "target",
                    "title": "Beyond Capitalism",
                    "author": "Aaron Benanav",
                    "text": "Target text",
                    "content_hash": _hash("Target text"),
                }
            ],
        )
        old_doc_id = first[0]["doc_id"]

        second = sync_external_documents(
            consumer_key=consumer_key,
            external_project_id=external_project_id,
            documents=[
                {
                    "external_doc_key": "target-doc",
                    "binding_role": "target",
                    "title": "Beyond Capitalism",
                    "author": "Aaron Benanav",
                    "text": "Target text revised",
                    "content_hash": _hash("Target text revised"),
                }
            ],
        )
        new_doc_id = second[0]["doc_id"]

        assert second[0]["sync_status"] == "updated"
        assert new_doc_id != old_doc_id
        assert get_document(old_doc_id)["text"] == "Target text"
        assert get_document(new_doc_id)["text"] == "Target text revised"

        resolved = load_registered_documents(
            consumer_key=consumer_key,
            external_project_id=external_project_id,
            external_doc_keys=["target-doc"],
        )
        assert resolved["target-doc"]["doc_id"] == new_doc_id
    finally:
        _cleanup_external_project(consumer_key, external_project_id)
        for doc_id in (old_doc_id, new_doc_id):
            if doc_id:
                execute("DELETE FROM executor_documents WHERE doc_id = %s", (doc_id,))


def test_analyze_by_ref_route_returns_400_for_chapter_role_mismatch():
    init_db()
    consumer_key = "test-consumer"
    external_project_id = f"proj-role-{uuid4().hex[:8]}"

    try:
        sync_external_documents(
            consumer_key=consumer_key,
            external_project_id=external_project_id,
            documents=[
                {
                    "external_doc_key": "target-doc",
                    "binding_role": "target",
                    "title": "Beyond Capitalism",
                    "author": "Aaron Benanav",
                    "text": "Target text",
                    "content_hash": _hash("Target text"),
                },
                {
                    "external_doc_key": "chapter-1",
                    "parent_external_doc_key": "target-doc",
                    "binding_role": "chapter",
                    "title": "Chapter 1",
                    "author": "Aaron Benanav",
                    "text": "Chapter text",
                    "content_hash": _hash("Chapter text"),
                },
                {
                    "external_doc_key": "prior-doc",
                    "binding_role": "prior_work",
                    "title": "Automation and the Future of Work",
                    "author": "Aaron Benanav",
                    "text": "Prior text",
                    "content_hash": _hash("Prior text"),
                },
            ],
        )

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(
                analyze_by_ref_route(
                    AnalyzeByRefRequest(
                        consumer_key=consumer_key,
                        external_project_id=external_project_id,
                        thinker_name="Aaron Benanav",
                        target_work={
                            "title": "Beyond Capitalism",
                            "author": "Aaron Benanav",
                            "description": "Target work",
                        },
                        target_external_doc_key="chapter-1",
                        prior_works=[
                            {
                                "external_doc_key": "prior-doc",
                                "description": "Prior work",
                                "relationship_hint": "early formulation",
                            }
                        ],
                        skip_plan_review=False,
                    )
                )
            )

        assert excinfo.value.status_code == 400
        assert "cannot resolve to a chapter binding" in str(excinfo.value.detail)
    finally:
        _cleanup_external_project(consumer_key, external_project_id)


def test_analyze_by_ref_request_requires_aoi_target_chapters_field():
    with pytest.raises(ValueError, match="must use target_chapters"):
        AnalyzeByRefRequest(
            consumer_key="test-consumer",
            external_project_id="proj-aoi",
            thinker_name="Aaron Benanav",
            target_work={
                "title": "Beyond Capitalism",
                "author": "Aaron Benanav",
                "description": "Target work",
            },
            target_external_doc_key="aoi_thematic_target",
            target_chapter_external_doc_keys=["chapter-1"],
            prior_works=[
                {
                    "external_doc_key": "text-otto-1",
                    "description": "Source work",
                    "relationship_hint": "selected_source_thinker_corpus",
                }
            ],
            workflow_key=AOI_WORKFLOW_KEY,
            selected_source_thinker_id="otto_neurath",
            selected_source_thinker_name="Otto Neurath",
            skip_plan_review=False,
        )


def test_build_plan_request_preserves_aoi_selected_thinker_identity():
    request = AnalyzeByRefRequest(
        consumer_key="test-consumer",
        external_project_id="proj-aoi",
        thinker_name="Aaron Benanav",
        target_work={
            "title": "Beyond Capitalism",
            "author": "Aaron Benanav",
            "description": "Target work",
        },
        target_external_doc_key="aoi_thematic_target",
        target_chapters=[
            {
                "external_doc_key": "aoi_thematic_target::chapter::chapter-a",
                "chapter_id": "chapter-a",
            }
        ],
        prior_works=[
            {
                "external_doc_key": "text-otto-1",
                "description": "Source work",
                "relationship_hint": "selected_source_thinker_corpus",
            }
        ],
        workflow_key=AOI_WORKFLOW_KEY,
        selected_source_thinker_id="otto_neurath",
        selected_source_thinker_name="Otto Neurath",
        skip_plan_review=False,
    )

    plan_request = _build_plan_request(
        request,
        [
            {
                "title": "International Planning for Freedom",
                "author": "Otto Neurath",
                "source_thinker_id": "otto_neurath",
                "source_thinker_name": "Otto Neurath",
                "source_document_id": "international_planning_for_freedom",
            }
        ],
    )

    assert plan_request.workflow_key == AOI_WORKFLOW_KEY
    assert plan_request.selected_source_thinker_id == "otto_neurath"
    assert plan_request.selected_source_thinker_name == "Otto Neurath"
    assert plan_request.prior_works[0].source_document_id == "international_planning_for_freedom"


def test_run_analysis_by_ref_preserves_analyze_response_shape(monkeypatch):
    init_db()
    consumer_key = "test-consumer"
    external_project_id = f"proj-by-ref-{uuid4().hex[:8]}"

    try:
        sync_external_documents(
            consumer_key=consumer_key,
            external_project_id=external_project_id,
            documents=[
                {
                    "external_doc_key": "target-doc",
                    "binding_role": "target",
                    "title": "Beyond Capitalism",
                    "author": "Aaron Benanav",
                    "text": "Target text",
                    "content_hash": _hash("Target text"),
                },
                {
                    "external_doc_key": "chapter-1",
                    "parent_external_doc_key": "target-doc",
                    "binding_role": "chapter",
                    "title": "Chapter 1",
                    "author": "Aaron Benanav",
                    "text": "Chapter text",
                    "content_hash": _hash("Chapter text"),
                },
                {
                    "external_doc_key": "prior-doc",
                    "binding_role": "prior_work",
                    "title": "Automation and the Future of Work",
                    "author": "Aaron Benanav",
                    "text": "Prior text",
                    "content_hash": _hash("Prior text"),
                },
            ],
        )

        monkeypatch.setattr("src.orchestrator.by_ref.generate_plan", lambda request: _fake_plan("checkpoint"))

        checkpoint = run_analysis_by_ref(
            AnalyzeByRefRequest(
                consumer_key=consumer_key,
                external_project_id=external_project_id,
                thinker_name="Aaron Benanav",
                target_work={
                    "title": "Beyond Capitalism",
                    "author": "Aaron Benanav",
                    "description": "Target work",
                },
                target_external_doc_key="target-doc",
                target_chapter_external_doc_keys=["chapter-1"],
                prior_works=[
                    {
                        "external_doc_key": "prior-doc",
                        "description": "Prior work",
                        "relationship_hint": "early formulation",
                    }
                ],
                skip_plan_review=False,
            )
        )

        assert checkpoint.job_id is None
        assert checkpoint.plan_id.startswith("plan-checkpoint-")
        assert checkpoint.cancel_token is None
        assert checkpoint.status == "plan_generated"
        assert checkpoint.document_ids["target"].startswith("doc-")
        assert checkpoint.document_ids["Automation and the Future of Work"].startswith("doc-")
        assert checkpoint.document_ids["chapter:target:chapter-1"].startswith("doc-")

        def _unexpected_generate_plan(_request):
            raise AssertionError("autonomous by-ref launch should not generate plan synchronously")

        monkeypatch.setattr("src.orchestrator.by_ref.generate_plan", _unexpected_generate_plan)
        thread_calls: list[tuple[str, dict, dict[str, str]]] = []
        monkeypatch.setattr(
            "src.orchestrator.by_ref._start_by_ref_pipeline_thread",
            lambda job_id, snapshot, document_ids: thread_calls.append((job_id, snapshot, document_ids)),
        )

        autonomous = run_analysis_by_ref(
            AnalyzeByRefRequest(
                consumer_key=consumer_key,
                external_project_id=external_project_id,
                thinker_name="Aaron Benanav",
                target_work={
                    "title": "Beyond Capitalism",
                    "author": "Aaron Benanav",
                    "description": "Target work",
                },
                target_external_doc_key="target-doc",
                target_chapter_external_doc_keys=["chapter-1"],
                prior_works=[
                    {
                        "external_doc_key": "prior-doc",
                        "description": "Prior work",
                        "relationship_hint": "early formulation",
                    }
                ],
                skip_plan_review=True,
            )
        )

        assert autonomous.job_id is not None
        assert autonomous.plan_id is None
        assert autonomous.document_ids == {}
        assert autonomous.cancel_token
        assert autonomous.status == "executing"
        assert len(thread_calls) == 1
        assert thread_calls[0][0] == autonomous.job_id
        assert thread_calls[0][1]["_type"] == "by_ref_request_snapshot"
        assert thread_calls[0][2]["target"].startswith("doc-")

        job = get_job(autonomous.job_id)
        assert job is not None
        assert job["status"] == "pending"
        assert job["plan_id"] == "(generating)"
        assert job["cancel_token"] == autonomous.cancel_token
        assert job["document_ids"]["target"].startswith("doc-")
        assert job["plan_data"]["_type"] == "by_ref_request_snapshot"

        execute("DELETE FROM analysis_artifacts WHERE job_id = %s", (autonomous.job_id,))
        execute(
            "DELETE FROM analysis_corpora WHERE corpus_ref IN (SELECT corpus_ref FROM executor_jobs WHERE job_id = %s)",
            (autonomous.job_id,),
        )
        execute("DELETE FROM executor_jobs WHERE job_id = %s", (autonomous.job_id,))
    finally:
        _cleanup_external_project(consumer_key, external_project_id)


def test_run_analysis_by_ref_aoi_preserves_semantic_chapter_ids_and_snapshot_metadata(monkeypatch):
    init_db()
    consumer_key = "test-consumer"
    external_project_id = f"proj-aoi-{uuid4().hex[:8]}"

    try:
        sync_external_documents(
            consumer_key=consumer_key,
            external_project_id=external_project_id,
            documents=[
                {
                    "external_doc_key": "aoi_thematic_target",
                    "binding_role": "target",
                    "title": "Beyond Capitalism",
                    "author": "Aaron Benanav",
                    "text": "## Subject\n\nTarget text",
                    "content_hash": _hash("## Subject\n\nTarget text"),
                },
                {
                    "external_doc_key": "aoi_thematic_target::chapter::chapter-a",
                    "parent_external_doc_key": "aoi_thematic_target",
                    "binding_role": "chapter",
                    "title": "Chapter A",
                    "author": "Aaron Benanav",
                    "text": "Chapter text",
                    "content_hash": _hash("Chapter text"),
                },
                {
                    "external_doc_key": "text-otto-1",
                    "binding_role": "prior_work",
                    "title": "International Planning for Freedom",
                    "author": "Otto Neurath",
                    "text": "Source text",
                    "content_hash": _hash("Source text"),
                    "source_thinker_id": "otto_neurath",
                    "source_thinker_name": "Otto Neurath",
                    "source_document_id": "international_planning_for_freedom",
                },
            ],
        )

        monkeypatch.setattr("src.orchestrator.by_ref.generate_plan", lambda request: _fake_aoi_plan("aoi-checkpoint"))

        checkpoint_request = AnalyzeByRefRequest(
            consumer_key=consumer_key,
            external_project_id=external_project_id,
            thinker_name="Aaron Benanav",
            target_work={
                "title": "Beyond Capitalism",
                "author": "Aaron Benanav",
                "description": "Target work",
            },
            target_external_doc_key="aoi_thematic_target",
            target_chapters=[
                {
                    "external_doc_key": "aoi_thematic_target::chapter::chapter-a",
                    "chapter_id": "chapter-a",
                }
            ],
            prior_works=[
                {
                    "external_doc_key": "text-otto-1",
                    "description": "Source work",
                    "relationship_hint": "selected_source_thinker_corpus",
                }
            ],
            workflow_key=AOI_WORKFLOW_KEY,
            selected_source_thinker_id="otto_neurath",
            selected_source_thinker_name="Otto Neurath",
            skip_plan_review=False,
        )

        checkpoint = run_analysis_by_ref(checkpoint_request)

        assert checkpoint.document_ids["chapter:target:chapter-a"].startswith("doc-")
        assert "chapter:target:aoi_thematic_target::chapter::chapter-a" not in checkpoint.document_ids

        corpus_payload = _build_aoi_corpus_payload(
            _fake_aoi_plan("aoi-payload").model_dump(),
            checkpoint.document_ids,
            objective_key="influence_thematic",
        )
        assert corpus_payload is not None
        chapter_members = [member for member in corpus_payload["members"] if member["role"] == "chapter"]
        assert chapter_members[0]["chapter_id"] == "chapter-a"

        def _unexpected_generate_plan(_request):
            raise AssertionError("autonomous AOI by-ref launch should not generate plan synchronously")

        monkeypatch.setattr("src.orchestrator.by_ref.generate_plan", _unexpected_generate_plan)
        thread_calls: list[tuple[str, dict, dict[str, str]]] = []
        monkeypatch.setattr(
            "src.orchestrator.by_ref._start_by_ref_pipeline_thread",
            lambda job_id, snapshot, document_ids: thread_calls.append((job_id, snapshot, document_ids)),
        )

        autonomous = run_analysis_by_ref(
            AnalyzeByRefRequest(
                consumer_key=consumer_key,
                external_project_id=external_project_id,
                thinker_name="Aaron Benanav",
                target_work={
                    "title": "Beyond Capitalism",
                    "author": "Aaron Benanav",
                    "description": "Target work",
                },
                target_external_doc_key="aoi_thematic_target",
                target_chapters=[
                    {
                        "external_doc_key": "aoi_thematic_target::chapter::chapter-a",
                        "chapter_id": "chapter-a",
                    }
                ],
                prior_works=[
                    {
                        "external_doc_key": "text-otto-1",
                        "description": "Source work",
                        "relationship_hint": "selected_source_thinker_corpus",
                    }
                ],
                workflow_key=AOI_WORKFLOW_KEY,
                selected_source_thinker_id="otto_neurath",
                selected_source_thinker_name="Otto Neurath",
                skip_plan_review=True,
            )
        )

        assert autonomous.status == "executing"
        assert len(thread_calls) == 1
        snapshot = thread_calls[0][1]
        assert snapshot["prior_binding_metadata"]["text-otto-1"]["source_document_id"] == "international_planning_for_freedom"
        assert snapshot["target_chapter_map"] == [
            {
                "external_doc_key": "aoi_thematic_target::chapter::chapter-a",
                "chapter_id": "chapter-a",
                "title": "Chapter A",
            }
        ]

        execute("DELETE FROM analysis_artifacts WHERE job_id = %s", (autonomous.job_id,))
        execute(
            "DELETE FROM analysis_corpora WHERE corpus_ref IN (SELECT corpus_ref FROM executor_jobs WHERE job_id = %s)",
            (autonomous.job_id,),
        )
        execute("DELETE FROM executor_jobs WHERE job_id = %s", (autonomous.job_id,))
    finally:
        _cleanup_external_project(consumer_key, external_project_id)
