#!/usr/bin/env python3
"""Migrate engine definitions from old prompt format to new stage_context format.

MIGRATION: 2026-01-29
Old format: extraction_prompt, curation_prompt, concretization_prompt (full text)
New format: stage_context with injection context for generic templates

This script:
1. Reads each engine JSON file
2. Analyzes the old prompts to extract engine-specific context
3. Determines appropriate framework_key based on content patterns
4. Builds the new stage_context structure
5. Backs up the original file
6. Writes the migrated JSON

Usage:
    python scripts/migrate_engines_to_stages.py [--dry-run] [--engine KEY]

Options:
    --dry-run       Preview changes without writing files
    --engine KEY    Migrate only the specified engine
    --backup-dir    Directory for backups (default: src/engines/definitions_backup_pre_stages)
"""

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any, Optional


# Patterns to detect framework usage
FRAMEWORK_PATTERNS = {
    "brandomian": [
        r"brandom",
        r"inferential commitment",
        r"deontic",
        r"scorekeeping",
        r"game of giving and asking",
        r"material inference",
        r"entitlement",
    ],
    "dennett": [
        r"surely alarm",
        r"occam's broom",
        r"boom crutch",
        r"steelman",
        r"jootsing",
        r"deepity",
        r"sturgeon",
    ],
    "toulmin": [
        r"toulmin",
        r"claim.*ground.*warrant",
        r"warrant.*backing",
        r"rebuttal",
        r"qualifier",
    ],
}


def detect_framework(extraction_prompt: str) -> Optional[str]:
    """Detect which framework the extraction prompt uses."""
    prompt_lower = extraction_prompt.lower()
    scores = {}

    for framework, patterns in FRAMEWORK_PATTERNS.items():
        score = sum(1 for p in patterns if re.search(p, prompt_lower))
        if score > 0:
            scores[framework] = score

    if not scores:
        return None

    # Return framework with highest score
    return max(scores, key=scores.get)


def detect_additional_frameworks(extraction_prompt: str, primary: Optional[str]) -> list[str]:
    """Detect additional frameworks layered on top of primary."""
    prompt_lower = extraction_prompt.lower()
    additional = []

    for framework, patterns in FRAMEWORK_PATTERNS.items():
        if framework == primary:
            continue
        score = sum(1 for p in patterns if re.search(p, prompt_lower))
        if score >= 2:  # Require at least 2 matches for additional
            additional.append(framework)

    return additional


def extract_analysis_type(engine_data: dict) -> tuple[str, str]:
    """Extract the analysis type from engine metadata."""
    # Try to infer from engine_key and description
    key = engine_data.get("engine_key", "")
    desc = engine_data.get("description", "")
    name = engine_data.get("engine_name", "")

    # Common patterns
    if "commitment" in key.lower():
        return "inferential commitment", "inferential commitments"
    if "argument" in key.lower():
        return "argument structure", "argument structures"
    if "concept" in key.lower():
        return "concept", "concepts"
    if "entity" in key.lower():
        return "entity", "entities"
    if "citation" in key.lower():
        return "citation", "citations"
    if "evidence" in key.lower():
        return "evidence", "evidence items"
    if "assumption" in key.lower():
        return "assumption", "assumptions"
    if "claim" in key.lower():
        return "claim", "claims"
    if "relationship" in key.lower():
        return "relationship", "relationships"
    if "pattern" in key.lower():
        return "pattern", "patterns"
    if "theme" in key.lower():
        return "theme", "themes"
    if "tension" in key.lower():
        return "tension", "tensions"
    if "contradiction" in key.lower():
        return "contradiction", "contradictions"

    # Default: use the engine name or key
    type_name = name.lower().replace("mapper", "").replace("analyzer", "").replace("extractor", "").strip()
    if not type_name:
        type_name = key.replace("_", " ")

    return type_name, type_name + "s" if not type_name.endswith("s") else type_name


def extract_id_field(engine_data: dict) -> str:
    """Determine the ID field convention from the schema."""
    schema = engine_data.get("canonical_schema", {})

    # Look for common ID patterns in schema
    schema_str = json.dumps(schema).lower()

    if "commitment_id" in schema_str:
        return "commitment_id"
    if "arg_id" in schema_str:
        return "arg_id"
    if "concept_id" in schema_str:
        return "concept_id"
    if "entity_id" in schema_str:
        return "entity_id"
    if "citation_id" in schema_str:
        return "citation_id"
    if "idea_id" in schema_str:
        return "idea_id"
    if "claim_id" in schema_str:
        return "claim_id"
    if "item_id" in schema_str:
        return "item_id"

    # Default based on engine key
    key = engine_data.get("engine_key", "item")
    base = key.split("_")[0] if "_" in key else key[:8]
    return f"{base}_id"


def extract_key_relationships(extraction_prompt: str, schema: dict) -> list[str]:
    """Extract relationship types from prompts and schema."""
    relationships = set()

    # Common relationship patterns
    patterns = [
        (r"supports", "supports"),
        (r"conflicts?_with", "conflicts_with"),
        (r"contradicts?", "contradicts"),
        (r"leads_to", "leads_to"),
        (r"depends_on", "depends_on"),
        (r"entails", "entails"),
        (r"implies", "implies"),
        (r"opposes", "opposes"),
        (r"chains?_to", "chains_to"),
        (r"responds_to", "responds_to"),
        (r"cites", "cites"),
        (r"references", "references"),
        (r"incompatible", "is_incompatible_with"),
        (r"presupposes", "presupposes"),
    ]

    prompt_lower = extraction_prompt.lower()
    schema_str = json.dumps(schema).lower()
    combined = prompt_lower + " " + schema_str

    for pattern, rel_name in patterns:
        if re.search(pattern, combined):
            relationships.add(rel_name)

    return list(relationships) if relationships else ["relates_to"]


def extract_extraction_steps(extraction_prompt: str) -> list[str]:
    """Extract numbered extraction steps from the prompt."""
    steps = []

    # Look for numbered steps or STEP patterns
    step_patterns = [
        r"### STEP \d+[:\s]*([^\n]+)",
        r"\d+\.\s*\*\*([^*]+)\*\*",
        r"(?:^|\n)\d+\.\s+([A-Z][^\n]{10,100})",
    ]

    for pattern in step_patterns:
        matches = re.findall(pattern, extraction_prompt)
        if matches and len(matches) >= 3:
            steps = [m.strip() for m in matches[:10]]  # Cap at 10 steps
            break

    if not steps:
        # Default generic steps
        steps = [
            "Read the document carefully to understand the context",
            "Identify key items matching the analysis type",
            "Extract relationships between items",
            "Build the relationship graph",
            "Verify completeness and accuracy",
        ]

    return steps


def extract_consolidation_rules(curation_prompt: str) -> list[str]:
    """Extract consolidation rules from curation prompt."""
    rules = []

    # Look for numbered rules or bullet points
    patterns = [
        r"\d+\.\s*\*\*([^*]+)\*\*[:\s]*([^\n]+)",
        r"[-*]\s*\*\*([^*]+)\*\*[:\s]*([^\n]+)",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, curation_prompt)
        if matches:
            for title, desc in matches[:6]:
                rules.append(f"{title.strip()}: {desc.strip()}")
            break

    return rules


def extract_id_examples(concretization_prompt: Optional[str]) -> list[dict[str, str]]:
    """Extract ID transformation examples from concretization prompt."""
    if not concretization_prompt:
        return []

    examples = []

    # Look for patterns like "A1" → "Something" or "A1" -> "Something"
    patterns = [
        r'"([A-Z]\d+)"\s*[→\->\u2192]\s*"([^"]+)"',
        r"'([A-Z]\d+)'\s*[→\->\u2192]\s*'([^']+)'",
        r"`([A-Z]\d+)`\s*[→\->\u2192]\s*`([^`]+)`",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, concretization_prompt)
        for from_id, to_name in matches[:5]:
            examples.append({"from": from_id, "to": to_name})

    return examples


def migrate_engine(engine_data: dict) -> dict:
    """Convert an engine from old format to new stage_context format."""
    # Extract old prompts
    extraction_prompt = engine_data.pop("extraction_prompt", "")
    curation_prompt = engine_data.pop("curation_prompt", "")
    concretization_prompt = engine_data.pop("concretization_prompt", None)

    # Detect framework
    framework_key = detect_framework(extraction_prompt)
    additional_frameworks = detect_additional_frameworks(extraction_prompt, framework_key)

    # Extract analysis type
    analysis_type, analysis_type_plural = extract_analysis_type(engine_data)

    # Get ID field
    id_field = extract_id_field(engine_data)

    # Get relationships
    key_relationships = extract_key_relationships(
        extraction_prompt,
        engine_data.get("canonical_schema", {}),
    )

    # Get extraction steps
    extraction_steps = extract_extraction_steps(extraction_prompt)

    # Get consolidation rules
    consolidation_rules = extract_consolidation_rules(curation_prompt)

    # Get ID examples
    id_examples = extract_id_examples(concretization_prompt)

    # Build stage_context
    stage_context = {
        "framework_key": framework_key,
        "additional_frameworks": additional_frameworks,
        "extraction": {
            "analysis_type": analysis_type,
            "analysis_type_plural": analysis_type_plural,
            "core_question": engine_data.get("researcher_question", f"What {analysis_type_plural} are present?"),
            "extraction_steps": extraction_steps,
            "key_fields": {},  # Could parse from schema
            "id_field": id_field,
            "key_relationships": key_relationships,
            "special_instructions": None,
        },
        "curation": {
            "item_type": analysis_type,
            "item_type_plural": analysis_type_plural,
            "consolidation_rules": consolidation_rules,
            "cross_doc_patterns": [
                "shared_items",
                "contested_items",
                "response_network",
            ],
            "synthesis_outputs": [
                "consolidated_item_list",
                "relationship_map",
                "cross_document_dynamics",
            ],
            "special_instructions": None,
        },
        "concretization": {
            "id_examples": id_examples,
            "naming_guidance": "",
            "recommended_table_types": [],
            "recommended_visual_patterns": [],
        },
        "audience_vocabulary": {
            "researcher": {},
            "analyst": {},
            "executive": {},
            "activist": {},
        },
        "skip_concretization": concretization_prompt is None,
    }

    # Update engine data
    engine_data["stage_context"] = stage_context

    return engine_data


def migrate_file(
    file_path: Path,
    backup_dir: Path,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """Migrate a single engine file.

    Returns:
        (success, message)
    """
    try:
        # Read original
        with open(file_path, "r") as f:
            original_data = json.load(f)

        # Check if already migrated
        if "stage_context" in original_data:
            return True, f"Already migrated: {file_path.name}"

        # Check if has old format
        if "extraction_prompt" not in original_data:
            return False, f"Missing extraction_prompt: {file_path.name}"

        # Migrate
        migrated_data = migrate_engine(original_data.copy())

        if dry_run:
            return True, f"Would migrate: {file_path.name} (framework: {migrated_data['stage_context'].get('framework_key', 'none')})"

        # Backup original
        backup_path = backup_dir / file_path.name
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, backup_path)

        # Write migrated
        with open(file_path, "w") as f:
            json.dump(migrated_data, f, indent=2)

        framework = migrated_data["stage_context"].get("framework_key", "none")
        return True, f"Migrated: {file_path.name} (framework: {framework})"

    except Exception as e:
        return False, f"Error migrating {file_path.name}: {e}"


def main():
    parser = argparse.ArgumentParser(
        description="Migrate engine definitions to stage_context format"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing files",
    )
    parser.add_argument(
        "--engine",
        type=str,
        help="Migrate only the specified engine key",
    )
    parser.add_argument(
        "--backup-dir",
        type=str,
        default="src/engines/definitions_backup_pre_stages",
        help="Directory for backups",
    )
    args = parser.parse_args()

    # Paths
    definitions_dir = Path("src/engines/definitions")
    backup_dir = Path(args.backup_dir)

    if not definitions_dir.exists():
        print(f"Error: Definitions directory not found: {definitions_dir}")
        return 1

    # Get files to migrate
    if args.engine:
        files = [definitions_dir / f"{args.engine}.json"]
        if not files[0].exists():
            print(f"Error: Engine file not found: {files[0]}")
            return 1
    else:
        files = sorted(definitions_dir.glob("*.json"))

    print(f"{'DRY RUN: ' if args.dry_run else ''}Migrating {len(files)} engine files...")
    print(f"Backup directory: {backup_dir}")
    print()

    success_count = 0
    skip_count = 0
    error_count = 0

    for file_path in files:
        success, message = migrate_file(file_path, backup_dir, args.dry_run)
        print(message)

        if "Already migrated" in message:
            skip_count += 1
        elif success:
            success_count += 1
        else:
            error_count += 1

    print()
    print(f"Summary: {success_count} migrated, {skip_count} skipped, {error_count} errors")

    if args.dry_run:
        print("\nThis was a dry run. No files were modified.")
        print("Run without --dry-run to apply changes.")

    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    exit(main())
