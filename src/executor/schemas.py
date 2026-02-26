"""Executor-side schemas for job lifecycle, results, and progress.

These are distinct from the orchestrator schemas (which describe plans).
Executor schemas describe what happens during and after execution.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Job lifecycle states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PhaseStatus(str, Enum):
    """Phase execution states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class EngineCallResult(BaseModel):
    """Result of a single LLM call within an engine pass."""

    engine_key: str
    pass_number: int = Field(description="Inner pass number within the engine (1-indexed)")
    stance_key: Optional[str] = None
    content: str = Field(description="The prose output")
    model_used: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    duration_ms: int = 0
    retries: int = 0


class PhaseResult(BaseModel):
    """Result of executing a single workflow phase."""

    phase_number: float
    phase_name: str
    status: PhaseStatus = PhaseStatus.COMPLETED
    engine_results: dict[str, list[EngineCallResult]] = Field(
        default_factory=dict,
        description="Results keyed by engine_key, each with list of pass results",
    )
    work_results: Optional[dict[str, dict[str, list[EngineCallResult]]]] = Field(
        default=None,
        description="For per-work phases: work_key -> engine_key -> pass results",
    )
    final_output: str = Field(
        default="",
        description="The final prose output of this phase (last engine's last pass)",
    )
    duration_ms: int = 0
    total_tokens: int = 0
    error: Optional[str] = None


class JobProgress(BaseModel):
    """Progress snapshot for a running job."""

    current_phase: float = 0
    total_phases: int = 5
    phase_name: str = ""
    detail: str = ""
    completed_phases: list[str] = Field(default_factory=list)
    phase_statuses: dict[str, str] = Field(
        default_factory=dict,
        description="Phase number (as string) -> status",
    )


class ExecutorJob(BaseModel):
    """Full job state for the executor."""

    job_id: str = Field(default_factory=lambda: f"job-{uuid.uuid4().hex[:12]}")
    plan_id: str
    status: JobStatus = JobStatus.PENDING
    progress: JobProgress = Field(default_factory=JobProgress)
    phase_results: dict[str, PhaseResult] = Field(
        default_factory=dict,
        description="Phase number (as string) -> PhaseResult",
    )
    error: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    # Aggregate stats
    total_llm_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_estimate: float = 0.0


class StartJobRequest(BaseModel):
    """Request to start executing a plan."""

    plan_id: str
    document_ids: Optional[dict[str, str]] = Field(
        default=None,
        description="Map of work title -> document_id for uploaded texts",
    )


class JobStatusResponse(BaseModel):
    """Response for job status polling."""

    job_id: str
    plan_id: str
    status: JobStatus
    progress: JobProgress
    error: Optional[str] = None
    workflow_key: str = "intellectual_genealogy"
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    total_llm_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0


class PhaseOutputSummary(BaseModel):
    """Summary of a phase's outputs (for listing, not full prose)."""

    phase_number: float
    phase_name: str
    status: str
    engine_keys: list[str] = Field(default_factory=list)
    output_preview: str = Field(
        default="",
        description="First 500 chars of final output",
    )
    total_tokens: int = 0
    duration_ms: int = 0


class DocumentUpload(BaseModel):
    """Request to upload a document text."""

    title: str
    author: Optional[str] = None
    text: str
    role: str = Field(
        default="target",
        description="Document role: 'target' or 'prior_work'",
    )


class DocumentRecord(BaseModel):
    """Stored document metadata."""

    doc_id: str = Field(default_factory=lambda: f"doc-{uuid.uuid4().hex[:12]}")
    title: str
    author: Optional[str] = None
    role: str = "target"
    char_count: int = 0
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
