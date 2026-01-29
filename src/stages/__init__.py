"""Stage prompt composition system.

This module provides generic stage prompt templates that are composed
with engine-specific context at runtime using Jinja2.

Architecture:
- templates/       - Generic Jinja2 templates for each stage
- frameworks/      - Shared methodological primers (Brandomian, Dennett, etc.)
- schemas.py       - Pydantic models for stage context
- registry.py      - StageRegistry for loading templates
- composer.py      - StageComposer for rendering templates with context
"""

from .schemas import (
    StageContext,
    ExtractionContext,
    CurationContext,
    ConcretizationContext,
    AudienceVocabulary,
    Framework,
)
from .registry import StageRegistry
from .composer import StageComposer

__all__ = [
    "StageContext",
    "ExtractionContext",
    "CurationContext",
    "ConcretizationContext",
    "AudienceVocabulary",
    "Framework",
    "StageRegistry",
    "StageComposer",
]
