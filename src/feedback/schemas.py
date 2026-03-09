"""Schemas for Tier 3a feedback capture."""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class FeedbackEventType(str, Enum):
    """Supported feedback event types."""

    VIEW_OPENED = "view_opened"
    VIEW_CLOSED = "view_closed"
    TAB_SELECTED = "tab_selected"
    ACCORDION_EXPANDED = "accordion_expanded"
    ACCORDION_COLLAPSED = "accordion_collapsed"
    POLISH_REQUESTED = "polish_requested"
    POLISH_SECTION_REQUESTED = "polish_section_requested"
    SCROLL_DEPTH = "scroll_depth"
    VARIANT_SELECTED = "variant_selected"


SECTION_REQUIRED_TYPES = {
    FeedbackEventType.ACCORDION_EXPANDED,
    FeedbackEventType.ACCORDION_COLLAPSED,
    FeedbackEventType.POLISH_SECTION_REQUESTED,
}

VIEW_REQUIRED_TYPES = {
    FeedbackEventType.VIEW_OPENED,
    FeedbackEventType.VIEW_CLOSED,
    FeedbackEventType.TAB_SELECTED,
    FeedbackEventType.ACCORDION_EXPANDED,
    FeedbackEventType.ACCORDION_COLLAPSED,
    FeedbackEventType.POLISH_REQUESTED,
    FeedbackEventType.POLISH_SECTION_REQUESTED,
    FeedbackEventType.SCROLL_DEPTH,
    FeedbackEventType.VARIANT_SELECTED,
}


class FeedbackEventInput(BaseModel):
    """Single feedback event input."""

    event_id: str = Field(..., min_length=1, max_length=64)
    event_type: FeedbackEventType
    job_id: str = Field(..., min_length=1)
    view_key: Optional[str] = None
    section_key: Optional[str] = None
    project_id: Optional[str] = None
    renderer_type: Optional[str] = None
    style_school: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)
    client_timestamp: Optional[str] = None

    @model_validator(mode="after")
    def validate_context_requirements(self):
        if self.event_type in VIEW_REQUIRED_TYPES and not self.view_key:
            raise ValueError(f"view_key required for {self.event_type}")
        if self.event_type in SECTION_REQUIRED_TYPES and not self.section_key:
            raise ValueError(f"section_key required for {self.event_type}")
        return self


class FeedbackIngestRequest(BaseModel):
    """Batch ingest request."""

    events: list[FeedbackEventInput] = Field(..., min_length=1, max_length=50)


class FeedbackIngestResponse(BaseModel):
    """Batch ingest response."""

    accepted: int = 0
    duplicates: int = 0


class FeedbackEventRecord(BaseModel):
    """Persisted feedback event."""

    id: int
    event_id: str
    event_type: str
    job_id: str
    project_id: Optional[str] = None
    view_key: Optional[str] = None
    section_key: Optional[str] = None
    renderer_type: Optional[str] = None
    style_school: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)
    client_timestamp: Optional[str] = None
    created_at: Optional[str] = None


class FeedbackListResponse(BaseModel):
    """Paginated feedback list response."""

    events: list[FeedbackEventRecord]
    count: int
    total: int
    limit: int
    offset: int


class FeedbackSummaryResponse(BaseModel):
    """Aggregate feedback summary response."""

    job_id: Optional[str] = None
    project_id: Optional[str] = None
    from_ts: Optional[str] = None
    to_ts: Optional[str] = None
    groups: list[dict[str, Any]]
    total_events: int
