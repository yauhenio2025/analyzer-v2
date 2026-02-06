"""Workflow registry for loading and managing workflow definitions."""

import json
from pathlib import Path
from typing import Optional

from .schemas import WorkflowDefinition, WorkflowSummary, WorkflowCategory


class WorkflowRegistry:
    """Registry for workflow definitions.

    Loads workflow definitions from JSON files in the definitions directory.
    """

    def __init__(self, definitions_dir: Optional[Path] = None):
        self.definitions_dir = definitions_dir or (
            Path(__file__).parent / "definitions"
        )
        self._workflows: dict[str, WorkflowDefinition] = {}
        self._loaded = False

    def load(self) -> None:
        """Load all workflow definitions from JSON files."""
        if self._loaded:
            return

        if not self.definitions_dir.exists():
            self._loaded = True
            return

        for json_file in self.definitions_dir.glob("*.json"):
            try:
                with open(json_file, "r") as f:
                    data = json.load(f)
                workflow = WorkflowDefinition.model_validate(data)
                self._workflows[workflow.workflow_key] = workflow
            except Exception as e:
                print(f"Warning: Failed to load workflow {json_file}: {e}")

        self._loaded = True

    def get(self, workflow_key: str) -> Optional[WorkflowDefinition]:
        """Get a workflow definition by key."""
        self.load()
        return self._workflows.get(workflow_key)

    def list_all(self) -> list[WorkflowSummary]:
        """List all workflow summaries."""
        self.load()
        return [
            WorkflowSummary(
                workflow_key=w.workflow_key,
                workflow_name=w.workflow_name,
                description=w.description,
                category=w.category,
                pass_count=len(w.passes),
                version=w.version,
            )
            for w in self._workflows.values()
        ]

    def list_by_category(self, category: WorkflowCategory) -> list[WorkflowSummary]:
        """List workflows in a specific category."""
        self.load()
        return [
            WorkflowSummary(
                workflow_key=w.workflow_key,
                workflow_name=w.workflow_name,
                description=w.description,
                category=w.category,
                pass_count=len(w.passes),
                version=w.version,
            )
            for w in self._workflows.values()
            if w.category == category
        ]

    def get_workflow_keys(self) -> list[str]:
        """Get all workflow keys."""
        self.load()
        return list(self._workflows.keys())

    def count(self) -> int:
        """Get total number of workflows."""
        self.load()
        return len(self._workflows)


# Global registry instance
_registry: Optional[WorkflowRegistry] = None


def get_workflow_registry() -> WorkflowRegistry:
    """Get the global workflow registry instance."""
    global _registry
    if _registry is None:
        _registry = WorkflowRegistry()
    return _registry
