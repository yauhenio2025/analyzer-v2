"""Paradigm definitions module."""

from src.paradigms.registry import ParadigmRegistry, get_paradigm_registry
from src.paradigms.schemas import (
    CritiquePattern,
    DynamicLayer,
    ExplanatoryLayer,
    FoundationalLayer,
    ParadigmCritiquePatternsResponse,
    ParadigmDefinition,
    ParadigmEnginesResponse,
    ParadigmPrimerResponse,
    ParadigmSummary,
    StructuralLayer,
    TraitDefinition,
)

__all__ = [
    "CritiquePattern",
    "DynamicLayer",
    "ExplanatoryLayer",
    "FoundationalLayer",
    "ParadigmCritiquePatternsResponse",
    "ParadigmDefinition",
    "ParadigmEnginesResponse",
    "ParadigmPrimerResponse",
    "ParadigmRegistry",
    "ParadigmSummary",
    "StructuralLayer",
    "TraitDefinition",
    "get_paradigm_registry",
]
