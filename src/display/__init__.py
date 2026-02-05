"""
Display module for Analyzer v2

Centralizes display formatting rules, hidden fields, visual format typology,
and Gemini instructions from the Visualizer codebase.
"""

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
from .registry import DisplayRegistry

__all__ = [
    "DisplayConfig",
    "DisplayInstructions",
    "HiddenFieldsConfig",
    "NumericDisplayRule",
    "VisualFormat",
    "VisualFormatCategory",
    "VisualFormatTypology",
    "DataTypeMapping",
    "DisplayRegistry",
]
