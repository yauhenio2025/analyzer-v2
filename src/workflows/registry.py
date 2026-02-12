"""Workflow registry for loading and managing workflow definitions."""

import json
import logging
from pathlib import Path
from typing import Optional

from .schemas import WorkflowDefinition, WorkflowSummary, WorkflowCategory, WorkflowPass

logger = logging.getLogger(__name__)


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
                logger.error(f"Failed to load workflow {json_file}: {e}")

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

    def save(self, workflow_key: str, definition: WorkflowDefinition) -> bool:
        """Save a workflow definition to a JSON file.

        Creates a new file if the workflow doesn't exist, or updates existing.

        Args:
            workflow_key: Key for the workflow
            definition: The workflow definition to save

        Returns:
            True if save was successful, False otherwise
        """
        self.load()

        json_file = self.definitions_dir / f"{workflow_key}.json"

        try:
            # Ensure definitions directory exists
            self.definitions_dir.mkdir(parents=True, exist_ok=True)

            # Save to file
            with open(json_file, "w") as f:
                json.dump(definition.model_dump(), f, indent=2)

            # Update in-memory cache
            self._workflows[workflow_key] = definition

            logger.info(f"Saved workflow: {workflow_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to save workflow {workflow_key}: {e}")
            return False

    def update_pass(
        self, workflow_key: str, pass_number: float, pass_def: WorkflowPass
    ) -> bool:
        """Update a single pass in a workflow.

        Args:
            workflow_key: Key of the workflow
            pass_number: Pass number to update (matches pass_number field, e.g. 1, 1.5, 2)
            pass_def: The updated pass definition

        Returns:
            True if update was successful, False otherwise
        """
        self.load()
        workflow = self._workflows.get(workflow_key)
        if workflow is None:
            logger.error(f"Workflow not found: {workflow_key}")
            return False

        # Find pass by pass_number value, not by index
        for i, p in enumerate(workflow.passes):
            if p.pass_number == pass_number:
                workflow.passes[i] = pass_def
                return self.save(workflow_key, workflow)

        logger.error(f"Pass {pass_number} not found in workflow {workflow_key}")
        return False

    def delete(self, workflow_key: str) -> bool:
        """Delete a workflow definition.

        Removes both the file and the in-memory entry.

        Args:
            workflow_key: Key of the workflow to delete

        Returns:
            True if delete was successful, False otherwise
        """
        self.load()

        if workflow_key not in self._workflows:
            logger.warning(f"Workflow not found for deletion: {workflow_key}")
            return False

        json_file = self.definitions_dir / f"{workflow_key}.json"

        try:
            if json_file.exists():
                json_file.unlink()

            del self._workflows[workflow_key]

            logger.info(f"Deleted workflow: {workflow_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete workflow {workflow_key}: {e}")
            return False

    def reload(self) -> None:
        """Force reload all definitions."""
        self._loaded = False
        self._workflows.clear()
        self.load()


# Global registry instance
_registry: Optional[WorkflowRegistry] = None


def get_workflow_registry() -> WorkflowRegistry:
    """Get the global workflow registry instance."""
    global _registry
    if _registry is None:
        _registry = WorkflowRegistry()
    return _registry
