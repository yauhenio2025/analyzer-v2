"""Shared utilities for work_key splitting and inference.

Used by both presentation_bridge.py (task creation) and presentation_api.py (assembly).
Handles the case where imported/legacy data has all outputs collapsed under a single
work_key (e.g., 'target') but actually represents multiple prior works.
"""

import json
import logging
import re
from typing import Optional

from src.executor.job_manager import get_job
from src.orchestrator.planner import load_plan

logger = logging.getLogger(__name__)


def resolve_chain_engine_keys(chain_key: str) -> list[str]:
    """Resolve a chain_key to the list of engine keys in that chain."""
    from src.chains.registry import get_chain_registry
    chain_registry = get_chain_registry()
    chain = chain_registry.get(chain_key)
    if chain is None:
        logger.warning(f"Chain not found: {chain_key}")
        return []
    return list(chain.engine_keys)


def sanitize_work_key_for_presenter(title: str) -> str:
    """Sanitize a work title into a work_key (mirrors phase_runner._sanitize_work_key)."""
    safe = "".join(
        c if c.isalnum() or c in " -" else "_"
        for c in title
    )
    return safe.strip().replace("  ", " ")[:100]


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
