"""Presentation API — assembles render-ready page payloads for the consumer.

Combines view definitions, structured data (from presentation_cache),
and raw prose (from phase_outputs) into a single PagePresentation
that The Critic can render directly.
"""

import hashlib
import json
import logging
import re
from collections import Counter
from datetime import UTC, datetime
from typing import Any, Optional

from src.executor.job_manager import get_job
from src.executor.output_store import (
    load_all_job_outputs,
    load_phase_outputs,
    load_presentation_cache,
    load_presentation_cache_batch,
    get_latest_output_for_phase,
)
from src.orchestrator.planner import load_plan
from src.transformations.registry import get_transformation_registry
from src.views.registry import get_view_registry

from .artifact_store import load_presentation_artifact_batch
from .composition_resolver import find_applicable_template, resolve_effective_render_contract
from .manifest_builder import (
    MANIFEST_SCHEMA_VERSION,
    TRACE_SCHEMA_VERSION,
    RESOLVER_VERSION,
    adapt_renderer_for_consumer,
    build_effective_manifest,
    derive_view_derivation_kind,
    derive_legacy_visibility,
    normalize_navigation_state,
    normalize_selection_priority,
    normalize_structuring_policy,
)
from .recommendation_defaults import get_default_recommendations_for_workflow
from .scaffold_generator import (
    READING_SCAFFOLD_ARTIFACT_KIND,
    READING_SCAFFOLD_ARTIFACT_VERSION,
    SCAFFOLD_PROMPT_VERSIONS,
    compute_scaffold_input_hash,
    resolve_scaffold_type,
)
from .schemas import EffectivePresentationManifest, PagePresentation, ViewPayload
from .store import load_view_refinement
from src.taxonomies.registry import get_taxonomy_registry
from .view_hierarchy import (
    is_chain_container_view as _is_chain_container_view,
    iter_active_child_views as _iter_active_child_views,
    match_container_sections_to_children as _match_container_sections_to_children,
)
from .work_key_utils import (
    resolve_work_metadata as _resolve_work_metadata,
    resolve_chain_engine_keys as _resolve_chain_engine_keys,
    sanitize_work_key_for_presenter as _sanitize_work_key_for_presenter,
    infer_work_key_from_content as _infer_work_key_from_content,
    try_split_collapsed_outputs as _try_split_collapsed_outputs,
)

logger = logging.getLogger(__name__)

PRESENTATION_CONTRACT_VERSION = 1
_STRUCTURED_PAYLOAD_META_KEYS = {"_section_order", "_section_titles"}


def _extract_result_path_value(data: Any, result_path: str) -> Any:
    """Extract a nested value from structured data using dotted result_path."""
    if not result_path:
        return data

    current = data
    for segment in result_path.split("."):
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(segment)
            continue
        if isinstance(current, list) and segment.isdigit():
            idx = int(segment)
            if 0 <= idx < len(current):
                current = current[idx]
                continue
        return None
    return current


def _load_output_metadata(output_row: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Parse a phase output metadata payload into a dict."""
    if not output_row:
        return {}
    metadata = output_row.get("metadata") or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            return {}
    return metadata if isinstance(metadata, dict) else {}


def _humanize_section_key(key: str) -> str:
    text = str(key).strip()
    if "_" not in text and any(char.isupper() for char in text):
        return text
    if "_" not in text and " " in text:
        return text
    return text.replace("_", " ").strip().title()


def _prepare_structured_payload_for_renderer(
    renderer_type: str,
    renderer_config: dict[str, Any],
    structured_data: Any,
) -> tuple[Any, dict[str, Any]]:
    """Apply renderer-facing normalization to persisted structured payloads."""
    if not isinstance(renderer_config, dict):
        renderer_config = {}

    cleaned_data = structured_data
    section_order: Optional[list[str]] = None
    section_titles: dict[str, str] = {}

    if isinstance(structured_data, dict):
        cleaned_data = {
            key: value
            for key, value in structured_data.items()
            if key not in _STRUCTURED_PAYLOAD_META_KEYS
        }
        raw_order = structured_data.get("_section_order")
        raw_titles = structured_data.get("_section_titles")
        if isinstance(raw_order, list):
            section_order = [str(item) for item in raw_order if isinstance(item, str)]
        if isinstance(raw_titles, dict):
            section_titles = {
                str(key): str(value)
                for key, value in raw_titles.items()
                if isinstance(key, str) and isinstance(value, str)
            }

    if renderer_type != "accordion" or not isinstance(cleaned_data, dict):
        return cleaned_data, renderer_config

    sections = renderer_config.get("sections")
    resolved_sections: list[dict[str, Any]] = []
    if isinstance(sections, list) and sections:
        for section in sections:
            if not isinstance(section, dict):
                continue
            key = section.get("key")
            if key in cleaned_data and cleaned_data.get(key) is not None:
                resolved_sections.append(section)
    else:
        ordered_keys = [
            key for key in (section_order or list(cleaned_data.keys()))
            if key in cleaned_data and cleaned_data.get(key) is not None
        ]
        if not ordered_keys:
            return cleaned_data, renderer_config

        resolved_sections = [
            {
                "key": key,
                "title": section_titles.get(key) or _humanize_section_key(key),
            }
            for key in ordered_keys
        ]

    if not resolved_sections:
        return cleaned_data, renderer_config

    resolved_keys = {
        str(section.get("key"))
        for section in resolved_sections
        if isinstance(section, dict) and section.get("key") is not None
    }
    derived_config = dict(renderer_config)
    derived_config["sections"] = resolved_sections

    section_renderers = derived_config.get("section_renderers")
    if isinstance(section_renderers, dict):
        filtered_section_renderers = {
            key: value
            for key, value in section_renderers.items()
            if key in resolved_keys
        }
        if filtered_section_renderers:
            derived_config["section_renderers"] = filtered_section_renderers
        else:
            derived_config.pop("section_renderers", None)

    return cleaned_data, derived_config


def _is_newer_output(candidate: dict, current: dict) -> bool:
    """True when candidate is the newer saved version of an output."""
    candidate_pass = candidate.get("pass_number", 0)
    current_pass = current.get("pass_number", 0)
    if candidate_pass != current_pass:
        return candidate_pass > current_pass

    candidate_created = candidate.get("created_at") or ""
    current_created = current.get("created_at") or ""
    if candidate_created != current_created:
        return candidate_created > current_created

    return (candidate.get("id") or "") > (current.get("id") or "")


def _normalize_renderer_shape(
    renderer_type: str,
    renderer_config: dict[str, Any],
    structured_data: Any,
) -> Any:
    """Coerce sliced data into the minimum shape expected by the renderer."""
    if structured_data is None:
        return None

    if renderer_type == "timeline" and isinstance(structured_data, list):
        label_field = renderer_config.get("label_field") or "label"
        date_field = renderer_config.get("date_field")
        normalized = []
        for idx, item in enumerate(structured_data, start=1):
            if not isinstance(item, dict):
                normalized.append(item)
                continue
            row = dict(item)
            row.setdefault("label", str(row.get(label_field) or f"Step {idx}"))
            if "date" not in row:
                if date_field and row.get(date_field) is not None:
                    row["date"] = row[date_field]
                else:
                    row["date"] = idx
            if "description" not in row and label_field != "description" and row.get("description") is None:
                candidate = row.get("if_absent") or row.get("what_changes") or row.get("summary")
                if isinstance(candidate, str):
                    row["description"] = candidate
            normalized.append(row)
        return normalized

    return structured_data


def _normalize_view_structured_data(
    view_key: str,
    structured_data: Any,
) -> Any:
    """Repair legacy cached shapes for views whose contracts were tightened."""
    if not isinstance(structured_data, dict):
        return structured_data

    if view_key == "genealogy_idea_evolution":
        return _normalize_idea_evolution_structured_data(structured_data)

    if view_key == "genealogy_tp_concept_evolution":
        comparisons = structured_data.get("dimensional_comparisons")
        if isinstance(comparisons, str) and comparisons.strip():
            normalized = dict(structured_data)
            normalized["dimensional_comparisons"] = _repair_legacy_dimensional_comparisons(comparisons)
            return normalized
        if (
            isinstance(comparisons, list)
            and len(comparisons) == 1
            and isinstance(comparisons[0], dict)
            and isinstance(comparisons[0].get("comparison"), str)
            and (
                len(comparisons[0].get("comparison", "")) > 1200
                or "\n\n" in comparisons[0].get("comparison", "")
                or comparisons[0].get("comparison", "").strip().startswith("**")
            )
        ):
            normalized = dict(structured_data)
            normalized["dimensional_comparisons"] = _repair_legacy_dimensional_comparisons(
                comparisons[0]["comparison"]
            )
            return normalized

    return structured_data


_IDEA_EVOLUTION_PATTERN_ALIAS_MAP: dict[str, str] = {
    "genuine_transformation": "radical_transformation",
    "concept_death": "radical_transformation",
    "conceptual_death": "radical_transformation",
    "foundational_revision": "radical_transformation",
    "methodological_radicalization": "radical_transformation",
    "strategic_reframing": "strategic_repurposing",
    "reframing": "strategic_repurposing",
    "incremental_refinement": "gradual_refinement",
    "deepening": "gradual_refinement",
}


def _slugify_pattern_value(value: str) -> str:
    lowered = value.strip().lower()
    lowered = re.sub(r"[^a-z0-9]+", "_", lowered)
    lowered = re.sub(r"_+", "_", lowered)
    return lowered.strip("_")


def _condense_pattern_summary(text: str, max_chars: int = 260) -> str:
    stripped = re.sub(r"[*_`#]+", "", text.strip())
    stripped = re.sub(r"\s+", " ", stripped)
    if not stripped:
        return ""

    sentences = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", stripped) if segment.strip()]
    selected: list[str] = []

    for sentence in sentences:
        candidate = " ".join(selected + [sentence]).strip()
        if selected and len(candidate) > max_chars:
            break
        selected.append(sentence)
        if len(selected) >= 2:
            break

    summary = " ".join(selected).strip() or stripped
    if len(summary) <= max_chars:
        return summary

    truncated = summary[:max_chars].rsplit(" ", 1)[0].rstrip(" ,;:")
    return f"{truncated}..."


def _normalize_idea_evolution_pattern(
    value: Any,
    *,
    context: str = "",
) -> Optional[str]:
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    taxonomy = get_taxonomy_registry().get("genealogy_idea_evolution_patterns")
    valid_keys = set(taxonomy.value_keys()) if taxonomy is not None else set()

    slug = _slugify_pattern_value(text)
    if slug in valid_keys:
        return slug

    alias = _IDEA_EVOLUTION_PATTERN_ALIAS_MAP.get(slug)
    if alias in valid_keys:
        return alias

    haystack = f"{text} {context}".lower()

    if taxonomy is not None:
        for item in taxonomy.values:
            if item.name and item.name.lower() in haystack:
                return item.key

    if "vocabulary" in haystack and "concept" in haystack and (
        "survival" in haystack or "same concept" in haystack or "wording changes" in haystack
    ):
        return "vocabulary_death_concept_survival"
    if any(token in haystack for token in ("synthesis", "synthesizes", "fuses", "fuse", "composite")):
        return "synthesis_of_influences"
    if any(token in haystack for token in ("historical problem-space", "problem-space", "conjuncture", "epoch", "temporal mutation")):
        return "temporal_mutation"
    if any(
        token in haystack
        for token in (
            "radical",
            "radicalization",
            "foundational revision",
            "concept death",
            "abandon",
            "self-limitation",
            "demolished",
            "demolition",
            "genuine transformation",
            "transformation",
        )
    ):
        return "radical_transformation"
    if any(token in haystack for token in ("repurpos", "refram", "different argumentative job", "new argumentative job")):
        return "strategic_repurposing"
    if any(token in haystack for token in ("refinement", "clarif", "sharpen", "deepening")):
        return "gradual_refinement"

    return None


def _normalize_idea_evolution_structured_data(structured_data: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(structured_data)
    changed = False

    ideas = structured_data.get("ideas")
    pattern_counts: Counter[str] = Counter()
    if isinstance(ideas, list):
        normalized_ideas: list[Any] = []
        for item in ideas:
            if not isinstance(item, dict):
                normalized_ideas.append(item)
                continue

            normalized_item = dict(item)
            normalized_pattern = _normalize_idea_evolution_pattern(
                normalized_item.get("evolution_pattern"),
                context=f"{normalized_item.get('description', '')} {normalized_item.get('evolution_narrative', '')}",
            )
            if normalized_pattern:
                pattern_counts[normalized_pattern] += 1
                if normalized_pattern != normalized_item.get("evolution_pattern"):
                    normalized_item["evolution_pattern"] = normalized_pattern
                    changed = True

            normalized_ideas.append(normalized_item)

        if changed:
            normalized["ideas"] = normalized_ideas

    cross_cutting_patterns = structured_data.get("cross_cutting_patterns")
    if isinstance(cross_cutting_patterns, dict):
        normalized_patterns = dict(cross_cutting_patterns)
        original_dominant = normalized_patterns.get("dominant_evolution_pattern")
        dominant_text = original_dominant.strip() if isinstance(original_dominant, str) else ""
        inferred_dominant = _normalize_idea_evolution_pattern(
            original_dominant,
            context=(
                f"{normalized_patterns.get('overall_trajectory', '')} "
                f"{normalized_patterns.get('audience_calibration', '')} "
                f"{normalized_patterns.get('prescription_diagnosis_gap', '')}"
            ),
        )
        if inferred_dominant is None and pattern_counts:
            inferred_dominant = pattern_counts.most_common(1)[0][0]

        if inferred_dominant and inferred_dominant != original_dominant:
            normalized_patterns["dominant_evolution_pattern"] = inferred_dominant
            changed = True

        if dominant_text and (len(dominant_text) > 120 or "\n" in dominant_text) and not normalized_patterns.get("overall_trajectory"):
            summary = _condense_pattern_summary(dominant_text)
            if summary:
                normalized_patterns["overall_trajectory"] = summary
                changed = True

        if changed:
            normalized["cross_cutting_patterns"] = normalized_patterns

    return normalized


_DIMENSION_KEYWORD_LABELS: list[tuple[str, list[str]]] = [
    ("Temporalization", ["tempor", "epoch", "historical depth", "chronolog"]),
    ("Democratization / Aristocratization", ["democrat", "aristocrat", "collective agency", "mass", "elite"]),
    ("Ideologization", ["ideolog", "ontology", "worldview", "totaliz"]),
    ("Politicization", ["politic", "class struggle", "contest", "agency"]),
    ("Methodological Shift", ["methodolog", "genealogical critique", "immanent critique", "diagnostic"]),
    ("Vocabulary Shift", ["vocabulary", "term", "lexic", "naming"]),
    ("Metaphor Shift", ["metaphor", "image", "ecosystem", "organism", "crystallization"]),
    ("Framing Shift", ["framing", "epistemic", "provisional", "formal criterion", "underdeterminacy"]),
    ("Coupling Pattern", ["coupling", "pattern", "paradigm-shift", "cluster"]),
    ("Construction Asymmetry", ["asymmetry", "construction phase", "deconstruction phase", "incomplete"]),
    ("Objectivation Tension", ["objectivation", "externalization", "material form"]),
    ("Position In Tradition", ["tradition", "post-hegelian", "departure", "loyalty"]),
]


def _infer_dimensional_label(block: str, index: int) -> str:
    lowered = block.lower()
    matches = [
        label
        for label, keywords in _DIMENSION_KEYWORD_LABELS
        if any(keyword in lowered for keyword in keywords)
    ]
    if index == 0 and len(set(matches)) > 1:
        return "Dimensional Overview"
    for preferred in ("Coupling Pattern", "Construction Asymmetry", "Objectivation Tension"):
        if preferred in matches:
            return preferred
    if matches:
        return matches[0]

    first_sentence = re.split(r"(?<=[.!?])\s+", block.strip(), maxsplit=1)[0]
    cleaned = re.sub(r"[*_#`]", "", first_sentence).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if cleaned:
        tokens = cleaned.split()
        return " ".join(tokens[:6]).strip(" :.-") or f"Dimension {index + 1}"
    return f"Dimension {index + 1}"


def _repair_legacy_dimensional_comparisons(text: str) -> list[dict[str, Any]]:
    cleaned = text.strip()
    if not cleaned:
        return []

    blocks = [block.strip() for block in re.split(r"\n\s*\n+", cleaned) if block.strip()]
    repaired: list[dict[str, Any]] = []

    for idx, block in enumerate(blocks):
        label = None
        comparison = block

        heading_match = re.match(r"^\*\*(.+?)\*\*(.*)$", block, flags=re.S)
        if heading_match:
            label = heading_match.group(1).strip(" :.-")
            trailing = heading_match.group(2).strip()
            comparison = trailing if trailing else block

        if not label:
            colon_match = re.match(r"^([A-Z][A-Za-z /&-]{3,60}):\s+(.*)$", block, flags=re.S)
            if colon_match and "." not in colon_match.group(1):
                label = colon_match.group(1).strip(" :.-")
                comparison = colon_match.group(2).strip()

        label = label or _infer_dimensional_label(block, idx)
        first_sentence = re.split(r"(?<=[.!?])\s+", comparison.strip(), maxsplit=1)[0].strip()
        significance = first_sentence[:140] if first_sentence else "legacy cached synthesis"

        repaired.append(
            {
                "dimension": label,
                "comparison": comparison.strip(),
                "significance": significance,
                "exemplar_concepts": [],
            }
        )

    if len(repaired) <= 1:
        return [
            {
                "dimension": "overall dimensional shift",
                "comparison": cleaned,
                "significance": "legacy cached synthesis",
                "exemplar_concepts": [],
            }
        ]

    return repaired


def _should_preserve_root_payload(
    renderer_type: str,
    renderer_config: dict[str, Any],
    result_path: str,
) -> bool:
    """Keep the root object when the renderer resolves items by path itself."""
    if not result_path:
        return False
    items_path = renderer_config.get("items_path")
    if not isinstance(items_path, str) or not items_path:
        return False
    return items_path == result_path


def _normalize_relationship_card(structured_data: Any) -> Any:
    """Repair relationship-card fields and sharpen overly broad classifications."""
    if not isinstance(structured_data, dict):
        return structured_data

    normalized = dict(structured_data)

    what_would_be_lost = normalized.get("what_would_be_lost")
    counterfactual_loss = normalized.get("counterfactual_loss")
    if what_would_be_lost and not counterfactual_loss:
        normalized["counterfactual_loss"] = what_would_be_lost
    elif counterfactual_loss and not what_would_be_lost:
        normalized["what_would_be_lost"] = counterfactual_loss

    primary = normalized.get("relationship_type")
    secondary = normalized.get("secondary_relationship_type")
    summary = str(normalized.get("summary", "") or "")
    mechanism = str(normalized.get("mechanism_of_inheritance", "") or "")
    centrality = str(normalized.get("centrality_assessment", "") or "")
    channels = normalized.get("influence_channels") or []
    channel_text = " ".join(
        f"{channel.get('channel', '')} {channel.get('description', '')}"
        for channel in channels
        if isinstance(channel, dict)
    )
    key_evidence = normalized.get("key_evidence") or []
    evidence_details = " ".join(
        f"{item.get('evidence_type', '')} {item.get('description', '')}"
        for item in key_evidence
        if isinstance(item, dict)
    )
    evidence_text = " ".join([summary, mechanism, centrality, channel_text, evidence_details]).lower()

    taxonomy = get_taxonomy_registry().get("genealogy_relationship_types")
    hints = taxonomy.normalization_hints if taxonomy is not None else {}
    problem_transmission_signals = tuple(hints.get("problem_transmission_signals", []))
    methodological_signals = tuple(hints.get("methodological_signals", []))
    explicit_method_only_markers = tuple(hints.get("method_only_markers", []))
    same_program_markers = tuple(hints.get("same_program_markers", []))

    if primary == "direct_precursor":
        problem_hits = [token for token in problem_transmission_signals if token in evidence_text]
        negated_problem_signal = any(_problem_signal_is_negated(evidence_text, token) for token in problem_hits)
        has_problem_signal = bool(problem_hits) and not negated_problem_signal
        has_method_signal = any(token in evidence_text for token in methodological_signals)
        explicit_method_only = any(marker in evidence_text for marker in explicit_method_only_markers)
        same_program_signal = any(marker in evidence_text for marker in same_program_markers)
        if has_method_signal and not has_problem_signal and (negated_problem_signal or explicit_method_only):
            normalized["relationship_type"] = "methodological_ancestor"
            if secondary in (None, "", "methodological_ancestor"):
                normalized["secondary_relationship_type"] = "direct_precursor"
        elif same_program_signal and not has_problem_signal:
            normalized["relationship_type"] = "conceptual_sibling"
            if secondary in (None, "", "conceptual_sibling"):
                normalized["secondary_relationship_type"] = (
                    "methodological_ancestor" if has_method_signal else "direct_precursor"
                )

    return normalized


def _problem_signal_is_negated(evidence_text: str, token: str) -> bool:
    """Detect local negation of precursor/problem-transmission signals."""
    escaped = re.escape(token)
    patterns = (
        rf"\bnot\b[^.:\n]{{0,80}}{escaped}\b",
        rf"\brather than\b[^.:\n]{{0,80}}{escaped}\b",
        rf"\binstead of\b[^.:\n]{{0,80}}{escaped}\b",
        rf"\bwithout\b[^.:\n]{{0,80}}{escaped}\b",
    )
    return any(re.search(pattern, evidence_text) for pattern in patterns)


def _resolve_workflow_key(job: dict, plan=None) -> str:
    """Resolve workflow_key from job record, falling back to plan, then default."""
    if job and job.get("workflow_key"):
        return job["workflow_key"]
    if plan and hasattr(plan, "workflow_key") and plan.workflow_key:
        return plan.workflow_key
    return "intellectual_genealogy"


def _prepare_page_payloads_for_recommendations(
    job_id: str,
    *,
    consumer_key: str,
    recommended: list[dict[str, Any]],
    slim: bool = False,
) -> dict[str, Any]:
    """Build the render tree inputs shared by /page and /status."""
    # Load job
    job = get_job(job_id)
    if job is None:
        raise ValueError(f"Job not found: {job_id}")

    plan_id = job["plan_id"]

    # Load plan for context
    plan = load_plan(plan_id)
    thinker_name = plan.thinker_name if plan else ""
    strategy_summary = plan.strategy_summary if plan else ""

    # Resolve workflow_key dynamically from job record
    workflow_key = _resolve_workflow_key(job, plan)

    # Prefetch ALL outputs in a single query to avoid N+1 per-view queries.
    # In slim mode, skip the content column entirely (saves ~1MB of data transfer).
    all_outputs = load_all_job_outputs(job_id, include_content=not slim)
    outputs_cache = _build_outputs_cache(all_outputs)

    # Prefetch ALL presentation_cache entries for this job's outputs in one query.
    # Eliminates ~50-70 individual cache lookups (each costing ~200ms cross-region).
    output_ids = [o["id"] for o in all_outputs]
    cache_batch = load_presentation_cache_batch(output_ids)

    # Build recommendation lookup
    rec_by_key = {r["view_key"]: r for r in recommended}

    # Load view registry
    view_registry = get_view_registry()

    # Build ViewPayloads
    payloads: dict[str, ViewPayload] = {}

    for rec in recommended:
        if rec.get("priority") == "hidden":
            continue

        view_def = view_registry.get(rec["view_key"])
        if view_def is None:
            logger.warning(f"View definition not found: {rec['view_key']}")
            continue

        payload = _build_view_payload(
            view_def=view_def,
            rec=rec,
            job_id=job_id,
            consumer_key=consumer_key,
            view_registry=view_registry,
            outputs_cache=outputs_cache,
            cache_batch=cache_batch,
            slim=slim,
        )
        payloads[payload.view_key] = payload

    # Also include views that aren't in recommendations but are active for the workflow
    all_workflow_views = view_registry.for_workflow(workflow_key)
    for view_def in all_workflow_views:
        if view_def.view_key in payloads:
            continue
        if view_def.status != "active":
            continue
        if view_def.visibility == "on_demand":
            # Include on-demand views with low priority
            payload = _build_view_payload(
                view_def=view_def,
                rec={"view_key": view_def.view_key, "priority": "optional", "rationale": ""},
                job_id=job_id,
                consumer_key=consumer_key,
                view_registry=view_registry,
                outputs_cache=outputs_cache,
                cache_batch=cache_batch,
                slim=slim,
            )
            payloads[payload.view_key] = payload

    # Include child views whose parent is already in payloads.
    # Child views often have workflow_key=None (they inherit from their parent)
    # so they won't be found by for_workflow(). Scan the full registry.
    parent_keys = set(payloads.keys())
    for view_def in view_registry.list_all():
        if view_def.view_key in payloads:
            continue
        if view_def.status != "active":
            continue
        if view_def.parent_view_key and view_def.parent_view_key in parent_keys:
            rec = rec_by_key.get(view_def.view_key, {
                "view_key": view_def.view_key,
                "priority": "secondary",
                "rationale": "child of included parent",
            })
            payload = _build_view_payload(
                view_def=view_def,
                rec=rec,
                job_id=job_id,
                consumer_key=consumer_key,
                view_registry=view_registry,
                outputs_cache=outputs_cache,
                cache_batch=cache_batch,
                slim=slim,
            )
            payloads[payload.view_key] = payload

    # Auto-generate views for chapter-targeted phases that have no view definitions
    if plan:
        _inject_chapter_views(plan, payloads, job_id, outputs_cache=outputs_cache, cache_batch=cache_batch, slim=slim)

    top_level = _build_view_tree(payloads, view_registry)
    return {
        "job": job,
        "plan_id": plan_id,
        "plan": plan,
        "workflow_key": workflow_key,
        "thinker_name": thinker_name,
        "strategy_summary": strategy_summary,
        "top_level": top_level,
        "payloads": payloads,
        "view_registry": view_registry,
        "recommended": recommended,
        "all_outputs": all_outputs,
        "outputs_cache": outputs_cache,
    }


def _prepare_page_payloads(
    job_id: str,
    *,
    consumer_key: str,
    slim: bool = False,
) -> dict[str, Any]:
    """Build the render tree inputs shared by /page and /status."""

    job = get_job(job_id)
    if job is None:
        raise ValueError(f"Job not found: {job_id}")

    workflow_key = _resolve_workflow_key(job)
    recommended = _get_recommendations(
        job_id,
        job["plan_id"],
        workflow_key=workflow_key,
        consumer_key=consumer_key,
    )
    return _prepare_page_payloads_for_recommendations(
        job_id,
        consumer_key=consumer_key,
        recommended=recommended,
        slim=slim,
    )


def build_presentation_manifest(
    job_id: str,
    *,
    consumer_key: str,
    slim: bool = False,
) -> EffectivePresentationManifest:
    """Build the single consumer-scoped effective manifest for a page."""

    page_inputs = _prepare_page_payloads(job_id, consumer_key=consumer_key, slim=slim)
    _attach_reading_scaffolds(job_id, page_inputs["payloads"])
    return build_effective_manifest(
        job_id=job_id,
        plan_id=page_inputs["plan_id"],
        consumer_key=consumer_key,
        thinker_name=page_inputs["thinker_name"],
        strategy_summary=page_inputs["strategy_summary"],
        payloads=page_inputs["payloads"],
        all_outputs=page_inputs["all_outputs"],
        job=page_inputs["job"],
    )


def assemble_page(job_id: str, *, consumer_key: str, slim: bool = False) -> PagePresentation:
    """Assemble a complete page presentation for a job.

    This is the primary consumer endpoint. It:
    1. Loads the plan + job metadata
    2. Prefetches ALL outputs in a single query (avoids N+1)
    3. Gets refined view recommendations (or plan defaults)
    4. For each view, loads structured data or raw prose
    5. Builds the parent-child view tree
    6. Returns a complete PagePresentation

    When slim=True, skips raw prose content to reduce response size
    from ~1MB to ~10KB. Use the /view/{job_id}/{view_key} endpoint
    to lazy-load prose for individual views.
    """
    page_inputs = _prepare_page_payloads(job_id, consumer_key=consumer_key, slim=slim)
    payloads = page_inputs["payloads"]
    top_level = page_inputs["top_level"]

    _attach_reading_scaffolds(job_id, payloads)
    manifest = build_effective_manifest(
        job_id=job_id,
        plan_id=page_inputs["plan_id"],
        consumer_key=consumer_key,
        thinker_name=page_inputs["thinker_name"],
        strategy_summary=page_inputs["strategy_summary"],
        payloads=payloads,
        all_outputs=page_inputs["all_outputs"],
        job=page_inputs["job"],
    )

    execution_summary = _build_execution_summary(page_inputs["job"])

    refinement = load_view_refinement(job_id)
    refinement_applied = refinement is not None
    refinement_summary = refinement.get("changes_summary", "") if refinement else ""

    return PagePresentation(
        job_id=job_id,
        plan_id=page_inputs["plan_id"],
        consumer_key=consumer_key,
        presentation_version=2,
        presentation_contract_version=manifest.presentation_contract_version,
        presentation_hash=manifest.presentation_hash,
        presentation_content_hash=manifest.presentation_content_hash,
        prepared_at=manifest.prepared_at,
        artifacts_ready=manifest.artifacts_ready,
        manifest_schema_version=manifest.manifest_schema_version,
        trace_schema_version=manifest.trace_schema_version,
        resolver_version=manifest.resolver_version,
        thinker_name=page_inputs["thinker_name"],
        strategy_summary=page_inputs["strategy_summary"],
        views=top_level,
        view_count=len(payloads),
        execution_summary=execution_summary,
        refinement_applied=refinement_applied,
        refinement_summary=refinement_summary,
    )


def assemble_single_view(job_id: str, view_key: str, *, consumer_key: str) -> Optional[ViewPayload]:
    """Assemble a single view payload (for lazy loading on-demand views)."""
    job = get_job(job_id)
    if job is None:
        raise ValueError(f"Job not found: {job_id}")

    # Resolve workflow_key dynamically from job record
    workflow_key = _resolve_workflow_key(job)

    view_registry = get_view_registry()
    view_def = view_registry.get(view_key)
    if view_def is None:
        return None

    # Check recommendations for this view
    recommended = _get_recommendations(
        job_id,
        job["plan_id"],
        workflow_key=workflow_key,
        consumer_key=consumer_key,
    )
    rec = next(
        (r for r in recommended if r["view_key"] == view_key),
        {"view_key": view_key, "priority": "optional", "rationale": ""},
    )

    payload = _build_view_payload(
        view_def=view_def,
        rec=rec,
        job_id=job_id,
        consumer_key=consumer_key,
        view_registry=view_registry,
    )

    # Include children
    all_views = view_registry.for_workflow(workflow_key)
    children_defs = [
        v for v in all_views
        if v.parent_view_key == view_key and v.status == "active"
    ]
    for child_def in sorted(children_defs, key=lambda v: v.position):
        child_rec = next(
            (r for r in recommended if r["view_key"] == child_def.view_key),
            {"view_key": child_def.view_key, "priority": "secondary", "rationale": ""},
        )
        child_payload = _build_view_payload(
            view_def=child_def,
            rec=child_rec,
            job_id=job_id,
            consumer_key=consumer_key,
            view_registry=view_registry,
        )
        payload.children.append(child_payload)

    _synthesize_container_payload(payload, view_def, view_registry)
    single_payloads = {payload.view_key: payload, **{child.view_key: child for child in payload.children}}
    _attach_reading_scaffolds(job_id, single_payloads)
    build_effective_manifest(
        job_id=job_id,
        plan_id=job["plan_id"],
        consumer_key=consumer_key,
        thinker_name="",
        strategy_summary="",
        payloads=single_payloads,
        all_outputs=load_all_job_outputs(job_id, include_content=False),
        job=job,
    )

    return payload


def get_presentation_status(job_id: str, *, consumer_key: str) -> dict:
    """Check which views have data ready, need transformation, or are empty."""
    job = get_job(job_id)
    if job is None:
        raise ValueError(f"Job not found: {job_id}")

    page_inputs = _prepare_page_payloads(job_id, consumer_key=consumer_key, slim=True)
    _attach_reading_scaffolds(job_id, page_inputs["payloads"])
    manifest = build_effective_manifest(
        job_id=job_id,
        plan_id=page_inputs["plan_id"],
        consumer_key=consumer_key,
        thinker_name=page_inputs["thinker_name"],
        strategy_summary=page_inputs["strategy_summary"],
        payloads=page_inputs["payloads"],
        all_outputs=page_inputs["all_outputs"],
        job=job,
    )

    from .preparation_coordinator import get_preparation_state
    from .presentation_bridge import (
        _build_transformation_tasks,
        _load_output_by_id,
        _prepare_task_content,
    )

    recommended = _get_recommendations(
        job_id,
        job["plan_id"],
        consumer_key=consumer_key,
    )
    view_registry = get_view_registry()
    tasks, _skipped, _recommended = _build_transformation_tasks(
        job_id,
        consumer_key=consumer_key,
    )

    task_status_by_view: dict[str, list[dict]] = {}
    for task in tasks:
        output_row = _load_output_by_id(job_id, task.output_id)
        has_prose = output_row is not None
        has_structured = False
        if output_row is not None:
            _llm_content, cache_source_content = _prepare_task_content(job_id, task, output_row)
            has_structured = load_presentation_cache(
                output_id=task.output_id,
                section=task.section,
                source_content=cache_source_content,
            ) is not None
        task_status_by_view.setdefault(task.view_key, []).append(
            {
                "has_prose": has_prose,
                "has_structured": has_structured,
            }
        )

    statuses = []
    status_by_key: dict[str, dict] = {}
    for rec in recommended:
        view_def = view_registry.get(rec["view_key"])
        if view_def is None:
            row = {
                "view_key": rec["view_key"],
                "status": "not_found",
                "has_prose": False,
                "has_structured_data": False,
            }
            statuses.append(row)
            status_by_key[rec["view_key"]] = row
            continue

        direct_task_statuses = task_status_by_view.get(rec["view_key"], [])
        if direct_task_statuses:
            has_prose = any(item["has_prose"] for item in direct_task_statuses)
            has_structured = any(item["has_structured"] for item in direct_task_statuses)
        else:
            phase_number = view_def.data_source.phase_number
            engine_key = view_def.data_source.engine_key
            chain_key = getattr(view_def.data_source, "chain_key", None)
            scope = getattr(view_def.data_source, "scope", "aggregated")

            outputs = []
            if phase_number is not None:
                outputs = load_phase_outputs(
                    job_id=job_id,
                    phase_number=phase_number,
                    engine_key=engine_key,
                )
                if not outputs and chain_key and not engine_key:
                    outputs = load_phase_outputs(
                        job_id=job_id,
                        phase_number=phase_number,
                    )

            has_prose = len(outputs) > 0
            has_structured = False
            if outputs:
                composition = resolve_effective_render_contract(
                    view_def=view_def,
                    rec=rec,
                    consumer_key=consumer_key,
                    job_id=job_id,
                    view_registry=view_registry,
                )
                renderer_type, _, _ = adapt_renderer_for_consumer(
                    renderer_type=composition.renderer_type,
                    renderer_config=composition.renderer_config,
                    consumer_key=consumer_key,
                )
                template = (
                    get_transformation_registry().get(composition.template_key)
                    if composition.template_key
                    else find_applicable_template(
                        view_def=view_def,
                        renderer_type=renderer_type,
                    )
                )
                if template is not None:
                    if scope == "per_item":
                        latest_by_work: dict[str, dict] = {}
                        for output in outputs:
                            work_key = output.get("work_key") or ""
                            current = latest_by_work.get(work_key)
                            output_order = (
                                output.get("pass_number", 0),
                                output.get("created_at") or "",
                                output.get("id") or "",
                            )
                            current_order = (
                                current.get("pass_number", 0),
                                current.get("created_at") or "",
                                current.get("id") or "",
                            ) if current else None
                            if current is None or output_order > current_order:
                                latest_by_work[work_key] = output

                        for work_key, output in latest_by_work.items():
                            section = f"{template.template_key}:{work_key}" if work_key else template.template_key
                            cached = load_presentation_cache(
                                output_id=output["id"],
                                section=section,
                            )
                            if cached is not None:
                                has_structured = True
                                break
                    else:
                        latest = max(
                            outputs,
                            key=lambda output: (
                                output.get("pass_number", 0),
                                output.get("created_at") or "",
                                output.get("id") or "",
                            ),
                        )
                        has_structured = load_presentation_cache(
                            output_id=latest["id"],
                            section=template.template_key,
                        ) is not None

        row = {
            "view_key": rec["view_key"],
            "priority": rec.get("priority", "secondary"),
            "status": "ready" if has_structured else ("prose_only" if has_prose else "empty"),
            "has_prose": has_prose,
            "has_structured_data": has_structured,
        }
        statuses.append(row)
        status_by_key[rec["view_key"]] = row

    for rec in recommended:
        view_def = view_registry.get(rec["view_key"])
        if view_def is None:
            continue
        if not _is_chain_container_view(view_def, view_registry):
            continue

        child_defs = [
            child for child in view_registry.list_all()
            if getattr(child, "status", "active") == "active"
            and getattr(child, "parent_view_key", None) == view_def.view_key
        ]
        child_rows = [
            status_by_key.get(child.view_key)
            for child in child_defs
            if status_by_key.get(child.view_key) is not None
        ]
        if not child_rows:
            continue

        parent_row = status_by_key.get(view_def.view_key)
        if parent_row is None:
            continue

        if any(child["has_structured_data"] for child in child_rows):
            parent_row["has_structured_data"] = True
            parent_row["status"] = "ready"
            parent_row["derived_from_children"] = True

    for rec in recommended:
        view_def = view_registry.get(rec["view_key"])
        if view_def is None:
            continue

        parent_key = getattr(view_def, "parent_view_key", None)
        result_path = getattr(view_def.data_source, "result_path", None)
        if not parent_key or not result_path:
            continue

        row = status_by_key.get(view_def.view_key)
        parent_row = status_by_key.get(parent_key)
        if row is None or parent_row is None:
            continue
        if row["has_structured_data"]:
            continue
        if not parent_row["has_structured_data"]:
            continue

        row["has_structured_data"] = True
        row["status"] = "ready"
        row["derived_from_parent"] = parent_key

    return {
        "job_id": job_id,
        "consumer_key": consumer_key,
        "presentation_contract_version": manifest.presentation_contract_version,
        "presentation_hash": manifest.presentation_hash,
        "presentation_content_hash": manifest.presentation_content_hash,
        "prepared_at": manifest.prepared_at,
        "artifacts_ready": manifest.artifacts_ready,
        "manifest_schema_version": manifest.manifest_schema_version,
        "trace_schema_version": manifest.trace_schema_version,
        "resolver_version": manifest.resolver_version,
        "preparation": get_preparation_state(job_id),
        "views": statuses,
        "total": len(statuses),
        "ready": sum(1 for s in statuses if s["status"] == "ready"),
        "prose_only": sum(1 for s in statuses if s["status"] == "prose_only"),
        "empty": sum(1 for s in statuses if s["status"] == "empty"),
    }


def _build_presentation_freshness(
    *,
    job_id: str,
    consumer_key: str = "the-critic",
    payloads: dict[str, ViewPayload],
    all_outputs: list[dict[str, Any]],
    job: dict[str, Any],
) -> dict[str, Any]:
    """Compute stable freshness metadata from the normalized slim page state.

    Fingerprints intentionally exclude row ids, created_at timestamps, pass
    numbers, and prepared_at. Only stable structural fields, actual view content,
    reading scaffold content, and stable output content hashes participate.
    """

    ordered_payloads = sorted(payloads.values(), key=lambda payload: (payload.position, payload.view_key))
    contract_manifest: list[dict[str, Any]] = []
    content_manifest: list[dict[str, Any]] = []
    artifacts_ready = True

    for payload in ordered_payloads:
        scaffold_type = resolve_scaffold_type(payload, payloads)
        output_hashes = _collect_output_hashes_for_payload(payload, all_outputs)
        section_keys = [
            section.get("key")
            for section in list((payload.renderer_config or {}).get("sections", []) or [])
            if isinstance(section, dict) and section.get("key")
        ]
        child_keys = sorted(child.view_key for child in (payload.children or []))

        contract_manifest.append(
            {
                "view_key": payload.view_key,
                "consumer_key": consumer_key,
                "renderer_type": payload.renderer_type,
                "presentation_stance": payload.presentation_stance,
                "position": payload.position,
                "visibility": payload.visibility,
                "selection_priority": getattr(payload, "selection_priority", None),
                "navigation_state": getattr(payload, "navigation_state", None),
                "source_parent_view_key": payload.source_parent_view_key,
                "promoted_to_top_level": payload.promoted_to_top_level,
                "top_level_group": payload.top_level_group,
                "section_keys": section_keys,
                "child_keys": child_keys,
                "scaffold_type": scaffold_type,
            }
        )
        content_manifest.append(
            {
                "view_key": payload.view_key,
                "consumer_key": consumer_key,
                "structured_data": payload.structured_data,
                "items": payload.items,
                "reading_scaffold": payload.reading_scaffold,
                "output_hashes": output_hashes,
            }
        )

        if _is_required_default_payload(payload) and not _is_payload_ready_for_default_page(
            payload,
            scaffold_type=scaffold_type,
            output_hashes=output_hashes,
        ):
            artifacts_ready = False

    return {
        "presentation_hash": _stable_fingerprint(contract_manifest),
        "presentation_content_hash": _stable_fingerprint(content_manifest),
        "prepared_at": _resolve_prepared_at(job, all_outputs),
        "artifacts_ready": artifacts_ready,
    }


def _stable_fingerprint(value: Any) -> str:
    serialized = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _collect_output_hashes_for_payload(
    payload: ViewPayload,
    all_outputs: list[dict[str, Any]],
) -> list[str]:
    """Collect stable output content hashes for the payload's underlying data."""

    phase_number = getattr(payload, "phase_number", None)
    if phase_number is None:
        return []

    engine_key = getattr(payload, "engine_key", None)
    relevant = [
        output
        for output in all_outputs
        if output.get("phase_number") == phase_number
        and (
            (engine_key and output.get("engine_key") == engine_key)
            or (not engine_key)
        )
    ]

    unique_hashes = {
        output.get("content_hash") or ""
        for output in relevant
        if output.get("content_hash")
    }
    return sorted(unique_hashes)


def _is_required_default_payload(payload: ViewPayload) -> bool:
    return getattr(payload, "visibility", "if_data_exists") != "on_demand"


def _is_payload_ready_for_default_page(
    payload: ViewPayload,
    *,
    scaffold_type: Optional[str],
    output_hashes: list[str],
) -> bool:
    if scaffold_type and payload.reading_scaffold is None:
        return False

    if payload.items is not None:
        if not payload.items:
            return False
        if any(bool(item.get("has_structured_data")) for item in payload.items if isinstance(item, dict)):
            return True
        return bool(output_hashes)

    if payload.has_structured_data:
        return True

    return bool(output_hashes)


def _resolve_prepared_at(job: dict[str, Any], all_outputs: list[dict[str, Any]]) -> str:
    timestamps = [
        output.get("created_at") or ""
        for output in all_outputs
        if output.get("created_at")
    ]
    for field in ("completed_at", "started_at", "created_at"):
        value = job.get(field) or ""
        if value:
            timestamps.append(value)
    return max(timestamps) if timestamps else datetime.now(UTC).isoformat()


def _validate_payload_data(
    view_key: str,
    renderer_type: str,
    renderer_config: dict[str, Any],
    structured_data,
) -> None:
    """Validate structured_data against renderer's input_data_schema at assembly time.

    Always runs in WARN mode — observational logging only, never modifies
    or strips data, never blocks assembly. Wrapped in try/except so
    validation errors never crash the page assembly.
    """
    try:
        from src.renderers.validator import ValidationMode, validate_renderer_data

        result = validate_renderer_data(
            renderer_key=renderer_type,
            data=structured_data,
            renderer_config=renderer_config,
            mode=ValidationMode.WARN,
        )
        if not result.valid:
            first_error = result.errors[0]["message"] if result.errors else "unknown"
            logger.warning(
                f"[renderer-validation:assembly] {view_key} "
                f"renderer={renderer_type}: "
                f"cached data invalid — {first_error} "
                f"({len(result.errors)} error(s) total)"
            )
    except Exception:
        logger.debug(
            f"[renderer-validation:assembly] Could not validate {view_key}",
            exc_info=True,
        )


# --- Internal helpers ---


def _build_outputs_cache(all_outputs: list[dict]) -> dict:
    """Index prefetched outputs for fast lookup by (phase_number, engine_key).

    Returns a dict with keys:
      - ("all",)  → all outputs
      - (phase_number,) → outputs for that phase
      - (phase_number, engine_key) → outputs for that phase+engine
    """
    cache: dict[tuple, list[dict]] = {("all",): all_outputs}
    for o in all_outputs:
        pn = o.get("phase_number")
        ek = o.get("engine_key")
        cache.setdefault((pn,), []).append(o)
        cache.setdefault((pn, ek), []).append(o)
    return cache


def _get_cached_outputs(
    outputs_cache: dict,
    phase_number: Optional[float],
    engine_key: Optional[str],
) -> list[dict]:
    """Retrieve outputs from the prefetched cache."""
    if phase_number is None:
        return []
    if engine_key is not None:
        return outputs_cache.get((phase_number, engine_key), [])
    return outputs_cache.get((phase_number,), [])


def _get_recommendations(
    job_id: str,
    plan_id: str,
    workflow_key: str = "intellectual_genealogy",
    *,
    consumer_key: str,
) -> list[dict]:
    """Get view recommendations — refined if available, else plan defaults."""
    refinement = load_view_refinement(job_id)
    if refinement and refinement.get("refined_views"):
        return refinement["refined_views"]

    plan = load_plan(plan_id)
    if plan and plan.recommended_views:
        return [v.model_dump() for v in plan.recommended_views]

    return get_default_recommendations_for_workflow(
        workflow_key,
        consumer_key=consumer_key,
    )


def _build_view_payload(
    view_def,
    rec: dict,
    job_id: str,
    consumer_key: str,
    view_registry=None,
    outputs_cache: Optional[dict] = None,
    cache_batch: Optional[dict] = None,
    slim: bool = False,
) -> ViewPayload:
    """Build a ViewPayload for a single view definition."""
    ds = view_def.data_source
    phase_number = ds.phase_number
    engine_key = ds.engine_key
    chain_key = ds.chain_key
    scope = ds.scope
    result_path = ds.result_path or ""
    composition = resolve_effective_render_contract(
        view_def=view_def,
        rec=rec,
        consumer_key=consumer_key,
        job_id=job_id,
        view_registry=view_registry,
    )
    renderer_type, renderer_config, adaptation = adapt_renderer_for_consumer(
        renderer_type=composition.renderer_type,
        renderer_config=composition.renderer_config,
        consumer_key=consumer_key,
    )
    selection_priority = normalize_selection_priority(rec.get("priority"))
    navigation_state = normalize_navigation_state(
        collapse_into_parent=bool(rec.get("collapse_into_parent", False))
    )
    legacy_visibility = derive_legacy_visibility(
        authored_visibility=view_def.visibility,
        selection_priority=selection_priority,
        navigation_state=navigation_state,
    )
    structuring_policy = (
        normalize_structuring_policy(view_def=view_def)
        if view_registry is not None
        else None
    )
    derivation_kind = (
        derive_view_derivation_kind(
            view_def=view_def,
            view_registry=view_registry,
        )
        if view_registry is not None
        else None
    )

    # Load data
    structured_data = None
    raw_prose = None
    items = None
    has_structured = False
    defer_to_children = bool(view_registry is not None and _is_chain_container_view(view_def, view_registry))

    if scope == "per_item":
        items = _load_per_item_data(
            job_id, phase_number, engine_key,
            chain_key=chain_key, outputs_cache=outputs_cache,
            cache_batch=cache_batch, slim=slim,
        )
    else:
        structured_data, raw_prose = _load_aggregated_data(
            job_id, phase_number, engine_key, chain_key,
            outputs_cache=outputs_cache, cache_batch=cache_batch, slim=slim,
            view_key=view_def.view_key,
        )
        if defer_to_children:
            structured_data = None
        else:
            if not _should_preserve_root_payload(
                renderer_type,
                renderer_config,
                result_path,
            ):
                structured_data = _extract_result_path_value(structured_data, result_path)
            structured_data = _normalize_view_structured_data(
                view_def.view_key,
                structured_data,
            )
            structured_data = _normalize_renderer_shape(
                renderer_type,
                renderer_config,
                structured_data,
            )
            structured_data, renderer_config = _prepare_structured_payload_for_renderer(
                renderer_type,
                renderer_config,
                structured_data,
            )
            has_structured = structured_data is not None

    # Assembly-time validation: check structured_data against renderer schema.
    # Catches stale/bad cached data written before schemas existed.
    # Always WARN mode — never blocks assembly.
    if structured_data is not None:
        _validate_payload_data(
            view_def.view_key,
            renderer_type,
            renderer_config,
            structured_data,
        )

    return ViewPayload(
        view_key=view_def.view_key,
        view_name=rec.get("display_label_override") or view_def.view_name,
        description=view_def.description,
        renderer_type=renderer_type,
        renderer_config=renderer_config,
        presentation_stance=composition.presentation_stance,
        priority=rec.get("priority", "secondary"),
        rationale=rec.get("rationale", ""),
        data_quality=composition.data_quality,
        top_level_group=rec.get("top_level_group"),
        source_parent_view_key=getattr(view_def, "parent_view_key", None),
        promoted_to_top_level=bool(rec.get("promote_to_top_level", False)),
        selection_priority=selection_priority,
        navigation_state=navigation_state,
        structuring_policy=structuring_policy,
        semantic_scaffold_type=None,
        scaffold_hosting_mode="fallback" if adaptation else None,
        derivation_kind=derivation_kind,
        phase_number=phase_number,
        engine_key=engine_key,
        chain_key=chain_key,
        scope=scope,
        has_structured_data=has_structured,
        structured_data=structured_data,
        reading_scaffold=None,
        raw_prose=raw_prose,
        prose_ref_view_key=None,
        items=items,
        tab_count=None,  # TODO: resolve tab_count_field
        visibility=legacy_visibility,
        position=(
            rec.get("top_level_position_override")
            if rec.get("top_level_position_override") is not None
            else view_def.position
        ),
        children=[],
    )



# _resolve_chain_engine_keys imported from work_key_utils


def _load_aggregated_data(
    job_id: str,
    phase_number: Optional[float],
    engine_key: Optional[str],
    chain_key: Optional[str],
    outputs_cache: Optional[dict] = None,
    cache_batch: Optional[dict] = None,
    slim: bool = False,
    view_key: Optional[str] = None,
) -> tuple[Optional[dict], Optional[str]]:
    """Load structured data and/or raw prose for an aggregated view.

    For chain-backed views (chain_key set, engine_key None), resolves the
    chain's engine keys and searches templates for ALL engines in the chain.
    Also concatenates ALL engine outputs for the phase into raw_prose.

    When slim=True, skips building raw_prose (returns None for prose).
    When outputs_cache is provided, uses prefetched data instead of querying DB.

    Returns (structured_data, raw_prose).
    """
    if phase_number is None:
        return None, None

    # Load outputs — from cache if available, else query DB
    if outputs_cache is not None:
        outputs = _get_cached_outputs(outputs_cache, phase_number, engine_key)
        if not outputs and chain_key:
            outputs = _get_cached_outputs(outputs_cache, phase_number, None)
    else:
        outputs = load_phase_outputs(
            job_id=job_id,
            phase_number=phase_number,
            engine_key=engine_key,
        )
        if not outputs and chain_key:
            outputs = load_phase_outputs(job_id=job_id, phase_number=phase_number)

    if not outputs:
        return None, None

    # Build raw_prose (skip in slim mode)
    raw_prose = None
    if not slim:
        if chain_key and not engine_key:
            sorted_outputs = sorted(outputs, key=lambda o: o.get("pass_number", 0))
            prose_parts = []
            for o in sorted_outputs:
                content = o.get("content", "")
                if content:
                    eng = o.get("engine_key", "unknown")
                    prose_parts.append(f"## [{eng}]\n\n{content}")
            raw_prose = "\n\n---\n\n".join(prose_parts) if prose_parts else ""
        else:
            sorted_outputs = sorted(outputs, key=lambda o: o.get("pass_number", 0))
            if len(sorted_outputs) > 1:
                prose_parts = []
                for o in sorted_outputs:
                    content = o.get("content", "")
                    if content:
                        prose_parts.append(f"## [Pass {o.get('pass_number', 0)}]\n\n{content}")
                raw_prose = "\n\n---\n\n".join(prose_parts) if prose_parts else ""
            else:
                raw_prose = sorted_outputs[0].get("content", "") if sorted_outputs else ""

    # Get latest output for structured data lookup
    latest = max(outputs, key=lambda o: o.get("pass_number", 0))

    # Prefer persisted workflow-level structured payloads when a specific
    # view contract has already been normalized and saved in output metadata.
    metadata = _load_output_metadata(latest)
    structured_payloads = metadata.get("structured_payloads") or {}
    if isinstance(structured_payloads, dict) and view_key and view_key in structured_payloads:
        return structured_payloads.get(view_key), raw_prose

    # Check presentation_cache for structured data
    structured_data = None
    from src.transformations.registry import get_transformation_registry
    transform_registry = get_transformation_registry()

    # Determine which engine keys to search templates for
    search_engine_keys = []
    if engine_key:
        search_engine_keys = [engine_key]
    elif chain_key:
        search_engine_keys = _resolve_chain_engine_keys(chain_key)

    # For multi-pass single-engine views, the bridge caches with
    # content_override (concatenated passes) but skips freshness check.
    # We must also skip freshness here since raw_prose is the concatenation
    # but the cache was saved without a source hash.
    is_multi_pass_single_engine = (
        engine_key and not chain_key
        and len(outputs) > 1
    )

    for ek in search_engine_keys:
        templates = transform_registry.for_engine(ek)
        for t in templates:
            # Use batch cache if available (zero DB queries)
            if cache_batch is not None:
                cached = cache_batch.get((latest["id"], t.template_key))
            else:
                # Fallback to individual query
                skip_freshness = (chain_key and not engine_key) or is_multi_pass_single_engine
                cached = load_presentation_cache(
                    output_id=latest["id"],
                    section=t.template_key,
                    source_content=None if skip_freshness else raw_prose,
                )
            if cached is not None:
                structured_data = cached
                break
        if structured_data is not None:
            break

    return structured_data, raw_prose



# _infer_work_key_from_content, _sanitize_work_key_for_presenter,
# _try_split_collapsed_outputs imported from work_key_utils


def _load_per_item_data(
    job_id: str,
    phase_number: Optional[float],
    engine_key: Optional[str],
    chain_key: Optional[str] = None,
    outputs_cache: Optional[dict] = None,
    cache_batch: Optional[dict] = None,
    slim: bool = False,
) -> list[dict]:
    """Load per-item data (one entry per prior work).

    For chain-backed per-item views, loads ALL phase outputs, groups by
    work_key, concatenates all engine outputs per work_key, and searches
    templates using chain engine keys.

    When outputs_cache is provided, uses prefetched data instead of querying DB.
    When slim=True, skips raw_prose in each item.

    Handles legacy imported data where all outputs share work_key='target'
    by attempting content-based splitting using prior work titles from the plan.

    Returns a list of {work_key, structured_data, raw_prose} dicts.
    """
    if phase_number is None:
        return []

    # Load outputs — from cache if available, else query DB
    if outputs_cache is not None:
        outputs = _get_cached_outputs(outputs_cache, phase_number, engine_key)
        if not outputs and chain_key and not engine_key:
            outputs = _get_cached_outputs(outputs_cache, phase_number, None)
    else:
        outputs = load_phase_outputs(
            job_id=job_id,
            phase_number=phase_number,
            engine_key=engine_key,
        )
        # For chain-backed views with no engine_key, get all outputs for the phase
        if not outputs and chain_key and not engine_key:
            outputs = load_phase_outputs(job_id=job_id, phase_number=phase_number)

    # Group by work_key
    if chain_key and not engine_key:
        # Chain-backed: collect ALL outputs per work_key, concatenate content

        # First, try to detect and fix collapsed outputs (legacy import issue
        # where all outputs share work_key='target' despite being per-work)
        #
        # In slim mode, outputs may lack content (loaded without it for performance).
        # Content-based splitting needs content, so reload with content if needed.
        outputs_for_split = outputs
        if slim and outputs:
            unique_wks = set(o.get("work_key", "") for o in outputs if o.get("work_key"))
            if len(unique_wks) == 1:
                # Likely collapsed — reload WITH content for splitting
                outputs_for_split = load_phase_outputs(
                    job_id=job_id, phase_number=phase_number,
                )
                logger.info(
                    f"[per-item-slim] Reloaded {len(outputs_for_split)} outputs "
                    f"with content for collapsed work_key splitting"
                )

        split_result = _try_split_collapsed_outputs(outputs_for_split, job_id, chain_key)
        if split_result is not None:
            # Outputs were re-keyed by content-based matching
            by_work_all = split_result
        else:
            by_work_all: dict[str, list[dict]] = {}
            for o in outputs:
                work_key = o.get("work_key", "")
                if not work_key:
                    continue
                by_work_all.setdefault(work_key, []).append(o)

        by_work: dict[str, dict] = {}
        for work_key, work_outputs in by_work_all.items():
            sorted_wo = sorted(work_outputs, key=lambda o: o.get("pass_number", 0))
            # Use the last output as the "primary" (for output_id, cache lookup)
            latest = sorted_wo[-1]
            # Concatenate all engine outputs for this work
            prose_parts = []
            for wo in sorted_wo:
                content = wo.get("content", "")
                if content:
                    eng = wo.get("engine_key", "unknown")
                    prose_parts.append(f"## [{eng}]\n\n{content}")
            combined_content = "\n\n---\n\n".join(prose_parts) if prose_parts else ""
            # Store combined content in a synthetic entry.
            # Also keep ALL output_ids so cache lookup can try each one
            # (the bridge may have cached against a different output_id
            # than the one we pick as "latest" here).
            all_ids = list({wo["id"] for wo in work_outputs})
            by_work[work_key] = {
                **latest,
                "_combined_content": combined_content,
                "_all_output_ids": all_ids,
            }
    else:
        # Single engine: keep latest pass per work_key
        by_work = {}
        for o in outputs:
            work_key = o.get("work_key", "")
            if not work_key:
                continue
            existing = by_work.get(work_key)
            if existing is None or _is_newer_output(o, existing):
                by_work[work_key] = o

    items = []
    from src.transformations.registry import get_transformation_registry
    transform_registry = get_transformation_registry()

    # Determine which engine keys to search templates for
    search_engine_keys = []
    if engine_key:
        search_engine_keys = [engine_key]
    elif chain_key:
        search_engine_keys = _resolve_chain_engine_keys(chain_key)

    for work_key, output in sorted(by_work.items()):
        content = "" if slim else output.get("_combined_content", output.get("content", ""))

        # Check for structured data.
        # Try ALL output_ids in the work_key group, not just the "latest",
        # because the bridge may have cached against a different output_id
        # than the one we picked as representative.
        candidate_ids = output.get("_all_output_ids", [output["id"]])
        structured = None
        for ek in search_engine_keys:
            templates = transform_registry.for_engine(ek)
            for t in templates:
                section = f"{t.template_key}:{work_key}"
                for oid in candidate_ids:
                    if cache_batch is not None:
                        cached = cache_batch.get((oid, section))
                    else:
                        cached = load_presentation_cache(
                            output_id=oid,
                            section=section,
                            source_content=None if (chain_key and not engine_key) else content,
                        )
                    if cached is not None:
                        structured = cached
                        break
                if structured is not None:
                    break
            if structured is not None:
                break

        # Extract work_title from metadata if available (set by content-based splitting)
        meta = output.get("metadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        work_meta = _resolve_work_metadata(
            job_id,
            work_key,
            fallback_title=meta.get("_inferred_work_title", ""),
        )
        work_title = work_meta.get("display_title", "")
        work_year = work_meta.get("year")

        if structured is not None and isinstance(structured, dict):
            structured = dict(structured)
            if work_title:
                structured["work_title"] = work_title
            if work_year is not None:
                structured["work_year"] = work_year
            structured = _normalize_relationship_card(structured)

        item = {
            "work_key": work_key,
            "has_structured_data": structured is not None,
            "structured_data": structured,
            "raw_prose": content if not slim else None,
        }
        if work_title:
            item["work_title"] = work_title
        if work_year is not None:
            item["work_year"] = work_year
        items.append(item)

    return items


def _inject_chapter_views(
    plan,
    payloads: dict[str, ViewPayload],
    job_id: str,
    outputs_cache: Optional[dict] = None,
    cache_batch: Optional[dict] = None,
    slim: bool = False,
) -> None:
    """Auto-generate ViewPayloads for chapter-targeted phases.

    The planner can dynamically create phases with document_scope="chapter".
    Since no static view definitions exist for these dynamic phases, we
    auto-generate per-item views so chapter outputs appear in the frontend.
    """
    for phase in plan.phases:
        if phase.skip:
            continue
        doc_scope = getattr(phase, "document_scope", "whole") or "whole"
        if doc_scope != "chapter":
            continue

        # Check if any existing view already covers this phase
        phase_covered = any(
            p.phase_number == phase.phase_number
            for p in payloads.values()
        )
        if phase_covered:
            continue

        # Build a synthetic per-item view for this chapter-targeted phase
        view_key = f"auto_chapter_{phase.phase_number}"

        # Load chapter items using the same per_item loader
        chain_key = phase.chain_key
        engine_key = phase.engine_key
        items = _load_per_item_data(
            job_id, phase.phase_number, engine_key, chain_key=chain_key,
            outputs_cache=outputs_cache, cache_batch=cache_batch, slim=slim,
        )

        # Add chapter metadata to each item
        chapter_targets = getattr(phase, "chapter_targets", None) or []
        chapter_lookup = {ct.chapter_id: ct for ct in chapter_targets}
        for item in items:
            wk = item.get("work_key", "")
            ct = chapter_lookup.get(wk)
            if ct:
                item["_is_chapter"] = True
                item["_chapter_title"] = ct.chapter_title
                item["_chapter_rationale"] = ct.rationale
            else:
                item["_is_chapter"] = True
                item["_chapter_title"] = wk

        if not items:
            continue

        chapter_count = len(items)
        engine_label = chain_key or engine_key or "analysis"

        payload = ViewPayload(
            view_key=view_key,
            view_name=f"Chapter Analysis — Phase {phase.phase_number}",
            description=(
                f"Per-chapter analysis from {phase.phase_name} "
                f"({chapter_count} chapters, engine: {engine_label})"
            ),
            renderer_type="per_item_cards",
            renderer_config={"card_style": "chapter"},
            presentation_stance=None,
            priority="primary",
            rationale=phase.rationale or "Chapter-level targeting by adaptive planner",
            data_quality="standard" if items else "empty",
            phase_number=phase.phase_number,
            engine_key=engine_key,
            chain_key=chain_key,
            scope="per_item",
            has_structured_data=any(i.get("has_structured_data") for i in items),
            items=items,
            tab_count=chapter_count,
            visibility="if_data_exists",
            position=phase.phase_number * 10,  # Sort after corresponding phase
        )
        payloads[view_key] = payload
        logger.info(
            f"Auto-generated chapter view '{view_key}' for phase {phase.phase_number}: "
            f"{chapter_count} chapter items"
        )


def _build_view_tree(
    payloads: dict[str, ViewPayload],
    view_registry,
) -> list[ViewPayload]:
    """Build parent-child view tree from flat dict.

    Returns top-level views sorted by position, with children nested.
    """
    top_level: list[ViewPayload] = []
    source_children_by_parent: dict[str, list[ViewPayload]] = {}

    for key, payload in payloads.items():
        view_def = view_registry.get(key)
        parent_key = getattr(payload, "source_parent_view_key", None) if view_def else None
        if parent_key and parent_key in payloads:
            source_children_by_parent.setdefault(parent_key, []).append(payload)

        if parent_key and parent_key in payloads and not getattr(payload, "promoted_to_top_level", False):
            payloads[parent_key].children.append(payload)
        else:
            top_level.append(payload)

    # Sort by position
    top_level.sort(key=lambda v: v.position)
    for payload in payloads.values():
        payload.children.sort(key=lambda v: v.position)
        view_def = view_registry.get(payload.view_key)
        if view_def is not None:
            logical_children = sorted(
                source_children_by_parent.get(payload.view_key, []),
                key=lambda child: child.position,
            )
            _synthesize_container_payload(payload, view_def, view_registry, logical_children)

    _dedupe_shared_raw_prose(payloads)

    return top_level


def _synthesize_container_payload(
    payload: ViewPayload,
    view_def,
    view_registry,
    logical_children: Optional[list[ViewPayload]] = None,
) -> None:
    """Build parent structured data from child payloads when sections map cleanly."""
    if not _is_chain_container_view(view_def, view_registry):
        return
    child_payload_list = logical_children if logical_children is not None else payload.children
    if not child_payload_list:
        return

    child_defs = _iter_active_child_views(view_registry, view_def.view_key)
    section_matches = _match_container_sections_to_children(view_def, child_defs)
    if not section_matches:
        return

    child_payloads = {child.view_key: child for child in child_payload_list}
    container_data: dict[str, Any] = {}
    for section_key, child_def in section_matches.items():
        child_payload = child_payloads.get(child_def.view_key)
        if child_payload is None or child_payload.structured_data is None:
            continue
        container_data[section_key] = child_payload.structured_data

    if not container_data:
        payload.structured_data = None
        payload.has_structured_data = False
        return

    payload.structured_data = container_data
    payload.has_structured_data = True


def _dedupe_shared_raw_prose(payloads: dict[str, ViewPayload]) -> None:
    """Replace identical parent/child prose blobs with a parent reference."""
    for payload in payloads.values():
        parent_key = getattr(payload, "source_parent_view_key", None)
        if not parent_key:
            continue

        parent = payloads.get(parent_key)
        parent_raw_prose = getattr(parent, "raw_prose", None) if parent is not None else None
        child_raw_prose = getattr(payload, "raw_prose", None)
        if parent is None or not parent_raw_prose or not child_raw_prose:
            continue
        if parent_raw_prose != child_raw_prose:
            continue
        if not _shares_prose_source(parent, payload):
            continue

        payload.raw_prose = None
        payload.prose_ref_view_key = parent.view_key


def _attach_reading_scaffolds(job_id: str, payloads: dict[str, ViewPayload]) -> None:
    """Attach matching reading scaffolds from the artifact store."""
    if not payloads:
        return

    artifact_batch = load_presentation_artifact_batch(
        job_id=job_id,
        artifact_kind=READING_SCAFFOLD_ARTIFACT_KIND,
    )
    resolved_scaffolds: dict[str, dict[str, Any]] = {}
    ordered_payloads = sorted(
        payloads.values(),
        key=lambda payload: (
            resolve_scaffold_type(payload, payloads) == "composite_overview",
            payload.position,
        ),
    )

    for payload in ordered_payloads:
        scaffold_type = resolve_scaffold_type(payload, payloads)
        if scaffold_type is None:
            payload.reading_scaffold = None
            continue

        input_hash = compute_scaffold_input_hash(
            payload,
            payloads,
            generated_scaffolds=resolved_scaffolds,
        )
        prompt_version = SCAFFOLD_PROMPT_VERSIONS[scaffold_type]
        payload.reading_scaffold = artifact_batch.get(
            (
                payload.view_key,
                READING_SCAFFOLD_ARTIFACT_VERSION,
                prompt_version,
                input_hash,
            )
        )
        if payload.reading_scaffold:
            resolved_scaffolds[payload.view_key] = payload.reading_scaffold


def _shares_prose_source(parent: ViewPayload, child: ViewPayload) -> bool:
    """True when parent/child prose came from the same underlying source rows."""
    if parent.phase_number is not None and child.phase_number is not None:
        if parent.phase_number != child.phase_number:
            return False

    if parent.scope != child.scope:
        return False

    same_engine = bool(parent.engine_key and child.engine_key and parent.engine_key == child.engine_key)
    same_chain = bool(parent.chain_key and child.chain_key and parent.chain_key == child.chain_key)
    return same_engine or same_chain


def _build_execution_summary(job: dict) -> dict:
    """Build execution summary from job record."""
    phase_results = job.get("phase_results", {})
    if isinstance(phase_results, str):
        phase_results = json.loads(phase_results) if phase_results else {}

    return {
        "status": job.get("status", "unknown"),
        "total_llm_calls": job.get("total_llm_calls", 0),
        "total_input_tokens": job.get("total_input_tokens", 0),
        "total_output_tokens": job.get("total_output_tokens", 0),
        "created_at": job.get("created_at", ""),
        "started_at": job.get("started_at", ""),
        "completed_at": job.get("completed_at", ""),
        "phase_results": phase_results,
    }
