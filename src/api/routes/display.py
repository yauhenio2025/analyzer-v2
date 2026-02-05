"""
API routes for display configuration and visual format typology.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...display import DisplayRegistry
from ...display.schemas import (
    DisplayConfig,
    VisualFormat,
    VisualFormatCategory,
    DataTypeMapping,
)


router = APIRouter(prefix="/display", tags=["display"])

# Initialize registry
display_registry = DisplayRegistry()


class DisplayInstructionsResponse(BaseModel):
    """Response containing display instructions for Gemini."""
    full_text: str
    branding_rules: str
    label_formatting: str
    numeric_display: str
    field_cleanup: str


class HiddenFieldsResponse(BaseModel):
    """Response containing hidden field configuration."""
    hidden_fields: list[str]
    hidden_suffixes: list[str]


class FieldCheckRequest(BaseModel):
    """Request to check if a field should be hidden."""
    field_name: str


class FieldCheckResponse(BaseModel):
    """Response indicating if a field should be hidden."""
    field_name: str
    should_hide: bool


class NumericLabelRequest(BaseModel):
    """Request to convert a numeric value to a label."""
    value: float


class NumericLabelResponse(BaseModel):
    """Response with descriptive label for numeric value."""
    value: float
    label: str


class FormatSummary(BaseModel):
    """Summary of a visual format."""
    key: str
    name: str
    data_structure: str
    use_when: str


class CategorySummary(BaseModel):
    """Summary of a format category."""
    key: str
    name: str
    description: str
    format_count: int


class DisplayStats(BaseModel):
    """Statistics about display configuration."""
    hidden_fields_count: int
    hidden_suffixes_count: int
    format_categories: int
    total_formats: int
    data_mappings: int


# -----------------------------------------------------------------------------
# Display Configuration Endpoints
# -----------------------------------------------------------------------------

@router.get("/config", response_model=DisplayConfig)
async def get_display_config():
    """Get the complete display configuration."""
    return display_registry.get_display_config()


@router.get("/instructions", response_model=DisplayInstructionsResponse)
async def get_display_instructions():
    """
    Get display instructions for Gemini.

    Returns the critical formatting rules that should be included in all
    visualization prompts to ensure proper display of labels, hiding of
    internal scores, and avoidance of branding issues.
    """
    config = display_registry.get_display_config()
    return DisplayInstructionsResponse(
        full_text=config.instructions.full_text,
        branding_rules=config.instructions.branding_rules,
        label_formatting=config.instructions.label_formatting,
        numeric_display=config.instructions.numeric_display,
        field_cleanup=config.instructions.field_cleanup,
    )


@router.get("/instructions/text")
async def get_display_instructions_text():
    """
    Get display instructions as plain text.

    Use this endpoint to get the raw instruction text to inject into
    Gemini prompts.
    """
    return {"text": display_registry.get_display_instructions()}


@router.get("/hidden-fields", response_model=HiddenFieldsResponse)
async def get_hidden_fields():
    """Get the list of fields that should be hidden from visualizations."""
    config = display_registry.get_display_config()
    return HiddenFieldsResponse(
        hidden_fields=config.hidden_fields.hidden_fields,
        hidden_suffixes=config.hidden_fields.hidden_suffixes,
    )


@router.post("/check-field", response_model=FieldCheckResponse)
async def check_field(request: FieldCheckRequest):
    """Check if a specific field should be hidden from visualization."""
    should_hide = display_registry.should_hide_field(request.field_name)
    return FieldCheckResponse(
        field_name=request.field_name,
        should_hide=should_hide,
    )


@router.post("/numeric-label", response_model=NumericLabelResponse)
async def get_numeric_label(request: NumericLabelRequest):
    """
    Convert a numeric value (0-1) to a descriptive label.

    Use this to convert confidence scores like 0.85 to descriptive terms
    like "Strong" instead of showing raw numbers on visualizations.
    """
    label = display_registry.get_numeric_label(request.value)
    return NumericLabelResponse(
        value=request.value,
        label=label,
    )


# -----------------------------------------------------------------------------
# Visual Format Endpoints
# -----------------------------------------------------------------------------

@router.get("/formats", response_model=list[CategorySummary])
async def list_format_categories():
    """List all visual format categories."""
    categories = display_registry.get_format_categories()
    return [
        CategorySummary(
            key=cat.key,
            name=cat.name,
            description=cat.description,
            format_count=len(cat.formats),
        )
        for cat in categories
    ]


@router.get("/formats/all", response_model=list[FormatSummary])
async def list_all_formats():
    """List all visual formats as a flat list."""
    formats = display_registry.get_all_formats()
    return [
        FormatSummary(
            key=fmt.key,
            name=fmt.name,
            data_structure=fmt.data_structure,
            use_when=fmt.use_when,
        )
        for fmt in formats
    ]


@router.get("/formats/category/{category_key}", response_model=VisualFormatCategory)
async def get_format_category(category_key: str):
    """Get a specific format category with all its formats."""
    for category in display_registry.get_format_categories():
        if category.key == category_key:
            return category
    raise HTTPException(status_code=404, detail=f"Category not found: {category_key}")


@router.get("/formats/{format_key}", response_model=VisualFormat)
async def get_format(format_key: str):
    """Get a specific visual format by key."""
    fmt = display_registry.get_format_by_key(format_key)
    if fmt is None:
        raise HTTPException(status_code=404, detail=f"Format not found: {format_key}")
    return fmt


@router.get("/formats/{format_key}/prompt")
async def get_format_prompt(format_key: str):
    """
    Get the Gemini prompt pattern for a specific format.

    Returns both the basic pattern and the full example prompt if available.
    """
    fmt = display_registry.get_format_by_key(format_key)
    if fmt is None:
        raise HTTPException(status_code=404, detail=f"Format not found: {format_key}")

    return {
        "format_key": format_key,
        "format_name": fmt.name,
        "prompt_pattern": fmt.gemini_prompt_pattern,
        "example_prompt": fmt.example_prompt,
        "has_example": fmt.example_prompt is not None,
    }


# -----------------------------------------------------------------------------
# Data Type Mapping Endpoints
# -----------------------------------------------------------------------------

@router.get("/mappings", response_model=list[DataTypeMapping])
async def list_data_mappings():
    """List all data type to visual format mappings."""
    return display_registry.get_visual_formats().data_mappings


@router.get("/mappings/for-data-type")
async def get_mapping_for_data_type(data_type: str):
    """
    Get format recommendations for a data type pattern.

    Query parameter:
    - data_type: The data structure pattern, e.g., "{nodes[], edges[]}"
    """
    mapping = display_registry.get_formats_for_data_type(data_type)
    if mapping is None:
        # Return empty recommendations, not 404
        return {
            "data_type": data_type,
            "found": False,
            "primary_format": None,
            "secondary_formats": [],
            "avoid": [],
        }

    return {
        "data_type": data_type,
        "found": True,
        "primary_format": mapping.primary_format,
        "secondary_formats": mapping.secondary_formats,
        "avoid": mapping.avoid,
    }


# -----------------------------------------------------------------------------
# Quality Criteria Endpoints
# -----------------------------------------------------------------------------

@router.get("/quality-criteria")
async def get_quality_criteria():
    """
    Get quality criteria for visualizations.

    Returns lists of must-have, should-have, and things to avoid.
    """
    return display_registry.get_quality_criteria()


# -----------------------------------------------------------------------------
# Stats Endpoint
# -----------------------------------------------------------------------------

@router.get("/stats", response_model=DisplayStats)
async def get_stats():
    """Get statistics about the display configuration."""
    config = display_registry.get_display_config()
    typology = display_registry.get_visual_formats()

    total_formats = sum(len(cat.formats) for cat in typology.categories)

    return DisplayStats(
        hidden_fields_count=len(config.hidden_fields.hidden_fields),
        hidden_suffixes_count=len(config.hidden_fields.hidden_suffixes),
        format_categories=len(typology.categories),
        total_formats=total_formats,
        data_mappings=len(typology.data_mappings),
    )
