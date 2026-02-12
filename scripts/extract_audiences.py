#!/usr/bin/env python3
"""Extract audience definitions from analyzer's audience_profiles.py into JSON files.

This script reads the rich audience data from the main Analyzer service and
generates individual JSON files for each audience in analyzer-v2's definitions format.

Usage:
    python scripts/extract_audiences.py

Reads from: /home/evgeny/projects/analyzer/src/core/audience_profiles.py
Writes to:  src/audiences/definitions/*.json
"""

import json
import sys
from pathlib import Path

# Add analyzer to path so we can import from it
sys.path.insert(0, "/home/evgeny/projects/analyzer")

from src.core.audience_profiles import (
    AudienceType,
    AUDIENCE_PROFILES,
    AUDIENCE_VISUAL_STYLES,
    TEXTUAL_AUDIENCE_STYLES,
    STRATEGIST_AUDIENCE_STYLES,
    PATTERN_DISCOVERY_AUDIENCE_STYLES,
    VOCABULARY_TRANSLATIONS,
)

OUTPUT_DIR = Path(__file__).parent.parent / "src" / "audiences" / "definitions"


# Human-readable names and descriptions for each audience
AUDIENCE_META = {
    AudienceType.ANALYST: {
        "name": "Analyst",
        "description": "Data-driven professionals who want comprehensive, nuanced analysis with full evidence chains. Comfortable with technical vocabulary and high information density.",
    },
    AudienceType.EXECUTIVE: {
        "name": "Executive",
        "description": "Decision-makers who need the bottom line fast. Focused on strategic implications, key risks/opportunities, and actionable takeaways. Zero tolerance for jargon.",
    },
    AudienceType.RESEARCHER: {
        "name": "Researcher",
        "description": "Scholars who want methodological rigor, theoretical depth, and literature positioning. Comfortable with academic prose and complex argumentation.",
    },
    AudienceType.ACTIVIST: {
        "name": "Activist",
        "description": "Change-makers focused on power dynamics, leverage points, and strategic intervention. Want evidence that enables action and exposes asymmetries.",
    },
    AudienceType.SOCIAL_MOVEMENTS: {
        "name": "Social Movements",
        "description": "Organizers and movement builders focused on mobilization. Need clear villains, visceral injustice, collective action paths, and urgent calls to action.",
    },
}

# Vocabulary guidance intro/outro per audience
VOCAB_GUIDANCE = {
    AudienceType.ANALYST: {
        "intro": "Technical and philosophical terminology is APPROPRIATE for this audience. Use domain vocabulary without apology.",
        "outro": "Maintain terminological precision. Do not oversimplify vocabulary.",
    },
    AudienceType.RESEARCHER: {
        "intro": "Full academic terminology is expected. Use technical terms with standard disciplinary meanings.",
        "outro": "Terminological precision is essential. Include parenthetical definitions only for cross-disciplinary terms.",
    },
    AudienceType.EXECUTIVE: {
        "intro": "TRANSLATE all technical/philosophical jargon into plain business language. Executives should never encounter unfamiliar terms.",
        "outro": "Every label, annotation, and term must be immediately understandable without specialized knowledge.",
    },
    AudienceType.ACTIVIST: {
        "intro": "TRANSLATE academic jargon into clear, action-oriented language. Frame terms as tools for understanding power.",
        "outro": "Language should empower, not gatekeep. If a term doesn't help understanding or action, replace it.",
    },
    AudienceType.SOCIAL_MOVEMENTS: {
        "intro": "NO JARGON. Every word must be accessible to everyone. Technical terms become weapons, tools, and calls to action.",
        "outro": "Could this be read aloud at a meeting and understood by everyone? If not, simplify it.",
    },
}


def pivot_vocabulary(audience_type: AudienceType) -> dict[str, str]:
    """Pivot vocabulary translations from per-term to per-audience format.

    VOCABULARY_TRANSLATIONS is {term: {audience: translation}}
    We need {term: translation} for each audience.
    """
    audience_key = audience_type.value
    translations = {}

    for term, audience_map in VOCABULARY_TRANSLATIONS.items():
        if audience_key in audience_map:
            translations[term] = audience_map[audience_key]

    return translations


def build_audience_json(audience_type: AudienceType) -> dict:
    """Build complete audience definition JSON for one audience type."""
    profile = AUDIENCE_PROFILES[audience_type]
    meta = AUDIENCE_META[audience_type]
    visual = AUDIENCE_VISUAL_STYLES.get(audience_type, {})
    textual = TEXTUAL_AUDIENCE_STYLES.get(audience_type, {})
    strategist = STRATEGIST_AUDIENCE_STYLES.get(audience_type, {})
    pattern = PATTERN_DISCOVERY_AUDIENCE_STYLES.get(audience_type, {})
    vocab_guidance = VOCAB_GUIDANCE.get(audience_type, {"intro": "", "outro": ""})

    return {
        "audience_key": audience_type.value,
        "audience_name": meta["name"],
        "description": meta["description"],
        "version": 1,
        "status": "active",
        "identity": {
            "core_questions": profile.core_questions,
            "priorities": profile.priorities,
            "deprioritize": profile.deprioritize,
            "detail_level": profile.detail_level,
        },
        "engine_affinities": {
            "preferred_categories": profile.preferred_categories,
            "high_affinity_engines": profile.high_affinity_engines,
            "low_affinity_engines": profile.low_affinity_engines,
            "category_weights": profile.category_weights,
        },
        "visual_style": {
            "style_preference": profile.style_preference,
            "aesthetic": visual.get("aesthetic", ""),
            "color_palette": visual.get("color_palette", ""),
            "typography": visual.get("typography", ""),
            "layout": visual.get("layout", ""),
            "visual_elements": visual.get("visual_elements", ""),
            "information_density": visual.get("information_density", "MEDIUM"),
            "emotional_tone": visual.get("emotional_tone", ""),
            "key_principle": visual.get("key_principle", ""),
            "style_affinities": [],
        },
        "textual_style": {
            "voice": textual.get("voice", ""),
            "structure": textual.get("structure", ""),
            "evidence_handling": textual.get("evidence_handling", ""),
            "sentence_style": textual.get("sentence_style", ""),
            "what_to_emphasize": textual.get("what_to_emphasize", ""),
            "what_to_avoid": textual.get("what_to_avoid", ""),
            "word_count_guidance": textual.get("word_count_guidance", ""),
            "opening_style": textual.get("opening_style", ""),
            "key_principle": textual.get("key_principle", ""),
        },
        "curation": {
            "curation_emphasis": profile.curation_emphasis.strip(),
            "fidelity_constraint": (
                "The audience framing adjusts HOW you present findings, NOT WHAT the findings are. "
                "You MUST faithfully represent the source document's actual argument."
            ),
        },
        "strategist": {
            "num_visualizations": strategist.get("num_visualizations", ""),
            "visualization_complexity": strategist.get("visualization_complexity", ""),
            "table_purposes": strategist.get("table_purposes", []),
            "table_differentiation": strategist.get("table_differentiation", ""),
            "narrative_focus": strategist.get("narrative_focus", ""),
            "what_matters_most": strategist.get("what_matters_most", ""),
            "what_to_avoid_in_strategy": strategist.get("what_to_avoid_in_strategy", ""),
        },
        "pattern_discovery": {
            "pattern_types_priority": pattern.get("pattern_types_priority", []),
            "meta_insight_focus": pattern.get("meta_insight_focus", ""),
            "what_counts_as_significant": pattern.get("what_counts_as_significant", ""),
            "surprise_definition": pattern.get("surprise_definition", ""),
        },
        "vocabulary": {
            "translations": pivot_vocabulary(audience_type),
            "guidance_intro": vocab_guidance["intro"],
            "guidance_outro": vocab_guidance["outro"],
        },
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for audience_type in AudienceType:
        audience_json = build_audience_json(audience_type)
        output_file = OUTPUT_DIR / f"{audience_type.value}.json"

        with open(output_file, "w") as f:
            json.dump(audience_json, f, indent=2, ensure_ascii=False)

        vocab_count = len(audience_json["vocabulary"]["translations"])
        affinity_count = len(audience_json["engine_affinities"]["high_affinity_engines"])
        print(f"  {audience_type.value}: {vocab_count} vocab translations, {affinity_count} high-affinity engines -> {output_file.name}")

    print(f"\nDone! Generated {len(AudienceType)} audience definitions in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
