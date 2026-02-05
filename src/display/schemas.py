"""
Display Schemas for Analyzer v2

Centralizes display formatting rules, hidden fields, and Gemini instructions.
"""

from typing import Optional
from pydantic import BaseModel, Field


class DisplayInstructions(BaseModel):
    """Critical instructions for Gemini about proper data display."""

    branding_rules: str = Field(
        description="Rules about branding and attribution - what's forbidden"
    )
    label_formatting: str = Field(
        description="Rules about formatting labels (snake_case → Title Case)"
    )
    numeric_display: str = Field(
        description="Rules about displaying numeric scores (NEVER show raw decimals)"
    )
    field_cleanup: str = Field(
        description="Rules about cleaning up field names for display"
    )
    full_text: str = Field(
        description="Complete display instructions text to pass to Gemini"
    )


class HiddenFieldsConfig(BaseModel):
    """Configuration for fields that should be hidden from visualizations."""

    hidden_fields: list[str] = Field(
        description="List of field names that should be hidden"
    )
    hidden_suffixes: list[str] = Field(
        description="Field name suffixes that indicate hidden fields"
    )


class NumericDisplayRule(BaseModel):
    """Rule for converting numeric scores to descriptive terms."""

    min_value: float
    max_value: float
    label: str


class DisplayConfig(BaseModel):
    """Complete display configuration."""

    instructions: DisplayInstructions
    hidden_fields: HiddenFieldsConfig
    numeric_rules: list[NumericDisplayRule] = Field(
        description="Rules for converting 0-1 scores to descriptive terms"
    )
    acronyms: list[str] = Field(
        description="Acronyms that should stay uppercase in Title Case conversion"
    )


class VisualFormatCategory(BaseModel):
    """A category of visual formats."""

    key: str
    name: str
    description: str
    formats: list["VisualFormat"]


class VisualFormat(BaseModel):
    """A specific visual format with prompting patterns."""

    key: str
    name: str
    data_structure: str = Field(
        description="Expected data structure pattern, e.g., '{nodes[], edges[]}'"
    )
    use_when: str = Field(
        description="When to use this format"
    )
    gemini_prompt_pattern: str = Field(
        description="Template prompt pattern for Gemini"
    )
    example_prompt: Optional[str] = Field(
        default=None,
        description="Full example prompt for this format"
    )


class DataTypeMapping(BaseModel):
    """Mapping from data type to recommended visual formats."""

    data_type: str = Field(
        description="Data structure pattern"
    )
    primary_format: str = Field(
        description="Best format for this data type"
    )
    secondary_formats: list[str] = Field(
        description="Alternative formats that work"
    )
    avoid: list[str] = Field(
        description="Formats to avoid for this data type"
    )


class VisualFormatTypology(BaseModel):
    """Complete visual format typology."""

    categories: list[VisualFormatCategory]
    data_mappings: list[DataTypeMapping]
    quality_criteria: dict[str, list[str]] = Field(
        description="Quality criteria: must_have, should_have, avoid"
    )
