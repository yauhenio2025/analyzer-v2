"""By-reference launch helpers for registered-corpus workflows.

Checkpoint mode stays synchronous, but autonomous launch preserves the
existing lifecycle contract: create the job first, return immediately,
and perform plan generation/execution in a background thread.
"""

from __future__ import annotations

import logging
import threading
import uuid
from types import SimpleNamespace
from typing import Any

from src.aoi import AOI_WORKFLOW_KEY
from src.analysis_products.store import register_job_corpus
from src.executor.db import _json_dumps, execute
from src.executor.document_store import (
    get_document,
    get_document_text,
    load_registered_documents,
    store_document,
)
from src.executor.job_manager import (
    create_job,
    is_cancelled,
    update_job_plan_id,
    update_job_progress,
    update_job_status,
)
from src.executor.workflow_runner import execute_plan
from src.objectives.registry import get_objective, list_objectives
from src.orchestrator.adaptive_planner import generate_adaptive_plan
from src.orchestrator.pipeline import _run_pre_execution_revision
from src.orchestrator.pipeline_schemas import AnalyzeByRefRequest, AnalyzeResponse
from src.orchestrator.planner import generate_plan
from src.orchestrator.sampler import sample_all_books
from src.orchestrator.schemas import OrchestratorPlanRequest, PriorWork

logger = logging.getLogger(__name__)

GENEALOGY_WORKFLOW_KEY = "intellectual_genealogy"


def _chapter_refs(request: AnalyzeByRefRequest) -> list[dict[str, str]]:
    workflow_key = request.workflow_key or GENEALOGY_WORKFLOW_KEY
    if workflow_key == AOI_WORKFLOW_KEY:
        return [
            {
                "external_doc_key": chapter.external_doc_key,
                "chapter_id": chapter.chapter_id,
            }
            for chapter in request.target_chapters
        ]
    return [
        {
            "external_doc_key": external_doc_key,
            "chapter_id": external_doc_key,
        }
        for external_doc_key in request.target_chapter_external_doc_keys
    ]


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _compose_target_text(target: dict[str, Any], contexts: list[dict[str, Any]]) -> str:
    blocks = [f"## {target['title']}\n\n{target['text']}"]
    for context in contexts:
        blocks.append(f"## {context['title']}\n\n{context['text']}")
    return "\n\n---\n\n".join(blocks)


def _resolve_request_documents(request: AnalyzeByRefRequest) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    chapter_refs = _chapter_refs(request)
    requested_keys = _dedupe_preserve_order(
        [request.target_external_doc_key]
        + [chapter_ref["external_doc_key"] for chapter_ref in chapter_refs]
        + [item.external_doc_key for item in request.prior_works]
        + list(request.context_external_doc_keys)
    )
    resolved = load_registered_documents(
        consumer_key=request.consumer_key,
        external_project_id=request.external_project_id,
        external_doc_keys=requested_keys,
    )
    missing = [key for key in requested_keys if key not in resolved]
    if missing:
        raise ValueError(f"Registered documents not found: {missing}")

    target = resolved[request.target_external_doc_key]
    if target.get("binding_role") == "chapter":
        raise ValueError("target_external_doc_key cannot resolve to a chapter binding")

    contexts: list[dict[str, Any]] = []
    for external_doc_key in _dedupe_preserve_order(list(request.context_external_doc_keys)):
        binding = resolved[external_doc_key]
        if binding.get("binding_role") == "chapter":
            raise ValueError(f"context document '{external_doc_key}' cannot be a chapter binding")
        contexts.append(binding)

    chapters: list[dict[str, Any]] = []
    for chapter_ref in chapter_refs:
        external_doc_key = chapter_ref["external_doc_key"]
        binding = resolved[external_doc_key]
        if binding.get("binding_role") != "chapter":
            raise ValueError(f"target chapter '{external_doc_key}' is not a chapter binding")
        parent_key = binding.get("parent_external_doc_key")
        if parent_key != request.target_external_doc_key:
            raise ValueError(
                f"target chapter '{external_doc_key}' does not belong to target '{request.target_external_doc_key}'"
            )
        chapters.append(
            {
                **binding,
                "chapter_id": chapter_ref["chapter_id"],
            }
        )

    prior_bindings: list[dict[str, Any]] = []
    for prior_item in request.prior_works:
        binding = resolved[prior_item.external_doc_key]
        if binding.get("binding_role") == "chapter":
            raise ValueError(f"prior work '{prior_item.external_doc_key}' cannot be a chapter binding")
        if request.workflow_key == AOI_WORKFLOW_KEY:
            if binding.get("source_thinker_id") != request.selected_source_thinker_id:
                raise ValueError(
                    f"prior work '{prior_item.external_doc_key}' does not belong to selected thinker "
                    f"'{request.selected_source_thinker_id}'"
                )
            if not binding.get("source_document_id"):
                raise ValueError(
                    f"prior work '{prior_item.external_doc_key}' is missing source_document_id"
                )
        prior_bindings.append(binding)

    return target, contexts, chapters, prior_bindings


def _build_document_ids(
    request: AnalyzeByRefRequest,
    target: dict[str, Any],
    contexts: list[dict[str, Any]],
    chapters: list[dict[str, Any]],
    prior_bindings: list[dict[str, Any]],
) -> tuple[dict[str, str], str]:
    document_ids: dict[str, str] = {}
    if contexts:
        combined_target_text = _compose_target_text(target, contexts)
        document_ids["target"] = store_document(
            title=request.target_work.title,
            text=combined_target_text,
            author=request.target_work.author,
            role="target",
        )
    else:
        combined_target_text = target.get("text") or ""
        document_ids["target"] = target["doc_id"]

    for chapter in chapters:
        chapter_id = chapter.get("chapter_id") or chapter["external_doc_key"]
        document_ids[f"chapter:target:{chapter_id}"] = chapter["doc_id"]

    seen_titles: set[str] = set()
    for prior_item, binding in zip(request.prior_works, prior_bindings, strict=False):
        title = binding.get("title") or prior_item.external_doc_key
        if title in seen_titles:
            raise ValueError(f"Duplicate prior-work title after binding resolution: '{title}'")
        seen_titles.add(title)
        document_ids[title] = binding["doc_id"]

    return document_ids, combined_target_text


def _prior_title_map(request: AnalyzeByRefRequest, prior_bindings: list[dict[str, Any]]) -> dict[str, str]:
    return {
        item.external_doc_key: binding.get("title") or item.external_doc_key
        for item, binding in zip(request.prior_works, prior_bindings, strict=False)
    }


def _build_plan_request(request: AnalyzeByRefRequest, prior_bindings: list[dict[str, Any]]) -> OrchestratorPlanRequest:
    prior_works = [
        PriorWork(
            title=binding.get("title") or item.external_doc_key,
            author=binding.get("author"),
            description=item.description,
            relationship_hint=item.relationship_hint,
            source_thinker_id=binding.get("source_thinker_id"),
            source_thinker_name=binding.get("source_thinker_name"),
            source_document_id=binding.get("source_document_id"),
        )
        for item, binding in zip(request.prior_works, prior_bindings, strict=False)
    ]
    return OrchestratorPlanRequest(
        thinker_name=request.thinker_name,
        target_work=request.target_work,
        prior_works=prior_works,
        research_question=request.research_question,
        depth_preference=request.depth_preference,
        focus_hint=request.focus_hint,
        selected_source_thinker_id=request.selected_source_thinker_id,
        selected_source_thinker_name=request.selected_source_thinker_name,
        workflow_key=request.workflow_key or GENEALOGY_WORKFLOW_KEY,
        planning_model=request.planning_model,
        execution_model=request.execution_model,
    )


def _generate_plan_for_registered_corpus(
    request: AnalyzeByRefRequest,
    *,
    target_text: str,
    chapters: list[dict[str, Any]],
    prior_bindings: list[dict[str, Any]],
):
    plan_request = _build_plan_request(request, prior_bindings)
    if request.objective_key:
        objective = get_objective(request.objective_key)
        if objective is None:
            valid_keys = ", ".join(sorted(obj.objective_key for obj in list_objectives())) or "(none loaded)"
            raise ValueError(
                f"Unknown objective_key: '{request.objective_key}'. Valid keys: {valid_keys}"
            )
        prior_works_for_sampling = [
            {"title": binding.get("title") or "", "text": binding.get("text") or ""}
            for binding in prior_bindings
        ]
        target_chapters = [
            {
                "chapter_id": binding.get("chapter_id") or binding["external_doc_key"],
                "title": binding.get("title") or binding.get("chapter_id") or binding["external_doc_key"],
                "char_count": len(binding.get("text") or ""),
            }
            for binding in chapters
        ] or None
        book_samples = sample_all_books(
            target_work_text=target_text,
            target_work_title=request.target_work.title,
            prior_works=prior_works_for_sampling,
            target_chapters=target_chapters,
        )
        plan = generate_adaptive_plan(
            request=plan_request,
            book_samples=book_samples,
            objective=objective,
            planning_model=request.planning_model,
        )
    else:
        plan = generate_plan(plan_request)

    if request.execution_model:
        plan.execution_model = request.execution_model

    return plan, plan_request


def _build_plan_inputs_from_snapshot(
    request: AnalyzeByRefRequest,
    *,
    document_ids: dict[str, str],
    prior_title_map: dict[str, str],
    prior_binding_metadata: dict[str, dict[str, Any]] | None = None,
    target_chapter_map: list[dict[str, Any]] | None = None,
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    target_doc_id = document_ids.get("target")
    target_text = get_document_text(target_doc_id) if target_doc_id else None
    if not target_text:
        raise ValueError("Registered target text not found for by-ref planning")

    chapters: list[dict[str, Any]] = []
    chapter_refs = target_chapter_map or _chapter_refs(request)
    for chapter_ref in chapter_refs:
        external_doc_key = chapter_ref["external_doc_key"]
        chapter_id = chapter_ref.get("chapter_id") or external_doc_key
        doc_id = document_ids.get(f"chapter:target:{chapter_id}")
        if not doc_id:
            raise ValueError(f"Registered chapter missing for target chapter '{chapter_id}'")
        row = get_document(doc_id)
        if not row:
            raise ValueError(f"Registered chapter doc not found: {doc_id}")
        chapters.append(
            {
                "external_doc_key": external_doc_key,
                "chapter_id": chapter_id,
                "title": (
                    chapter_ref.get("title")
                    or row.get("title")
                    or chapter_id
                ),
                "text": row.get("text") or "",
            }
        )

    prior_bindings: list[dict[str, Any]] = []
    metadata_by_key = dict(prior_binding_metadata or {})
    for prior_item in request.prior_works:
        metadata = metadata_by_key.get(prior_item.external_doc_key) or {}
        title = (
            metadata.get("title")
            or prior_title_map.get(prior_item.external_doc_key)
            or prior_item.external_doc_key
        )
        doc_id = document_ids.get(title)
        if not doc_id:
            raise ValueError(f"Registered prior-work doc missing for '{title}'")
        row = get_document(doc_id)
        if not row:
            raise ValueError(f"Registered prior-work doc not found: {doc_id}")
        prior_bindings.append(
            {
                "title": title,
                "author": metadata.get("author", row.get("author")),
                "text": row.get("text") or "",
                "source_thinker_id": metadata.get("source_thinker_id"),
                "source_thinker_name": metadata.get("source_thinker_name"),
                "source_document_id": metadata.get("source_document_id"),
            }
        )

    return target_text, chapters, prior_bindings


def _store_by_ref_snapshot(
    job_id: str,
    *,
    request: AnalyzeByRefRequest,
    document_ids: dict[str, str],
    prior_title_map: dict[str, str],
    prior_bindings: list[dict[str, Any]],
    chapters: list[dict[str, Any]],
) -> dict[str, Any]:
    snapshot = {
        "_type": "by_ref_request_snapshot",
        "request": request.model_dump(),
        "prior_title_map": prior_title_map,
        "prior_binding_metadata": {
            item.external_doc_key: {
                "title": binding.get("title") or item.external_doc_key,
                "author": binding.get("author"),
                "source_thinker_id": binding.get("source_thinker_id"),
                "source_thinker_name": binding.get("source_thinker_name"),
                "source_document_id": binding.get("source_document_id"),
            }
            for item, binding in zip(request.prior_works, prior_bindings, strict=False)
        },
        "target_chapter_map": [
            {
                "external_doc_key": chapter["external_doc_key"],
                "chapter_id": chapter.get("chapter_id") or chapter["external_doc_key"],
                "title": chapter.get("title") or chapter.get("chapter_id") or chapter["external_doc_key"],
            }
            for chapter in chapters
        ],
    }
    execute(
        """UPDATE executor_jobs
           SET plan_data = %s, document_ids = %s
           WHERE job_id = %s""",
        (_json_dumps(snapshot), _json_dumps(document_ids), job_id),
    )
    return snapshot


def _store_by_ref_plan(job_id: str, plan, document_ids: dict[str, str]) -> None:
    execute(
        """UPDATE executor_jobs
           SET plan_data = %s, document_ids = %s
           WHERE job_id = %s""",
        (_json_dumps(plan.model_dump()), _json_dumps(document_ids), job_id),
    )
    try:
        register_job_corpus(
            job_id,
            plan_data=plan.model_dump(),
            document_ids=document_ids,
            workflow_key=plan.workflow_key,
            objective_key=getattr(plan, "objective_key", None),
        )
    except Exception as e:
        logger.warning("Could not register corpus_ref for by-ref job %s: %s", job_id, e)


def resume_by_ref_from_snapshot(job_id: str, snapshot: dict[str, Any], document_ids: dict[str, str]) -> None:
    """Generate a plan from a stored by-ref snapshot, then execute it."""
    try:
        request = AnalyzeByRefRequest(**snapshot["request"])
        prior_title_map = dict(snapshot.get("prior_title_map") or {})
        prior_binding_metadata = dict(snapshot.get("prior_binding_metadata") or {})
        target_chapter_map = list(snapshot.get("target_chapter_map") or [])
        update_job_progress(
            job_id,
            current_phase=0,
            phase_name="Generating Analysis Plan",
            detail="Planning from registered documents...",
        )
        target_text, chapters, prior_bindings = _build_plan_inputs_from_snapshot(
            request,
            document_ids=document_ids,
            prior_title_map=prior_title_map,
            prior_binding_metadata=prior_binding_metadata,
            target_chapter_map=target_chapter_map,
        )
        plan, _plan_request = _generate_plan_for_registered_corpus(
            request,
            target_text=target_text,
            chapters=chapters,
            prior_bindings=prior_bindings,
        )

        if request.objective_key and not request.skip_plan_revision:
            plan = _run_pre_execution_revision(
                plan,
                SimpleNamespace(
                    objective_key=request.objective_key,
                    planning_model=request.planning_model,
                ),
            )

        update_job_plan_id(job_id, plan.plan_id)
        _store_by_ref_plan(job_id, plan, document_ids)

        if is_cancelled(job_id):
            update_job_status(job_id, "cancelled", error="Analysis cancelled by user")
            return

        update_job_progress(
            job_id,
            current_phase=0,
            phase_name="Starting Execution",
            detail=f"Executing plan with {plan.estimated_llm_calls} LLM calls...",
        )
        execute_plan(
            job_id=job_id,
            plan_id=plan.plan_id,
            document_ids=document_ids,
            plan_object=plan,
        )
    except Exception as e:
        logger.error("By-ref pipeline failed for job %s: %s", job_id, e, exc_info=True)
        update_job_status(job_id, "failed", error=str(e))


def _start_by_ref_pipeline_thread(job_id: str, snapshot: dict[str, Any], document_ids: dict[str, str]) -> threading.Thread:
    thread = threading.Thread(
        target=resume_by_ref_from_snapshot,
        args=(job_id, snapshot, document_ids),
        name=f"by-ref-{job_id}",
        daemon=True,
    )
    thread.start()
    logger.info("Started by-ref planning thread for job %s", job_id)
    return thread


def _run_checkpoint_mode_by_ref(
    request: AnalyzeByRefRequest,
    *,
    target: dict[str, Any],
    contexts: list[dict[str, Any]],
    chapters: list[dict[str, Any]],
    prior_bindings: list[dict[str, Any]],
) -> AnalyzeResponse:
    document_ids, target_text = _build_document_ids(request, target, contexts, chapters, prior_bindings)
    plan, _plan_request = _generate_plan_for_registered_corpus(
        request,
        target_text=target_text,
        chapters=chapters,
        prior_bindings=prior_bindings,
    )
    return AnalyzeResponse(
        job_id=None,
        plan_id=plan.plan_id,
        document_ids=document_ids,
        status="plan_generated",
        message=(
            f"Plan generated with {len(plan.phases)} phases and "
            f"{plan.estimated_llm_calls} estimated LLM calls. "
            f"Review at GET /v1/orchestrator/plans/{plan.plan_id}, "
            f"then start execution with POST /v1/executor/jobs."
        ),
    )


def _run_autonomous_mode_by_ref(
    request: AnalyzeByRefRequest,
    *,
    target: dict[str, Any],
    contexts: list[dict[str, Any]],
    chapters: list[dict[str, Any]],
    prior_bindings: list[dict[str, Any]],
) -> AnalyzeResponse:
    document_ids, _target_text = _build_document_ids(request, target, contexts, chapters, prior_bindings)
    prior_title_map = _prior_title_map(request, prior_bindings)

    job_id = f"job-{uuid.uuid4().hex[:12]}"
    project_id = request.project_id or request.external_project_id
    job_record = create_job(
        job_id=job_id,
        plan_id="(generating)",
        plan_data=None,
        document_ids=document_ids,
        workflow_key=request.workflow_key or GENEALOGY_WORKFLOW_KEY,
        project_id=project_id,
    )
    snapshot = _store_by_ref_snapshot(
        job_id,
        request=request,
        document_ids=document_ids,
        prior_title_map=prior_title_map,
        prior_bindings=prior_bindings,
        chapters=chapters,
    )
    update_job_progress(
        job_id,
        current_phase=0,
        phase_name="Generating Analysis Plan",
        detail="Planning from registered documents...",
    )
    _start_by_ref_pipeline_thread(job_id, snapshot, document_ids)

    return AnalyzeResponse(
        job_id=job_id,
        plan_id=None,
        document_ids={},
        cancel_token=job_record.get("cancel_token"),
        status="executing",
        message=(
            f"Pipeline accepted. Poll GET /v1/executor/jobs/{job_id} for progress. "
            f"Plan generation uses registered documents and runs in background."
        ),
    )


def run_analysis_by_ref(request: AnalyzeByRefRequest) -> AnalyzeResponse:
    """Generate a plan and optionally start execution from registered docs."""
    target, contexts, chapters, prior_bindings = _resolve_request_documents(request)
    if not prior_bindings:
        raise ValueError("By-ref launch requires at least one prior work")

    if not request.skip_plan_review:
        return _run_checkpoint_mode_by_ref(
            request,
            target=target,
            contexts=contexts,
            chapters=chapters,
            prior_bindings=prior_bindings,
        )

    return _run_autonomous_mode_by_ref(
        request,
        target=target,
        contexts=contexts,
        chapters=chapters,
        prior_bindings=prior_bindings,
    )
