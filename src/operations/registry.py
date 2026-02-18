"""Registry for analytical stances.

Loads stance definitions from YAML and provides lookup methods.
"""

import logging
from pathlib import Path
from typing import Optional

import yaml

from .schemas import AnalyticalStance, StanceSummary

logger = logging.getLogger(__name__)

DEFINITIONS_DIR = Path(__file__).parent / "definitions"


class StanceRegistry:
    """Loads and serves analytical stance definitions."""

    def __init__(self) -> None:
        self._stances: dict[str, AnalyticalStance] = {}
        self._load_stances()

    def _load_stances(self) -> None:
        """Load stances from YAML file."""
        stances_file = DEFINITIONS_DIR / "stances.yaml"
        if not stances_file.exists():
            logger.warning(f"Stances file not found: {stances_file}")
            return

        with open(stances_file) as f:
            data = yaml.safe_load(f)

        for stance_data in data.get("stances", []):
            try:
                stance = AnalyticalStance(**stance_data)
                self._stances[stance.key] = stance
                logger.debug(f"Loaded stance: {stance.key}")
            except Exception as e:
                logger.error(f"Failed to load stance: {e}")

        logger.info(f"Loaded {len(self._stances)} analytical stances")

    def get(self, key: str) -> Optional[AnalyticalStance]:
        """Get a stance by key."""
        return self._stances.get(key)

    def list_all(self, stance_type: Optional[str] = None) -> list[AnalyticalStance]:
        """List all stances, optionally filtered by type."""
        stances = list(self._stances.values())
        if stance_type:
            stances = [s for s in stances if s.stance_type == stance_type]
        return stances

    def list_summaries(self, stance_type: Optional[str] = None) -> list[StanceSummary]:
        """List stance summaries, optionally filtered by type."""
        stances = self._stances.values()
        if stance_type:
            stances = [s for s in stances if s.stance_type == stance_type]
        return [
            StanceSummary(
                key=s.key,
                name=s.name,
                cognitive_mode=s.cognitive_mode,
                typical_position=s.typical_position,
                stance_type=s.stance_type,
            )
            for s in stances
        ]

    def get_by_position(self, position: str) -> list[AnalyticalStance]:
        """Get stances suitable for a given position (early/middle/late/any)."""
        return [
            s for s in self._stances.values()
            if s.typical_position == position or s.typical_position == "any"
        ]

    def get_stance_text(self, key: str) -> Optional[str]:
        """Get just the stance prose for prompt injection."""
        stance = self._stances.get(key)
        return stance.stance if stance else None

    @property
    def count(self) -> int:
        return len(self._stances)

    def reload(self) -> None:
        """Reload stances from disk."""
        self._stances.clear()
        self._load_stances()
