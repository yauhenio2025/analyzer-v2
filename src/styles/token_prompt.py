"""
Prompt template for LLM-based design token generation.

Given a StyleGuide JSON and the DesignTokenSet JSON schema,
produces a prompt that instructs the LLM to generate a complete,
harmonious token set for that style school.
"""

import json
from .token_schema import DesignTokenSet


# Structural invariants: spacing and radius are identical across all schools.
# The LLM should NOT vary these — they are injected post-generation.
STRUCTURAL_INVARIANTS = {
    "space_2xs": "0.125rem",
    "space_xs": "0.25rem",
    "space_sm": "0.5rem",
    "space_md": "1rem",
    "space_lg": "1.5rem",
    "space_xl": "2rem",
    "space_2xl": "3rem",
    "space_3xl": "4rem",
    "radius_sm": "0.25rem",
    "radius_md": "0.5rem",
    "radius_lg": "0.75rem",
    "radius_xl": "1rem",
    "radius_pill": "9999px",
}


def build_token_generation_prompt(style_guide_json: dict) -> str:
    """Build the prompt for generating a complete DesignTokenSet.

    Args:
        style_guide_json: The StyleGuide definition as a dict

    Returns:
        The complete prompt string for the LLM
    """
    school_key = style_guide_json.get("key", "unknown")
    school_name = style_guide_json.get("name", "Unknown School")

    return f"""You are a senior design systems engineer generating a complete design token set
for the "{school_name}" visual style school.

## Style School Definition

```json
{json.dumps(style_guide_json, indent=2)}
```

## Your Task

Generate a COMPLETE design token set with all 6 tiers. Every field must be filled.
The token set must be internally harmonious and faithfully express this school's
design philosophy.

## Design Principles

1. **Color Harmony**: All colors must form a cohesive palette. Use the school's
   color_palette as your starting point but expand it thoughtfully to cover all
   the semantic and categorical needs.

2. **Visual Distinctness**: Categorical items (tactics, idea types, etc.) must be
   visually distinguishable from each other. Use hue variation, not just lightness.
   Aim for at least 30 degrees of hue separation between adjacent categories.

3. **Chip Weight Hierarchy**: The 5 chip weight levels (0%, 25%, 50%, 75%, 100%)
   must form a clear visual progression from lightest/most neutral to
   darkest/most saturated. This is critical for data legibility.

4. **Semantic Appropriateness**:
   - severity_high should feel urgent/alarming; severity_low should feel calm
   - visibility_explicit should feel clear/bold; visibility_hidden should feel subtle
   - modality types should each have a distinct character
   - status_completed = success/done; status_failed = error/danger

5. **Accessibility**: Maintain at least 4.5:1 contrast ratio between text and
   background colors for all semantic triples and categorical items.

6. **School Fidelity**: The tokens must authentically express the school's
   philosophy. For example:
   - Minimalist Precision: muted palette, high contrast text, no flashy accents
   - Emergent Systems: network-inspired, interconnected feel, organic colors
   - Mobilization: bold, high-contrast, call-to-action energy
   - Restrained Elegance: sophisticated, subdued, editorial quality
   - Humanist Craft: warm, handmade feel, natural tones
   - Explanatory Narrative: clear, didactic, accessible color coding

## Structural Invariants

The following spacing and radius values are FIXED across all schools. Do NOT change them:
```json
{json.dumps(STRUCTURAL_INVARIANTS, indent=2)}
```

Include these exact values in the scales tier.

## Label Guidelines for CategoricalItems

Each CategoricalItem has a `label` field. Use clear, concise human-readable labels:
- Tactics: "Conceptual Recycling", "Silent Revision", etc.
- Idea forms: "Proto-Form", "Full Form", "Contradictory Form", etc.
- Idea types: "Central Thesis", "Supporting Argument", etc.
- Condition types: "Conceptual Foundation", "Audience Preparation", etc.
- Relationship types: "Direct Precursor", "Counter-Position", etc.
- Strength: "Strong", "Moderate", "Weak"
- Awareness: "Explicit", "Implicit", "Unconscious"
- Pattern types: "Analytical Method", "Cognitive Habit", etc.
- Attack types: "Empirical", "Conceptual", "Logical", "Historical", "Rhetorical", "Scope", "Definitional", "Comparative", "Structural", "Cascade"
- Sin types: "Misreading", "Unacknowledged Debt", "Misappropriation", "Decontextualization", "Selective Citation", "Flattening", "Ventriloquism", "Strategic Silence", "Premature Synthesis", "Legitimation Borrowing"
- Provenance categories: "Target Analysis", "Relationships", "Prior Works", "Idea Evolution", "Tactics", "Conditions", "Synthesis", "Research Answers", "Research Contextualizers", "Manual", "Other"

## Output Format

Return the COMPLETE token set matching the DesignTokenSet schema exactly.
All hex colors as 6-digit lowercase hex with # prefix (e.g., "#1a2b3c").
All CSS values as valid CSS strings.
Shadows as valid CSS box-shadow values (e.g., "0 1px 3px rgba(0,0,0,0.12)").
Font weights as numeric strings ("300", "400", "500", "600", "700").
Font sizes as rem values ("0.75rem", "1rem", "1.25rem", etc.).
Line heights as unitless numbers ("1.2", "1.5", "1.75").

Generate the token set for school_key="{school_key}" and school_name="{school_name}".
Set generated_at to the current time and version to "1.0.0".
"""


def get_token_tool_schema() -> dict:
    """Get the JSON schema for use as an Anthropic tool input_schema.

    Returns the DesignTokenSet model's JSON schema for use with
    Anthropic's tool_use structured output feature.
    """
    return DesignTokenSet.model_json_schema()


def get_token_tool_definition() -> dict:
    """Get the complete Anthropic tool definition for token generation.

    Returns:
        A dict suitable for the `tools` parameter in client.messages.create()
    """
    return {
        "name": "generate_tokens",
        "description": (
            "Generate a complete design token set for a visual style school. "
            "The token set must include all 6 tiers: primitives, surfaces, scales, "
            "semantic, categorical, and components. Every field must be filled."
        ),
        "input_schema": get_token_tool_schema(),
    }
