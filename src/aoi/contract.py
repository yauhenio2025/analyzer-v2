"""Normalization helpers for the bounded AOI thematic workflow."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Optional

from src.llm.client import parse_llm_json_response
from src.taxonomies.registry import get_taxonomy_registry

from .constants import AOI_WORKFLOW_KEY
from .fixture_profiles import resolve_profile_source_document

AOI_THEMATIC_SYNTHESIS_ENGINE = "aoi_thematic_synthesis"
AOI_ENGAGEMENT_MAPPING_ENGINE = "aoi_engagement_mapping"
AOI_SIN_FINDINGS_ENGINE = "aoi_sin_findings"
AOI_THEMATIC_REPORT_ENGINE = "aoi_thematic_report"
AOI_ENGINE_KEYS = {
    AOI_THEMATIC_SYNTHESIS_ENGINE,
    AOI_ENGAGEMENT_MAPPING_ENGINE,
    AOI_SIN_FINDINGS_ENGINE,
    AOI_THEMATIC_REPORT_ENGINE,
}
AOI_SIN_TAXONOMY_KEY = "anxiety_of_influence_sin_types"


def is_aoi_workflow_key(workflow_key: Optional[str]) -> bool:
    return workflow_key == AOI_WORKFLOW_KEY


def build_aoi_output_metadata(
    *,
    job_id: str,
    phase_number: float,
    engine_key: str,
    content: str,
) -> Optional[dict[str, Any]]:
    """Build persisted AOI metadata from a JSON engine output."""
    if engine_key not in AOI_ENGINE_KEYS:
        return None

    plan_context = _load_plan_context(job_id)
    if not plan_context:
        return {
            "contract_family": "aoi_thematic_single_thinker",
            "contract_version": 1,
            "engine_key": engine_key,
            "parse_error": "Could not load AOI plan context for normalization.",
        }

    try:
        parsed = parse_llm_json_response(content)
    except Exception as exc:
        return {
            "contract_family": "aoi_thematic_single_thinker",
            "contract_version": 1,
            "engine_key": engine_key,
            "parse_error": f"Could not parse AOI JSON output: {exc}",
        }

    normalized: dict[str, Any]
    structured_payloads: dict[str, Any] = {}

    if engine_key == AOI_THEMATIC_SYNTHESIS_ENGINE:
        normalized = _normalize_thematic_synthesis(parsed, plan_context)
        structured_payloads["aoi_source_documents"] = normalized["source_documents"]
    elif engine_key == AOI_ENGAGEMENT_MAPPING_ENGINE:
        themes = _load_previous_normalized(job_id, AOI_THEMATIC_SYNTHESIS_ENGINE)
        normalized = _normalize_engagement_mapping(parsed, themes or {})
    elif engine_key == AOI_SIN_FINDINGS_ENGINE:
        themes = _load_previous_normalized(job_id, AOI_THEMATIC_SYNTHESIS_ENGINE) or {}
        engagements = _load_previous_normalized(job_id, AOI_ENGAGEMENT_MAPPING_ENGINE) or {}
        normalized = _normalize_sin_findings(parsed, themes, engagements)
        structured_payloads["aoi_by_theme"] = _build_by_theme_payload(
            themes=themes,
            engagements=engagements,
            findings=normalized,
        )
        structured_payloads["aoi_by_sin_type"] = _build_by_sin_type_payload(normalized)
    elif engine_key == AOI_THEMATIC_REPORT_ENGINE:
        themes = _load_previous_normalized(job_id, AOI_THEMATIC_SYNTHESIS_ENGINE) or {}
        engagements = _load_previous_normalized(job_id, AOI_ENGAGEMENT_MAPPING_ENGINE) or {}
        findings = _load_previous_normalized(job_id, AOI_SIN_FINDINGS_ENGINE) or {}
        normalized = _normalize_thematic_report(parsed, themes, engagements, findings)
        structured_payloads["aoi_thematic_report"] = normalized["report_sections"]
    else:
        return None

    return {
        "contract_family": "aoi_thematic_single_thinker",
        "contract_version": 1,
        "workflow_key": AOI_WORKFLOW_KEY,
        "phase_number": phase_number,
        "engine_key": engine_key,
        "selected_source_thinker": plan_context["selected_source_thinker"],
        "normalized": normalized,
        "structured_payloads": structured_payloads,
    }


def _load_plan_context(job_id: str) -> Optional[dict[str, Any]]:
    from src.executor.job_manager import get_job

    job = get_job(job_id) or {}
    plan_data = job.get("plan_data") or {}
    if plan_data.get("_type") == "request_snapshot":
        plan_data = plan_data.get("plan_request") or {}

    workflow_key = plan_data.get("workflow_key")
    if workflow_key != AOI_WORKFLOW_KEY:
        return None

    selected_thinker = {
        "thinker_id": plan_data.get("selected_source_thinker_id"),
        "thinker_name": plan_data.get("selected_source_thinker_name"),
    }
    prior_works = plan_data.get("prior_works") or []
    matching_source_documents = [
        _build_source_document_inventory_item(work, selected_thinker["thinker_name"])
        for work in prior_works
        if work.get("source_thinker_id") == selected_thinker["thinker_id"]
    ]
    return {
        "workflow_key": workflow_key,
        "selected_source_thinker": selected_thinker,
        "source_documents": matching_source_documents,
    }


def _load_previous_normalized(job_id: str, engine_key: str) -> Optional[dict[str, Any]]:
    from src.executor.output_store import load_phase_outputs

    outputs = load_phase_outputs(job_id=job_id, engine_key=engine_key)
    if not outputs:
        return None
    latest = max(outputs, key=lambda row: (row.get("phase_number", 0), row.get("pass_number", 0)))
    metadata = latest.get("metadata") or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            return None
    normalized = metadata.get("normalized")
    return normalized if isinstance(normalized, dict) else None


def _build_source_document_inventory_item(work: dict[str, Any], thinker_name: Optional[str]) -> dict[str, Any]:
    title = work.get("title") or "Untitled source"
    year = work.get("year")
    subtitle_parts = [part for part in [work.get("author"), str(year) if year else None] if part]
    return {
        "source_document_id": work.get("source_document_id") or _slugify(title),
        "title": title,
        "subtitle": " | ".join(subtitle_parts),
        "description": work.get("description") or "",
        "badge": thinker_name or work.get("source_thinker_name") or "Source",
    }


def _normalize_thematic_synthesis(parsed: dict[str, Any], plan_context: dict[str, Any]) -> dict[str, Any]:
    themes = parsed.get("themes") or []
    seen_ids: dict[str, int] = {}
    normalized_themes = []
    for theme in themes:
        theme_name = (
            theme.get("theme_name")
            or theme.get("title")
            or theme.get("name")
            or "Untitled Theme"
        )
        theme_id = _stable_theme_id(theme_name, seen_ids)
        source_documents = theme.get("source_documents") or []
        normalized_themes.append(
            {
                "theme_id": theme_id,
                "theme_name": theme_name,
                "overview": theme.get("overview") or theme.get("description") or "",
                "key_claims": _ensure_string_list(theme.get("key_claims")),
                "philosophical_commitments": _ensure_string_list(theme.get("philosophical_commitments")),
                "argumentative_moves": _ensure_string_list(theme.get("argumentative_moves")),
                "source_documents": [
                    _normalize_source_document_ref(
                        doc,
                        plan_context["source_documents"],
                        plan_context["selected_source_thinker"].get("thinker_id"),
                    )
                    for doc in source_documents
                ],
                "representative_quotes": _normalize_representative_quotes(
                    theme.get("representative_quotes"),
                    plan_context["source_documents"],
                    plan_context["selected_source_thinker"].get("thinker_id"),
                ),
                "centrality": theme.get("centrality") or "major",
            }
        )

    return {
        "selected_source_thinker": plan_context["selected_source_thinker"],
        "source_documents": plan_context["source_documents"],
        "themes": normalized_themes,
        "overall_synthesis": parsed.get("overall_synthesis") or parsed.get("summary") or "",
    }


def _normalize_engagement_mapping(
    parsed: dict[str, Any],
    themes: dict[str, Any],
) -> dict[str, Any]:
    theme_ids = {theme["theme_id"] for theme in themes.get("themes", [])}
    normalized = []
    for idx, engagement in enumerate(parsed.get("engagements") or [], start=1):
        theme_id = engagement.get("theme_id") or ""
        if not theme_id and idx <= len(themes.get("themes", [])):
            theme_id = themes["themes"][idx - 1]["theme_id"]
        if theme_id and theme_ids and theme_id not in theme_ids:
            theme_id = _best_matching_theme_id(theme_id, theme_ids)
        normalized.append(
            {
                "engagement_id": engagement.get("engagement_id") or f"eng-{idx:03d}",
                "theme_id": theme_id,
                "theme_name": engagement.get("theme_name") or _theme_name_for_id(themes, theme_id),
                "engagement_level": engagement.get("engagement_level") or "partial",
                "benanav_position": engagement.get("benanav_position") or "",
                "benanav_sources": _normalize_target_sources(engagement.get("benanav_sources")),
                "divergence_description": engagement.get("divergence_description") or "",
                "divergence_type": engagement.get("divergence_type") or "emphasis",
                "severity": engagement.get("severity") or "medium",
                "severity_rationale": engagement.get("severity_rationale") or "",
            }
        )

    return {
        "engagements": normalized,
        "engagement_pattern": parsed.get("engagement_pattern") or "",
        "themes_engaged": parsed.get("themes_engaged") or _count_by_level(normalized, "engaged"),
        "themes_partial": parsed.get("themes_partial") or _count_by_level(normalized, "partial"),
        "themes_ignored": parsed.get("themes_ignored") or _count_by_level(normalized, "ignored"),
        "themes_distorted": parsed.get("themes_distorted") or _count_by_level(normalized, "distorted"),
    }


def _normalize_sin_findings(
    parsed: dict[str, Any],
    themes: dict[str, Any],
    engagements: dict[str, Any],
) -> dict[str, Any]:
    theme_ids = {theme["theme_id"] for theme in themes.get("themes", [])}
    engagements_by_theme = {
        entry.get("theme_id"): entry for entry in engagements.get("engagements", [])
        if entry.get("theme_id")
    }
    available_documents = themes.get("source_documents") or []
    findings = []
    for idx, finding in enumerate(parsed.get("findings") or [], start=1):
        theme_id = finding.get("theme_id") or ""
        if theme_id and theme_ids and theme_id not in theme_ids:
            theme_id = _best_matching_theme_id(theme_id, theme_ids)
        engagement = engagements_by_theme.get(theme_id, {})
        target_chapter_key = (
            finding.get("target_chapter_key")
            or finding.get("benanav_source")
            or finding.get("target_document_label")
            or "target"
        )
        source_work_title = finding.get("source_work_title") or finding.get("source_work") or "Source work"
        source_document_id = _resolve_source_document_id(
            selected_source_thinker_id=themes.get("selected_source_thinker", {}).get("thinker_id"),
            source_document_id=finding.get("source_document_id"),
            source_work_title=source_work_title,
            available_documents=available_documents,
        )
        target_quote = finding.get("target_quote") or finding.get("benanav_quote") or ""
        fingerprint = "|".join(
            [
                theme_id or f"theme-{idx}",
                finding.get("sin_type") or "uncategorized",
                _slugify(str(target_chapter_key)),
                source_document_id,
                _slugify(target_quote[:80]),
            ]
        )
        finding_id = finding.get("finding_id") or f"find-{hashlib.sha1(fingerprint.encode()).hexdigest()[:10]}"
        findings.append(
            {
                "finding_id": finding_id,
                "theme_id": theme_id,
                "theme_name": finding.get("theme_name") or _theme_name_for_id(themes, theme_id),
                "engagement_level": finding.get("engagement_level") or engagement.get("engagement_level") or "partial",
                "sin_type": finding.get("sin_type") or "misreading",
                "severity": finding.get("severity") or "medium",
                "severity_rationale": finding.get("severity_rationale") or "",
                "title": finding.get("title") or finding.get("summary") or finding.get("sin_type") or f"Finding {idx}",
                "summary": finding.get("summary") or finding.get("discrepancy_analysis") or "",
                "target_chapter_key": _slugify(str(target_chapter_key)),
                "target_document_label": finding.get("target_document_label") or finding.get("benanav_source") or str(target_chapter_key),
                "target_locator": finding.get("target_locator") or finding.get("benanav_page") or "",
                "target_quote": target_quote,
                "source_document_id": source_document_id,
                "source_work_title": source_work_title,
                "source_locator": finding.get("source_locator") or finding.get("source_page") or "",
                "source_quote": finding.get("source_quote") or "",
                "discrepancy_analysis": finding.get("discrepancy_analysis") or "",
                "what_benanav_misses": finding.get("what_benanav_misses") or "",
                "implication_for_argument": finding.get("implication_for_argument") or "",
            }
        )

    findings_by_theme = {}
    findings_by_sin_type = {}
    for finding in findings:
        findings_by_theme.setdefault(finding["theme_id"], []).append(finding)
        findings_by_sin_type.setdefault(finding["sin_type"], []).append(finding)

    return {
        "findings": findings,
        "findings_by_theme": findings_by_theme,
        "findings_by_sin_type": findings_by_sin_type,
    }


def _normalize_thematic_report(
    parsed: dict[str, Any],
    themes: dict[str, Any],
    engagements: dict[str, Any],
    findings: dict[str, Any],
) -> dict[str, Any]:
    report_sections = parsed.get("report_sections")
    if not isinstance(report_sections, dict):
        report_sections = {
            "summary": parsed.get("summary") or parsed.get("executive_summary") or "",
            "engagement_pattern": parsed.get("engagement_pattern") or engagements.get("engagement_pattern") or "",
            "key_divergences": parsed.get("key_divergences") or _build_key_divergence_cards(findings),
            "sin_distribution": parsed.get("sin_distribution") or _build_sin_distribution(findings),
            "reading_implications": parsed.get("reading_implications") or parsed.get("implications") or "",
        }

    return {
        "selected_source_thinker": themes.get("selected_source_thinker"),
        "report_sections": {
            "summary": report_sections.get("summary") or "",
            "engagement_pattern": report_sections.get("engagement_pattern") or "",
            "key_divergences": report_sections.get("key_divergences") or _build_key_divergence_cards(findings),
            "sin_distribution": report_sections.get("sin_distribution") or _build_sin_distribution(findings),
            "reading_implications": report_sections.get("reading_implications") or "",
        },
    }


def _build_by_theme_payload(
    *,
    themes: dict[str, Any],
    engagements: dict[str, Any],
    findings: dict[str, Any],
) -> dict[str, Any]:
    engagements_by_theme = {
        entry.get("theme_id"): entry for entry in engagements.get("engagements", [])
        if entry.get("theme_id")
    }
    findings_by_theme = findings.get("findings_by_theme") or {}
    payload: dict[str, Any] = {
        "_section_order": [],
        "_section_titles": {},
    }
    for theme in themes.get("themes", []):
        theme_id = theme["theme_id"]
        theme_name = theme["theme_name"]
        engagement = engagements_by_theme.get(theme_id, {})
        payload["_section_order"].append(theme_id)
        payload["_section_titles"][theme_id] = theme_name
        payload[theme_id] = {
            "theme_id": theme_id,
            "theme_name": theme_name,
            "overview": {
                "summary": theme.get("overview") or "",
                "key_claims": theme.get("key_claims") or [],
                "philosophical_commitments": theme.get("philosophical_commitments") or [],
                "argumentative_moves": theme.get("argumentative_moves") or [],
                "source_documents": [doc.get("title") for doc in theme.get("source_documents", [])],
            },
            "engagement": {
                "engagement_level": engagement.get("engagement_level") or "unmapped",
                "benanav_position": engagement.get("benanav_position") or "",
                "divergence_description": engagement.get("divergence_description") or "",
                "severity": engagement.get("severity") or "n/a",
                "severity_rationale": engagement.get("severity_rationale") or "",
            },
            "findings": [
                _finding_card(finding) for finding in findings_by_theme.get(theme_id, [])
            ],
        }
    return payload


def _build_by_sin_type_payload(findings: dict[str, Any]) -> dict[str, Any]:
    taxonomy = get_taxonomy_registry().get(AOI_SIN_TAXONOMY_KEY)
    names = {value.key: value.name for value in (taxonomy.values if taxonomy else [])}
    payload: dict[str, Any] = {
        "_section_order": [],
        "_section_titles": {},
    }
    for sin_type, items in (findings.get("findings_by_sin_type") or {}).items():
        label = names.get(sin_type, sin_type.replace("_", " ").title())
        payload["_section_order"].append(sin_type)
        payload["_section_titles"][sin_type] = label
        payload[sin_type] = [_finding_card(item) for item in items]
    return payload


def _build_key_divergence_cards(findings: dict[str, Any]) -> list[dict[str, Any]]:
    cards = []
    for finding in (findings.get("findings") or [])[:6]:
        cards.append(
            {
                "title": finding.get("title") or finding.get("theme_name"),
                "subtitle": finding.get("sin_type") or "",
                "description": finding.get("discrepancy_analysis") or "",
                "badge": finding.get("severity") or "",
            }
        )
    return cards


def _build_sin_distribution(findings: dict[str, Any]) -> list[dict[str, Any]]:
    distribution = []
    grouped = findings.get("findings_by_sin_type") or {}
    for sin_type, items in grouped.items():
        distribution.append(
            {
                "sin_type": _sin_type_label(sin_type),
                "count": len(items),
                "description": f"{len(items)} finding(s) tagged as {sin_type}.",
            }
        )
    return distribution


def _finding_card(finding: dict[str, Any]) -> dict[str, Any]:
    sin_type = finding.get("sin_type") or ""
    return {
        "title": finding.get("title") or finding.get("theme_name") or "Finding",
        "subtitle": finding.get("target_document_label") or "",
        "description": finding.get("discrepancy_analysis") or finding.get("summary") or "",
        "badge": finding.get("severity") or "",
        "sin_type": sin_type,
        "sin_type_label": _sin_type_label(sin_type),
        "theme_name": finding.get("theme_name") or "",
        "source_document_id": finding.get("source_document_id") or "",
        "target_quote": finding.get("target_quote") or "",
        "source_quote": finding.get("source_quote") or "",
        "implication_for_argument": finding.get("implication_for_argument") or "",
    }


def _sin_type_label(sin_type: str) -> str:
    taxonomy = get_taxonomy_registry().get(AOI_SIN_TAXONOMY_KEY)
    if taxonomy:
        for value in taxonomy.values or []:
            if value.key == sin_type:
                return value.name
    return sin_type.replace("_", " ").title()


def _normalize_source_document_ref(
    value: Any,
    available_documents: list[dict[str, Any]],
    selected_source_thinker_id: Optional[str] = None,
) -> dict[str, Any]:
    if isinstance(value, dict):
        title = value.get("title") or value.get("source_work_title") or value.get("name") or "Source work"
        matched = _lookup_available_document(
            value.get("source_document_id"),
            title,
            available_documents,
            selected_source_thinker_id,
        )
        return {
            "source_document_id": matched.get("source_document_id") or "unknown",
            "title": matched.get("title") or title,
            "subtitle": value.get("subtitle") or matched.get("subtitle") or "",
            "description": value.get("description") or matched.get("description") or "",
            "badge": value.get("badge") or matched.get("badge") or "Source",
        }
    if isinstance(value, str):
        matched = _lookup_available_document(None, value, available_documents, selected_source_thinker_id)
        if matched:
            return matched
        return {
            "source_document_id": "unknown",
            "title": value,
            "subtitle": "",
            "description": "",
            "badge": "Source",
        }
    return {
        "source_document_id": "unknown",
        "title": "Unknown source",
        "subtitle": "",
        "description": "",
        "badge": "Source",
    }


def _normalize_representative_quotes(
    value: Any,
    available_documents: list[dict[str, Any]],
    selected_source_thinker_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        title = entry.get("source_work_title") or entry.get("title") or "Source work"
        source_document_id = _resolve_source_document_id(
            selected_source_thinker_id=selected_source_thinker_id,
            source_document_id=entry.get("source_document_id"),
            source_work_title=title,
            available_documents=available_documents,
        )
        normalized.append(
            {
                "source_document_id": source_document_id,
                "source_work_title": title,
                "source_locator": entry.get("source_locator") or entry.get("page") or "",
                "quote": entry.get("quote") or entry.get("excerpt") or "",
            }
        )
    return normalized


def _normalize_target_sources(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized = []
    for item in value:
        if isinstance(item, dict):
            label = item.get("target_document_label") or item.get("label") or item.get("title") or "Target"
            normalized.append(
                {
                    "target_chapter_key": _slugify(item.get("target_chapter_key") or label),
                    "target_document_label": label,
                    "target_locator": item.get("target_locator") or item.get("page") or "",
                    "target_quote": item.get("target_quote") or item.get("quote") or "",
                }
            )
        elif isinstance(item, str):
            normalized.append(
                {
                    "target_chapter_key": _slugify(item),
                    "target_document_label": item,
                    "target_locator": "",
                    "target_quote": "",
                }
            )
    return normalized


def _stable_theme_id(theme_name: str, seen_ids: dict[str, int]) -> str:
    base = f"theme_{_slugify(theme_name)}"
    count = seen_ids.get(base, 0) + 1
    seen_ids[base] = count
    return base if count == 1 else f"{base}_{count}"


def _theme_name_for_id(themes: dict[str, Any], theme_id: str) -> str:
    for theme in themes.get("themes", []):
        if theme.get("theme_id") == theme_id:
            return theme.get("theme_name") or theme_id
    return theme_id


def _lookup_available_document(
    source_document_id: Optional[str],
    title: Optional[str],
    available_documents: list[dict[str, Any]],
    selected_source_thinker_id: Optional[str] = None,
) -> dict[str, Any]:
    if source_document_id:
        for doc in available_documents:
            if doc.get("source_document_id") == source_document_id:
                return doc
    if title:
        normalized_title = _slugify(title)
        for doc in available_documents:
            if doc.get("title") == title or _slugify(doc.get("title") or "") == normalized_title:
                return doc
    profile_doc = resolve_profile_source_document(
        thinker_id=selected_source_thinker_id,
        source_document_id=source_document_id,
        title=title,
    )
    if profile_doc is not None:
        return {
            "source_document_id": profile_doc.source_document_id,
            "title": profile_doc.title,
            "subtitle": "",
            "description": profile_doc.description,
            "badge": "Source",
        }
    return {}


def _resolve_source_document_id(
    *,
    selected_source_thinker_id: Optional[str],
    source_document_id: Optional[str],
    source_work_title: str,
    available_documents: list[dict[str, Any]],
) -> str:
    matched = _lookup_available_document(
        source_document_id,
        source_work_title,
        available_documents,
        selected_source_thinker_id,
    )
    return matched.get("source_document_id") or "unknown"


def _best_matching_theme_id(candidate: str, theme_ids: set[str]) -> str:
    candidate_slug = _slugify(candidate)
    candidate_slug = candidate_slug.removeprefix("theme_")
    for theme_id in theme_ids:
        theme_slug = _slugify(theme_id).removeprefix("theme_")
        if theme_slug == candidate_slug:
            return theme_id
    return candidate


def _count_by_level(items: list[dict[str, Any]], level: str) -> int:
    return sum(1 for item in items if item.get("engagement_level") == level)


def _ensure_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value in (None, ""):
        return []
    return [str(value).strip()]


def _slugify(value: Any) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")
    return text or "unknown"
