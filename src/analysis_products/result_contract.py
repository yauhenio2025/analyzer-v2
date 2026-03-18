"""Server-owned result manifest, discovery, and read/refresh helpers."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional

from src.analysis_products.schemas import (
    AnalysisResultLinks,
    AnalysisResultManifest,
    AnalysisResultPresentationResponse,
    AttachProjectResponse,
    DiscoverySummary,
    RefreshPresentationResponse,
)
from src.analysis_products.store import lookup_job_corpus, summarize_job_artifacts
from src.aoi.constants import AOI_WORKFLOW_KEY
from src.executor.job_manager import get_job
from src.executor.plan_context import load_effective_plan_context
from src.presenter.preparation_coordinator import get_preparation_state, run_presentation_pipeline_sync
from src.presenter.presentation_api import assemble_page, build_presentation_manifest

logger = logging.getLogger(__name__)

DEFAULT_CONSUMER_KEY = "the-critic"

RESULT_STATE_READY = "ready"
RESULT_STATE_PREPARING = "preparing"
RESULT_STATE_STALE = "stale"
RESULT_STATE_LEGACY_UNTRACKED = "legacy_untracked"
RESULT_STATE_FAILED = "failed"

STALE_REASON_ARTIFACTS_NOT_READY = "artifacts_not_ready"
STALE_REASON_ARTIFACT_PRODUCER_DRIFT = "artifact_producer_drift"
STALE_REASON_MISSING_CORPUS_REF = "missing_corpus_ref"
STALE_REASON_MISSING_PLAN_CONTEXT = "missing_plan_context"
STALE_REASON_PREPARATION_NOT_RUN = "preparation_not_run"
STALE_REASON_PREPARATION_FAILED = "preparation_failed"

WARNING_ARTIFACT_MATERIALIZATION_FAILED = "artifact_materialization_failed"
WARNING_CORPUS_REGISTRATION_FAILED = "corpus_registration_failed"
WARNING_LEGACY_IMPORTED_JOB = "legacy_imported_job"

GENEALOGY_WORKFLOW_KEY = "intellectual_genealogy"
SUPPORTED_PRODUCT_WORKFLOWS = {AOI_WORKFLOW_KEY, GENEALOGY_WORKFLOW_KEY}

RESTORE_REASON_PRESENTATION_READY = "presentation_ready"
RESTORE_REASON_PRESENTATION_STALE = "presentation_stale"
RESTORE_REASON_LEGACY_UNTRACKED = "legacy_untracked"
RESTORE_REASON_NOT_PREPARED = "not_prepared"
RESTORE_REASON_PREPARING = "preparing"
RESTORE_REASON_FAILED = "failed"


def _fallback_freshness() -> dict[str, Any]:
    return {
        "presentation_contract_version": 1,
        "presentation_hash": "",
        "presentation_content_hash": "",
        "prepared_at": "",
        "artifacts_ready": False,
    }


def _stable_hash(value: Any) -> str:
    serialized = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _stable_result_id(job_id: str, consumer_key: str) -> str:
    digest = _stable_hash({"job_id": job_id, "consumer_key": consumer_key})[:24]
    return f"result-{digest}"


def _has_concrete_document_identity(job: dict[str, Any]) -> bool:
    document_ids = job.get("document_ids")
    return isinstance(document_ids, dict) and any(bool(value) for value in document_ids.values())


def _is_supported_workflow(job: dict[str, Any]) -> bool:
    return (job.get("workflow_key") or "") in SUPPORTED_PRODUCT_WORKFLOWS


def _merge_artifact_freshness(
    freshness: dict[str, Any],
    artifact_families: list[dict[str, Any]],
) -> dict[str, Any]:
    if not artifact_families:
        return freshness

    artifact_contract = [
        {
            "artifact_family": family.get("artifact_family"),
            "state": family.get("state"),
            "total_slots": family.get("total_slots", 0),
            "ready_slots": family.get("ready_slots", 0),
            "pending_slots": family.get("pending_slots", 0),
            "stale_slots": family.get("stale_slots", 0),
            "unavailable_slots": family.get("unavailable_slots", 0),
            "slots": [
                {
                    "slot": slot.get("slot"),
                    "state": slot.get("state"),
                }
                for slot in family.get("slots", [])
            ],
        }
        for family in artifact_families
    ]
    any_not_ready = any(family.get("state") != RESULT_STATE_READY for family in artifact_families)
    return {
        **freshness,
        "presentation_hash": _stable_hash(
            {
                "presentation_hash": freshness.get("presentation_hash", ""),
                "artifact_contract": [
                    {
                        "artifact_family": family["artifact_family"],
                        "state": family["state"],
                        "total_slots": family["total_slots"],
                    }
                    for family in artifact_contract
                ],
            }
        ),
        "presentation_content_hash": _stable_hash(
            {
                "presentation_content_hash": freshness.get("presentation_content_hash", ""),
                "artifact_contract": artifact_contract,
            }
        ),
        "artifacts_ready": bool(freshness.get("artifacts_ready")) and not any_not_ready,
    }


def _collect_staleness_reasons(
    *,
    job: dict[str, Any],
    corpus_ref: str | None,
    plan_context_source: str,
    preparation: dict[str, Any],
    artifact_families: list[dict[str, Any]],
) -> list[str]:
    reasons: list[str] = []

    if any(family.get("state") in {"pending", "unavailable"} for family in artifact_families):
        reasons.append(STALE_REASON_ARTIFACTS_NOT_READY)
    if any(family.get("state") == "stale" for family in artifact_families):
        reasons.append(STALE_REASON_ARTIFACT_PRODUCER_DRIFT)
    if corpus_ref is None:
        reasons.append(STALE_REASON_MISSING_CORPUS_REF)
    if plan_context_source == "missing":
        reasons.append(STALE_REASON_MISSING_PLAN_CONTEXT)

    preparation_status = preparation.get("status", "not_started")
    if preparation_status == "not_started":
        reasons.append(STALE_REASON_PREPARATION_NOT_RUN)
    elif preparation_status == "failed":
        reasons.append(STALE_REASON_PREPARATION_FAILED)

    return reasons


def _collect_product_warnings(
    *,
    job: dict[str, Any],
    corpus_ref: str | None,
    preparation: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    prep_stats = preparation.get("stats") or {}

    if prep_stats.get("stage1_artifacts_failed"):
        warnings.append(WARNING_ARTIFACT_MATERIALIZATION_FAILED)

    if corpus_ref is None:
        if not _has_concrete_document_identity(job):
            warnings.append(WARNING_LEGACY_IMPORTED_JOB)
        elif _is_supported_workflow(job):
            warnings.append(WARNING_CORPUS_REGISTRATION_FAILED)

    return warnings


def _determine_result_state(
    *,
    job: dict[str, Any],
    corpus_ref: str | None,
    preparation: dict[str, Any],
    staleness_reasons: list[str],
) -> str:
    job_status = job.get("status", "")
    preparation_status = preparation.get("status", "not_started")

    if job_status == "failed" or preparation_status == "failed":
        return RESULT_STATE_FAILED
    if corpus_ref is None and not _has_concrete_document_identity(job):
        return RESULT_STATE_LEGACY_UNTRACKED
    if (
        job_status in {"pending", "running"}
        or preparation.get("active")
        or preparation_status in {"not_started", "running"}
    ):
        return RESULT_STATE_PREPARING
    if staleness_reasons:
        return RESULT_STATE_STALE
    return RESULT_STATE_READY


def _build_manifest_links(job_id: str, consumer_key: str) -> AnalysisResultLinks:
    query = f"?consumer_key={consumer_key}"
    return AnalysisResultLinks(
        page_url=f"/v1/presenter/page/{job_id}{query}",
        presentation_url=f"/v1/results/by-job/{job_id}/presentation{query}",
        manifest_url=f"/v1/results/by-job/{job_id}{query}",
        trace_url=f"/v1/presenter/trace/{job_id}{query}",
        refresh_presentation_url=f"/v1/results/by-job/{job_id}/refresh-presentation{query}",
    )


def _compute_restore(
    *,
    result_state: str,
    preparation_status: str,
    job_status: str,
) -> tuple[bool, str]:
    """Compute restore_available and restore_reason.

    restore_available is true only when analyzer-v2 can return a prepared
    presentation from GET /v1/results/by-job/{job_id}/presentation.

    restore_reason uses stable enum-like codes:
      presentation_ready  - prepared and servable
      presentation_stale  - prepared but stale (still servable)
      legacy_untracked    - legacy/imported job without product tracking
      not_prepared        - preparation has not run
      preparing           - preparation in progress
      failed              - job or preparation failed
    """
    if job_status == "failed" or result_state == RESULT_STATE_FAILED:
        return False, RESTORE_REASON_FAILED
    if result_state == RESULT_STATE_LEGACY_UNTRACKED:
        return False, RESTORE_REASON_LEGACY_UNTRACKED
    if result_state == RESULT_STATE_STALE:
        return False, RESTORE_REASON_PRESENTATION_STALE
    if preparation_status == "completed":
        return True, RESTORE_REASON_PRESENTATION_READY
    if preparation_status == "running" or result_state == RESULT_STATE_PREPARING:
        return False, RESTORE_REASON_PREPARING
    if preparation_status == "failed":
        return False, RESTORE_REASON_FAILED
    return False, RESTORE_REASON_NOT_PREPARED


def build_result_manifest(
    job_id: str,
    *,
    consumer_key: str = DEFAULT_CONSUMER_KEY,
) -> AnalysisResultManifest:
    job = get_job(job_id)
    if job is None:
        raise ValueError(f"Job not found: {job_id}")

    corpus_ref = lookup_job_corpus(job_id)
    plan_context = load_effective_plan_context(job_id, job.get("plan_id", ""))
    preparation = get_preparation_state(job_id)
    presenter_manifest = None
    freshness = _fallback_freshness()

    if preparation.get("status") == "completed":
        try:
            presenter_manifest = build_presentation_manifest(
                job_id,
                consumer_key=consumer_key,
                slim=True,
                read_only=True,
            )
            freshness = {
                "presentation_contract_version": presenter_manifest.presentation_contract_version,
                "presentation_hash": presenter_manifest.presentation_hash,
                "presentation_content_hash": presenter_manifest.presentation_content_hash,
                "prepared_at": presenter_manifest.prepared_at,
                "artifacts_ready": presenter_manifest.artifacts_ready,
            }
        except Exception:
            presenter_manifest = None
            freshness = _fallback_freshness()

    artifact_families = summarize_job_artifacts(
        job_id,
        preparation_status=preparation.get("status"),
        ensure_corpus=False,
    )
    if presenter_manifest is None:
        freshness["artifacts_ready"] = all(
            family.get("state") == RESULT_STATE_READY for family in artifact_families
        ) if artifact_families else False
    freshness = _merge_artifact_freshness(freshness, artifact_families)

    staleness_reasons = _collect_staleness_reasons(
        job=job,
        corpus_ref=corpus_ref,
        plan_context_source=plan_context.source,
        preparation=preparation,
        artifact_families=artifact_families,
    )
    product_warnings = _collect_product_warnings(
        job=job,
        corpus_ref=corpus_ref,
        preparation=preparation,
    )
    result_state = _determine_result_state(
        job=job,
        corpus_ref=corpus_ref,
        preparation=preparation,
        staleness_reasons=staleness_reasons,
    )

    restore_available, restore_reason = _compute_restore(
        result_state=result_state,
        preparation_status=preparation.get("status", "not_started"),
        job_status=job.get("status", ""),
    )

    return AnalysisResultManifest(
        job_id=job_id,
        plan_id=job.get("plan_id", ""),
        workflow_key=job.get("workflow_key", ""),
        consumer_key=consumer_key,
        result_id=_stable_result_id(job_id, consumer_key),
        result_state=result_state,
        corpus_ref=corpus_ref,
        status=job.get("status", ""),
        presentation_contract_version=freshness["presentation_contract_version"],
        presentation_hash=freshness["presentation_hash"],
        presentation_content_hash=freshness["presentation_content_hash"],
        prepared_at=freshness["prepared_at"],
        artifacts_ready=freshness["artifacts_ready"],
        presentation_status=preparation.get("status", "not_started"),
        preparation_detail=preparation.get("detail", ""),
        presentation_active=bool(preparation.get("active")),
        restore_available=restore_available,
        restore_reason=restore_reason,
        staleness_reasons=staleness_reasons,
        product_warnings=product_warnings,
        links=_build_manifest_links(job_id, consumer_key),
        artifact_families=artifact_families,
    )


def get_result_presentation(
    job_id: str,
    *,
    consumer_key: str = DEFAULT_CONSUMER_KEY,
) -> AnalysisResultPresentationResponse:
    manifest = build_result_manifest(job_id, consumer_key=consumer_key)
    presentation = None

    if manifest.restore_available and manifest.presentation_status == "completed":
        page = assemble_page(
            job_id,
            consumer_key=consumer_key,
            read_only=True,
        )
        presentation = page.model_copy(
            update={
                "presentation_contract_version": manifest.presentation_contract_version,
                "presentation_hash": manifest.presentation_hash,
                "presentation_content_hash": manifest.presentation_content_hash,
                "prepared_at": manifest.prepared_at,
                "artifacts_ready": manifest.artifacts_ready,
            }
        )

    return AnalysisResultPresentationResponse(
        job_id=job_id,
        consumer_key=consumer_key,
        manifest=manifest,
        presentation=presentation,
    )


def refresh_presentation_result(
    job_id: str,
    *,
    consumer_key: str = DEFAULT_CONSUMER_KEY,
) -> RefreshPresentationResponse:
    job = get_job(job_id)
    if job is None:
        raise ValueError(f"Job not found: {job_id}")

    run_presentation_pipeline_sync(
        job_id,
        job.get("plan_id", ""),
        consumer_key=consumer_key,
        force=True,
        wait_if_active=True,
    )
    manifest = build_result_manifest(job_id, consumer_key=consumer_key)
    response = get_result_presentation(job_id, consumer_key=consumer_key)
    page = response.presentation
    if page is None:
        raise ValueError(f"No prepared presentation available for job: {job_id}")
    return RefreshPresentationResponse(
        job_id=job_id,
        consumer_key=consumer_key,
        refreshed=True,
        manifest=manifest,
        presentation=page,
    )


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def _extract_thinker_fields(job: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """Extract selected_source_thinker_id/name from plan_data if available."""
    plan_data = job.get("plan_data")
    if not isinstance(plan_data, dict):
        return None, None
    if plan_data.get("_type") == "request_snapshot":
        merged = dict(plan_data.get("plan_request") or {})
        for key, value in (plan_data.get("request_options") or {}).items():
            if key not in merged and value is not None:
                merged[key] = value
        plan_data = merged
    return (
        plan_data.get("selected_source_thinker_id"),
        plan_data.get("selected_source_thinker_name"),
    )


def build_discovery_summaries(
    *,
    project_id: str,
    workflow_key: Optional[str] = None,
    consumer_key: str = DEFAULT_CONSUMER_KEY,
    selected_source_thinker_id: Optional[str] = None,
    limit: int = 50,
) -> list[DiscoverySummary]:
    """List discoverable completed results as lightweight summaries.

    Queries executor_jobs for completed jobs matching the filters, builds
    a manifest for each (without assembling any pages), and returns
    discovery summaries sorted by completed_at DESC, created_at DESC.
    """
    from src.executor.job_manager import list_completed_jobs

    if not project_id.strip():
        raise ValueError("project_id is required")

    source_limit = limit
    if selected_source_thinker_id:
        source_limit = max(limit * 5, 200)

    jobs = list_completed_jobs(
        project_id=project_id,
        workflow_key=workflow_key,
        limit=source_limit,
    )

    summaries: list[DiscoverySummary] = []
    for job in jobs:
        job_id = job["job_id"]

        # Filter by thinker if requested (requires reading plan_data)
        thinker_id, thinker_name = _extract_thinker_fields(job)
        if selected_source_thinker_id and thinker_id != selected_source_thinker_id:
            continue

        try:
            manifest = build_result_manifest(job_id, consumer_key=consumer_key)
        except Exception:
            logger.warning("Discovery: skipping job %s (manifest build failed)", job_id)
            continue

        summaries.append(DiscoverySummary(
            job_id=job_id,
            result_id=manifest.result_id,
            project_id=job.get("project_id"),
            workflow_key=manifest.workflow_key,
            mode="v2_presentation",
            status=manifest.status,
            result_state=manifest.result_state,
            presentation_status=manifest.presentation_status,
            prepared_at=manifest.prepared_at,
            completed_at=job.get("completed_at") or job.get("created_at") or "",
            restore_available=manifest.restore_available,
            restore_reason=manifest.restore_reason,
            selected_source_thinker_id=thinker_id,
            selected_source_thinker_name=thinker_name,
            links=manifest.links,
        ))
        if len(summaries) >= limit:
            break

    return summaries


# ---------------------------------------------------------------------------
# Attach project
# ---------------------------------------------------------------------------


def attach_project_to_job(job_id: str, project_id: str) -> AttachProjectResponse:
    """Attach a project_id to an existing job.

    - If project_id is null on the job, sets it.
    - If it already matches, returns success (idempotent).
    - If it points to a different project, raises ValueError.
    """
    from src.executor.job_manager import get_job as _get_job, set_job_project_id

    job = _get_job(job_id)
    if job is None:
        raise ValueError(f"Job not found: {job_id}")

    normalized_project_id = project_id.strip()
    if not normalized_project_id:
        raise ValueError("project_id is required")

    current = job.get("project_id")
    if current == normalized_project_id:
        return AttachProjectResponse(
            job_id=job_id,
            project_id=normalized_project_id,
            attached=False,
            idempotent=True,
        )

    if current is not None and current != normalized_project_id:
        raise ConflictError(
            f"Job {job_id} is already attached to project {current}, "
            f"cannot re-attach to {normalized_project_id}"
        )

    set_job_project_id(job_id, normalized_project_id)
    return AttachProjectResponse(
        job_id=job_id,
        project_id=normalized_project_id,
        attached=True,
        idempotent=False,
    )


class ConflictError(Exception):
    """Raised when a project attachment conflicts with an existing one."""
