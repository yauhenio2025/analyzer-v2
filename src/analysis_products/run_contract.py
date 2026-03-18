"""Consumer-facing live-run contract and discovery helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from src.analysis_products.result_contract import (
    DEFAULT_CONSUMER_KEY,
    _compute_restore,
    _determine_result_state,
    _extract_thinker_fields,
)
from src.analysis_products.schemas import RunDetail, RunLinks, RunProgress, RunSummary
from src.analysis_products.store import lookup_job_corpus, lookup_job_corpora, summarize_jobs_artifacts
from src.executor.db import _json_loads, execute
from src.executor.job_manager import get_job
from src.executor.plan_context import load_effective_plan_context
from src.presenter.preparation_coordinator import get_preparation_state, is_presentation_active
from src.presenter.preparation_store import load_presentation_runs

RUN_SCOPE_ACTIVE = "active"
RUN_SCOPE_RECENT = "recent"
RUN_SCOPE_ALL = "all"
RUN_SCOPES = {RUN_SCOPE_ACTIVE, RUN_SCOPE_RECENT, RUN_SCOPE_ALL}

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
ACTIVE_STATUSES = {"pending", "running"}


def _as_timestamp(value: Any) -> Optional[str]:
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None or isinstance(value, str):
        return value
    return str(value)


def _normalize_job_row(row: dict[str, Any]) -> dict[str, Any]:
    for field in ("progress", "plan_data"):
        value = row.get(field)
        if isinstance(value, str):
            row[field] = _json_loads(value)
    for field in ("created_at", "started_at", "completed_at"):
        row[field] = _as_timestamp(row.get(field))
    return row


def _build_run_links(job_id: str, consumer_key: str) -> RunLinks:
    query = f"?consumer_key={consumer_key}"
    return RunLinks(
        result_url=f"/v1/results/by-job/{job_id}{query}",
        presentation_url=f"/v1/results/by-job/{job_id}/presentation{query}",
    )


def _build_progress(progress: Optional[dict[str, Any]]) -> RunProgress:
    progress = progress if isinstance(progress, dict) else {}
    current_phase = progress.get("current_phase", 0) or 0
    total_phases = progress.get("total_phases", 0) or 0
    phase_name = progress.get("phase_name", "") or ""
    return RunProgress(
        current_phase=current_phase,
        total_phases=total_phases,
        phase_name=phase_name,
        detail=progress.get("detail", "") or "",
        completed_phases=list(progress.get("completed_phases") or []),
        phase_statuses=dict(progress.get("phase_statuses") or {}),
        structured_detail=progress.get("structured_detail")
        if isinstance(progress.get("structured_detail"), dict)
        else None,
        current_pass=current_phase,
        total_passes=total_phases,
        current_pass_name=phase_name,
    )


def _batched_preparation_states(job_ids: list[str]) -> dict[str, dict[str, Any]]:
    stored = load_presentation_runs(job_ids)
    states: dict[str, dict[str, Any]] = {}
    for job_id in job_ids:
        state = stored.get(job_id) or {
            "job_id": job_id,
            "status": "not_started",
            "detail": "",
            "stats": {},
            "error": None,
            "started_at": None,
            "updated_at": None,
            "completed_at": None,
        }
        state["active"] = is_presentation_active(job_id)
        states[job_id] = state
    return states


def _derive_result_transition(
    *,
    job: dict[str, Any],
    consumer_key: str,
    corpus_ref: Optional[str],
    preparation: dict[str, Any],
    artifact_families: list[dict[str, Any]],
) -> tuple[str, bool, str]:
    plan_context = load_effective_plan_context(job.get("job_id", ""), job.get("plan_id", ""))
    staleness_reasons: list[str] = []
    if any(family.get("state") in {"pending", "unavailable"} for family in artifact_families):
        staleness_reasons.append("artifacts_not_ready")
    if any(family.get("state") == "stale" for family in artifact_families):
        staleness_reasons.append("artifact_producer_drift")
    if corpus_ref is None:
        staleness_reasons.append("missing_corpus_ref")
    if plan_context.source == "missing":
        staleness_reasons.append("missing_plan_context")
    preparation_status = preparation.get("status", "not_started")
    if preparation_status == "not_started":
        staleness_reasons.append("preparation_not_run")
    elif preparation_status == "failed":
        staleness_reasons.append("preparation_failed")

    result_state = _determine_result_state(
        job=job,
        corpus_ref=corpus_ref,
        preparation=preparation,
        staleness_reasons=staleness_reasons,
    )
    restore_available, restore_reason = _compute_restore(
        result_state=result_state,
        preparation_status=preparation_status,
        job_status=job.get("status", ""),
    )
    return result_state, restore_available, restore_reason


def _to_run_summary(
    *,
    job: dict[str, Any],
    consumer_key: str,
    corpus_ref: Optional[str],
    preparation: dict[str, Any],
    artifact_families: list[dict[str, Any]],
) -> RunSummary:
    thinker_id, thinker_name = _extract_thinker_fields(job)
    result_state, restore_available, restore_reason = _derive_result_transition(
        job=job,
        consumer_key=consumer_key,
        corpus_ref=corpus_ref,
        preparation=preparation,
        artifact_families=artifact_families,
    )
    return RunSummary(
        job_id=job.get("job_id", ""),
        plan_id=job.get("plan_id", ""),
        project_id=job.get("project_id"),
        workflow_key=job.get("workflow_key", ""),
        consumer_key=consumer_key,
        status=job.get("status", ""),
        created_at=_as_timestamp(job.get("created_at")) or "",
        started_at=_as_timestamp(job.get("started_at")),
        completed_at=_as_timestamp(job.get("completed_at")),
        error=job.get("error"),
        progress=_build_progress(job.get("progress")),
        presentation_status=preparation.get("status", "not_started"),
        presentation_active=bool(preparation.get("active")),
        result_state=result_state,
        restore_available=restore_available,
        restore_reason=restore_reason,
        selected_source_thinker_id=thinker_id,
        selected_source_thinker_name=thinker_name,
        links=_build_run_links(job.get("job_id", ""), consumer_key),
    )


def build_run_detail(
    job_id: str,
    *,
    consumer_key: str = DEFAULT_CONSUMER_KEY,
) -> RunDetail:
    job = get_job(job_id)
    if job is None:
        raise ValueError(f"Job not found: {job_id}")

    preparation = get_preparation_state(job_id)
    corpus_ref = lookup_job_corpus(job_id)
    artifact_families = summarize_jobs_artifacts(
        [job_id],
        jobs_by_id={job_id: job},
        preparation_statuses={job_id: preparation.get("status")},
        ensure_corpus=False,
    ).get(job_id, [])
    summary = _to_run_summary(
        job=job,
        consumer_key=consumer_key,
        corpus_ref=corpus_ref,
        preparation=preparation,
        artifact_families=artifact_families,
    )
    return RunDetail(**summary.model_dump())


def _load_jobs_for_discovery(
    *,
    project_id: str,
    workflow_key: Optional[str],
    scope: str,
    limit: int,
) -> list[dict[str, Any]]:
    conditions = ["project_id = %s"]
    params: list[Any] = [project_id]

    if workflow_key:
        conditions.append("workflow_key = %s")
        params.append(workflow_key)

    if scope == RUN_SCOPE_ACTIVE:
        conditions.append("status IN ('pending', 'running')")
        order_by = "created_at DESC"
    elif scope == RUN_SCOPE_RECENT:
        conditions.append("status IN ('completed', 'failed', 'cancelled')")
        order_by = "completed_at DESC, created_at DESC"
    else:
        order_by = "created_at DESC"

    params.append(limit)
    rows = execute(
        f"""SELECT job_id, plan_id, status, progress, error, workflow_key, project_id,
                   plan_data, created_at, started_at, completed_at
            FROM executor_jobs
            WHERE {' AND '.join(conditions)}
            ORDER BY {order_by}
            LIMIT %s""",
        tuple(params),
        fetch="all",
    )
    return [_normalize_job_row(row) for row in rows]


def build_run_discovery(
    *,
    project_id: str,
    workflow_key: Optional[str] = None,
    consumer_key: str = DEFAULT_CONSUMER_KEY,
    scope: str = RUN_SCOPE_ACTIVE,
    limit: int = 20,
    selected_source_thinker_id: Optional[str] = None,
) -> list[RunSummary]:
    if not project_id.strip():
        raise ValueError("project_id is required")
    if scope not in RUN_SCOPES:
        raise ValueError(f"Unsupported scope: {scope}")

    jobs = _load_jobs_for_discovery(
        project_id=project_id,
        workflow_key=workflow_key,
        scope=scope,
        limit=limit * 5 if selected_source_thinker_id else limit,
    )
    if selected_source_thinker_id:
        filtered: list[dict[str, Any]] = []
        for job in jobs:
            thinker_id, _ = _extract_thinker_fields(job)
            if thinker_id == selected_source_thinker_id:
                filtered.append(job)
            if len(filtered) >= limit:
                break
        jobs = filtered
    else:
        jobs = jobs[:limit]

    job_ids = [job["job_id"] for job in jobs]
    preparation_states = _batched_preparation_states(job_ids)
    corpus_by_job = lookup_job_corpora(job_ids)
    artifact_summaries = summarize_jobs_artifacts(
        job_ids,
        jobs_by_id={job["job_id"]: job for job in jobs},
        preparation_statuses={
            job_id: preparation_states.get(job_id, {}).get("status")
            for job_id in job_ids
        },
        ensure_corpus=False,
    )

    return [
        _to_run_summary(
            job=job,
            consumer_key=consumer_key,
            corpus_ref=corpus_by_job.get(job["job_id"]),
            preparation=preparation_states.get(job["job_id"], {"status": "not_started", "active": False}),
            artifact_families=artifact_summaries.get(job["job_id"], []),
        )
        for job in jobs
    ]
