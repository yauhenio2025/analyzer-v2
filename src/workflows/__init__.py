"""Workflows module for multi-pass analysis pipelines.

Workflows differ from chains in that they:
- Support multi-pass analysis with intermediate state
- Can require external documents beyond the corpus
- Support caching between passes
- Are resumable
"""

from .schemas import WorkflowDefinition, WorkflowPass, WorkflowCategory
from .registry import WorkflowRegistry

__all__ = [
    "WorkflowDefinition",
    "WorkflowPass",
    "WorkflowCategory",
    "WorkflowRegistry",
]
