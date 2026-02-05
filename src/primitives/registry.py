"""
Primitives Registry - loads and serves analytical primitives.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from .schemas import AnalyticalPrimitive, PrimitiveSummary, EnginePrimitiveMapping

logger = logging.getLogger(__name__)

DEFINITIONS_DIR = Path(__file__).parent / "definitions"


class PrimitivesRegistry:
    """Registry for analytical primitives."""

    def __init__(self, definitions_dir: Optional[Path] = None):
        self.definitions_dir = definitions_dir or DEFINITIONS_DIR
        self._primitives: dict[str, AnalyticalPrimitive] = {}
        self._engine_to_primitives: dict[str, list[str]] = {}
        self._load()

    def _load(self):
        """Load primitives from JSON."""
        primitives_file = self.definitions_dir / "primitives.json"
        if not primitives_file.exists():
            logger.warning(f"Primitives file not found: {primitives_file}")
            return

        try:
            with open(primitives_file, "r") as f:
                data = json.load(f)

            for p_data in data.get("primitives", []):
                primitive = AnalyticalPrimitive(**p_data)
                self._primitives[primitive.key] = primitive

                # Build reverse index: engine -> primitives
                for engine_key in primitive.associated_engines:
                    if engine_key not in self._engine_to_primitives:
                        self._engine_to_primitives[engine_key] = []
                    self._engine_to_primitives[engine_key].append(primitive.key)

            logger.info(f"Loaded {len(self._primitives)} analytical primitives")
        except Exception as e:
            logger.error(f"Failed to load primitives: {e}")

    def reload(self):
        """Reload from disk."""
        self._primitives.clear()
        self._engine_to_primitives.clear()
        self._load()

    def list_primitives(self) -> list[PrimitiveSummary]:
        """List all primitives as summaries."""
        return [
            PrimitiveSummary(
                key=p.key,
                name=p.name,
                description=p.description,
                engine_count=len(p.associated_engines),
                visual_forms_preview=p.visual_forms[:3],
            )
            for p in self._primitives.values()
        ]

    def get_primitive(self, key: str) -> Optional[AnalyticalPrimitive]:
        """Get a specific primitive."""
        return self._primitives.get(key)

    def get_primitives_for_engine(self, engine_key: str) -> list[AnalyticalPrimitive]:
        """Get primitives associated with an engine."""
        primitive_keys = self._engine_to_primitives.get(engine_key, [])
        return [self._primitives[k] for k in primitive_keys if k in self._primitives]

    def get_guidance_for_engine(self, engine_key: str) -> Optional[str]:
        """Get combined Gemini guidance for an engine's primitives."""
        primitives = self.get_primitives_for_engine(engine_key)
        if not primitives:
            return None

        guidance_parts = []
        for p in primitives:
            guidance_parts.append(f"## {p.name}\n{p.gemini_guidance}")

        return "\n\n".join(guidance_parts)

    def get_all_engine_mappings(self) -> list[EnginePrimitiveMapping]:
        """Get primitive mappings for all known engines."""
        # Collect all engines mentioned in primitives
        all_engines = set()
        for p in self._primitives.values():
            all_engines.update(p.associated_engines)

        mappings = []
        for engine_key in sorted(all_engines):
            primitive_keys = self._engine_to_primitives.get(engine_key, [])
            mappings.append(EnginePrimitiveMapping(
                engine_key=engine_key,
                engine_name=engine_key.replace("_", " ").title(),  # Simple name conversion
                primitives=primitive_keys,
                has_primitive=len(primitive_keys) > 0,
            ))
        return mappings

    def get_stats(self) -> dict:
        """Get registry statistics."""
        total_engine_associations = sum(
            len(p.associated_engines) for p in self._primitives.values()
        )
        return {
            "primitives_loaded": len(self._primitives),
            "engines_with_primitives": len(self._engine_to_primitives),
            "total_associations": total_engine_associations,
        }


# Global instance
_registry: Optional[PrimitivesRegistry] = None


def get_primitives_registry() -> PrimitivesRegistry:
    """Get the global primitives registry."""
    global _registry
    if _registry is None:
        _registry = PrimitivesRegistry()
    return _registry
