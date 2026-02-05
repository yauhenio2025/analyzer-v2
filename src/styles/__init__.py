"""
Styles module for visual style definitions and affinity mappings.

This module provides:
- StyleGuide definitions for 6 dataviz schools (Tufte, NYT, FT, Lupi, Stefaner, Activist)
- Affinity mappings (engine→style, format→style, audience→style)
- Registry for loading and serving style definitions
"""

from .schemas import (
    StyleSchool,
    StyleGuide,
    StyleAffinity,
    ColorPalette,
    Typography,
)

from .registry import StyleRegistry

__all__ = [
    "StyleSchool",
    "StyleGuide",
    "StyleAffinity",
    "ColorPalette",
    "Typography",
    "StyleRegistry",
]
