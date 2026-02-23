"""Consumer registry — loads and serves consumer definitions from JSON files.

Follows the same pattern as RendererRegistry:
- JSON-per-file in definitions/ directory
- Lazy loading with _loaded guard
- In-memory dict keyed by consumer_key
- Global singleton via get_consumer_registry()
- CRUD with file persistence
- Query methods: supports_renderer, supports_sub_renderer
"""

import json
import logging
from pathlib import Path
from typing import Optional

from .schemas import ConsumerDefinition, ConsumerSummary

logger = logging.getLogger(__name__)


class ConsumerRegistry:
    """Registry of consumer definitions loaded from JSON files."""

    def __init__(self, definitions_dir: Optional[Path] = None):
        if definitions_dir is None:
            definitions_dir = Path(__file__).parent / "definitions"
        self.definitions_dir = definitions_dir
        self._consumers: dict[str, ConsumerDefinition] = {}
        self._file_map: dict[str, Path] = {}
        self._loaded = False

    def load(self) -> None:
        """Load all consumer definitions from JSON files."""
        if self._loaded:
            return

        if not self.definitions_dir.exists():
            logger.warning(
                f"Consumer definitions directory not found: {self.definitions_dir}"
            )
            self._loaded = True
            return

        for json_file in self.definitions_dir.glob("*.json"):
            try:
                with open(json_file, "r") as f:
                    data = json.load(f)
                consumer = ConsumerDefinition.model_validate(data)
                self._consumers[consumer.consumer_key] = consumer
                self._file_map[consumer.consumer_key] = json_file
                logger.debug(f"Loaded consumer: {consumer.consumer_key}")
            except Exception as e:
                logger.error(f"Failed to load consumer from {json_file}: {e}")

        self._loaded = True
        logger.info(f"Loaded {len(self._consumers)} consumer definitions")

    def get(self, consumer_key: str) -> Optional[ConsumerDefinition]:
        """Get a consumer definition by key."""
        self.load()
        return self._consumers.get(consumer_key)

    def list_all(self) -> list[ConsumerDefinition]:
        """List all consumer definitions."""
        self.load()
        return list(self._consumers.values())

    def list_summaries(self) -> list[ConsumerSummary]:
        """List consumer summaries."""
        self.load()
        return [
            ConsumerSummary(
                consumer_key=c.consumer_key,
                consumer_name=c.consumer_name,
                description=c.description,
                consumer_type=c.consumer_type,
                supported_renderers=c.supported_renderers,
                supported_sub_renderers=c.supported_sub_renderers,
                page_count=len(c.pages),
                status=c.status,
            )
            for c in sorted(
                self._consumers.values(), key=lambda c: c.consumer_key
            )
        ]

    def list_keys(self) -> list[str]:
        """List all consumer keys."""
        self.load()
        return list(self._consumers.keys())

    def count(self) -> int:
        """Get total number of consumers."""
        self.load()
        return len(self._consumers)

    def consumers_for_renderer(self, renderer_key: str) -> list[ConsumerDefinition]:
        """Get consumers that support a specific renderer."""
        self.load()
        return [
            c for c in self._consumers.values()
            if renderer_key in c.supported_renderers and c.status == "active"
        ]

    def renderers_for_consumer(self, consumer_key: str) -> list[str]:
        """Get renderer keys supported by a consumer."""
        self.load()
        consumer = self._consumers.get(consumer_key)
        if consumer is None:
            return []
        return consumer.supported_renderers

    def save(self, consumer_key: str, consumer: ConsumerDefinition) -> bool:
        """Save a consumer definition to JSON file."""
        self.load()

        json_file = self._file_map.get(
            consumer_key, self.definitions_dir / f"{consumer_key}.json"
        )

        try:
            self.definitions_dir.mkdir(parents=True, exist_ok=True)

            with open(json_file, "w") as f:
                json.dump(consumer.model_dump(), f, indent=2)
                f.write("\n")

            self._consumers[consumer_key] = consumer
            self._file_map[consumer_key] = json_file

            logger.info(f"Saved consumer: {consumer_key} -> {json_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save consumer {consumer_key}: {e}")
            return False

    def delete(self, consumer_key: str) -> bool:
        """Delete a consumer definition."""
        self.load()

        if consumer_key not in self._consumers:
            return False

        json_file = self._file_map.get(
            consumer_key, self.definitions_dir / f"{consumer_key}.json"
        )

        try:
            if json_file.exists():
                json_file.unlink()

            del self._consumers[consumer_key]
            self._file_map.pop(consumer_key, None)

            logger.info(f"Deleted consumer: {consumer_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete consumer {consumer_key}: {e}")
            return False

    def reload(self) -> None:
        """Force reload all definitions."""
        self._loaded = False
        self._consumers.clear()
        self._file_map.clear()
        self.load()


# Global registry instance
_registry: Optional[ConsumerRegistry] = None


def get_consumer_registry() -> ConsumerRegistry:
    """Get the global consumer registry instance."""
    global _registry
    if _registry is None:
        _registry = ConsumerRegistry()
        _registry.load()
    return _registry
