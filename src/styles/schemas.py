"""
Pydantic schemas for visual style definitions.
"""

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, model_validator


class StyleSchool(str, Enum):
    """The 6 major dataviz style schools."""
    MINIMALIST_PRECISION = "minimalist_precision"
    EXPLANATORY_NARRATIVE = "explanatory_narrative"
    RESTRAINED_ELEGANCE = "restrained_elegance"
    HUMANIST_CRAFT = "humanist_craft"
    EMERGENT_SYSTEMS = "emergent_systems"
    MOBILIZATION = "mobilization"


class StyleExemplar(BaseModel):
    """A person or organization whose work exemplifies this style tradition."""
    name: str = Field(..., description="Name of the person or organization")
    contribution: str = Field(..., description="What aspect of the style they exemplify")


class StyleInfluences(BaseModel):
    """Influences, exemplars, and key works in this style tradition."""
    tradition_note: str = Field(
        ...,
        description="Explanation of how this style draws from a broader tradition"
    )
    exemplars: list[StyleExemplar] = Field(
        ...,
        description="People/organizations whose work exemplifies this approach"
    )
    key_works: list[str] = Field(
        default_factory=list,
        description="Foundational texts, projects, or artifacts in this tradition"
    )


class ColorPalette(BaseModel):
    """Color palette specification for a style."""
    primary: str = Field(..., description="Primary color (hex)")
    secondary: str = Field(..., description="Secondary color (hex)")
    tertiary: str = Field(..., description="Tertiary color (hex)")
    accent: str = Field(..., description="Accent color for emphasis (hex)")
    background: str = Field(..., description="Background color (hex)")
    text: str = Field(..., description="Text color (hex)")
    # Optional additional colors
    accent_alt: Optional[str] = Field(None, description="Alternative accent color")
    highlight: Optional[str] = Field(None, description="Highlight color")
    muted: Optional[str] = Field(None, description="Muted/de-emphasized color")
    positive: Optional[str] = Field(None, description="Positive value color")
    negative: Optional[str] = Field(None, description="Negative value color")
    # Palette arrays for multi-series data
    series_palette: Optional[list[str]] = Field(None, description="Ordered palette for data series")


class Typography(BaseModel):
    """Typography specification for a style."""
    primary_font: str = Field(..., description="Primary font stack")
    title_font: str = Field(..., description="Title/headline font stack")
    caption_font: str = Field(..., description="Caption/annotation font stack")
    number_font: str = Field(..., description="Number/data font stack")
    title_size: str = Field(..., description="Title size range (e.g., '18-24px')")
    label_size: str = Field(..., description="Label size range")
    annotation_size: str = Field(..., description="Annotation size range")
    line_height: str = Field(..., description="Line height multiplier")
    title_weight: str = Field(..., description="Title font weight")


class StyleGuide(BaseModel):
    """Complete style specification for a dataviz school."""
    key: StyleSchool = Field(..., description="Style school identifier")
    name: str = Field(..., description="Human-readable name")
    philosophy: str = Field(..., description="Design philosophy and principles")
    color_palette: ColorPalette = Field(..., description="Color palette specification")
    typography: Typography = Field(..., description="Typography specification")
    layout_principles: list[str] = Field(..., description="Layout guidelines")
    annotation_style: str = Field(..., description="Annotation philosophy and approach")
    gemini_modifiers: str = Field(..., description="Instructions to append to Gemini prompts")
    best_for: list[str] = Field(..., description="Contexts where this style excels")
    avoid_for: list[str] = Field(..., description="Contexts to avoid this style")
    # Influences - proper attribution without implying we're copying IP
    influences: Optional[StyleInfluences] = Field(
        None,
        description="Tradition, exemplars, and key works that inform this style approach"
    )
    # Renderer-specific guidance for the polish system
    renderer_guidance: Optional[dict[str, str]] = Field(
        None,
        description="Per-renderer-type guidance for how this school should style "
        "accordion, chip_grid, prose, timeline, card_grid components"
    )


class StyleGuideSummary(BaseModel):
    """Summary of a style guide for list endpoints."""
    key: StyleSchool
    name: str
    philosophy_summary: str = Field(..., description="First 200 chars of philosophy")
    color_preview: dict[str, str] = Field(..., description="Primary, accent, background colors")
    best_for_summary: list[str] = Field(..., description="First 3 best_for items")


class StyleAffinity(BaseModel):
    """Affinity mapping between an entity and style schools."""
    entity_key: str = Field(..., description="Engine key, format key, or audience type")
    entity_type: str = Field(..., description="Type: 'engine', 'format', or 'audience'")
    preferred_styles: list[StyleSchool] = Field(
        ...,
        description="Ordered list of preferred styles (first is most preferred)"
    )
    rationale: Optional[str] = Field(None, description="Why these styles are preferred")


class AffinitySet(BaseModel):
    """Complete set of affinities for a category."""
    category: str = Field(..., description="Category: 'engine', 'format', or 'audience'")
    affinities: dict[str, list[StyleSchool]] = Field(
        ...,
        description="Mapping of entity_key to ordered style preferences"
    )
    default: list[StyleSchool] = Field(
        ...,
        description="Default styles when no specific mapping exists"
    )


class EngineStyleMapping(BaseModel):
    """Complete style mapping for an engine."""
    engine_key: str
    engine_name: str
    style_affinities: list[StyleSchool] = Field(..., description="Preferred styles for this engine")
    has_semantic_intent: bool = Field(False, description="Whether engine has semantic visual intent")
    recommended_visual_patterns: list[str] = Field(
        default_factory=list,
        description="Visual patterns from engine definition"
    )


# ---------------------------------------------------------------------------
# Style Recommendation Models
# ---------------------------------------------------------------------------

class StyleRecommendRequest(BaseModel):
    engine_keys: list[str] = Field(default_factory=list)
    renderer_types: list[str] = Field(default_factory=list)
    audience: Optional[str] = None
    limit: int = Field(default=3, ge=1, le=6)

    @model_validator(mode='after')
    def at_least_one_signal(self):
        if not self.engine_keys and not self.renderer_types and not self.audience:
            raise ValueError("At least one of engine_keys, renderer_types, or audience required")
        return self


class RecommendationReasoning(BaseModel):
    engine_matches: dict[str, int] = Field(
        default_factory=dict,
        description="engine_key -> position in affinity list (0=primary, 1=secondary, -1=not listed)"
    )
    format_matches: dict[str, int] = Field(
        default_factory=dict,
        description="format_key -> position (-1=not listed)"
    )
    audience_match: int = Field(
        -1,
        description="Position in audience affinity list (-1=not listed or no audience)"
    )
    total_signals: int = Field(0, description="Number of signals that contributed to scoring")
    matched_signals: int = Field(0, description="How many signals this school was listed in")


class StyleRecommendation(BaseModel):
    school: StyleSchool
    score: float = Field(..., description="Normalized 0.0-1.0")
    raw_score: float = Field(..., description="Unnormalized sum of position points")
    rank: int
    reasoning: RecommendationReasoning


class StyleRecommendContextSummary(BaseModel):
    engines_provided: int = 0
    engines_with_explicit_mapping: int = 0
    engines_using_default: int = 0
    renderer_types_provided: int = 0
    renderer_types_mapped: int = 0
    formats_with_explicit_mapping: int = 0
    formats_using_default: int = 0
    audience_provided: Optional[str] = None
    audience_used_default: bool = False
    effective_signals: int = 0


class StyleRecommendResponse(BaseModel):
    recommendations: list[StyleRecommendation]
    context_summary: StyleRecommendContextSummary
