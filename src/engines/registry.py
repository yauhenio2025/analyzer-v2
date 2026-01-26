"""Engine registry - loads and serves engine definitions from JSON files."""

import json
import logging
from pathlib import Path
from typing import Optional

from src.engines.schemas import (
    EngineCategory,
    EngineDefinition,
    EngineSummary,
)

logger = logging.getLogger(__name__)


class EngineRegistry:
    """Registry of engine definitions loaded from JSON files.

    Engines are loaded from src/engines/definitions/*.json at startup.
    Each JSON file should contain one EngineDefinition.
    """

    def __init__(self, definitions_dir: Optional[Path] = None):
        """Initialize registry with optional custom definitions directory."""
        if definitions_dir is None:
            definitions_dir = Path(__file__).parent / "definitions"
        self.definitions_dir = definitions_dir
        self._engines: dict[str, EngineDefinition] = {}
        self._loaded = False

    def load(self) -> None:
        """Load all engine definitions from JSON files."""
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
                engine = EngineDefinition.model_validate(data)
                self._engines[engine.engine_key] = engine
                logger.debug(f"Loaded engine: {engine.engine_key}")
            except Exception as e:
                logger.error(f"Failed to load engine from {json_file}: {e}")

        self._loaded = True
        logger.info(f"Loaded {len(self._engines)} engines")

    def get(self, engine_key: str) -> Optional[EngineDefinition]:
        """Get engine definition by key."""
        self.load()
        return self._engines.get(engine_key)

    def get_validated(self, engine_key: str) -> EngineDefinition:
        """Get engine definition by key, raising if not found."""
        engine = self.get(engine_key)
        if engine is None:
            available = list(self._engines.keys())[:10]
            raise ValueError(
                f"Engine not found: {engine_key}. "
                f"Available (first 10): {available}"
            )
        return engine

    def list_all(self) -> list[EngineDefinition]:
        """List all engine definitions."""
        self.load()
        return list(self._engines.values())

    def list_summaries(self) -> list[EngineSummary]:
        """List lightweight engine summaries."""
        self.load()
        return [
            EngineSummary(
                engine_key=e.engine_key,
                engine_name=e.engine_name,
                description=e.description,
                category=e.category,
                kind=e.kind,
                version=e.version,
                paradigm_keys=e.paradigm_keys,
            )
            for e in self._engines.values()
        ]

    def list_keys(self) -> list[str]:
        """List all engine keys."""
        self.load()
        return list(self._engines.keys())

    def list_by_category(self, category: EngineCategory) -> list[EngineDefinition]:
        """List engines in a specific category."""
        self.load()
        return [e for e in self._engines.values() if e.category == category]

    def list_by_paradigm(self, paradigm_key: str) -> list[EngineDefinition]:
        """List engines associated with a paradigm."""
        self.load()
        return [
            e for e in self._engines.values()
            if paradigm_key in e.paradigm_keys
        ]

    def search(self, query: str) -> list[EngineDefinition]:
        """Search engines by name or description."""
        self.load()
        query_lower = query.lower()
        return [
            e for e in self._engines.values()
            if query_lower in e.engine_name.lower()
            or query_lower in e.description.lower()
        ]

    def count(self) -> int:
        """Get total number of engines."""
        self.load()
        return len(self._engines)

    def reload(self) -> None:
        """Force reload all definitions."""
        self._loaded = False
        self._engines.clear()
        self.load()


# Global registry instance
_registry: Optional[EngineRegistry] = None


def get_engine_registry() -> EngineRegistry:
    """Get the global engine registry instance."""
    global _registry
    if _registry is None:
        _registry = EngineRegistry()
        _registry.load()
    return _registry
