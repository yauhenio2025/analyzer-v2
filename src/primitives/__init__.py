"""
Primitives module - the trading zone between engines and visual styles.

Analytical primitives are intermediate concepts that bridge what engines produce
(analytical structures) with how they should be visualized (forms and styles).

They provide soft guidance to Gemini rather than strict rules.
"""

from .schemas import (
    AnalyticalPrimitive,
    PrimitiveSummary,
    EnginePrimitiveMapping,
)
from .registry import PrimitivesRegistry, get_primitives_registry

__all__ = [
    "AnalyticalPrimitive",
    "PrimitiveSummary",
    "EnginePrimitiveMapping",
    "PrimitivesRegistry",
    "get_primitives_registry",
]
