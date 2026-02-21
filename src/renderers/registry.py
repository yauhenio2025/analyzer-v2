"""Renderer registry — loads and serves renderer definitions from JSON files.

Follows the same pattern as ViewRegistry:
- JSON-per-file in definitions/ directory
- Lazy loading with _loaded guard
- In-memory dict keyed by renderer_key
- Global singleton via get_renderer_registry()
- CRUD with file persistence
- Query methods: for_stance, for_data_shape, for_app
"""

import json
import logging
from pathlib import Path
from typing import Optional

from .schemas import RendererDefinition, RendererSummary

logger = logging.getLogger(__name__)


class RendererRegistry:
    """Registry of renderer definitions loaded from JSON files."""

    def __init__(self, definitions_dir: Optional[Path] = None):
        if definitions_dir is None:
            definitions_dir = Path(__file__).parent / "definitions"
        self.definitions_dir = definitions_dir
        self._renderers: dict[str, RendererDefinition] = {}
        self._file_map: dict[str, Path] = {}
        self._loaded = False

    def load(self) -> None:
        """Load all renderer definitions from JSON files."""
        if self._loaded:
            return

        if not self.definitions_dir.exists():
            logger.warning(
                f"Renderer definitions directory not found: {self.definitions_dir}"
            )
            self._loaded = True
            return

        for json_file in self.definitions_dir.glob("*.json"):
            try:
                with open(json_file, "r") as f:
                    data = json.load(f)
                renderer = RendererDefinition.model_validate(data)
                self._renderers[renderer.renderer_key] = renderer
                self._file_map[renderer.renderer_key] = json_file
                logger.debug(f"Loaded renderer: {renderer.renderer_key}")
            except Exception as e:
                logger.error(f"Failed to load renderer from {json_file}: {e}")

        self._loaded = True
        logger.info(f"Loaded {len(self._renderers)} renderer definitions")

    def get(self, renderer_key: str) -> Optional[RendererDefinition]:
        """Get a renderer definition by key."""
        self.load()
        return self._renderers.get(renderer_key)

    def list_all(self) -> list[RendererDefinition]:
        """List all renderer definitions."""
        self.load()
        return list(self._renderers.values())

    def list_summaries(self) -> list[RendererSummary]:
        """List renderer summaries."""
        self.load()
        return [
            RendererSummary(
                renderer_key=r.renderer_key,
                renderer_name=r.renderer_name,
                description=r.description,
                category=r.category,
                stance_affinities=r.stance_affinities,
                supported_apps=r.supported_apps,
                status=r.status,
            )
            for r in sorted(
                self._renderers.values(), key=lambda r: r.renderer_key
            )
        ]

    def list_keys(self) -> list[str]:
        """List all renderer keys."""
        self.load()
        return list(self._renderers.keys())

    def count(self) -> int:
        """Get total number of renderers."""
        self.load()
        return len(self._renderers)

    def for_stance(self, stance_key: str) -> list[RendererDefinition]:
        """Get renderers sorted by affinity to a presentation stance."""
        self.load()
        matching = [
            r
            for r in self._renderers.values()
            if stance_key in r.stance_affinities and r.status == "active"
        ]
        return sorted(
            matching,
            key=lambda r: r.stance_affinities.get(stance_key, 0),
            reverse=True,
        )

    def for_data_shape(self, shape: str) -> list[RendererDefinition]:
        """Get renderers that handle a given data shape."""
        self.load()
        return [
            r
            for r in self._renderers.values()
            if shape in r.ideal_data_shapes and r.status == "active"
        ]

    def for_app(self, app: str) -> list[RendererDefinition]:
        """Get renderers supported by a consumer app."""
        self.load()
        return [
            r
            for r in self._renderers.values()
            if app in r.supported_apps and r.status == "active"
        ]

    def save(self, renderer_key: str, renderer: RendererDefinition) -> bool:
        """Save a renderer definition to JSON file."""
        self.load()

        json_file = self._file_map.get(
            renderer_key, self.definitions_dir / f"{renderer_key}.json"
        )

        try:
            self.definitions_dir.mkdir(parents=True, exist_ok=True)

            with open(json_file, "w") as f:
                json.dump(renderer.model_dump(), f, indent=2)
                f.write("\n")

            self._renderers[renderer_key] = renderer
            self._file_map[renderer_key] = json_file

            logger.info(f"Saved renderer: {renderer_key} -> {json_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save renderer {renderer_key}: {e}")
            return False

    def delete(self, renderer_key: str) -> bool:
        """Delete a renderer definition."""
        self.load()

        if renderer_key not in self._renderers:
            return False

        json_file = self._file_map.get(
            renderer_key, self.definitions_dir / f"{renderer_key}.json"
        )

        try:
            if json_file.exists():
                json_file.unlink()

            del self._renderers[renderer_key]
            self._file_map.pop(renderer_key, None)

            logger.info(f"Deleted renderer: {renderer_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete renderer {renderer_key}: {e}")
            return False

    def reload(self) -> None:
        """Force reload all definitions."""
        self._loaded = False
        self._renderers.clear()
        self._file_map.clear()
        self.load()


# Global registry instance
_registry: Optional[RendererRegistry] = None


def get_renderer_registry() -> RendererRegistry:
    """Get the global renderer registry instance."""
    global _registry
    if _registry is None:
        _registry = RendererRegistry()
        _registry.load()
    return _registry
