"""Capability definition change history tracker.

Auto-detects changes to capability YAML files by comparing against
stored snapshots. Stores history as JSON files in capability_history/.

Usage (called from registry.py during startup):
    from src.engines.history_tracker import check_and_record_changes
    entry = check_and_record_changes(cap_def)
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .history_schemas import (
    CapabilityHistory,
    ChangeAction,
    FieldChange,
    HistoryEntry,
)
from .schemas_v2 import CapabilityEngineDefinition

logger = logging.getLogger(__name__)

HISTORY_DIR = Path(__file__).parent / "capability_history"


# ── Hashing ──────────────────────────────────────────────────────


def compute_definition_hash(cap_def: CapabilityEngineDefinition) -> str:
    """Compute a stable SHA-256 hash of a capability definition.

    Uses model_dump with sorted keys and deterministic JSON serialization
    so the same definition always produces the same hash.
    """
    data = cap_def.model_dump(mode="json")
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ── File I/O ─────────────────────────────────────────────────────


def _history_path(engine_key: str) -> Path:
    return HISTORY_DIR / f"{engine_key}.json"


def _snapshot_path(engine_key: str) -> Path:
    return HISTORY_DIR / f"{engine_key}_snapshot.json"


def load_history(engine_key: str) -> CapabilityHistory:
    """Load history from JSON file. Returns empty history if file doesn't exist."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    path = _history_path(engine_key)
    if not path.exists():
        return CapabilityHistory(engine_key=engine_key, entries=[])
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return CapabilityHistory.model_validate(data)
    except Exception as e:
        logger.error(f"Failed to load history for {engine_key}: {e}")
        return CapabilityHistory(engine_key=engine_key, entries=[])


def save_history(history: CapabilityHistory) -> None:
    """Save history to JSON file."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    path = _history_path(history.engine_key)
    with open(path, "w") as f:
        json.dump(history.model_dump(mode="json"), f, indent=2)
    logger.info(f"Saved history for {history.engine_key}: {len(history.entries)} entries")


def _load_snapshot(engine_key: str) -> Optional[CapabilityEngineDefinition]:
    """Load the most recent snapshot of a capability definition."""
    path = _snapshot_path(engine_key)
    if not path.exists():
        return None
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return CapabilityEngineDefinition.model_validate(data)
    except Exception as e:
        logger.error(f"Failed to load snapshot for {engine_key}: {e}")
        return None


def _save_snapshot(cap_def: CapabilityEngineDefinition) -> None:
    """Save current definition as snapshot for next comparison."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    path = _snapshot_path(cap_def.engine_key)
    with open(path, "w") as f:
        json.dump(cap_def.model_dump(mode="json"), f, indent=2, sort_keys=True)


# ── Diffing ──────────────────────────────────────────────────────


def _trunc(val: object, max_len: int = 500) -> str:
    """Stringify and truncate a value for storage in FieldChange."""
    s = str(val)
    return s[:max_len] + "..." if len(s) > max_len else s


def diff_definitions(
    old_def: CapabilityEngineDefinition,
    new_def: CapabilityEngineDefinition,
) -> list[FieldChange]:
    """Compute field-level diff between two capability definitions.

    Compares structured sections: top-level scalars, intellectual lineage,
    analytical dimensions, capabilities, composability, depth levels.
    """
    changes: list[FieldChange] = []

    # ── Top-level scalars ──
    for field_name in ["problematique", "researcher_question", "version"]:
        old_val = getattr(old_def, field_name)
        new_val = getattr(new_def, field_name)
        if old_val != new_val:
            changes.append(
                FieldChange(
                    section="top_level",
                    field=field_name,
                    action=ChangeAction.MODIFIED,
                    old_value=_trunc(old_val),
                    new_value=_trunc(new_val),
                )
            )

    # ── Intellectual Lineage ──
    old_lin = old_def.intellectual_lineage
    new_lin = new_def.intellectual_lineage

    if old_lin.primary != new_lin.primary:
        changes.append(
            FieldChange(
                section="intellectual_lineage",
                field="primary",
                action=ChangeAction.MODIFIED,
                old_value=old_lin.primary,
                new_value=new_lin.primary,
            )
        )

    for list_field in ["secondary", "traditions", "key_concepts"]:
        old_set = set(getattr(old_lin, list_field))
        new_set = set(getattr(new_lin, list_field))
        for item in sorted(new_set - old_set):
            changes.append(
                FieldChange(
                    section="intellectual_lineage",
                    field=list_field,
                    action=ChangeAction.ADDED,
                    new_value=item,
                )
            )
        for item in sorted(old_set - new_set):
            changes.append(
                FieldChange(
                    section="intellectual_lineage",
                    field=list_field,
                    action=ChangeAction.REMOVED,
                    old_value=item,
                )
            )

    # ── Analytical Dimensions ──
    old_dims = {d.key: d for d in old_def.analytical_dimensions}
    new_dims = {d.key: d for d in new_def.analytical_dimensions}

    for key in sorted(set(new_dims) - set(old_dims)):
        changes.append(
            FieldChange(
                section="analytical_dimensions",
                field=key,
                action=ChangeAction.ADDED,
                new_value=_trunc(new_dims[key].description, 200),
            )
        )
    for key in sorted(set(old_dims) - set(new_dims)):
        changes.append(
            FieldChange(
                section="analytical_dimensions",
                field=key,
                action=ChangeAction.REMOVED,
                old_value=_trunc(old_dims[key].description, 200),
            )
        )
    for key in sorted(set(old_dims) & set(new_dims)):
        if old_dims[key].model_dump() != new_dims[key].model_dump():
            changes.append(
                FieldChange(
                    section="analytical_dimensions",
                    field=key,
                    action=ChangeAction.MODIFIED,
                    old_value=f"{len(old_dims[key].probing_questions)} questions",
                    new_value=f"{len(new_dims[key].probing_questions)} questions",
                )
            )

    # ── Capabilities ──
    old_caps = {c.key: c for c in old_def.capabilities}
    new_caps = {c.key: c for c in new_def.capabilities}

    for key in sorted(set(new_caps) - set(old_caps)):
        changes.append(
            FieldChange(
                section="capabilities",
                field=key,
                action=ChangeAction.ADDED,
                new_value=_trunc(new_caps[key].description, 200),
            )
        )
    for key in sorted(set(old_caps) - set(new_caps)):
        changes.append(
            FieldChange(
                section="capabilities",
                field=key,
                action=ChangeAction.REMOVED,
                old_value=_trunc(old_caps[key].description, 200),
            )
        )
    for key in sorted(set(old_caps) & set(new_caps)):
        old_dump = old_caps[key].model_dump()
        new_dump = new_caps[key].model_dump()
        if old_dump != new_dump:
            changed_subfields = [
                sf
                for sf in [
                    "description",
                    "extended_description",
                    "intellectual_grounding",
                    "indicators",
                    "depth_scaling",
                    "produces_dimensions",
                    "requires_dimensions",
                ]
                if old_dump.get(sf) != new_dump.get(sf)
            ]
            changes.append(
                FieldChange(
                    section="capabilities",
                    field=key,
                    action=ChangeAction.MODIFIED,
                    old_value=f"changed: {', '.join(changed_subfields)}" if changed_subfields else "modified",
                    new_value=f"{len(changed_subfields)} sub-field(s)",
                )
            )

    # ── Composability ──
    old_comp = old_def.composability.model_dump()
    new_comp = new_def.composability.model_dump()
    for comp_field in ["shares_with", "consumes_from", "synergy_engines"]:
        if old_comp.get(comp_field) != new_comp.get(comp_field):
            changes.append(
                FieldChange(
                    section="composability",
                    field=comp_field,
                    action=ChangeAction.MODIFIED,
                    old_value=_trunc(json.dumps(old_comp.get(comp_field)), 300),
                    new_value=_trunc(json.dumps(new_comp.get(comp_field)), 300),
                )
            )

    # ── Depth Levels ──
    old_depths = {d.key: d for d in old_def.depth_levels}
    new_depths = {d.key: d for d in new_def.depth_levels}

    for key in sorted(set(new_depths) - set(old_depths)):
        changes.append(
            FieldChange(
                section="depth_levels",
                field=key,
                action=ChangeAction.ADDED,
                new_value=f"{new_depths[key].typical_passes} passes",
            )
        )
    for key in sorted(set(old_depths) - set(new_depths)):
        changes.append(
            FieldChange(
                section="depth_levels",
                field=key,
                action=ChangeAction.REMOVED,
                old_value=f"{old_depths[key].typical_passes} passes",
            )
        )
    for key in sorted(set(old_depths) & set(new_depths)):
        if old_depths[key].model_dump() != new_depths[key].model_dump():
            old_passes = len(old_depths[key].passes) if old_depths[key].passes else 0
            new_passes = len(new_depths[key].passes) if new_depths[key].passes else 0
            changes.append(
                FieldChange(
                    section="depth_levels",
                    field=key,
                    action=ChangeAction.MODIFIED,
                    old_value=f"{old_passes} passes",
                    new_value=f"{new_passes} passes",
                )
            )

    return changes


# ── Summary generation ───────────────────────────────────────────


def generate_summary(changes: list[FieldChange], engine_key: str) -> str:
    """Generate a human-readable summary from a list of field changes."""
    if not changes:
        return "No changes detected"

    parts: list[str] = []
    by_section: dict[str, list[FieldChange]] = {}
    for c in changes:
        by_section.setdefault(c.section, []).append(c)

    section_labels = {
        "top_level": "definition",
        "intellectual_lineage": "intellectual lineage",
        "analytical_dimensions": "analytical dimensions",
        "capabilities": "capabilities",
        "composability": "composability",
        "depth_levels": "depth levels",
    }

    for section, section_changes in by_section.items():
        label = section_labels.get(section, section)
        added = [c for c in section_changes if c.action == ChangeAction.ADDED]
        removed = [c for c in section_changes if c.action == ChangeAction.REMOVED]
        modified = [c for c in section_changes if c.action == ChangeAction.MODIFIED]

        if added:
            if section in ("capabilities", "analytical_dimensions"):
                names = ", ".join(f"'{c.field}'" for c in added)
                parts.append(f"Added {names} to {label}")
            else:
                for c in added:
                    parts.append(f"Added '{c.new_value}' to {label} {c.field}")

        if removed:
            if section in ("capabilities", "analytical_dimensions"):
                names = ", ".join(f"'{c.field}'" for c in removed)
                parts.append(f"Removed {names} from {label}")
            else:
                for c in removed:
                    parts.append(f"Removed '{c.old_value}' from {label} {c.field}")

        if modified:
            if section == "top_level":
                fields = ", ".join(c.field for c in modified)
                parts.append(f"Modified {fields}")
            elif section in ("capabilities", "analytical_dimensions"):
                count = len(modified)
                parts.append(f"Modified {count} {label}")
            else:
                for c in modified:
                    parts.append(f"Modified {label} {c.field}")

    return "; ".join(parts)


# ── Main entry point ─────────────────────────────────────────────


def check_and_record_changes(
    cap_def: CapabilityEngineDefinition,
) -> Optional[HistoryEntry]:
    """Check if a capability definition changed since last recorded state.

    On first call (no history): creates baseline entry + snapshot.
    On change detected: computes diff, generates summary, records entry.
    On no change: returns None.
    """
    current_hash = compute_definition_hash(cap_def)
    history = load_history(cap_def.engine_key)

    if not history.entries:
        # First time — create baseline
        entry = HistoryEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            version=1,
            definition_hash=current_hash,
            changes=[],
            summary="Initial baseline snapshot",
            is_baseline=True,
        )
        history.entries.insert(0, entry)
        save_history(history)
        _save_snapshot(cap_def)
        logger.info(f"Created baseline history for {cap_def.engine_key}")
        return entry

    last_entry = history.entries[0]  # newest first

    if last_entry.definition_hash == current_hash:
        return None  # No change

    # Load previous snapshot for diffing
    prev_def = _load_snapshot(cap_def.engine_key)

    if prev_def is None:
        # Snapshot missing — record change without detailed diff
        entry = HistoryEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            version=last_entry.version + 1,
            definition_hash=current_hash,
            changes=[],
            summary="Definition changed (previous snapshot unavailable for diff)",
            is_baseline=False,
        )
    else:
        changes = diff_definitions(prev_def, cap_def)
        summary = generate_summary(changes, cap_def.engine_key)
        entry = HistoryEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            version=last_entry.version + 1,
            definition_hash=current_hash,
            changes=changes,
            summary=summary,
            is_baseline=False,
        )

    history.entries.insert(0, entry)
    save_history(history)
    _save_snapshot(cap_def)

    logger.info(
        f"Recorded change for {cap_def.engine_key}: v{entry.version} — {entry.summary}"
    )
    return entry
