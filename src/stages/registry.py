"""Stage registry for loading templates and frameworks.

MIGRATION NOTES (2026-01-29):
- Templates are loaded from src/stages/templates/*.md.j2
- Frameworks are loaded from src/stages/frameworks/*.json
- Both are cached at startup for performance
"""

import json
from pathlib import Path
from typing import Optional

from .schemas import Framework


class StageRegistry:
    """Registry for stage templates and shared frameworks.

    Loads Jinja2 templates and framework definitions from disk,
    caches them for fast access.
    """

    def __init__(
        self,
        templates_dir: Optional[Path] = None,
        frameworks_dir: Optional[Path] = None,
    ):
        """Initialize the registry.

        Args:
            templates_dir: Path to templates directory (default: src/stages/templates)
            frameworks_dir: Path to frameworks directory (default: src/stages/frameworks)
        """
        base_dir = Path(__file__).parent

        self.templates_dir = templates_dir or base_dir / "templates"
        self.frameworks_dir = frameworks_dir or base_dir / "frameworks"

        # Caches
        self._templates: dict[str, str] = {}
        self._frameworks: dict[str, Framework] = {}

        # Load on init
        self._load_templates()
        self._load_frameworks()

    def _load_templates(self) -> None:
        """Load all Jinja2 templates from templates directory."""
        if not self.templates_dir.exists():
            print(f"Warning: Templates directory not found: {self.templates_dir}")
            return

        for template_file in self.templates_dir.glob("*.md.j2"):
            stage_name = template_file.stem.replace(".md", "")  # extraction.md.j2 -> extraction
            self._templates[stage_name] = template_file.read_text()
            print(f"Loaded template: {stage_name}")

        print(f"StageRegistry: Loaded {len(self._templates)} templates")

    def _load_frameworks(self) -> None:
        """Load all framework definitions from frameworks directory."""
        if not self.frameworks_dir.exists():
            print(f"Warning: Frameworks directory not found: {self.frameworks_dir}")
            return

        for framework_file in self.frameworks_dir.glob("*.json"):
            try:
                data = json.loads(framework_file.read_text())
                framework = Framework(**data)
                self._frameworks[framework.key] = framework
                print(f"Loaded framework: {framework.key} ({framework.name})")
            except Exception as e:
                print(f"Error loading framework {framework_file}: {e}")

        print(f"StageRegistry: Loaded {len(self._frameworks)} frameworks")

    def get_template(self, stage: str) -> Optional[str]:
        """Get a stage template by name.

        Args:
            stage: Stage name ("extraction", "curation", "concretization")

        Returns:
            Template content as string, or None if not found
        """
        return self._templates.get(stage)

    def get_framework(self, key: str) -> Optional[Framework]:
        """Get a framework by key.

        Args:
            key: Framework key (e.g., "brandomian", "dennett")

        Returns:
            Framework object, or None if not found
        """
        return self._frameworks.get(key)

    def list_templates(self) -> list[str]:
        """List all available template names."""
        return list(self._templates.keys())

    def list_frameworks(self) -> list[str]:
        """List all available framework keys."""
        return list(self._frameworks.keys())

    def get_framework_primer(self, key: str) -> Optional[str]:
        """Get just the primer text for a framework.

        Args:
            key: Framework key

        Returns:
            Primer text, or None if framework not found
        """
        framework = self.get_framework(key)
        return framework.primer if framework else None

    def reload(self) -> None:
        """Reload all templates and frameworks from disk."""
        self._templates.clear()
        self._frameworks.clear()
        self._load_templates()
        self._load_frameworks()


# Global singleton instance
_registry: Optional[StageRegistry] = None


def get_stage_registry() -> StageRegistry:
    """Get the global StageRegistry singleton."""
    global _registry
    if _registry is None:
        _registry = StageRegistry()
    return _registry
