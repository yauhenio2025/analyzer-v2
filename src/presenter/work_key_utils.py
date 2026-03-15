"""Shared utilities for work_key splitting, display metadata, and inference.

Used by both presentation_bridge.py (task creation) and presentation_api.py (assembly).
Handles the case where imported/legacy data has all outputs collapsed under a single
work_key (e.g., 'target') but actually represents multiple prior works.
"""

import json
import logging
import re
from typing import Any, Optional

from src.executor.job_manager import get_job
from src.orchestrator.planner import load_plan

logger = logging.getLogger(__name__)


def resolve_chain_engine_keys(chain_key: str) -> list[str]:
    """Resolve a chain key to engine keys.

    Accepts either:
    - a real registered chain key -> returns all engines in that chain
    - a lone engine key (legacy per-item fallback path) -> returns [engine_key]
    """
    from src.chains.registry import get_chain_registry
    from src.engines.registry import get_engine_registry

    chain_registry = get_chain_registry()
    chain = chain_registry.get(chain_key)
    if chain is not None:
        return list(chain.engine_keys)

    engine_registry = get_engine_registry()
    if (
        engine_registry.get(chain_key) is not None
        or engine_registry.get_capability_definition(chain_key) is not None
    ):
        return [chain_key]

    logger.warning(f"Chain not found: {chain_key}")
    return []


def sanitize_work_key_for_presenter(title: str) -> str:
    """Sanitize a work title into a work_key (mirrors phase_runner._sanitize_work_key)."""
    safe = "".join(
        c if c.isalnum() or c in " -" else "_"
        for c in title
    )
    return safe.strip().replace("  ", " ")[:100]


def normalize_work_title_for_display(title: str) -> str:
    """Convert filenames/slugs into a human-readable work title."""
    if not title:
        return ""

    display = re.sub(r"\.(?:md|markdown|txt|pdf|docx?)$", "", title, flags=re.IGNORECASE)
    display = display.replace("_", " ")
    display = re.sub(r"\s+", " ", display).strip(" -_")
    return display or title


def infer_year_from_title(title: str) -> Optional[int]:
    """Infer a publication year from a work title or filename."""
    if not title:
        return None
    match = re.search(r"\b(18|19|20)\d{2}\b", title)
    return int(match.group(0)) if match else None


def humanize_work_key(work_key: str) -> str:
    """Best-effort display label when all we have is a sanitized work_key."""
    if not work_key:
        return ""

    label = re.sub(r"_(?:md|markdown|txt|pdf|docx?)$", "", work_key, flags=re.IGNORECASE)
    label = label.replace("_", " ")
    label = re.sub(r"\s+", " ", label).strip(" -_")
    return label or work_key


def looks_like_sanitized_work_title(title: str, work_key: str = "") -> bool:
    """Heuristic: detect slug/file-key style titles that should be replaced."""
    if not title:
        return True

    normalized = title.strip()
    if not normalized:
        return True
    if work_key and normalized == work_key:
        return True
    if re.search(r"_(?:md|markdown|txt|pdf|docx?)$", normalized, flags=re.IGNORECASE):
        return True
    return "_" in normalized


def load_prior_work_metadata(job_id: str) -> dict[str, dict[str, Any]]:
    """Load normalized prior-work metadata keyed by sanitized work_key."""
    job = get_job(job_id)
    if not job:
        return {}

    plan = load_plan(job.get("plan_id", ""))
    if not plan or not getattr(plan, "prior_works", None):
        return {}

    metadata: dict[str, dict[str, Any]] = {}
    for prior_work in plan.prior_works:
        source_title = getattr(prior_work, "title", "") or ""
        if not source_title:
            continue

        work_key = sanitize_work_key_for_presenter(source_title)
        year = getattr(prior_work, "year", None) or infer_year_from_title(source_title)
        metadata[work_key] = {
            "source_title": source_title,
            "display_title": normalize_work_title_for_display(source_title),
            "year": year,
        }

    return metadata


def resolve_work_metadata(
    job_id: str,
    work_key: str,
    fallback_title: str = "",
) -> dict[str, Any]:
    """Resolve display-ready metadata for a work_key using plan metadata first."""
    metadata = load_prior_work_metadata(job_id).get(work_key, {})
    display_title = (
        metadata.get("display_title")
        or normalize_work_title_for_display(fallback_title)
        or humanize_work_key(work_key)
    )
    source_title = metadata.get("source_title") or fallback_title or display_title
    year = metadata.get("year") or infer_year_from_title(source_title)

    return {
        "display_title": display_title,
        "source_title": source_title,
        "year": year,
    }


def infer_work_key_from_content(content: str, prior_work_titles: list[str]) -> str:
    """Match an output's content to a prior work title by checking for title mentions.

    Returns the sanitized work_key for the best-matching prior work, or empty string
    if no match found. Checks first ~800 chars for italicized (*Title*) or quoted
    references to prior work titles.
    """
    if not content or not prior_work_titles:
        return ""

    snippet = content[:800].lower()

    best_match = ""
    best_score = 0

    for title in prior_work_titles:
        title_lower = title.lower()
        # Check for exact title match (case-insensitive) in first 800 chars
        if title_lower in snippet:
            # Score by how early the title appears
            pos = snippet.index(title_lower)
            score = 1000 - pos  # Earlier = higher score
            if score > best_score:
                best_score = score
                best_match = title

    if best_match:
        return sanitize_work_key_for_presenter(best_match)
    return ""


def try_split_collapsed_outputs(
    outputs: list[dict],
    job_id: str,
    chain_key: str,
) -> Optional[dict[str, list[dict]]]:
    """Detect and split outputs that all share the same work_key but represent
    multiple prior works (common in imported legacy data).

    Returns None if splitting isn't needed (outputs already have distinct work_keys).
    Returns dict[work_key -> list[outputs]] if splitting succeeds.
    """
    # Check if all outputs share the same work_key
    unique_work_keys = set(o.get("work_key", "") for o in outputs if o.get("work_key"))
    if len(unique_work_keys) != 1:
        return None  # Already properly keyed

    # Count unique engine keys in the chain
    chain_engine_keys = resolve_chain_engine_keys(chain_key)
    if not chain_engine_keys:
        return None

    # Check if there are more outputs than expected for a single work
    # (single work = num_engines x num_passes, multiple works = that x num_works)
    engines_per_pass = len(chain_engine_keys)
    if len(outputs) <= engines_per_pass * 3:
        return None  # Could be just 1 work with multi-pass, don't split

    # Load plan to get prior work titles
    job = get_job(job_id)
    if not job:
        return None
    plan = load_plan(job.get("plan_id", ""))
    if not plan or not hasattr(plan, "prior_works") or not plan.prior_works:
        return None

    prior_titles = [pw.title for pw in plan.prior_works if pw.title]
    if not prior_titles:
        return None

    logger.info(
        f"[per-item-split] Detected {len(outputs)} outputs with single work_key, "
        f"attempting to split across {len(prior_titles)} prior works: {prior_titles}"
    )

    # Try to match each output to a prior work by content analysis
    by_work: dict[str, list[dict]] = {}
    unmatched = []

    for o in outputs:
        content = o.get("content", "")
        matched_key = infer_work_key_from_content(content, prior_titles)
        if matched_key:
            by_work.setdefault(matched_key, []).append(o)
        else:
            unmatched.append(o)

    # Only accept if we matched a reasonable fraction
    matched_count = sum(len(v) for v in by_work.values())
    if matched_count < len(outputs) * 0.5:
        logger.warning(
            f"[per-item-split] Only matched {matched_count}/{len(outputs)} outputs, "
            f"aborting split"
        )
        return None

    # For unmatched outputs, try to infer titles from content
    if unmatched:
        sub_groups: dict[str, list[dict]] = {}
        still_unmatched = []
        for o in unmatched:
            content = o.get("content", "")
            # Extract first italicized title (*Title*) from content
            match = re.search(r'\*([A-Z][^*]{2,60})\*', content[:500])
            if match:
                inferred_title = match.group(1)
                inferred_key = sanitize_work_key_for_presenter(inferred_title)
                if inferred_key not in by_work:
                    sub_groups.setdefault(inferred_key, []).append(o)
                    meta = o.get("metadata") or {}
                    if isinstance(meta, str):
                        try:
                            meta = json.loads(meta)
                        except Exception:
                            meta = {}
                    meta["_inferred_work_title"] = inferred_title
                    o["metadata"] = meta
                else:
                    by_work[inferred_key].append(o)
            else:
                still_unmatched.append(o)

        for key, outputs_list in sub_groups.items():
            by_work.setdefault(key, []).extend(outputs_list)

        if still_unmatched:
            by_work.setdefault("_unmatched", []).extend(still_unmatched)
            logger.info(f"[per-item-split] {len(still_unmatched)} outputs still unmatched after content inference")
        else:
            logger.info(f"[per-item-split] All unmatched outputs resolved via content inference")

    # Store title metadata on each output for downstream use
    title_by_key = {}
    for title in prior_titles:
        key = sanitize_work_key_for_presenter(title)
        title_by_key[key] = title

    for work_key, work_outputs in by_work.items():
        for o in work_outputs:
            o["work_key"] = work_key
            if work_key in title_by_key:
                meta = o.get("metadata") or {}
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except Exception:
                        meta = {}
                meta["_inferred_work_title"] = title_by_key[work_key]
                o["metadata"] = meta

    logger.info(
        f"[per-item-split] Successfully split into {len(by_work)} groups: "
        f"{', '.join(f'{k}({len(v)})' for k, v in by_work.items())}"
    )
    return by_work
