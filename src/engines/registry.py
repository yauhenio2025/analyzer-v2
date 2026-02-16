"""Engine registry - loads and serves engine definitions from JSON files."""

import json
import logging
from pathlib import Path
from typing import Optional

import yaml

from src.engines.schemas import (
    EngineCategory,
    EngineDefinition,
    EngineProfile,
    EngineSummary,
)
from src.engines.schemas_v2 import (
    CapabilityEngineDefinition,
    CapabilityEngineSummary,
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
        self.capability_definitions_dir = definitions_dir.parent / "capability_definitions"
        self._engines: dict[str, EngineDefinition] = {}
        self._capability_engines: dict[str, CapabilityEngineDefinition] = {}
        self._capability_loaded = False
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

    def save_profile(self, engine_key: str, profile: EngineProfile) -> bool:
        """Save a profile to an engine's JSON file.

        Updates both the in-memory engine and the JSON file on disk.

        Args:
            engine_key: Key of the engine to update
            profile: The profile to save

        Returns:
            True if save was successful, False otherwise
        """
        self.load()
        engine = self._engines.get(engine_key)
        if engine is None:
            return False

        # Find the JSON file for this engine
        json_file = self.definitions_dir / f"{engine_key}.json"
        if not json_file.exists():
            logger.error(f"JSON file not found for engine: {engine_key}")
            return False

        try:
            # Load current JSON
            with open(json_file, "r") as f:
                data = json.load(f)

            # Update with profile
            data["engine_profile"] = profile.model_dump()

            # Save back to file
            with open(json_file, "w") as f:
                json.dump(data, f, indent=2)

            # Update in-memory engine
            engine.engine_profile = profile
            self._engines[engine_key] = engine

            logger.info(f"Saved profile for engine: {engine_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to save profile for {engine_key}: {e}")
            return False

    def delete_profile(self, engine_key: str) -> bool:
        """Delete a profile from an engine's JSON file.

        Args:
            engine_key: Key of the engine to update

        Returns:
            True if delete was successful, False otherwise
        """
        self.load()
        engine = self._engines.get(engine_key)
        if engine is None:
            return False

        json_file = self.definitions_dir / f"{engine_key}.json"
        if not json_file.exists():
            return False

        try:
            # Load current JSON
            with open(json_file, "r") as f:
                data = json.load(f)

            # Remove profile if present
            if "engine_profile" in data:
                del data["engine_profile"]

            # Save back to file
            with open(json_file, "w") as f:
                json.dump(data, f, indent=2)

            # Update in-memory engine
            engine.engine_profile = None
            self._engines[engine_key] = engine

            logger.info(f"Deleted profile for engine: {engine_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete profile for {engine_key}: {e}")
            return False

    # ── Capability definitions (v2 format) ──────────────────────

    def _load_capability_definitions(self) -> None:
        """Load all capability engine definitions from YAML files."""
        if self._capability_loaded:
            return

        if not self.capability_definitions_dir.exists():
            logger.info(f"No capability definitions directory: {self.capability_definitions_dir}")
            self._capability_loaded = True
            return

        for yaml_file in self.capability_definitions_dir.glob("*.yaml"):
            try:
                with open(yaml_file, "r") as f:
                    data = yaml.safe_load(f)
                cap_engine = CapabilityEngineDefinition.model_validate(data)
                self._capability_engines[cap_engine.engine_key] = cap_engine
                logger.debug(f"Loaded capability definition: {cap_engine.engine_key}")
            except Exception as e:
                logger.error(f"Failed to load capability definition from {yaml_file}: {e}")

        self._capability_loaded = True
        logger.info(f"Loaded {len(self._capability_engines)} capability definitions")

    def get_capability_definition(self, engine_key: str) -> Optional[CapabilityEngineDefinition]:
        """Get capability engine definition by key."""
        self._load_capability_definitions()
        return self._capability_engines.get(engine_key)

    def list_capability_definitions(self) -> list[CapabilityEngineDefinition]:
        """List all capability engine definitions."""
        self._load_capability_definitions()
        return list(self._capability_engines.values())

    def list_capability_summaries(self) -> list[CapabilityEngineSummary]:
        """List lightweight capability engine summaries."""
        self._load_capability_definitions()
        return [
            CapabilityEngineSummary(
                engine_key=e.engine_key,
                engine_name=e.engine_name,
                category=e.category,
                kind=e.kind,
                problematique=e.problematique,
                capability_count=len(e.capabilities),
                dimension_count=len(e.analytical_dimensions),
                depth_levels=[d.key for d in e.depth_levels],
                synergy_engines=e.composability.synergy_engines,
                apps=e.apps,
            )
            for e in self._capability_engines.values()
        ]

    def list_capability_keys(self) -> list[str]:
        """List all capability definition keys."""
        self._load_capability_definitions()
        return list(self._capability_engines.keys())

    def reload(self) -> None:
        """Force reload all definitions."""
        self._loaded = False
        self._engines.clear()
        self._capability_loaded = False
        self._capability_engines.clear()
        self.load()
        self._load_capability_definitions()


# Global registry instance
_registry: Optional[EngineRegistry] = None


def get_engine_registry() -> EngineRegistry:
    """Get the global engine registry instance."""
    global _registry
    if _registry is None:
        _registry = EngineRegistry()
        _registry.load()
    return _registry
