"""Workflows module for multi-phase analysis pipelines.

Workflows differ from chains in that they:
- Support multi-phase analysis with intermediate state
- Can require external documents beyond the corpus
- Support caching between phases
- Are resumable

Terminology: workflow-level steps are "phases" (not "passes").
Engine-level stance iterations within depth levels remain "passes".
"""

from .schemas import WorkflowDefinition, WorkflowPhase, WorkflowPass, WorkflowCategory
from .registry import WorkflowRegistry

__all__ = [
    "WorkflowDefinition",
    "WorkflowPhase",
    "WorkflowPass",  # backwards compat alias
    "WorkflowCategory",
    "WorkflowRegistry",
]
