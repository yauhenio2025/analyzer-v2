#!/usr/bin/env python3
"""Extract operationalizations from engine capability YAMLs.

Reads inline PassDefinitions from each engine's depth_levels and extracts them
into standalone operationalization YAML files. This is a one-time migration
script that creates the operationalization layer from existing coupled data.

Usage:
    python scripts/extract_operationalizations.py
"""

import sys
from pathlib import Path

import yaml

# Ensure project root is on path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.operationalizations.schemas import (
    DepthPassEntry,
    DepthSequence,
    EngineOperationalization,
    StanceOperationalization,
)

CAPABILITY_DIR = project_root / "src" / "engines" / "capability_definitions"
OUTPUT_DIR = project_root / "src" / "operationalizations" / "definitions"


def extract_from_engine(yaml_path: Path) -> EngineOperationalization | None:
    """Extract operationalization from a single engine capability YAML."""
    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)

    if data is None:
        return None

    engine_key = data.get("engine_key", "")
    engine_name = data.get("engine_name", "")
    depth_levels = data.get("depth_levels", [])

    if not depth_levels:
        print(f"  Skipping {engine_key}: no depth_levels")
        return None

    # Collect unique stance operationalizations across all depths
    # Key: (stance_key, label) to handle same stance with different labels at different depths
    stance_ops_map: dict[str, StanceOperationalization] = {}
    depth_sequences: list[DepthSequence] = []

    for dl in depth_levels:
        passes = dl.get("passes", [])
        if not passes:
            continue

        pass_entries: list[DepthPassEntry] = []

        for p in passes:
            stance_key = p.get("stance", "")
            label = p.get("label", "")
            description = p.get("description", "")
            focus_dims = p.get("focus_dimensions", [])
            focus_caps = p.get("focus_capabilities", [])
            pass_number = p.get("pass_number", 0)
            consumes_from = p.get("consumes_from", [])

            # Build a unique key for this stance operationalization
            # Same stance may have different labels across depths — use the
            # deepest/richest description (longest) as the canonical one
            if stance_key not in stance_ops_map or len(description) > len(
                stance_ops_map[stance_key].description
            ):
                stance_ops_map[stance_key] = StanceOperationalization(
                    stance_key=stance_key,
                    label=label,
                    description=description.strip(),
                    focus_dimensions=focus_dims,
                    focus_capabilities=focus_caps,
                )

            pass_entries.append(
                DepthPassEntry(
                    pass_number=pass_number,
                    stance_key=stance_key,
                    consumes_from=consumes_from,
                )
            )

        depth_sequences.append(
            DepthSequence(
                depth_key=dl.get("key", ""),
                passes=pass_entries,
            )
        )

    if not stance_ops_map:
        print(f"  Skipping {engine_key}: no passes found")
        return None

    return EngineOperationalization(
        engine_key=engine_key,
        engine_name=engine_name,
        stance_operationalizations=list(stance_ops_map.values()),
        depth_sequences=depth_sequences,
    )


class LiteralStr(str):
    """String that should be rendered as a YAML literal block."""
    pass


def literal_representer(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


yaml.add_representer(LiteralStr, literal_representer)


def write_operationalization(op: EngineOperationalization, output_dir: Path) -> None:
    """Write an operationalization to a YAML file with nice formatting."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{op.engine_key}.yaml"

    data = op.model_dump(mode="json")

    # Convert long descriptions to literal block style for readability
    for stance_op in data.get("stance_operationalizations", []):
        desc = stance_op.get("description", "")
        if "\n" in desc or len(desc) > 100:
            stance_op["description"] = LiteralStr(desc)

    with open(output_path, "w") as f:
        yaml.dump(
            data,
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            width=120,
        )

    stance_count = len(op.stance_operationalizations)
    depth_count = len(op.depth_sequences)
    print(f"  Wrote {output_path.name}: {stance_count} stances, {depth_count} depths")


def main():
    print(f"Scanning {CAPABILITY_DIR} for engine capability YAMLs...")
    yaml_files = sorted(CAPABILITY_DIR.glob("*.yaml"))
    print(f"Found {len(yaml_files)} capability definitions")
    print()

    extracted = 0
    for yaml_path in yaml_files:
        print(f"Processing: {yaml_path.name}")
        op = extract_from_engine(yaml_path)
        if op:
            write_operationalization(op, OUTPUT_DIR)
            extracted += 1

    print()
    print(f"Extracted {extracted} operationalizations to {OUTPUT_DIR}")

    # Validate by loading through registry
    print()
    print("Validating via registry...")
    from src.operationalizations.registry import OperationalizationRegistry

    reg = OperationalizationRegistry(OUTPUT_DIR)
    reg.load()
    print(f"Registry loaded {reg.count()} operationalizations")

    matrix = reg.coverage_matrix()
    print(f"Stance coverage: {matrix.all_stance_keys}")
    for entry in matrix.engines:
        print(f"  {entry.engine_key}: {entry.stance_keys}")


if __name__ == "__main__":
    main()
