"""Generate additive reading scaffolds from canonical presentation payloads."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional

from src.llm.client import GENERATION_MODEL, call_extraction_model, parse_llm_json_response

from .artifact_store import (
    load_presentation_artifact,
    save_presentation_artifact,
)
from .scaffold_contracts import resolve_effective_scaffold_type_for_payload
from .schemas import (
    ScaffoldArtifactDetail,
    ScaffoldGenerationResult,
)

logger = logging.getLogger(__name__)

READING_SCAFFOLD_ARTIFACT_KIND = "reading_scaffold"
READING_SCAFFOLD_ARTIFACT_VERSION = 1

SCAFFOLD_PROMPT_VERSIONS = {
    "composite_overview": "2026-03-12-composite-v1",
    "concept_atlas": "2026-03-12-concept-atlas-v1",
    "argument_map": "2026-03-12-argument-map-v1",
}


def generate_reading_scaffolds(
    job_id: str,
    *,
    consumer_key: str,
    force: bool = False,
) -> ScaffoldGenerationResult:
    """Generate reading scaffolds for scaffold-worthy views in a job."""
    from .presentation_api import assemble_page

    page = assemble_page(job_id, consumer_key=consumer_key, slim=True)
    payload_by_key = flatten_payload_tree(page.views)

    details: list[ScaffoldArtifactDetail] = []
    generated_scaffolds: dict[str, dict[str, Any]] = {}

    candidates = _collect_scaffold_candidates(payload_by_key)
    ordered_candidates = sorted(
        candidates,
        key=lambda item: (item["scaffold_type"] == "composite_overview", item["payload"].position),
    )

    generated = 0
    cached = 0
    failed = 0

    for candidate in ordered_candidates:
        payload = candidate["payload"]
        scaffold_type = candidate["scaffold_type"]
        prompt_version = SCAFFOLD_PROMPT_VERSIONS[scaffold_type]
        input_hash = compute_scaffold_input_hash(
            payload,
            payload_by_key,
            generated_scaffolds=generated_scaffolds,
        )

        if not force:
            cached_content = load_presentation_artifact(
                job_id=job_id,
                view_key=payload.view_key,
                artifact_kind=READING_SCAFFOLD_ARTIFACT_KIND,
                artifact_version=READING_SCAFFOLD_ARTIFACT_VERSION,
                prompt_version=prompt_version,
                input_hash=input_hash,
            )
            if cached_content is not None:
                generated_scaffolds[payload.view_key] = cached_content
                cached += 1
                details.append(
                    ScaffoldArtifactDetail(
                        view_key=payload.view_key,
                        scaffold_type=scaffold_type,
                        status="cached",
                        prompt_version=prompt_version,
                        input_hash=input_hash,
                    )
                )
                continue

        try:
            scaffold, model_used = build_reading_scaffold(
                payload,
                payload_by_key,
                generated_scaffolds=generated_scaffolds,
            )
            saved = save_presentation_artifact(
                job_id=job_id,
                view_key=payload.view_key,
                artifact_kind=READING_SCAFFOLD_ARTIFACT_KIND,
                artifact_version=READING_SCAFFOLD_ARTIFACT_VERSION,
                prompt_version=prompt_version,
                input_hash=input_hash,
                content=scaffold,
                model_used=model_used,
            )
            if not saved:
                raise RuntimeError("Failed to persist reading scaffold artifact")
            generated_scaffolds[payload.view_key] = scaffold
            generated += 1
            details.append(
                ScaffoldArtifactDetail(
                    view_key=payload.view_key,
                    scaffold_type=scaffold_type,
                    status="generated",
                    prompt_version=prompt_version,
                    input_hash=input_hash,
                    model_used=model_used,
                )
            )
        except Exception as exc:
            logger.warning(
                "Reading scaffold generation failed for %s/%s: %s",
                payload.view_key,
                scaffold_type,
                exc,
                exc_info=True,
            )
            failed += 1
            details.append(
                ScaffoldArtifactDetail(
                    view_key=payload.view_key,
                    scaffold_type=scaffold_type,
                    status="failed",
                    prompt_version=prompt_version,
                    input_hash=input_hash,
                    error=str(exc),
                )
            )

    return ScaffoldGenerationResult(
        job_id=job_id,
        artifacts_planned=len(ordered_candidates),
        artifacts_generated=generated,
        artifacts_cached=cached,
        artifacts_failed=failed,
        details=details,
    )


def flatten_payload_tree(views: list[Any]) -> dict[str, Any]:
    """Flatten nested view payloads into a lookup by view_key."""
    flat: dict[str, Any] = {}

    def _walk(nodes: list[Any]) -> None:
        for node in nodes or []:
            flat[node.view_key] = node
            _walk(getattr(node, "children", []) or [])

    _walk(views)
    return flat


def compute_scaffold_input_hash(
    payload: Any,
    payload_by_key: dict[str, Any],
    *,
    generated_scaffolds: Optional[dict[str, dict[str, Any]]] = None,
) -> str:
    """Compute a stable hash of the scaffold source snapshot."""
    source = build_scaffold_source(
        payload,
        payload_by_key,
        generated_scaffolds=generated_scaffolds,
    )
    serialized = json.dumps(source, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def resolve_scaffold_type(
    payload: Any,
    payload_by_key: dict[str, Any],
) -> Optional[str]:
    """Return scaffold type for a payload when one should be generated."""
    return resolve_effective_scaffold_type_for_payload(
        payload,
        payload_by_key,
        density_ok=_passes_density_threshold(payload),
    )


def build_scaffold_source(
    payload: Any,
    payload_by_key: dict[str, Any],
    *,
    generated_scaffolds: Optional[dict[str, dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Build the source snapshot used for cache invalidation and generation."""
    scaffold_type = resolve_scaffold_type(payload, payload_by_key)
    if scaffold_type is None:
        return {
            "view_key": payload.view_key,
            "structured_data": payload.structured_data,
        }

    source: dict[str, Any] = {
        "scaffold_type": scaffold_type,
        "view_key": payload.view_key,
        "view_name": payload.view_name,
        "description": payload.description,
        "sections": list((payload.renderer_config or {}).get("sections", []) or []),
        "structured_data": payload.structured_data,
    }

    if scaffold_type == "composite_overview":
        children = []
        for child in _get_logical_children(payload, payload_by_key):
            child_scaffold = (generated_scaffolds or {}).get(child.view_key)
            children.append(
                {
                    "view_key": child.view_key,
                    "view_name": child.view_name,
                    "description": child.description,
                    "structured_data": child.structured_data,
                    "reading_scaffold": child_scaffold,
                }
            )
        source["children"] = children

    return source


def build_reading_scaffold(
    payload: Any,
    payload_by_key: dict[str, Any],
    *,
    generated_scaffolds: Optional[dict[str, dict[str, Any]]] = None,
) -> tuple[dict[str, Any], str]:
    """Build a scaffold payload for a single view."""
    scaffold_type = resolve_scaffold_type(payload, payload_by_key)
    if scaffold_type is None:
        raise ValueError(f"View {payload.view_key} is not scaffold-eligible")

    if scaffold_type == "composite_overview":
        scaffold, model_used = _build_composite_overview(
            payload,
            payload_by_key,
            generated_scaffolds=generated_scaffolds,
        )
    elif scaffold_type == "concept_atlas":
        scaffold, model_used = _build_concept_atlas(payload)
    else:
        scaffold, model_used = _build_argument_map(payload)

    return scaffold, model_used


def _collect_scaffold_candidates(payload_by_key: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = []
    for payload in payload_by_key.values():
        scaffold_type = resolve_scaffold_type(payload, payload_by_key)
        if scaffold_type is None:
            continue
        candidates.append(
            {
                "payload": payload,
                "scaffold_type": scaffold_type,
            }
        )
    return candidates


def _passes_density_threshold(payload: Any) -> bool:
    total_items = _count_items(payload.structured_data)
    prose_chars = len(payload.raw_prose or "")
    section_count = len((payload.renderer_config or {}).get("sections", []) or [])
    has_brief = _has_existing_brief(payload.structured_data)
    return (
        total_items > 12
        or section_count > 3
        or (prose_chars > 1500 and not has_brief)
    )


def _has_existing_brief(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    for key in ("brief", "overview", "executive_summary"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return True
    return False


def _count_items(value: Any) -> int:
    if isinstance(value, list):
        return len(value) + sum(_count_items(item) for item in value[:8])
    if isinstance(value, dict):
        return sum(_count_items(item) for item in value.values())
    return 0


def _get_logical_children(payload: Any, payload_by_key: dict[str, Any]) -> list[Any]:
    children = [
        child
        for child in payload_by_key.values()
        if getattr(child, "source_parent_view_key", None) == payload.view_key
    ]
    return sorted(children, key=lambda child: child.position)


def _build_composite_overview(
    payload: Any,
    payload_by_key: dict[str, Any],
    *,
    generated_scaffolds: Optional[dict[str, dict[str, Any]]] = None,
) -> tuple[dict[str, Any], str]:
    children = _get_logical_children(payload, payload_by_key)
    child_surface_items = []
    section_intros = []

    for idx, child in enumerate(children, start=1):
        child_scaffold = (generated_scaffolds or {}).get(child.view_key)
        summary = _summarize_child_surface(child, child_scaffold)
        child_surface_items.append(
            {
                "label": child.view_name,
                "text": summary,
                "view_key": child.view_key,
                "provenance": [f"{child.view_key}.structured_data"],
            }
        )
        section_intros.append(
            {
                "section_key": child.view_key,
                "title": child.view_name,
                "intro": summary,
                "provenance": [f"{child.view_key}.structured_data"],
            }
        )

    fallback = {
        "brief": (
            f"{payload.view_name} braids {len(children)} analytical surfaces into a single reading order."
            if children else
            f"{payload.view_name} consolidates its major analytical sections into a guided entry point."
        ),
        "how_to_read": (
            "Start with the child surface summaries to locate the main analytical lanes, "
            "then open the deep-dive sections that carry the most weight for your question."
        ),
        "top_takeaways": [
            item["text"] for item in child_surface_items[:3]
        ],
    }
    llm_fields, model_used = _llm_refine_scaffold_fields(
        scaffold_type="composite_overview",
        source={
            "view_name": payload.view_name,
            "description": payload.description,
            "children": child_surface_items,
        },
        fallback=fallback,
    )

    scaffold = {
        "surface_type": "composite_overview",
        "brief": llm_fields["brief"],
        "how_to_read": llm_fields["how_to_read"],
        "section_intros": section_intros,
        "blocks": [
            {
                "key": "top_takeaways",
                "title": "What This Surface Covers",
                "style": "bullet_list",
                "items": [
                    {
                        "text": text,
                        "provenance": [item["provenance"][0]],
                    }
                    for text, item in zip(llm_fields["top_takeaways"], child_surface_items)
                ],
            },
            {
                "key": "child_surfaces",
                "title": "Child Surfaces",
                "style": "bullet_list",
                "items": child_surface_items,
            },
        ],
        "provenance": [
            {
                "scaffold_element": "brief",
                "sources": [f"{child.view_key}.structured_data" for child in children],
            }
        ],
    }
    return scaffold, model_used


def _build_concept_atlas(payload: Any) -> tuple[dict[str, Any], str]:
    data = payload.structured_data if isinstance(payload.structured_data, dict) else {}
    clusters = _top_ranked_items(
        data.get("concept_clusters") or data.get("frameworks") or [],
        limit=4,
        numeric_fields=("centrality", "weight", "frequency"),
    )
    terms = _top_ranked_items(
        data.get("load_bearing_terms") or data.get("vocabulary_map") or data.get("core_concepts") or [],
        limit=5,
        numeric_fields=("centrality", "semantic_weight", "frequency"),
    )
    tensions = _top_ranked_items(
        data.get("boundary_tensions") or data.get("framework_relationships") or [],
        limit=3,
    )

    cluster_items = [
        {
            "label": _pick_label(item, fallback=f"Cluster {idx}"),
            "text": _describe_item(item),
            "provenance": [f"{'concept_clusters' if data.get('concept_clusters') else 'frameworks'}[{idx - 1}]"],
        }
        for idx, item in enumerate(clusters, start=1)
    ]
    term_items = [
        {
            "label": _pick_label(item, fallback=f"Term {idx}"),
            "text": _describe_item(item),
            "provenance": [f"{'load_bearing_terms' if data.get('load_bearing_terms') else ('vocabulary_map' if data.get('vocabulary_map') else 'core_concepts')}[{idx - 1}]"],
        }
        for idx, item in enumerate(terms, start=1)
    ]
    tension_items = [
        {
            "label": _pick_pair_label(item, fallback=f"Tension {idx}"),
            "text": _describe_item(item),
            "provenance": [f"{'boundary_tensions' if data.get('boundary_tensions') else 'framework_relationships'}[{idx - 1}]"],
        }
        for idx, item in enumerate(tensions, start=1)
    ]

    fallback = {
        "brief": (
            f"{payload.view_name} organizes the material around {len(cluster_items)} dominant clusters, "
            f"{len(term_items)} load-bearing terms, and {len(tension_items)} active tensions."
        ),
        "how_to_read": (
            "Start with the clusters to get the field structure, move to the terms that carry the most weight, "
            "and finish with the tensions that show where the framework strains or turns."
        ),
    }
    llm_fields, model_used = _llm_refine_scaffold_fields(
        scaffold_type="concept_atlas",
        source={
            "view_name": payload.view_name,
            "clusters": cluster_items,
            "terms": term_items,
            "tensions": tension_items,
        },
        fallback=fallback,
    )

    sections = list((payload.renderer_config or {}).get("sections", []) or [])
    section_intros = [
        {
            "section_key": section.get("key") or "",
            "title": section.get("title") or (section.get("key") or "").replace("_", " ").title(),
            "intro": _section_intro_for_atlas(section.get("key") or ""),
            "provenance": [f"{section.get('key') or 'structured_data'}"],
        }
        for section in sections
        if section.get("key")
    ]

    scaffold = {
        "surface_type": "concept_atlas",
        "brief": llm_fields["brief"],
        "how_to_read": llm_fields["how_to_read"],
        "section_intros": section_intros,
        "blocks": [
            {
                "key": "clusters",
                "title": "Dominant Clusters",
                "style": "bullet_list",
                "items": cluster_items,
            },
            {
                "key": "terms",
                "title": "Load-Bearing Terms",
                "style": "bullet_list",
                "items": term_items,
            },
            {
                "key": "tensions",
                "title": "Boundary Tensions",
                "style": "bullet_list",
                "items": tension_items,
            },
        ],
        "provenance": [
            {
                "scaffold_element": "brief",
                "sources": [
                    "concept_clusters",
                    "frameworks",
                    "load_bearing_terms",
                    "vocabulary_map",
                    "boundary_tensions",
                    "framework_relationships",
                ],
            }
        ],
    }
    return scaffold, model_used


def _build_argument_map(payload: Any) -> tuple[dict[str, Any], str]:
    data = payload.structured_data if isinstance(payload.structured_data, dict) else {}
    commitments = _top_ranked_items(
        data.get("commitments") or [],
        limit=4,
        numeric_fields=("strength", "explicitness"),
    )
    premises = _top_ranked_items(
        data.get("hidden_premises") or [],
        limit=3,
    )
    implications = _top_ranked_items(
        data.get("practical_implications") or [],
        limit=3,
    )

    spine = _build_argument_spine(commitments, premises, implications)

    fallback = {
        "brief": (
            f"{payload.view_name} concentrates {len(commitments)} front-stage commitments, "
            f"{len(premises)} hidden premises, and {len(implications)} practical consequences."
        ),
        "how_to_read": (
            "Read the spine first to see the main inferential path, then inspect the hidden premises "
            "that keep the structure standing, and finish with the practical implications."
        ),
    }
    llm_fields, model_used = _llm_refine_scaffold_fields(
        scaffold_type="argument_map",
        source={
            "view_name": payload.view_name,
            "spine": spine,
            "premises": premises,
            "implications": implications,
        },
        fallback=fallback,
    )

    sections = list((payload.renderer_config or {}).get("sections", []) or [])
    section_intros = [
        {
            "section_key": section.get("key") or "",
            "title": section.get("title") or (section.get("key") or "").replace("_", " ").title(),
            "intro": _section_intro_for_argument(section.get("key") or ""),
            "provenance": [f"{section.get('key') or 'structured_data'}"],
        }
        for section in sections
        if section.get("key")
    ]

    scaffold = {
        "surface_type": "argument_map",
        "brief": llm_fields["brief"],
        "how_to_read": llm_fields["how_to_read"],
        "section_intros": section_intros,
        "blocks": [
            {
                "key": "argument_spine",
                "title": "Argument Spine",
                "style": "numbered_list",
                "items": [
                    {
                        "label": f"Step {idx}",
                        "text": text,
                        "provenance": [source_path],
                    }
                    for idx, (text, source_path) in enumerate(spine, start=1)
                ],
            },
            {
                "key": "hidden_premises",
                "title": "Load-Bearing Premises",
                "style": "bullet_list",
                "items": [
                    {
                        "label": _pick_label(item, fallback=f"Premise {idx}"),
                        "text": _describe_item(item),
                        "provenance": [f"hidden_premises[{idx - 1}]"],
                    }
                    for idx, item in enumerate(premises, start=1)
                ],
            },
            {
                "key": "practical_implications",
                "title": "Practical Consequences",
                "style": "bullet_list",
                "items": [
                    {
                        "label": _pick_label(item, fallback=f"Implication {idx}"),
                        "text": _describe_item(item),
                        "provenance": [f"practical_implications[{idx - 1}]"],
                    }
                    for idx, item in enumerate(implications, start=1)
                ],
            },
        ],
        "provenance": [
            {
                "scaffold_element": "brief",
                "sources": [
                    "commitments",
                    "hidden_premises",
                    "practical_implications",
                    "argumentative_structure",
                ],
            }
        ],
    }
    return scaffold, model_used


def _llm_refine_scaffold_fields(
    *,
    scaffold_type: str,
    source: dict[str, Any],
    fallback: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    """Ask the LLM for light-weight scaffold prose, falling back deterministically."""
    prompt_version = SCAFFOLD_PROMPT_VERSIONS[scaffold_type]
    system_prompt = (
        "You generate concise reading scaffolds for analysis tabs.\n"
        "Return ONLY valid JSON.\n"
        "Keep prose concrete and avoid generic filler.\n"
        "Preserve the exact keys requested.\n"
    )
    requested_keys = ", ".join(sorted(fallback.keys()))
    user_prompt = (
        f"Scaffold type: {scaffold_type}\n"
        f"Prompt version: {prompt_version}\n"
        f"Return JSON with keys: {requested_keys}.\n\n"
        f"SOURCE:\n{json.dumps(source, ensure_ascii=False, default=str)}"
    )

    try:
        raw_text, model_used, _tokens = call_extraction_model(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model=GENERATION_MODEL,
            fallback_model=GENERATION_MODEL,
            max_tokens=1800,
        )
        parsed = parse_llm_json_response(raw_text)
        if not isinstance(parsed, dict):
            return fallback, ""
        refined = dict(fallback)
        for key, default_value in fallback.items():
            value = parsed.get(key)
            if isinstance(default_value, list):
                if isinstance(value, list) and value:
                    refined[key] = [str(item).strip() for item in value if str(item).strip()]
            elif isinstance(value, str) and value.strip():
                refined[key] = value.strip()
        return refined, model_used
    except Exception:
        return fallback, ""


def _summarize_child_surface(child: Any, child_scaffold: Optional[dict[str, Any]]) -> str:
    if isinstance(child_scaffold, dict):
        brief = child_scaffold.get("brief")
        if isinstance(brief, str) and brief.strip():
            return brief.strip()

    data = child.structured_data
    if isinstance(data, dict):
        list_keys = [
            key for key, value in data.items()
            if isinstance(value, list) and value
        ]
        if list_keys:
            primary = list_keys[:2]
            counts = ", ".join(f"{len(data[key])} {key.replace('_', ' ')}" for key in primary)
            return f"Tracks {counts}."
        text_keys = [
            key for key, value in data.items()
            if isinstance(value, str) and value.strip()
        ]
        if text_keys:
            return _truncate(str(data[text_keys[0]]), 180)

    if child.description:
        return child.description
    return f"Extends the parent surface through {child.view_name.lower()}."


def _top_ranked_items(
    rows: Any,
    *,
    limit: int,
    numeric_fields: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []

    normalized = [row for row in rows if isinstance(row, dict)]

    def _score(row: dict[str, Any]) -> tuple[float, str]:
        numeric_score = 0.0
        for field in numeric_fields:
            value = row.get(field)
            if isinstance(value, (int, float)):
                numeric_score = max(numeric_score, float(value))
            elif isinstance(value, str):
                lowered = value.lower()
                if lowered in {"high", "strong", "core", "central"}:
                    numeric_score = max(numeric_score, 3.0)
                elif lowered in {"medium", "moderate"}:
                    numeric_score = max(numeric_score, 2.0)
                elif lowered in {"low", "weak", "peripheral"}:
                    numeric_score = max(numeric_score, 1.0)
        return (numeric_score, _pick_label(row))

    normalized.sort(key=_score, reverse=True)
    return normalized[:limit]


def _build_argument_spine(
    commitments: list[dict[str, Any]],
    premises: list[dict[str, Any]],
    implications: list[dict[str, Any]],
) -> list[tuple[str, str]]:
    spine: list[tuple[str, str]] = []

    for idx, commitment in enumerate(commitments[:2], start=1):
        spine.append(
            (
                f"Advance {_pick_label(commitment, fallback=f'commitment {idx}').lower()} as a governing claim.",
                f"commitments[{idx - 1}]",
            )
        )

    if premises:
        spine.append(
            (
                f"Rely on {_pick_label(premises[0], fallback='a hidden premise').lower()} to keep the argument moving.",
                "hidden_premises[0]",
            )
        )

    if implications:
        spine.append(
            (
                f"Carry the structure forward into {_pick_label(implications[0], fallback='practical implications').lower()}.",
                "practical_implications[0]",
            )
        )

    return spine[:4]


def _pick_label(item: dict[str, Any], *, fallback: str = "") -> str:
    for key in (
        "cluster_name",
        "term",
        "name",
        "framework_name",
        "method",
        "metaphor",
        "commitment",
        "premise",
        "implication",
        "idea",
        "title",
        "path_not_taken",
        "what_is_owed",
    ):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback or "Item"


def _pick_pair_label(item: dict[str, Any], *, fallback: str = "") -> str:
    left = item.get("pole_a") or item.get("framework_a") or item.get("option_a")
    right = item.get("pole_b") or item.get("framework_b") or item.get("option_b")
    if isinstance(left, str) and left.strip() and isinstance(right, str) and right.strip():
        return f"{left.strip()} vs {right.strip()}"
    return _pick_label(item, fallback=fallback)


def _describe_item(item: dict[str, Any]) -> str:
    preferred_fields = (
        "binding_logic",
        "description",
        "definition",
        "role_in_argument",
        "weight_description",
        "function",
        "distinguishing_features",
        "transformation",
        "why_hidden",
        "implications",
        "evidence",
    )
    for field in preferred_fields:
        value = item.get(field)
        if isinstance(value, str) and value.strip():
            return _truncate(value.strip(), 220)

    parts = []
    for key, value in item.items():
        if key.startswith("_"):
            continue
        if isinstance(value, str) and value.strip():
            parts.append(f"{key.replace('_', ' ')}: {value.strip()}")
        elif isinstance(value, (int, float)):
            parts.append(f"{key.replace('_', ' ')}: {value}")
        if len(parts) == 2:
            break
    return _truncate("; ".join(parts), 220)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _section_intro_for_atlas(section_key: str) -> str:
    mapping = {
        "core_concepts": "Use this section to identify the terms that anchor the whole semantic field.",
        "concept_clusters": "Read these clusters as the medium-scale groupings that hold the field together.",
        "load_bearing_terms": "These are the terms that carry more argumentative weight than their surface frequency suggests.",
        "boundary_tensions": "This section marks the live fault-lines where the semantic field pulls against itself.",
    }
    return mapping.get(
        section_key,
        f"This section extends the atlas through {section_key.replace('_', ' ')}."
    )


def _section_intro_for_argument(section_key: str) -> str:
    mapping = {
        "commitments": "Read these commitments as the explicit claims the rest of the structure depends on.",
        "hidden_premises": "These premises do work precisely because they remain under-argued or backgrounded.",
        "practical_implications": "This section shows what the inferential structure licenses once it leaves the page.",
        "argumentative_structure": "Use this as the long-form connective tissue behind the compact argument spine.",
    }
    return mapping.get(
        section_key,
        f"This section adds detail to the {section_key.replace('_', ' ')} layer of the argument."
    )
