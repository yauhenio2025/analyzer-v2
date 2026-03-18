"""Stage 1 analysis-product registry helpers.

This module adds a narrow product layer above phase_outputs without
displacing the executor ledger. Stage 1 keeps identity mixed:

- corpus_ref identifies a concretized document set plus qualifiers
- artifact_ref identifies a logical artifact slot under a corpus
- job_id remains the primary consumer lookup key for manifests
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Optional

from src.aoi.constants import AOI_WORKFLOW_KEY
from src.executor.db import _json_dumps, _json_loads, execute, init_db
from src.presenter.work_key_utils import sanitize_work_key_for_presenter

GENEALOGY_WORKFLOW_KEY = "intellectual_genealogy"

AOI_ARTIFACT_FAMILY_BY_ENGINE = {
    "aoi_thematic_synthesis": "aoi.source_thematic_map",
    "aoi_engagement_mapping": "aoi.engagement_map",
    "aoi_sin_findings": "aoi.findings_bank",
}

AOI_ARTIFACT_PRODUCER_FINGERPRINTS = {
    "aoi.source_thematic_map": "aoi.source_thematic_map:v1",
    "aoi.engagement_map": "aoi.engagement_map:v1",
    "aoi.findings_bank": "aoi.findings_bank:v1",
}

GENEALOGY_RELATIONSHIP_ARTIFACT_FAMILY = "genealogy.relationship_classification"
GENEALOGY_RELATIONSHIP_FINGERPRINT = "genealogy.relationship_classification:v1"

ARTIFACT_STATE_READY = "ready"
ARTIFACT_STATE_PENDING = "pending"
ARTIFACT_STATE_STALE = "stale"
ARTIFACT_STATE_UNAVAILABLE = "unavailable"
ARTIFACT_STATES = {
    ARTIFACT_STATE_READY,
    ARTIFACT_STATE_PENDING,
    ARTIFACT_STATE_STALE,
    ARTIFACT_STATE_UNAVAILABLE,
}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _stable_hash(value: Any) -> str:
    serialized = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _normalize_json(value: Any) -> Any:
    if isinstance(value, str):
        return _json_loads(value)
    return value


def _normalize_plan_data(plan_data: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(plan_data, dict):
        return {}

    if plan_data.get("_type") == "request_snapshot":
        merged = dict(plan_data.get("plan_request") or {})
        request_options = plan_data.get("request_options") or {}
        for key, value in request_options.items():
            if key not in merged and value is not None:
                merged[key] = value
        return merged

    return dict(plan_data)


def _normalize_document_ids(document_ids: Any) -> dict[str, str]:
    if isinstance(document_ids, str):
        parsed = _json_loads(document_ids)
        return parsed if isinstance(parsed, dict) else {}
    return document_ids if isinstance(document_ids, dict) else {}


def _artifact_ref(corpus_ref: str, artifact_family: str, artifact_slot: str) -> str:
    digest = _stable_hash(
        {
            "corpus_ref": corpus_ref,
            "artifact_family": artifact_family,
            "artifact_slot": artifact_slot,
        }
    )[:24]
    return f"artifact-{digest}"


def _extract_workflow_identity(
    plan_data: dict[str, Any],
    workflow_key: Optional[str],
    objective_key: Optional[str],
) -> tuple[str, Optional[str]]:
    resolved_workflow = workflow_key or plan_data.get("workflow_key") or GENEALOGY_WORKFLOW_KEY
    resolved_objective = objective_key or plan_data.get("objective_key")
    return resolved_workflow, resolved_objective


def _chapter_members(document_ids: dict[str, str], work_key: str) -> list[dict[str, Any]]:
    prefix = f"chapter:{work_key}:"
    members: list[dict[str, Any]] = []
    for doc_key, doc_id in sorted(document_ids.items()):
        if not doc_key.startswith(prefix):
            continue
        chapter_id = doc_key[len(prefix):]
        members.append(
            {
                "role": "chapter",
                "doc_key": doc_key,
                "document_id": doc_id,
                "chapter_id": chapter_id,
            }
        )
    return members


def _load_document_content_hash(document_id: str) -> Optional[str]:
    from src.executor.document_store import get_document

    row = get_document(document_id)
    if not row:
        return None
    stored_hash = row.get("content_hash")
    if stored_hash:
        return stored_hash
    content = row.get("text") or ""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _member_sort_key(member: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        member.get("role") or "",
        member.get("source_document_id") or member.get("doc_key") or member.get("title") or "",
        member.get("chapter_id") or "",
        member.get("title") or "",
    )


def _member_fingerprint(member: dict[str, Any]) -> dict[str, Any]:
    document_id = member.get("document_id") or ""
    content_hash = _load_document_content_hash(document_id) if document_id else None
    fingerprint = {
        "role": member.get("role") or "",
        "doc_key": member.get("doc_key") or "",
        "title": member.get("title") or "",
        "author": member.get("author") or "",
        "year": member.get("year"),
        "chapter_id": member.get("chapter_id") or "",
        "source_document_id": member.get("source_document_id") or "",
        "source_thinker_id": member.get("source_thinker_id") or "",
        "source_thinker_name": member.get("source_thinker_name") or "",
    }
    if content_hash:
        fingerprint["content_hash"] = content_hash
    return fingerprint


def _build_aoi_corpus_payload(
    plan_data: dict[str, Any],
    document_ids: dict[str, str],
    objective_key: Optional[str],
) -> Optional[dict[str, Any]]:
    target_work = plan_data.get("target_work") or {}
    prior_works = list(plan_data.get("prior_works") or [])
    selected_source_thinker_id = plan_data.get("selected_source_thinker_id")
    selected_source_thinker_name = plan_data.get("selected_source_thinker_name")

    if (
        not target_work
        or not prior_works
        or not selected_source_thinker_id
        or not selected_source_thinker_name
    ):
        return None

    members: list[dict[str, Any]] = []
    target_doc_id = document_ids.get("target")
    if not target_doc_id:
        return None

    members.append(
        {
            "role": "target",
            "doc_key": "target",
            "document_id": target_doc_id,
            "title": target_work.get("title") or "",
            "author": target_work.get("author") or "",
        }
    )
    members.extend(_chapter_members(document_ids, "target"))

    matching_prior_works = [
        work
        for work in prior_works
        if work.get("source_thinker_id") == selected_source_thinker_id
        and work.get("source_thinker_name") == selected_source_thinker_name
        and work.get("source_document_id")
    ]
    if not matching_prior_works:
        return None

    for work in sorted(matching_prior_works, key=lambda row: row.get("source_document_id") or row.get("title") or ""):
        doc_key = work.get("title") or ""
        doc_id = document_ids.get(doc_key)
        if not doc_id:
            return None
        members.append(
            {
                "role": "source_prior_work",
                "doc_key": doc_key,
                "document_id": doc_id,
                "title": work.get("title") or "",
                "author": work.get("author") or "",
                "year": work.get("year"),
                "source_document_id": work.get("source_document_id"),
                "source_thinker_id": work.get("source_thinker_id"),
                "source_thinker_name": work.get("source_thinker_name"),
            }
        )
        members.extend(_chapter_members(document_ids, doc_key))

    qualifiers = {
        "workflow_key": AOI_WORKFLOW_KEY,
        "objective_key": objective_key,
        "selected_source_thinker_id": selected_source_thinker_id,
        "selected_source_thinker_name": selected_source_thinker_name,
    }
    sorted_members = sorted(members, key=_member_sort_key)
    return {
        "members": sorted_members,
        "fingerprint_members": [_member_fingerprint(member) for member in sorted_members],
        "qualifiers": qualifiers,
    }


def _build_genealogy_corpus_payload(
    plan_data: dict[str, Any],
    document_ids: dict[str, str],
    workflow_key: str,
    objective_key: Optional[str],
) -> Optional[dict[str, Any]]:
    target_work = plan_data.get("target_work") or {}
    prior_works = list(plan_data.get("prior_works") or [])
    target_doc_id = document_ids.get("target")
    if not target_work or not target_doc_id or not prior_works:
        return None

    members: list[dict[str, Any]] = [
        {
            "role": "target",
            "doc_key": "target",
            "document_id": target_doc_id,
            "title": target_work.get("title") or "",
            "author": target_work.get("author") or "",
        }
    ]
    members.extend(_chapter_members(document_ids, "target"))

    normalized_prior: list[dict[str, Any]] = []
    for work in prior_works:
        title = work.get("title") or ""
        if not title:
            continue
        doc_id = document_ids.get(title)
        if not doc_id:
            return None
        normalized_prior.append(
            {
                "role": "prior_work",
                "doc_key": title,
                "document_id": doc_id,
                "title": title,
                "author": work.get("author") or "",
                "year": work.get("year"),
                "source_document_id": work.get("source_document_id"),
            }
        )
        members.extend(_chapter_members(document_ids, title))

    if not normalized_prior:
        return None

    members.extend(sorted(normalized_prior, key=lambda row: (row.get("title") or "", row.get("year") or 0)))
    qualifiers = {
        "workflow_key": workflow_key,
        "objective_key": objective_key,
    }
    sorted_members = sorted(members, key=_member_sort_key)
    return {
        "members": sorted_members,
        "fingerprint_members": [_member_fingerprint(member) for member in sorted_members],
        "qualifiers": qualifiers,
    }


def build_corpus_registration(
    *,
    plan_data: Optional[dict[str, Any]],
    document_ids: Any,
    workflow_key: Optional[str] = None,
    objective_key: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Build a deterministic corpus registration payload for supported workflows."""

    normalized_plan = _normalize_plan_data(plan_data)
    normalized_doc_ids = _normalize_document_ids(document_ids)
    if not normalized_plan or not normalized_doc_ids:
        return None

    resolved_workflow, resolved_objective = _extract_workflow_identity(
        normalized_plan,
        workflow_key,
        objective_key,
    )

    if resolved_workflow == AOI_WORKFLOW_KEY:
        payload = _build_aoi_corpus_payload(normalized_plan, normalized_doc_ids, resolved_objective)
    elif resolved_workflow == GENEALOGY_WORKFLOW_KEY:
        payload = _build_genealogy_corpus_payload(
            normalized_plan,
            normalized_doc_ids,
            resolved_workflow,
            resolved_objective,
        )
    else:
        payload = None

    if not payload:
        return None

    fingerprint = {
        "workflow_key": resolved_workflow,
        "objective_key": resolved_objective,
        "qualifiers": payload["qualifiers"],
        "members": payload["fingerprint_members"],
    }
    corpus_ref = f"corp-{_stable_hash(fingerprint)[:24]}"
    return {
        "corpus_ref": corpus_ref,
        "workflow_key": resolved_workflow,
        "objective_key": resolved_objective,
        "member_manifest": payload["members"],
        "qualifiers": payload["qualifiers"],
    }


def register_job_corpus(
    job_id: str,
    *,
    plan_data: Optional[dict[str, Any]],
    document_ids: Any,
    workflow_key: Optional[str] = None,
    objective_key: Optional[str] = None,
) -> Optional[str]:
    """Register a corpus for a concretized run and attach it to the job."""

    init_db()
    registration = build_corpus_registration(
        plan_data=plan_data,
        document_ids=document_ids,
        workflow_key=workflow_key,
        objective_key=objective_key,
    )
    if registration is None:
        return None

    now = _now_iso()
    execute(
        """INSERT INTO analysis_corpora
           (corpus_ref, workflow_key, objective_key, member_manifest, qualifiers, created_at, updated_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (corpus_ref) DO UPDATE SET
             workflow_key = EXCLUDED.workflow_key,
             objective_key = EXCLUDED.objective_key,
             member_manifest = EXCLUDED.member_manifest,
             qualifiers = EXCLUDED.qualifiers,
             updated_at = EXCLUDED.updated_at""",
        (
            registration["corpus_ref"],
            registration["workflow_key"],
            registration["objective_key"],
            _json_dumps(registration["member_manifest"]),
            _json_dumps(registration["qualifiers"]),
            now,
            now,
        ),
    )
    execute(
        "UPDATE executor_jobs SET corpus_ref = %s WHERE job_id = %s",
        (registration["corpus_ref"], job_id),
    )
    return registration["corpus_ref"]


def ensure_job_corpus(job_id: str) -> Optional[str]:
    """Attach a corpus_ref to a supported job if enough context exists."""

    from src.executor.job_manager import get_job

    job = get_job(job_id)
    if not job:
        return None

    existing = job.get("corpus_ref")
    if existing:
        return existing

    return register_job_corpus(
        job_id,
        plan_data=job.get("plan_data"),
        document_ids=job.get("document_ids"),
        workflow_key=job.get("workflow_key"),
    )


def lookup_job_corpus(job_id: str) -> Optional[str]:
    """Return the current corpus_ref for a job without mutating state."""

    from src.executor.job_manager import get_job

    job = get_job(job_id)
    if not job:
        return None
    return job.get("corpus_ref")


def lookup_job_corpora(job_ids: list[str]) -> dict[str, str]:
    """Return corpus_ref values for multiple jobs without mutating state."""
    if not job_ids:
        return {}

    placeholders = ", ".join(["%s"] * len(job_ids))
    rows = execute(
        f"""SELECT job_id, corpus_ref
            FROM executor_jobs
            WHERE job_id IN ({placeholders})
              AND corpus_ref IS NOT NULL""",
        tuple(job_ids),
        fetch="all",
    )
    return {
        row["job_id"]: row["corpus_ref"]
        for row in rows
        if row.get("job_id") and row.get("corpus_ref")
    }


def _parse_artifact_row(row: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    for field in ("payload_json", "depends_on"):
        value = row.get(field)
        if isinstance(value, str):
            row[field] = _json_loads(value)
        elif value is None and field == "depends_on":
            row[field] = []
    return row


def upsert_analysis_artifact(
    *,
    job_id: str,
    artifact_family: str,
    artifact_slot: str = "default",
    format: str,
    payload_json: Optional[dict[str, Any]] = None,
    payload_text: str = "",
    depends_on: Optional[list[str]] = None,
    engine_key: str = "",
    phase_number: Optional[float] = None,
    source_output_id: str = "",
    producer_fingerprint: str,
    state: str = ARTIFACT_STATE_READY,
) -> Optional[dict[str, Any]]:
    """Persist or update a Stage 1 artifact row."""

    if state not in ARTIFACT_STATES:
        raise ValueError(f"Unsupported artifact state: {state}")

    corpus_ref = ensure_job_corpus(job_id)
    if not corpus_ref:
        return None

    artifact_ref = _artifact_ref(corpus_ref, artifact_family, artifact_slot)
    payload_hash = _stable_hash(
        {
            "format": format,
            "payload_json": payload_json or {},
            "payload_text": payload_text or "",
            "producer_fingerprint": producer_fingerprint,
        }
    )
    now = _now_iso()

    execute("DELETE FROM analysis_artifacts WHERE artifact_ref = %s", (artifact_ref,))
    execute(
        """INSERT INTO analysis_artifacts
           (artifact_ref, corpus_ref, artifact_family, artifact_slot, format,
            payload_json, payload_text, depends_on, job_id, engine_key, phase_number,
            source_output_id, payload_hash, producer_fingerprint, state, created_at, updated_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            artifact_ref,
            corpus_ref,
            artifact_family,
            artifact_slot,
            format,
            _json_dumps(payload_json or {}),
            payload_text or "",
            _json_dumps(depends_on or []),
            job_id,
            engine_key,
            phase_number,
            source_output_id,
            payload_hash,
            producer_fingerprint,
            state,
            now,
            now,
        ),
    )
    return load_analysis_artifact(corpus_ref=corpus_ref, artifact_family=artifact_family, artifact_slot=artifact_slot)


def load_analysis_artifact(
    *,
    corpus_ref: str,
    artifact_family: str,
    artifact_slot: str = "default",
) -> Optional[dict[str, Any]]:
    init_db()
    row = execute(
        """SELECT *
           FROM analysis_artifacts
           WHERE corpus_ref = %s AND artifact_family = %s AND artifact_slot = %s
           ORDER BY updated_at DESC, created_at DESC
           LIMIT 1""",
        (corpus_ref, artifact_family, artifact_slot),
        fetch="one",
    )
    return _parse_artifact_row(row)


def load_job_artifact(
    job_id: str,
    artifact_family: str,
    artifact_slot: str = "default",
    *,
    ensure_corpus: bool = True,
) -> Optional[dict[str, Any]]:
    corpus_ref = ensure_job_corpus(job_id) if ensure_corpus else lookup_job_corpus(job_id)
    if not corpus_ref:
        return None
    return load_analysis_artifact(
        corpus_ref=corpus_ref,
        artifact_family=artifact_family,
        artifact_slot=artifact_slot,
    )


def list_job_artifacts(job_id: str, *, ensure_corpus: bool = True) -> list[dict[str, Any]]:
    """List latest artifact rows for the job's corpus."""

    corpus_ref = ensure_job_corpus(job_id) if ensure_corpus else lookup_job_corpus(job_id)
    if not corpus_ref:
        return []
    rows = execute(
        """SELECT *
           FROM analysis_artifacts
           WHERE corpus_ref = %s
           ORDER BY artifact_family, artifact_slot, updated_at DESC""",
        (corpus_ref,),
        fetch="all",
    )
    seen: set[tuple[str, str]] = set()
    results: list[dict[str, Any]] = []
    for row in rows:
        key = (row.get("artifact_family", ""), row.get("artifact_slot", "default"))
        if key in seen:
            continue
        seen.add(key)
        parsed = _parse_artifact_row(row)
        if parsed is not None:
            results.append(parsed)
    return results


def list_job_artifacts_for_jobs(job_ids: list[str], *, ensure_corpus: bool = False) -> dict[str, list[dict[str, Any]]]:
    """List latest artifact rows for multiple jobs keyed by job_id."""
    if not job_ids:
        return {}

    corpus_by_job = (
        {job_id: ensure_job_corpus(job_id) for job_id in job_ids}
        if ensure_corpus
        else lookup_job_corpora(job_ids)
    )
    corpus_to_jobs: dict[str, list[str]] = {}
    for job_id, corpus_ref in corpus_by_job.items():
        if not corpus_ref:
            continue
        corpus_to_jobs.setdefault(corpus_ref, []).append(job_id)

    results: dict[str, list[dict[str, Any]]] = {job_id: [] for job_id in job_ids}
    for corpus_ref, mapped_job_ids in corpus_to_jobs.items():
        rows = execute(
            """SELECT *
               FROM analysis_artifacts
               WHERE corpus_ref = %s
               ORDER BY artifact_family, artifact_slot, updated_at DESC""",
            (corpus_ref,),
            fetch="all",
        )
        seen: set[tuple[str, str]] = set()
        latest: list[dict[str, Any]] = []
        for row in rows:
            key = (row.get("artifact_family", ""), row.get("artifact_slot", "default"))
            if key in seen:
                continue
            seen.add(key)
            parsed = _parse_artifact_row(row)
            if parsed is not None:
                latest.append(parsed)
        for job_id in mapped_job_ids:
            results[job_id] = [dict(row) for row in latest]
    return results


def record_aoi_artifact_from_metadata(
    *,
    job_id: str,
    phase_number: float,
    engine_key: str,
    source_output_id: str,
    output_metadata: Optional[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Persist normalized AOI outputs as Stage 1 structured artifacts."""

    if not output_metadata or output_metadata.get("parse_error"):
        return None
    artifact_family = AOI_ARTIFACT_FAMILY_BY_ENGINE.get(engine_key)
    normalized = output_metadata.get("normalized")
    if artifact_family is None or not isinstance(normalized, dict):
        return None

    depends_on: list[str] = []
    if artifact_family == "aoi.engagement_map":
        depends_on = ["aoi.source_thematic_map:default"]
    elif artifact_family == "aoi.findings_bank":
        depends_on = [
            "aoi.source_thematic_map:default",
            "aoi.engagement_map:default",
        ]

    return upsert_analysis_artifact(
        job_id=job_id,
        artifact_family=artifact_family,
        artifact_slot="default",
        format="structured_json",
        payload_json=normalized,
        depends_on=depends_on,
        engine_key=engine_key,
        phase_number=phase_number,
        source_output_id=source_output_id,
        producer_fingerprint=AOI_ARTIFACT_PRODUCER_FINGERPRINTS[artifact_family],
    )


def store_relationship_classification_artifact(
    *,
    job_id: str,
    work_key: str,
    source_output_id: str,
    raw_prose: str,
    structured_card: dict[str, Any],
) -> Optional[dict[str, Any]]:
    """Persist a per-work genealogy relationship artifact."""

    return upsert_analysis_artifact(
        job_id=job_id,
        artifact_family=GENEALOGY_RELATIONSHIP_ARTIFACT_FAMILY,
        artifact_slot=work_key,
        format="annotated_prose",
        payload_json=structured_card,
        payload_text=raw_prose,
        depends_on=[f"phase_output:{source_output_id}"] if source_output_id else [],
        engine_key="genealogy_relationship_classification",
        phase_number=1.5,
        source_output_id=source_output_id,
        producer_fingerprint=GENEALOGY_RELATIONSHIP_FINGERPRINT,
    )


def load_aoi_normalized_artifact(job_id: str, engine_key: str) -> Optional[dict[str, Any]]:
    artifact_family = AOI_ARTIFACT_FAMILY_BY_ENGINE.get(engine_key)
    if artifact_family is None:
        return None
    artifact = load_job_artifact(job_id, artifact_family)
    if artifact is None:
        return None
    payload = artifact.get("payload_json")
    return payload if isinstance(payload, dict) else None


def _expected_genealogy_slots(plan_data: dict[str, Any]) -> list[str]:
    prior_works = plan_data.get("prior_works") or []
    slots = [
        sanitize_work_key_for_presenter(work.get("title") or "")
        for work in prior_works
        if work.get("title")
    ]
    return sorted({slot for slot in slots if slot})


def _current_fingerprint(artifact_family: str) -> str:
    if artifact_family in AOI_ARTIFACT_PRODUCER_FINGERPRINTS:
        return AOI_ARTIFACT_PRODUCER_FINGERPRINTS[artifact_family]
    if artifact_family == GENEALOGY_RELATIONSHIP_ARTIFACT_FAMILY:
        return GENEALOGY_RELATIONSHIP_FINGERPRINT
    return ""


def _slot_state_for_missing(
    *,
    job_status: str,
    preparation_status: Optional[str],
    presenter_derived: bool,
) -> str:
    if job_status in {"pending", "running"}:
        return ARTIFACT_STATE_PENDING
    if presenter_derived and preparation_status in {None, "not_started", "running"}:
        return ARTIFACT_STATE_PENDING
    return ARTIFACT_STATE_UNAVAILABLE


def _expected_artifact_slots(
    *,
    workflow_key: str,
    plan_data: dict[str, Any],
) -> tuple[dict[str, list[str]], set[str]]:
    expected: dict[str, list[str]] = {}
    presenter_derived_families: set[str] = set()
    if workflow_key == AOI_WORKFLOW_KEY:
        expected = {
            "aoi.source_thematic_map": ["default"],
            "aoi.engagement_map": ["default"],
            "aoi.findings_bank": ["default"],
        }
    elif workflow_key == GENEALOGY_WORKFLOW_KEY:
        expected = {
            GENEALOGY_RELATIONSHIP_ARTIFACT_FAMILY: _expected_genealogy_slots(plan_data),
        }
        presenter_derived_families.add(GENEALOGY_RELATIONSHIP_ARTIFACT_FAMILY)
    return expected, presenter_derived_families


def _summarize_artifacts_for_job(
    *,
    job: dict[str, Any],
    stored_artifacts: list[dict[str, Any]],
    preparation_status: Optional[str] = None,
) -> list[dict[str, Any]]:
    plan_data = _normalize_plan_data(job.get("plan_data"))
    workflow_key = job.get("workflow_key") or plan_data.get("workflow_key") or GENEALOGY_WORKFLOW_KEY
    stored_rows = {
        (row.get("artifact_family"), row.get("artifact_slot")): row
        for row in stored_artifacts
    }

    expected, presenter_derived_families = _expected_artifact_slots(
        workflow_key=workflow_key,
        plan_data=plan_data,
    )

    summaries: list[dict[str, Any]] = []
    for family in sorted(expected):
        slots = expected[family] or ["default"]
        slot_rows: list[dict[str, Any]] = []
        ready = pending = stale = unavailable = 0
        presenter_derived = family in presenter_derived_families
        current_fingerprint = _current_fingerprint(family)

        for slot in slots:
            row = stored_rows.get((family, slot))
            if row is None:
                state = _slot_state_for_missing(
                    job_status=job.get("status", "unknown"),
                    preparation_status=preparation_status,
                    presenter_derived=presenter_derived,
                )
                artifact_ref = None
                source_output_id = None
            else:
                artifact_ref = row.get("artifact_ref")
                source_output_id = row.get("source_output_id")
                if current_fingerprint and row.get("producer_fingerprint") != current_fingerprint:
                    state = ARTIFACT_STATE_STALE
                else:
                    state = row.get("state") or ARTIFACT_STATE_READY

            if state == ARTIFACT_STATE_READY:
                ready += 1
            elif state == ARTIFACT_STATE_PENDING:
                pending += 1
            elif state == ARTIFACT_STATE_STALE:
                stale += 1
            else:
                unavailable += 1

            slot_rows.append(
                {
                    "slot": slot,
                    "state": state,
                    "artifact_ref": artifact_ref,
                    "source_output_id": source_output_id,
                }
            )

        if stale:
            family_state = ARTIFACT_STATE_STALE
        elif pending:
            family_state = ARTIFACT_STATE_PENDING
        elif ready == len(slots):
            family_state = ARTIFACT_STATE_READY
        else:
            family_state = ARTIFACT_STATE_UNAVAILABLE

        summaries.append(
            {
                "artifact_family": family,
                "state": family_state,
                "format": (
                    "annotated_prose"
                    if family == GENEALOGY_RELATIONSHIP_ARTIFACT_FAMILY
                    else "structured_json"
                ),
                "total_slots": len(slots),
                "ready_slots": ready,
                "pending_slots": pending,
                "stale_slots": stale,
                "unavailable_slots": unavailable,
                "slots": slot_rows,
            }
        )

    return summaries


def summarize_job_artifacts(
    job_id: str,
    *,
    preparation_status: Optional[str] = None,
    ensure_corpus: bool = True,
) -> list[dict[str, Any]]:
    """Summarize expected Stage 1 artifacts for manifest delivery."""

    from src.executor.job_manager import get_job

    job = get_job(job_id) or {}
    stored_artifacts = list_job_artifacts(job_id, ensure_corpus=ensure_corpus)
    return _summarize_artifacts_for_job(
        job=job,
        stored_artifacts=stored_artifacts,
        preparation_status=preparation_status,
    )


def summarize_jobs_artifacts(
    job_ids: list[str],
    *,
    jobs_by_id: Optional[dict[str, dict[str, Any]]] = None,
    preparation_statuses: Optional[dict[str, Optional[str]]] = None,
    ensure_corpus: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    """Summarize expected Stage 1 artifacts for multiple jobs."""

    from src.executor.job_manager import get_job

    if not job_ids:
        return {}

    job_records = dict(jobs_by_id or {})
    for job_id in job_ids:
        if job_id not in job_records:
            job_records[job_id] = get_job(job_id) or {}

    artifact_rows = list_job_artifacts_for_jobs(job_ids, ensure_corpus=ensure_corpus)
    result: dict[str, list[dict[str, Any]]] = {}
    for job_id in job_ids:
        result[job_id] = _summarize_artifacts_for_job(
            job=job_records.get(job_id) or {},
            stored_artifacts=artifact_rows.get(job_id, []),
            preparation_status=(preparation_statuses or {}).get(job_id),
        )
    return result
