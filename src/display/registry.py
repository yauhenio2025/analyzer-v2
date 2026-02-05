"""
Display Registry for Analyzer v2

Loads display configuration and visual format typology from JSON definitions.
"""

import json
from pathlib import Path
from typing import Optional

from .schemas import (
    DisplayConfig,
    DisplayInstructions,
    HiddenFieldsConfig,
    NumericDisplayRule,
    VisualFormat,
    VisualFormatCategory,
    VisualFormatTypology,
    DataTypeMapping,
)


class DisplayRegistry:
    """Registry for display configuration and visual formats."""

    def __init__(self, definitions_path: Optional[Path] = None):
        if definitions_path is None:
            definitions_path = Path(__file__).parent / "definitions"
        self.definitions_path = definitions_path
        self._display_config: Optional[DisplayConfig] = None
        self._visual_formats: Optional[VisualFormatTypology] = None
        self._load()

    def _load(self) -> None:
        """Load all definitions from JSON files."""
        self._load_display_config()
        self._load_visual_formats()

    def _load_display_config(self) -> None:
        """Load display configuration from JSON."""
        config_path = self.definitions_path / "display_config.json"
        if not config_path.exists():
            raise FileNotFoundError(f"Display config not found: {config_path}")

        with open(config_path, "r") as f:
            data = json.load(f)

        self._display_config = DisplayConfig(
            instructions=DisplayInstructions(**data["instructions"]),
            hidden_fields=HiddenFieldsConfig(**data["hidden_fields"]),
            numeric_rules=[NumericDisplayRule(**r) for r in data["numeric_rules"]],
            acronyms=data["acronyms"],
        )

    def _load_visual_formats(self) -> None:
        """Load visual format typology from JSON."""
        formats_path = self.definitions_path / "visual_formats.json"
        if not formats_path.exists():
            raise FileNotFoundError(f"Visual formats not found: {formats_path}")

        with open(formats_path, "r") as f:
            data = json.load(f)

        categories = []
        for cat_data in data["categories"]:
            formats = [VisualFormat(**f) for f in cat_data["formats"]]
            categories.append(
                VisualFormatCategory(
                    key=cat_data["key"],
                    name=cat_data["name"],
                    description=cat_data["description"],
                    formats=formats,
                )
            )

        mappings = [DataTypeMapping(**m) for m in data["data_mappings"]]

        self._visual_formats = VisualFormatTypology(
            categories=categories,
            data_mappings=mappings,
            quality_criteria=data["quality_criteria"],
        )

    def get_display_config(self) -> DisplayConfig:
        """Get the complete display configuration."""
        if self._display_config is None:
            self._load_display_config()
        return self._display_config

    def get_display_instructions(self) -> str:
        """Get the full display instructions text for Gemini."""
        return self.get_display_config().instructions.full_text

    def get_hidden_fields(self) -> list[str]:
        """Get list of fields that should be hidden from visualizations."""
        return self.get_display_config().hidden_fields.hidden_fields

    def get_hidden_suffixes(self) -> list[str]:
        """Get list of field suffixes that indicate hidden fields."""
        return self.get_display_config().hidden_fields.hidden_suffixes

    def should_hide_field(self, field_name: str) -> bool:
        """Check if a field should be hidden from visualization."""
        if not field_name:
            return False

        field_lower = field_name.lower()
        config = self.get_display_config()

        # Check exact matches
        if field_lower in [f.lower() for f in config.hidden_fields.hidden_fields]:
            return True

        # Check suffixes
        for suffix in config.hidden_fields.hidden_suffixes:
            if field_lower.endswith(suffix):
                return True

        return False

    def get_numeric_label(self, value: float) -> str:
        """Convert a 0-1 numeric value to a descriptive label."""
        if not 0 <= value <= 1:
            return str(value)

        for rule in self.get_display_config().numeric_rules:
            if rule.min_value <= value <= rule.max_value:
                return rule.label

        return "Unknown"

    def get_visual_formats(self) -> VisualFormatTypology:
        """Get the complete visual format typology."""
        if self._visual_formats is None:
            self._load_visual_formats()
        return self._visual_formats

    def get_format_categories(self) -> list[VisualFormatCategory]:
        """Get all visual format categories."""
        return self.get_visual_formats().categories

    def get_format_by_key(self, format_key: str) -> Optional[VisualFormat]:
        """Get a specific visual format by its key."""
        for category in self.get_format_categories():
            for fmt in category.formats:
                if fmt.key == format_key:
                    return fmt
        return None

    def get_formats_for_data_type(self, data_type: str) -> Optional[DataTypeMapping]:
        """Get format recommendations for a data type pattern."""
        for mapping in self.get_visual_formats().data_mappings:
            if mapping.data_type == data_type:
                return mapping
        return None

    def get_all_formats(self) -> list[VisualFormat]:
        """Get all visual formats as a flat list."""
        formats = []
        for category in self.get_format_categories():
            formats.extend(category.formats)
        return formats

    def get_quality_criteria(self) -> dict[str, list[str]]:
        """Get quality criteria for visualizations."""
        return self.get_visual_formats().quality_criteria
