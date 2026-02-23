"""View pattern registry — loads and serves view patterns from JSON files.

Follows the same pattern as RendererRegistry:
- JSON-per-file in patterns/ directory
- Lazy loading with _loaded guard
- In-memory dict keyed by pattern_key
- Global singleton via get_pattern_registry()
- CRUD with file persistence
- Query methods: for_renderer, for_data_shape
"""

import json
import logging
from pathlib import Path
from typing import Optional

from .pattern_schemas import ViewPattern, ViewPatternSummary

logger = logging.getLogger(__name__)


class PatternRegistry:
    """Registry of view patterns loaded from JSON files."""

    def __init__(self, definitions_dir: Optional[Path] = None):
        if definitions_dir is None:
            definitions_dir = Path(__file__).parent / "patterns"
        self.definitions_dir = definitions_dir
        self._patterns: dict[str, ViewPattern] = {}
        self._file_map: dict[str, Path] = {}
        self._loaded = False

    def load(self) -> None:
        """Load all view patterns from JSON files."""
        if self._loaded:
            return

        if not self.definitions_dir.exists():
            logger.warning(
                f"View patterns directory not found: {self.definitions_dir}"
            )
            self._loaded = True
            return

        for json_file in self.definitions_dir.glob("*.json"):
            try:
                with open(json_file, "r") as f:
                    data = json.load(f)
                pattern = ViewPattern.model_validate(data)
                self._patterns[pattern.pattern_key] = pattern
                self._file_map[pattern.pattern_key] = json_file
                logger.debug(f"Loaded view pattern: {pattern.pattern_key}")
            except Exception as e:
                logger.error(f"Failed to load view pattern from {json_file}: {e}")

        self._loaded = True
        logger.info(f"Loaded {len(self._patterns)} view patterns")

    def get(self, pattern_key: str) -> Optional[ViewPattern]:
        """Get a view pattern by key."""
        self.load()
        return self._patterns.get(pattern_key)

    def list_all(self) -> list[ViewPattern]:
        """List all view patterns."""
        self.load()
        return list(self._patterns.values())

    def list_summaries(self) -> list[ViewPatternSummary]:
        """List view pattern summaries."""
        self.load()
        return [
            ViewPatternSummary(
                pattern_key=p.pattern_key,
                pattern_name=p.pattern_name,
                description=p.description,
                renderer_type=p.renderer_type,
                ideal_for=p.ideal_for,
                data_shape_in=p.data_shape_in,
                example_views=p.example_views,
                status=p.status,
            )
            for p in sorted(
                self._patterns.values(), key=lambda p: p.pattern_key
            )
        ]

    def list_keys(self) -> list[str]:
        """List all pattern keys."""
        self.load()
        return list(self._patterns.keys())

    def count(self) -> int:
        """Get total number of patterns."""
        self.load()
        return len(self._patterns)

    def for_renderer(self, renderer_type: str) -> list[ViewPattern]:
        """Get patterns that use a specific renderer type."""
        self.load()
        return [
            p for p in self._patterns.values()
            if p.renderer_type == renderer_type and p.status == "active"
        ]

    def for_data_shape(self, shape: str) -> list[ViewPattern]:
        """Get patterns that expect a given data shape."""
        self.load()
        return [
            p for p in self._patterns.values()
            if p.data_shape_in == shape and p.status == "active"
        ]

    def save(self, pattern_key: str, pattern: ViewPattern) -> bool:
        """Save a view pattern to JSON file."""
        self.load()

        json_file = self._file_map.get(
            pattern_key, self.definitions_dir / f"{pattern_key}.json"
        )

        try:
            self.definitions_dir.mkdir(parents=True, exist_ok=True)

            with open(json_file, "w") as f:
                json.dump(pattern.model_dump(), f, indent=2)
                f.write("\n")

            self._patterns[pattern_key] = pattern
            self._file_map[pattern_key] = json_file

            logger.info(f"Saved view pattern: {pattern_key} -> {json_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save view pattern {pattern_key}: {e}")
            return False

    def delete(self, pattern_key: str) -> bool:
        """Delete a view pattern."""
        self.load()

        if pattern_key not in self._patterns:
            return False

        json_file = self._file_map.get(
            pattern_key, self.definitions_dir / f"{pattern_key}.json"
        )

        try:
            if json_file.exists():
                json_file.unlink()

            del self._patterns[pattern_key]
            self._file_map.pop(pattern_key, None)

            logger.info(f"Deleted view pattern: {pattern_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete view pattern {pattern_key}: {e}")
            return False

    def reload(self) -> None:
        """Force reload all definitions."""
        self._loaded = False
        self._patterns.clear()
        self._file_map.clear()
        self.load()


# Global registry instance
_registry: Optional[PatternRegistry] = None


def get_pattern_registry() -> PatternRegistry:
    """Get the global view pattern registry instance."""
    global _registry
    if _registry is None:
        _registry = PatternRegistry()
        _registry.load()
    return _registry
