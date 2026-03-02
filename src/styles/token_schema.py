"""
Pydantic v2 schemas for the Design Token System.

Six tiers of design tokens that fully parameterize the visual rendering
of any analysis output:

1. PrimitiveTokens - raw colors and font stacks
2. SurfaceTokens - surface/background/shadow semantics
3. ScaleTokens - typography scale, spacing scale, radius scale
4. SemanticTokens - domain-specific color triples (severity, visibility, modality, etc.)
5. CategoricalTokens - per-category color+label for tactics, idea forms, types, etc.
6. ComponentTokens - concrete component-level tokens (cards, chips, timelines, etc.)

These are generated per-school by an LLM that reads the StyleGuide JSON and
produces a coherent, harmonious token set.
"""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Tier 1: Primitives
# ---------------------------------------------------------------------------

class PrimitiveTokens(BaseModel):
    """Raw colors and font stacks. The atomic building blocks."""
    color_primary: str = Field(..., description="Primary brand color (hex)")
    color_secondary: str = Field(..., description="Secondary color (hex)")
    color_tertiary: str = Field(..., description="Tertiary color (hex)")
    color_accent: str = Field(..., description="Accent / call-to-action color (hex)")
    color_accent_alt: str = Field(..., description="Alternative accent color (hex)")
    color_background: str = Field(..., description="Page background (hex)")
    color_highlight: str = Field(..., description="Highlight / selection color (hex)")
    color_text: str = Field(..., description="Default body text color (hex)")
    color_muted: str = Field(..., description="Muted / de-emphasized color (hex)")
    color_positive: str = Field(..., description="Positive / success color (hex)")
    color_negative: str = Field(..., description="Negative / error color (hex)")
    series_palette: list[str] = Field(
        ...,
        min_length=5,
        max_length=8,
        description="5-8 visually distinct colors for data series (hex list)"
    )
    font_primary: str = Field(..., description="Primary body font CSS stack")
    font_title: str = Field(..., description="Title / headline font CSS stack")
    font_caption: str = Field(..., description="Caption / annotation font CSS stack")
    font_number: str = Field(..., description="Tabular / numeric font CSS stack")


# ---------------------------------------------------------------------------
# Tier 2: Surfaces
# ---------------------------------------------------------------------------

class SurfaceTokens(BaseModel):
    """Surface, border, text-on-surface, and shadow tokens."""
    surface_default: str = Field(..., description="Default surface background (hex)")
    surface_alt: str = Field(..., description="Alternate / striped surface (hex)")
    surface_elevated: str = Field(..., description="Elevated card surface (hex)")
    surface_inset: str = Field(..., description="Inset / recessed surface (hex)")
    border_default: str = Field(..., description="Default border color (hex)")
    border_light: str = Field(..., description="Light / subtle border (hex)")
    border_accent: str = Field(..., description="Accent-colored border (hex)")
    text_default: str = Field(..., description="Default text on surface (hex)")
    text_muted: str = Field(..., description="Muted text (hex)")
    text_faint: str = Field(..., description="Faint / ghost text (hex)")
    text_on_accent: str = Field(..., description="Text on accent background (hex)")
    text_inverse: str = Field(..., description="Text on dark background (hex)")
    shadow_sm: str = Field(..., description="Small shadow (CSS box-shadow value)")
    shadow_md: str = Field(..., description="Medium shadow (CSS box-shadow value)")
    shadow_lg: str = Field(..., description="Large shadow (CSS box-shadow value)")


# ---------------------------------------------------------------------------
# Tier 3: Scales
# ---------------------------------------------------------------------------

class ScaleTokens(BaseModel):
    """Typography scale, spacing scale, and radius scale.

    Spacing and radius are structural invariants - identical across all schools.
    Typography varies per school.
    """
    # Typography sizes (CSS values like "2.25rem", "1.5rem", etc.)
    type_display: str = Field(..., description="Display / hero text size")
    type_heading: str = Field(..., description="Section heading size")
    type_subheading: str = Field(..., description="Sub-heading size")
    type_body: str = Field(..., description="Body text size")
    type_caption: str = Field(..., description="Caption / small text size")
    type_label: str = Field(..., description="Label / chip text size")

    # Font weights (CSS values: "300", "400", "500", "600", "700", etc.)
    weight_light: str = Field(..., description="Light weight")
    weight_regular: str = Field(..., description="Regular weight")
    weight_medium: str = Field(..., description="Medium weight")
    weight_semibold: str = Field(..., description="Semibold weight")
    weight_bold: str = Field(..., description="Bold weight")
    weight_title: str = Field(..., description="Title weight (may differ from bold)")

    # Line heights (unitless multipliers or CSS values)
    leading_tight: str = Field(..., description="Tight line-height")
    leading_normal: str = Field(..., description="Normal line-height")
    leading_loose: str = Field(..., description="Loose / comfortable line-height")

    # Spacing (CSS values - STRUCTURAL INVARIANTS, same across all schools)
    space_2xs: str = Field(..., description="2x-small spacing")
    space_xs: str = Field(..., description="Extra-small spacing")
    space_sm: str = Field(..., description="Small spacing")
    space_md: str = Field(..., description="Medium spacing")
    space_lg: str = Field(..., description="Large spacing")
    space_xl: str = Field(..., description="Extra-large spacing")
    space_2xl: str = Field(..., description="2x-large spacing")
    space_3xl: str = Field(..., description="3x-large spacing")

    # Border radii (CSS values - STRUCTURAL INVARIANTS, same across all schools)
    radius_sm: str = Field(..., description="Small radius")
    radius_md: str = Field(..., description="Medium radius")
    radius_lg: str = Field(..., description="Large radius")
    radius_xl: str = Field(..., description="Extra-large radius")
    radius_pill: str = Field(..., description="Pill / fully rounded radius")


# ---------------------------------------------------------------------------
# Tier 4: Semantic
# ---------------------------------------------------------------------------

class SemanticTriple(BaseModel):
    """A background + text + border triple for semantic categories."""
    bg: str = Field(..., description="Background color (hex)")
    text: str = Field(..., description="Text color (hex)")
    border: str = Field(..., description="Border color (hex)")


class SemanticTokens(BaseModel):
    """Domain-specific semantic color triples."""

    # Severity levels
    severity_high: SemanticTriple
    severity_medium: SemanticTriple
    severity_low: SemanticTriple

    # Visibility levels
    visibility_explicit: SemanticTriple
    visibility_implicit: SemanticTriple
    visibility_hidden: SemanticTriple

    # Modality types
    modality_ontological: SemanticTriple
    modality_methodological: SemanticTriple
    modality_normative: SemanticTriple
    modality_epistemic: SemanticTriple
    modality_causal: SemanticTriple

    # Change types
    change_stable: SemanticTriple
    change_narrowed: SemanticTriple
    change_expanded: SemanticTriple
    change_inverted: SemanticTriple
    change_metaphorized: SemanticTriple

    # Centrality levels
    centrality_core: SemanticTriple
    centrality_supporting: SemanticTriple
    centrality_peripheral: SemanticTriple

    # Status indicators
    status_completed: SemanticTriple
    status_running: SemanticTriple
    status_pending: SemanticTriple
    status_failed: SemanticTriple


# ---------------------------------------------------------------------------
# Tier 5: Categorical
# ---------------------------------------------------------------------------

class CategoricalItem(BaseModel):
    """A single categorical item with color triple + human label."""
    bg: str = Field(..., description="Background color (hex)")
    text: str = Field(..., description="Text color (hex)")
    border: str = Field(..., description="Border color (hex)")
    label: str = Field(..., description="Human-readable label")


class CategoricalTokens(BaseModel):
    """Per-category color + label tokens for every domain concept."""

    # Tactics (10)
    tactic_conceptual_recycling: CategoricalItem
    tactic_silent_revision: CategoricalItem
    tactic_selective_continuity: CategoricalItem
    tactic_retroactive_framing: CategoricalItem
    tactic_escalation: CategoricalItem
    tactic_narrative_bootstrapping: CategoricalItem
    tactic_framework_migration: CategoricalItem
    tactic_condition_shift: CategoricalItem
    tactic_biographical_teleology: CategoricalItem
    tactic_strategic_amnesia: CategoricalItem

    # Idea forms (5)
    form_proto_form: CategoricalItem
    form_full_form: CategoricalItem
    form_contradictory_form: CategoricalItem
    form_absent_but_implied: CategoricalItem
    form_different_framing: CategoricalItem

    # Idea types (11)
    idea_central_thesis: CategoricalItem
    idea_supporting_argument: CategoricalItem
    idea_supporting_framework: CategoricalItem
    idea_methodological_tool: CategoricalItem
    idea_conceptual_framework: CategoricalItem
    idea_empirical_finding: CategoricalItem
    idea_normative_claim: CategoricalItem
    idea_analytical_distinction: CategoricalItem
    idea_rhetorical_strategy: CategoricalItem
    idea_rhetorical_device: CategoricalItem
    idea_historical_analysis: CategoricalItem

    # Condition types (8)
    condition_conceptual_foundation: CategoricalItem
    condition_audience_preparation: CategoricalItem
    condition_authority_establishment: CategoricalItem
    condition_framework_provision: CategoricalItem
    condition_problem_definition: CategoricalItem
    condition_methodological_precedent: CategoricalItem
    condition_intellectual_toolkit: CategoricalItem
    condition_cross_domain_transfer: CategoricalItem

    # Relationship types (8)
    relationship_direct_precursor: CategoricalItem
    relationship_methodological_ancestor: CategoricalItem
    relationship_counter_position: CategoricalItem
    relationship_indirect_contextualizer: CategoricalItem
    relationship_stylistic_influence: CategoricalItem
    relationship_conceptual_sibling: CategoricalItem
    relationship_different_field_relevant: CategoricalItem
    relationship_tangential: CategoricalItem

    # Strength levels (3)
    strength_strong: CategoricalItem
    strength_moderate: CategoricalItem
    strength_weak: CategoricalItem

    # Awareness levels (3)
    awareness_explicit: CategoricalItem
    awareness_implicit: CategoricalItem
    awareness_unconscious: CategoricalItem

    # Pattern types (7)
    pattern_analytical_method: CategoricalItem
    pattern_cognitive_habit: CategoricalItem
    pattern_recurring_metaphor: CategoricalItem
    pattern_problem_solving_approach: CategoricalItem
    pattern_theoretical_framework: CategoricalItem
    pattern_argumentative_structure: CategoricalItem
    pattern_epistemic_commitment: CategoricalItem


# ---------------------------------------------------------------------------
# Tier 6: Components
# ---------------------------------------------------------------------------

class ComponentTokens(BaseModel):
    """Concrete component-level tokens for UI elements."""

    # Page-level accents
    page_accent: str = Field(..., description="Page accent color")
    page_accent_hover: str = Field(..., description="Page accent hover state")
    page_accent_bg: str = Field(..., description="Page accent background tint")

    # Section headers
    section_header_bg: str
    section_header_border: str
    section_header_text: str

    # Cards
    card_bg: str
    card_border: str
    card_border_accent: str
    card_header_bg: str
    card_header_text: str

    # Chip weight progression (0%, 25%, 50%, 75%, 100%)
    chip_weight_0_bg: str
    chip_weight_0_text: str
    chip_weight_0_border: str
    chip_weight_25_bg: str
    chip_weight_25_text: str
    chip_weight_25_border: str
    chip_weight_50_bg: str
    chip_weight_50_text: str
    chip_weight_50_border: str
    chip_weight_75_bg: str
    chip_weight_75_text: str
    chip_weight_75_border: str
    chip_weight_100_bg: str
    chip_weight_100_text: str
    chip_weight_100_border: str
    chip_header_bg: str
    chip_header_text: str

    # Prose
    prose_lede_color: str
    prose_lede_weight: str
    prose_blockquote_border: str
    prose_blockquote_bg: str

    # Timeline
    timeline_connector: str
    timeline_connector_width: str
    timeline_node_bg: str
    timeline_node_border: str

    # Evidence
    evidence_dot_bg: str
    evidence_connector: str

    # Stats
    stat_number_color: str
    stat_label_color: str
    stat_card_bg: str


# ---------------------------------------------------------------------------
# Top-level container
# ---------------------------------------------------------------------------

class DesignTokenSet(BaseModel):
    """Complete design token set for a style school.

    Contains all 6 tiers of tokens that fully parameterize the visual rendering
    of any analysis output in a given style school.
    """
    school_key: str = Field(..., description="Style school key (e.g., 'minimalist_precision')")
    school_name: str = Field(..., description="Human-readable school name")
    generated_at: str = Field(..., description="ISO 8601 timestamp of generation")
    version: str = Field(default="1.0.0", description="Token schema version")

    primitives: PrimitiveTokens
    surfaces: SurfaceTokens
    scales: ScaleTokens
    semantic: SemanticTokens
    categorical: CategoricalTokens
    components: ComponentTokens
