#!/usr/bin/env python3
"""Add 'critic' app tag to all Critic-related engines.

This script tags all engines used by The Critic app with "apps": ["critic"]
to enable filtering in the API.
"""

import json
from pathlib import Path

DEFINITIONS_DIR = Path(__file__).parent.parent / "src" / "engines" / "definitions"

# All engine patterns to tag with "critic"
CRITIC_ENGINES = [
    # New debate-specific rhetoric engines
    "rhetoric_deflection_analyzer",
    "rhetoric_contradiction_detector",
    "rhetoric_leap_finder",
    "rhetoric_silence_mapper",
    "rhetoric_concession_tracker",
    "rhetoric_retreat_detector",
    "rhetoric_cherrypick_analyzer",
    # Vulnerability engines (self-analysis)
    "vulnerability_strawman_risk",
    "vulnerability_inconsistency",
    "vulnerability_logic_gap",
    "vulnerability_unanswered",
    "vulnerability_overconcession",
    "vulnerability_overreach",
    "vulnerability_undercitation",
    "vulnerability_weak_authority",
    "vulnerability_exposed_flank",
    # Outline editor engines
    "outline_talking_point_generator",
    "outline_notes_extractor",
    "outline_talking_point_upgrader",
    "outline_document_summarizer",
    "outline_synthesis_generator",
    # Big picture analysis
    "big_picture_inferential",
    # Existing rhetoric engines used by Critic
    "tu_quoque_tracker",
    "motte_bailey_detector",
    "strategic_omission_detector",
    "authenticity_forensics",
]

# Concept engines used by Critic's 12-phase concept analysis
CONCEPT_ENGINE_PREFIXES = [
    "concept_semantic_constellation",
    "concept_structural_landscape",
    "concept_argument_formalization",
    "concept_chain_building",
    "concept_taxonomy_",  # All taxonomy engines
    "concept_causal_",  # All causal engines
    "concept_conditional_",  # All conditional engines
    "concept_argumentative_weight",
    "concept_vulnerability_",  # All concept vulnerability engines
    "concept_cross_text_comparison",
    "concept_quote_retrieval",
    "concept_synthesis",
    "concept_centrality_mapper",
    "concept_demarcation_analyzer",
    "concept_evolution",
    "concept_appropriation_tracker",
]


def should_tag_engine(engine_key: str) -> bool:
    """Check if an engine should be tagged with 'critic'."""
    if engine_key in CRITIC_ENGINES:
        return True
    for prefix in CONCEPT_ENGINE_PREFIXES:
        if engine_key.startswith(prefix):
            return True
    return False


def tag_engine(file_path: Path) -> bool:
    """Add 'critic' to the apps list of an engine."""
    with open(file_path, "r") as f:
        data = json.load(f)

    engine_key = data.get("engine_key", "")
    if not should_tag_engine(engine_key):
        return False

    # Get or create apps list
    apps = data.get("apps", [])
    if "critic" in apps:
        print(f"  Already tagged: {engine_key}")
        return False

    # Add critic to apps
    apps.append("critic")
    data["apps"] = apps

    # Write back
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")  # Trailing newline

    print(f"  Tagged: {engine_key}")
    return True


def main():
    print("Tagging Critic engines...")
    print(f"Scanning: {DEFINITIONS_DIR}")

    tagged_count = 0
    scanned_count = 0

    for json_file in sorted(DEFINITIONS_DIR.glob("*.json")):
        scanned_count += 1
        if tag_engine(json_file):
            tagged_count += 1

    print(f"\nDone! Tagged {tagged_count} engines (scanned {scanned_count} total)")


if __name__ == "__main__":
    main()
