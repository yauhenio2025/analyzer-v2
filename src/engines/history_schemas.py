"""Schemas for capability definition change history.

Tracks field-level changes to capability engine YAML definitions.
History is stored as JSON files alongside the definitions, committed
to git so it persists across deploys.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ChangeAction(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


class FieldChange(BaseModel):
    """A single field-level change within a capability definition."""

    section: str = Field(
        ...,
        description="Top-level section: top_level, intellectual_lineage, "
        "analytical_dimensions, capabilities, composability, depth_levels",
    )
    field: str = Field(
        ...,
        description="Specific field or item key that changed",
    )
    action: ChangeAction
    old_value: Optional[str] = Field(
        None, description="Previous value (stringified, truncated to 500 chars)"
    )
    new_value: Optional[str] = Field(
        None, description="New value (stringified, truncated to 500 chars)"
    )


class HistoryEntry(BaseModel):
    """A single history entry for a capability definition."""

    timestamp: str = Field(..., description="ISO 8601 timestamp (UTC)")
    version: int = Field(..., description="Monotonically increasing version number")
    definition_hash: str = Field(
        ..., description="SHA-256 of canonical JSON serialization"
    )
    changes: list[FieldChange] = Field(
        default_factory=list, description="Field-level changes from previous version"
    )
    summary: str = Field(default="", description="Human-readable change summary")
    is_baseline: bool = Field(
        default=False, description="True for the initial baseline snapshot"
    )


class CapabilityHistory(BaseModel):
    """Full change history for a capability definition."""

    engine_key: str
    entries: list[HistoryEntry] = Field(
        default_factory=list, description="History entries, newest first"
    )
