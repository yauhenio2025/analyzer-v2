"""
Pydantic schemas for visual style definitions.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class StyleSchool(str, Enum):
    """The 6 major dataviz style schools."""
    TUFTE = "tufte"
    NYT_COX = "nyt_cox"
    FT_BURN_MURDOCH = "ft_burn_murdoch"
    LUPI_DATA_HUMANISM = "lupi_data_humanism"
    STEFANER_TRUTH_BEAUTY = "stefaner_truth_beauty"
    ACTIVIST_AGITPROP = "activist_agitprop"


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
    # Metadata
    practitioners: Optional[list[str]] = Field(None, description="Key practitioners of this style")
    references: Optional[list[str]] = Field(None, description="Key books/articles about this style")


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
