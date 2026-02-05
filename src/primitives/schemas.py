"""
Analytical Primitives - the trading zone between engines and visual styles.

These are the intermediate concepts that bridge analytical meaning to visual form.
They provide soft guidance to Gemini about what tends to work well together.
"""

from typing import Optional
from pydantic import BaseModel, Field


class AnalyticalPrimitive(BaseModel):
    """A primitive analytical concept that bridges engines and visuals."""

    key: str = Field(..., description="Unique identifier (e.g., 'cyclical_causation')")
    name: str = Field(..., description="Human-readable name")

    # What this primitive captures
    description: str = Field(
        ...,
        description="What this analytical pattern is about (1-2 sentences)"
    )

    # Visual guidance (soft, not prescriptive)
    visual_hint: str = Field(
        ...,
        description="Brief guidance on what visual approaches tend to work"
    )
    visual_forms: list[str] = Field(
        default_factory=list,
        description="Visual forms that often work well (suggestions, not requirements)"
    )

    # Style guidance (soft affinities)
    style_hint: str = Field(
        ...,
        description="Brief guidance on what aesthetic approaches tend to fit"
    )
    style_leanings: list[str] = Field(
        default_factory=list,
        description="Style schools that often work (suggestions, not requirements)"
    )

    # The guidance text that gets passed to Gemini
    gemini_guidance: str = Field(
        ...,
        description="Soft guidance text to include in Gemini prompts"
    )

    # Which engines use this primitive
    associated_engines: list[str] = Field(
        default_factory=list,
        description="Engine keys that produce this kind of analysis"
    )


class PrimitiveSummary(BaseModel):
    """Lightweight summary for list endpoints."""
    key: str
    name: str
    description: str
    engine_count: int
    visual_forms_preview: list[str] = Field(
        default_factory=list,
        description="First 3 visual forms"
    )


class EnginePrimitiveMapping(BaseModel):
    """Shows which primitive(s) an engine maps to."""
    engine_key: str
    engine_name: str
    primitives: list[str] = Field(
        default_factory=list,
        description="Primitive keys this engine is associated with"
    )
    has_primitive: bool = Field(
        default=False,
        description="Whether this engine has any primitive mapping"
    )
