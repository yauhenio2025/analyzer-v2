"""Operationalization registry — loads and manages stance operationalizations per engine.

Follows the same singleton registry pattern as AudienceRegistry:
lazy-load from YAML files, CRUD operations, global instance.
"""

import logging
from pathlib import Path
from typing import Optional

import yaml

from .schemas import (
    CoverageEntry,
    CoverageMatrix,
    DepthSequence,
    EngineOperationalization,
    OperationalizationSummary,
    StanceOperationalization,
)

logger = logging.getLogger(__name__)


class OperationalizationRegistry:
    """Registry for engine operationalizations.

    Loads operationalization definitions from YAML files in definitions/.
    Each file is named {engine_key}.yaml and contains stance operationalizations
    and depth sequences for that engine.
    """

    def __init__(self, definitions_dir: Optional[Path] = None):
        self.definitions_dir = definitions_dir or (
            Path(__file__).parent / "definitions"
        )
        self._ops: dict[str, EngineOperationalization] = {}
        self._loaded = False

    def load(self) -> None:
        """Load all operationalization definitions from YAML files."""
        if self._loaded:
            return

        if not self.definitions_dir.exists():
            self._loaded = True
            return

        for yaml_file in sorted(self.definitions_dir.glob("*.yaml")):
            try:
                with open(yaml_file, "r") as f:
                    data = yaml.safe_load(f)
                if data is None:
                    continue
                op = EngineOperationalization.model_validate(data)
                self._ops[op.engine_key] = op
                logger.debug(f"Loaded operationalization: {op.engine_key}")
            except Exception as e:
                logger.error(f"Failed to load operationalization {yaml_file}: {e}")

        logger.info(
            f"Loaded {len(self._ops)} operationalizations from {self.definitions_dir}"
        )
        self._loaded = True

    def get(self, engine_key: str) -> Optional[EngineOperationalization]:
        """Get operationalization for an engine."""
        self.load()
        return self._ops.get(engine_key)

    def list_all(self) -> list[EngineOperationalization]:
        """List all operationalizations."""
        self.load()
        return list(self._ops.values())

    def list_summaries(self) -> list[OperationalizationSummary]:
        """List all operationalization summaries (lightweight)."""
        self.load()
        return [
            OperationalizationSummary(
                engine_key=op.engine_key,
                engine_name=op.engine_name,
                stance_count=len(op.stance_operationalizations),
                depth_count=len(op.depth_sequences),
                stance_keys=op.stance_keys,
                depth_keys=op.depth_keys,
            )
            for op in self._ops.values()
        ]

    def get_keys(self) -> list[str]:
        """Get all engine keys with operationalizations."""
        self.load()
        return sorted(self._ops.keys())

    def count(self) -> int:
        """Get total number of operationalizations."""
        self.load()
        return len(self._ops)

    def get_stance_for_engine(
        self, engine_key: str, stance_key: str
    ) -> Optional[StanceOperationalization]:
        """Get a specific stance operationalization for an engine."""
        op = self.get(engine_key)
        if op is None:
            return None
        return op.get_stance_op(stance_key)

    def get_depth_sequence(
        self, engine_key: str, depth_key: str
    ) -> Optional[DepthSequence]:
        """Get the depth sequence for an engine at a depth level."""
        op = self.get(engine_key)
        if op is None:
            return None
        return op.get_depth_sequence(depth_key)

    def coverage_matrix(self) -> CoverageMatrix:
        """Build the engine x stance coverage matrix.

        Returns all known stance keys as columns and each engine's
        coverage status as rows.
        """
        self.load()

        # Collect all unique stance keys across all engines
        all_stances: set[str] = set()
        for op in self._ops.values():
            all_stances.update(op.stance_keys)

        entries = []
        for op in sorted(self._ops.values(), key=lambda o: o.engine_key):
            entries.append(
                CoverageEntry(
                    engine_key=op.engine_key,
                    engine_name=op.engine_name,
                    has_operationalization=True,
                    stance_keys=op.stance_keys,
                )
            )

        return CoverageMatrix(
            all_stance_keys=sorted(all_stances),
            engines=entries,
        )

    def save(self, engine_key: str, definition: EngineOperationalization) -> bool:
        """Save an operationalization to YAML file.

        Creates or updates the file and in-memory cache.
        """
        self.load()

        yaml_file = self.definitions_dir / f"{engine_key}.yaml"

        try:
            self.definitions_dir.mkdir(parents=True, exist_ok=True)

            data = definition.model_dump(mode="json")

            with open(yaml_file, "w") as f:
                yaml.dump(
                    data,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                    width=120,
                )

            self._ops[engine_key] = definition
            logger.info(f"Saved operationalization: {engine_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to save operationalization {engine_key}: {e}")
            return False

    def delete(self, engine_key: str) -> bool:
        """Delete an operationalization."""
        self.load()

        if engine_key not in self._ops:
            logger.warning(f"Operationalization not found for deletion: {engine_key}")
            return False

        yaml_file = self.definitions_dir / f"{engine_key}.yaml"

        try:
            if yaml_file.exists():
                yaml_file.unlink()

            del self._ops[engine_key]
            logger.info(f"Deleted operationalization: {engine_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete operationalization {engine_key}: {e}")
            return False

    def reload(self) -> None:
        """Force reload all definitions from disk."""
        self._loaded = False
        self._ops.clear()
        self.load()


# Global registry instance
_registry: Optional[OperationalizationRegistry] = None


def get_operationalization_registry() -> OperationalizationRegistry:
    """Get the global operationalization registry instance."""
    global _registry
    if _registry is None:
        _registry = OperationalizationRegistry()
    return _registry
