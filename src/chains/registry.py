"""Chain registry - loads and serves chain definitions from JSON files."""

import json
import logging
from pathlib import Path
from typing import Optional

from src.chains.schemas import (
    BlendMode,
    ChainSummary,
    EngineChainSpec,
)

logger = logging.getLogger(__name__)


class ChainRegistry:
    """Registry of engine chain definitions loaded from JSON files.

    Chains are loaded from src/chains/definitions/*.json at startup.
    Each JSON file should contain one EngineChainSpec.
    """

    def __init__(self, definitions_dir: Optional[Path] = None):
        """Initialize registry with optional custom definitions directory."""
        if definitions_dir is None:
            definitions_dir = Path(__file__).parent / "definitions"
        self.definitions_dir = definitions_dir
        self._chains: dict[str, EngineChainSpec] = {}
        self._loaded = False

    def load(self) -> None:
        """Load all chain definitions from JSON files."""
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
                chain = EngineChainSpec.model_validate(data)
                self._chains[chain.chain_key] = chain
                logger.debug(f"Loaded chain: {chain.chain_key}")
            except Exception as e:
                logger.error(f"Failed to load chain from {json_file}: {e}")

        self._loaded = True
        logger.info(f"Loaded {len(self._chains)} chains")

    def get(self, chain_key: str) -> Optional[EngineChainSpec]:
        """Get chain definition by key."""
        self.load()
        return self._chains.get(chain_key)

    def get_validated(self, chain_key: str) -> EngineChainSpec:
        """Get chain definition by key, raising if not found."""
        chain = self.get(chain_key)
        if chain is None:
            available = list(self._chains.keys())
            raise ValueError(
                f"Chain not found: {chain_key}. Available: {available}"
            )
        return chain

    def list_all(self) -> list[EngineChainSpec]:
        """List all chain definitions."""
        self.load()
        return list(self._chains.values())

    def list_summaries(self) -> list[ChainSummary]:
        """List lightweight chain summaries."""
        self.load()
        return [
            ChainSummary(
                chain_key=c.chain_key,
                chain_name=c.chain_name,
                description=c.description,
                blend_mode=c.blend_mode,
                engine_count=len(c.engine_keys),
                category=c.category,
                has_context_parameters=c.context_parameter_schema is not None,
            )
            for c in self._chains.values()
        ]

    def list_keys(self) -> list[str]:
        """List all chain keys."""
        self.load()
        return list(self._chains.keys())

    def list_by_category(self, category: str) -> list[EngineChainSpec]:
        """List chains in a specific category."""
        self.load()
        return [c for c in self._chains.values() if c.category == category]

    def list_by_blend_mode(self, blend_mode: BlendMode) -> list[EngineChainSpec]:
        """List chains with a specific blend mode."""
        self.load()
        return [c for c in self._chains.values() if c.blend_mode == blend_mode]

    def count(self) -> int:
        """Get total number of chains."""
        self.load()
        return len(self._chains)

    def reload(self) -> None:
        """Force reload all definitions."""
        self._loaded = False
        self._chains.clear()
        self.load()


# Global registry instance
_registry: Optional[ChainRegistry] = None


def get_chain_registry() -> ChainRegistry:
    """Get the global chain registry instance."""
    global _registry
    if _registry is None:
        _registry = ChainRegistry()
        _registry.load()
    return _registry
