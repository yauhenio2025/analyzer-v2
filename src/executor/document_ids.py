"""Helpers for normalizing executor document-id mappings."""

from typing import Optional


def extract_target_title(plan_data: Optional[dict]) -> Optional[str]:
    """Extract the target-work title from a full plan or request snapshot."""
    if not isinstance(plan_data, dict):
        return None

    target_work = plan_data.get("target_work")
    if isinstance(target_work, dict):
        title = target_work.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()

    plan_request = plan_data.get("plan_request")
    if isinstance(plan_request, dict):
        target_work = plan_request.get("target_work")
        if isinstance(target_work, dict):
            title = target_work.get("title")
            if isinstance(title, str) and title.strip():
                return title.strip()

    return None


def normalize_document_ids(
    document_ids: Optional[dict[str, str]],
    plan_data: Optional[dict] = None,
) -> dict[str, str]:
    """Ensure the canonical `target` alias exists when the plan reveals it."""
    normalized = dict(document_ids or {})
    target_title = extract_target_title(plan_data)
    if not target_title:
        return normalized

    target_doc_id = normalized.get("target") or normalized.get(target_title)
    if target_doc_id:
        normalized["target"] = target_doc_id
        normalized.setdefault(target_title, target_doc_id)

    return normalized


def resolve_target_doc_id(
    document_ids: Optional[dict[str, str]],
    plan_data: Optional[dict] = None,
) -> Optional[str]:
    """Resolve the target document ID from canonical or title-based mappings."""
    return normalize_document_ids(document_ids, plan_data).get("target")
