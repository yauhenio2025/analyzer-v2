"""Registry for analysis objectives — loads from JSON definitions."""

import json
import logging
from pathlib import Path
from typing import Optional

from .schemas import AnalysisObjective

logger = logging.getLogger(__name__)

DEFINITIONS_DIR = Path(__file__).parent / "definitions"

_registry: dict[str, AnalysisObjective] = {}
_loaded = False


def _load_definitions() -> None:
    """Load all objective definitions from JSON files."""
    global _registry, _loaded
    if _loaded:
        return
    
    DEFINITIONS_DIR.mkdir(parents=True, exist_ok=True)
    
    for json_path in sorted(DEFINITIONS_DIR.glob("*.json")):
        try:
            with open(json_path) as f:
                data = json.load(f)
            objective = AnalysisObjective.model_validate(data)
            _registry[objective.objective_key] = objective
            logger.info(f"Loaded objective: {objective.objective_key} ({objective.objective_name})")
        except Exception as e:
            logger.error(f"Failed to load objective from {json_path}: {e}")
    
    _loaded = True
    logger.info(f"Loaded {len(_registry)} analysis objectives")


def get_objective(key: str) -> Optional[AnalysisObjective]:
    """Get an objective by key."""
    _load_definitions()
    return _registry.get(key)


def list_objectives() -> list[AnalysisObjective]:
    """List all objectives."""
    _load_definitions()
    return list(_registry.values())


def get_objective_registry() -> dict[str, AnalysisObjective]:
    """Get the full registry dict."""
    _load_definitions()
    return _registry


def reload() -> None:
    """Force reload of definitions (for development)."""
    global _loaded
    _loaded = False
    _registry.clear()
    _load_definitions()
