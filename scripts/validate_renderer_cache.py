#!/usr/bin/env python3
"""Dry-run validation of existing presentation_cache data against renderer schemas.

Calibration tool: run ONCE after populating input_data_schema in renderer
definitions to gauge expected warning volume before enabling pipeline validation.

Usage:
    python scripts/validate_renderer_cache.py [--limit N]

Output:
    Per-renderer summary: {total, valid, invalid} counts.
    If any renderer shows >30% failure rate, consider relaxing its schema.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.renderers.registry import get_renderer_registry
from src.renderers.validator import ValidationMode, validate_renderer_data

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def _resolve_renderer_type(output_id: str, section: str, db_execute) -> str | None:
    """Try to resolve renderer_type for a cache entry.

    Looks up the view definition via transformation templates and view registry.
    Falls back to inferring from section key patterns.
    """
    # Try to match section to a known template_key
    from src.transformations.registry import get_transformation_registry
    from src.views.registry import get_view_registry

    transform_registry = get_transformation_registry()
    view_registry = get_view_registry()

    # Strip work_key suffix if present (e.g., "template_key:work_key")
    base_section = section.split(":")[0] if ":" in section else section

    # Check if base_section is a template_key
    template = transform_registry.get(base_section)
    if template:
        # Find views that use this engine and renderer type
        for view_def in view_registry.list_all():
            engine_key = view_def.data_source.engine_key
            if engine_key and engine_key in template.engine_keys:
                return view_def.renderer_type

    # Try dynamic section format: "dyn:engine_key:renderer_type"
    if base_section.startswith("dyn:"):
        parts = base_section.split(":")
        if len(parts) >= 3:
            return parts[2]

    return None


def main():
    parser = argparse.ArgumentParser(description="Validate renderer cache against schemas")
    parser.add_argument("--limit", type=int, default=500, help="Max cache entries to check")
    args = parser.parse_args()

    from src.executor.db import execute

    # Load recent cache entries
    rows = execute(
        "SELECT id, output_id, section, structured_data FROM presentation_cache "
        "ORDER BY updated_at DESC LIMIT %s",
        (args.limit,),
        fetch="all",
    )

    if not rows:
        logger.info("No presentation_cache entries found.")
        return

    logger.info(f"Loaded {len(rows)} cache entries. Resolving renderer types...")

    # Tally results by renderer
    by_renderer: dict[str, dict[str, int]] = {}
    unresolved = 0

    for row in rows:
        renderer_type = _resolve_renderer_type(row["output_id"], row["section"], execute)
        if not renderer_type:
            unresolved += 1
            continue

        if renderer_type not in by_renderer:
            by_renderer[renderer_type] = {"total": 0, "valid": 0, "invalid": 0}

        # Parse structured_data
        data = row["structured_data"]
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                by_renderer[renderer_type]["total"] += 1
                by_renderer[renderer_type]["invalid"] += 1
                continue

        result = validate_renderer_data(renderer_type, data, mode=ValidationMode.SILENT)

        # Re-run in warn mode to get actual errors for silent results
        from src.renderers.validator import validate_renderer_data as _validate
        result = _validate(renderer_type, data, mode=ValidationMode.WARN)

        by_renderer[renderer_type]["total"] += 1
        if result.valid:
            by_renderer[renderer_type]["valid"] += 1
        else:
            by_renderer[renderer_type]["invalid"] += 1

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("RENDERER CACHE VALIDATION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"{'Renderer':<20} {'Total':>6} {'Valid':>6} {'Invalid':>8} {'Fail%':>6}")
    logger.info("-" * 60)

    alerts = []
    for renderer_key in sorted(by_renderer.keys()):
        stats = by_renderer[renderer_key]
        total = stats["total"]
        valid = stats["valid"]
        invalid = stats["invalid"]
        fail_pct = (invalid / total * 100) if total > 0 else 0
        marker = " !!!" if fail_pct > 30 else ""
        logger.info(f"{renderer_key:<20} {total:>6} {valid:>6} {invalid:>8} {fail_pct:>5.1f}%{marker}")
        if fail_pct > 30:
            alerts.append(renderer_key)

    logger.info("-" * 60)
    logger.info(f"Unresolved (no renderer_type): {unresolved}")

    if alerts:
        logger.info(f"\n!!! ALERT: These renderers have >30% failure rate: {alerts}")
        logger.info("Consider relaxing their input_data_schema before deploying.")
    else:
        logger.info("\nAll renderers within acceptable failure thresholds.")


if __name__ == "__main__":
    main()
