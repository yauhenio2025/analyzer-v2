"""Transformation template registry — loads from JSON files.

Follows the ViewRegistry pattern:
- JSON-per-file in definitions/ directory
- Lazy loading with _loaded guard
- In-memory dict keyed by template_key
- Global singleton via get_transformation_registry()
- CRUD with file persistence
"""

import json
import logging
from pathlib import Path
from typing import Optional

from .schemas import TransformationTemplate, TransformationTemplateSummary

logger = logging.getLogger(__name__)


class TransformationRegistry:
    """Registry of transformation templates loaded from JSON files."""

    def __init__(self, definitions_dir: Optional[Path] = None):
        if definitions_dir is None:
            definitions_dir = Path(__file__).parent / "definitions"
        self.definitions_dir = definitions_dir
        self._templates: dict[str, TransformationTemplate] = {}
        self._file_map: dict[str, Path] = {}
        self._loaded = False

    def load(self) -> None:
        """Load all transformation templates from JSON files."""
        if self._loaded:
            return

        if not self.definitions_dir.exists():
            logger.warning(
                f"Transformations definitions directory not found: "
                f"{self.definitions_dir}"
            )
            self._loaded = True
            return

        for json_file in sorted(self.definitions_dir.glob("*.json")):
            try:
                with open(json_file, "r") as f:
                    data = json.load(f)
                template = TransformationTemplate.model_validate(data)
                self._templates[template.template_key] = template
                self._file_map[template.template_key] = json_file
                logger.debug(f"Loaded transformation template: {template.template_key}")
            except Exception as e:
                logger.error(
                    f"Failed to load transformation template from {json_file}: {e}"
                )

        self._loaded = True
        logger.info(f"Loaded {len(self._templates)} transformation templates")

    def get(self, template_key: str) -> Optional[TransformationTemplate]:
        """Get a template by key."""
        self.load()
        return self._templates.get(template_key)

    def list_all(self) -> list[TransformationTemplate]:
        """List all templates."""
        self.load()
        return list(self._templates.values())

    def list_summaries(
        self,
        transformation_type: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> list[TransformationTemplateSummary]:
        """List template summaries with optional filters."""
        self.load()
        templates = self._templates.values()

        if transformation_type:
            templates = [
                t for t in templates
                if t.transformation_type == transformation_type
            ]
        if tag:
            templates = [t for t in templates if tag in t.tags]

        return [
            TransformationTemplateSummary(
                template_key=t.template_key,
                template_name=t.template_name,
                description=t.description,
                transformation_type=t.transformation_type,
                applicable_renderer_types=t.applicable_renderer_types,
                tags=t.tags,
                status=t.status,
            )
            for t in sorted(templates, key=lambda t: t.template_key)
        ]

    def list_keys(self) -> list[str]:
        """List all template keys."""
        self.load()
        return sorted(self._templates.keys())

    def count(self) -> int:
        """Get total number of templates."""
        self.load()
        return len(self._templates)

    def for_engine(self, engine_key: str) -> list[TransformationTemplate]:
        """Get active templates applicable to a specific engine (excludes deprecated)."""
        self.load()
        return [
            t for t in self._templates.values()
            if engine_key in t.applicable_engines
            and t.status != "deprecated"
        ]

    def for_renderer(self, renderer_type: str) -> list[TransformationTemplate]:
        """Get templates applicable to a specific renderer type."""
        self.load()
        return [
            t for t in self._templates.values()
            if renderer_type in t.applicable_renderer_types
        ]

    def for_primitive(self, primitive_key: str) -> list[TransformationTemplate]:
        """Get templates that serve a given analytical primitive.

        Enables planner discovery: primitive -> renderer -> transformation.
        """
        self.load()
        return [
            t for t in self._templates.values()
            if primitive_key in t.primitive_affinities
            and t.status != "deprecated"
        ]

    def save(self, template_key: str, template: TransformationTemplate) -> bool:
        """Save a template to JSON file."""
        self.load()

        json_file = self._file_map.get(
            template_key, self.definitions_dir / f"{template_key}.json"
        )

        try:
            self.definitions_dir.mkdir(parents=True, exist_ok=True)

            with open(json_file, "w") as f:
                json.dump(template.model_dump(), f, indent=2)
                f.write("\n")

            self._templates[template_key] = template
            self._file_map[template_key] = json_file

            logger.info(f"Saved transformation template: {template_key} -> {json_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save transformation template {template_key}: {e}")
            return False

    def delete(self, template_key: str) -> bool:
        """Delete a template."""
        self.load()

        if template_key not in self._templates:
            return False

        json_file = self._file_map.get(
            template_key, self.definitions_dir / f"{template_key}.json"
        )

        try:
            if json_file.exists():
                json_file.unlink()

            del self._templates[template_key]
            self._file_map.pop(template_key, None)

            logger.info(f"Deleted transformation template: {template_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete transformation template {template_key}: {e}")
            return False

    def reload(self) -> None:
        """Force reload all definitions."""
        self._loaded = False
        self._templates.clear()
        self._file_map.clear()
        self.load()


# Global registry instance
_registry: Optional[TransformationRegistry] = None


def get_transformation_registry() -> TransformationRegistry:
    """Get the global transformation registry instance."""
    global _registry
    if _registry is None:
        _registry = TransformationRegistry()
        _registry.load()
    return _registry
