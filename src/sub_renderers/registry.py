"""Sub-renderer registry — loads and serves sub-renderer definitions from JSON files.

Follows the same pattern as RendererRegistry:
- JSON-per-file in definitions/ directory
- Lazy loading with _loaded guard
- In-memory dict keyed by sub_renderer_key
- Global singleton via get_sub_renderer_registry()
- CRUD with file persistence
- Query methods: for_parent, for_data_shape
"""

import json
import logging
from pathlib import Path
from typing import Optional

from .schemas import SubRendererDefinition, SubRendererSummary

logger = logging.getLogger(__name__)


class SubRendererRegistry:
    """Registry of sub-renderer definitions loaded from JSON files."""

    def __init__(self, definitions_dir: Optional[Path] = None):
        if definitions_dir is None:
            definitions_dir = Path(__file__).parent / "definitions"
        self.definitions_dir = definitions_dir
        self._sub_renderers: dict[str, SubRendererDefinition] = {}
        self._file_map: dict[str, Path] = {}
        self._loaded = False

    def load(self) -> None:
        """Load all sub-renderer definitions from JSON files."""
        if self._loaded:
            return

        if not self.definitions_dir.exists():
            logger.warning(
                f"Sub-renderer definitions directory not found: {self.definitions_dir}"
            )
            self._loaded = True
            return

        for json_file in self.definitions_dir.glob("*.json"):
            try:
                with open(json_file, "r") as f:
                    data = json.load(f)
                sub_renderer = SubRendererDefinition.model_validate(data)
                self._sub_renderers[sub_renderer.sub_renderer_key] = sub_renderer
                self._file_map[sub_renderer.sub_renderer_key] = json_file
                logger.debug(f"Loaded sub-renderer: {sub_renderer.sub_renderer_key}")
            except Exception as e:
                logger.error(f"Failed to load sub-renderer from {json_file}: {e}")

        self._loaded = True
        logger.info(f"Loaded {len(self._sub_renderers)} sub-renderer definitions")

    def get(self, sub_renderer_key: str) -> Optional[SubRendererDefinition]:
        """Get a sub-renderer definition by key."""
        self.load()
        return self._sub_renderers.get(sub_renderer_key)

    def list_all(self) -> list[SubRendererDefinition]:
        """List all sub-renderer definitions."""
        self.load()
        return list(self._sub_renderers.values())

    def list_summaries(self) -> list[SubRendererSummary]:
        """List sub-renderer summaries."""
        self.load()
        return [
            SubRendererSummary(
                sub_renderer_key=r.sub_renderer_key,
                sub_renderer_name=r.sub_renderer_name,
                description=r.description,
                category=r.category,
                ideal_data_shapes=r.ideal_data_shapes,
                stance_affinities=r.stance_affinities,
                parent_renderer_types=r.parent_renderer_types,
                status=r.status,
            )
            for r in sorted(
                self._sub_renderers.values(), key=lambda r: r.sub_renderer_key
            )
        ]

    def list_keys(self) -> list[str]:
        """List all sub-renderer keys."""
        self.load()
        return list(self._sub_renderers.keys())

    def count(self) -> int:
        """Get total number of sub-renderers."""
        self.load()
        return len(self._sub_renderers)

    def for_parent(self, renderer_type: str) -> list[SubRendererDefinition]:
        """Get sub-renderers compatible with a parent renderer type."""
        self.load()
        return [
            r
            for r in self._sub_renderers.values()
            if renderer_type in r.parent_renderer_types and r.status == "active"
        ]

    def for_data_shape(self, shape: str) -> list[SubRendererDefinition]:
        """Get sub-renderers that handle a given data shape."""
        self.load()
        return [
            r
            for r in self._sub_renderers.values()
            if shape in r.ideal_data_shapes and r.status == "active"
        ]

    def save(self, sub_renderer_key: str, sub_renderer: SubRendererDefinition) -> bool:
        """Save a sub-renderer definition to JSON file."""
        self.load()

        json_file = self._file_map.get(
            sub_renderer_key, self.definitions_dir / f"{sub_renderer_key}.json"
        )

        try:
            self.definitions_dir.mkdir(parents=True, exist_ok=True)

            with open(json_file, "w") as f:
                json.dump(sub_renderer.model_dump(), f, indent=2)
                f.write("\n")

            self._sub_renderers[sub_renderer_key] = sub_renderer
            self._file_map[sub_renderer_key] = json_file

            logger.info(f"Saved sub-renderer: {sub_renderer_key} -> {json_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save sub-renderer {sub_renderer_key}: {e}")
            return False

    def delete(self, sub_renderer_key: str) -> bool:
        """Delete a sub-renderer definition."""
        self.load()

        if sub_renderer_key not in self._sub_renderers:
            return False

        json_file = self._file_map.get(
            sub_renderer_key, self.definitions_dir / f"{sub_renderer_key}.json"
        )

        try:
            if json_file.exists():
                json_file.unlink()

            del self._sub_renderers[sub_renderer_key]
            self._file_map.pop(sub_renderer_key, None)

            logger.info(f"Deleted sub-renderer: {sub_renderer_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete sub-renderer {sub_renderer_key}: {e}")
            return False

    def reload(self) -> None:
        """Force reload all definitions."""
        self._loaded = False
        self._sub_renderers.clear()
        self._file_map.clear()
        self.load()


# Global registry instance
_registry: Optional[SubRendererRegistry] = None


def get_sub_renderer_registry() -> SubRendererRegistry:
    """Get the global sub-renderer registry instance."""
    global _registry
    if _registry is None:
        _registry = SubRendererRegistry()
        _registry.load()
    return _registry
