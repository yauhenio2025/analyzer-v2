"""Function registry - loads and serves function definitions from JSON files."""

import json
import logging
from pathlib import Path
from typing import Optional

from src.functions.schemas import (
    FunctionCategory,
    FunctionDefinition,
    FunctionSummary,
    FunctionTier,
)

logger = logging.getLogger(__name__)


class FunctionRegistry:
    """Registry of function definitions loaded from JSON files.

    Functions are loaded from src/functions/definitions/*.json at startup.
    Each JSON file should contain one FunctionDefinition.
    """

    def __init__(self, definitions_dir: Optional[Path] = None):
        if definitions_dir is None:
            definitions_dir = Path(__file__).parent / "definitions"
        self.definitions_dir = definitions_dir
        self._functions: dict[str, FunctionDefinition] = {}
        self._loaded = False

    def load(self) -> None:
        """Load all function definitions from JSON files."""
        if self._loaded:
            return

        if not self.definitions_dir.exists():
            logger.warning(f"Definitions directory not found: {self.definitions_dir}")
            self._loaded = True
            return

        for json_file in self.definitions_dir.glob("*.json"):
            try:
                with open(json_file, "r") as f:
                    data = json.load(f)
                func = FunctionDefinition.model_validate(data)
                self._functions[func.function_key] = func
                logger.debug(f"Loaded function: {func.function_key}")
            except Exception as e:
                logger.error(f"Failed to load function from {json_file}: {e}")

        self._loaded = True
        logger.info(f"Loaded {len(self._functions)} functions")

    def get(self, function_key: str) -> Optional[FunctionDefinition]:
        """Get function definition by key."""
        self.load()
        return self._functions.get(function_key)

    def list_all(self) -> list[FunctionDefinition]:
        """List all function definitions."""
        self.load()
        return list(self._functions.values())

    def list_summaries(self) -> list[FunctionSummary]:
        """List lightweight function summaries."""
        self.load()
        return [
            FunctionSummary(
                function_key=f.function_key,
                function_name=f.function_name,
                description=f.description,
                category=f.category,
                tier=f.tier,
                invocation_pattern=f.invocation_pattern,
                source_projects=f.source_projects,
                implementation_count=len(f.implementations),
                track=f.track,
                tags=f.tags,
            )
            for f in self._functions.values()
        ]

    def list_by_category(self, category: FunctionCategory) -> list[FunctionDefinition]:
        """List functions in a specific category."""
        self.load()
        return [f for f in self._functions.values() if f.category == category]

    def list_by_tier(self, tier: FunctionTier) -> list[FunctionDefinition]:
        """List functions of a specific tier."""
        self.load()
        return [f for f in self._functions.values() if f.tier == tier]

    def list_by_project(self, project: str) -> list[FunctionDefinition]:
        """List functions associated with a specific project."""
        self.load()
        return [f for f in self._functions.values() if project in f.source_projects]

    def list_projects(self) -> list[str]:
        """List all unique project names across functions."""
        self.load()
        projects: set[str] = set()
        for f in self._functions.values():
            projects.update(f.source_projects)
        return sorted(projects)

    def search(self, query: str) -> list[FunctionDefinition]:
        """Search functions by name, description, or tags."""
        self.load()
        query_lower = query.lower()
        return [
            f for f in self._functions.values()
            if query_lower in f.function_name.lower()
            or query_lower in f.description.lower()
            or any(query_lower in tag.lower() for tag in f.tags)
        ]

    def count(self) -> int:
        """Get total number of functions."""
        self.load()
        return len(self._functions)

    def reload(self) -> None:
        """Force reload all definitions."""
        self._loaded = False
        self._functions.clear()
        self.load()


# Global registry instance
_registry: Optional[FunctionRegistry] = None


def get_function_registry() -> FunctionRegistry:
    """Get the global function registry instance."""
    global _registry
    if _registry is None:
        _registry = FunctionRegistry()
        _registry.load()
    return _registry
