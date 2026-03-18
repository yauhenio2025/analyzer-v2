"""Schemas for the analysis-product result contract."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from src.presenter.schemas import PagePresentation


class ArtifactSlotSummary(BaseModel):
    slot: str
    state: str
    artifact_ref: Optional[str] = None
    source_output_id: Optional[str] = None


class ArtifactFamilySummary(BaseModel):
    artifact_family: str
    state: str
    format: str
    total_slots: int = 0
    ready_slots: int = 0
    pending_slots: int = 0
    stale_slots: int = 0
    unavailable_slots: int = 0
    slots: list[ArtifactSlotSummary] = Field(default_factory=list)


class AnalysisResultLinks(BaseModel):
    page_url: str = ""
    presentation_url: str = ""
    manifest_url: str = ""
    trace_url: str = ""
    refresh_presentation_url: str = ""


class AnalysisResultManifest(BaseModel):
    job_id: str
    plan_id: str
    workflow_key: str
    consumer_key: str
    result_id: str = ""
    result_state: str = ""
    corpus_ref: Optional[str] = None
    status: str = ""
    presentation_contract_version: int = 1
    presentation_hash: str = ""
    presentation_content_hash: str = ""
    prepared_at: str = ""
    artifacts_ready: bool = False
    presentation_status: str = ""
    preparation_detail: str = ""
    presentation_active: bool = False
    restore_available: bool = False
    restore_reason: str = "not_prepared"
    staleness_reasons: list[str] = Field(default_factory=list)
    product_warnings: list[str] = Field(default_factory=list)
    links: AnalysisResultLinks
    artifact_families: list[ArtifactFamilySummary] = Field(default_factory=list)


class AnalysisResultPresentationResponse(BaseModel):
    job_id: str
    consumer_key: str
    manifest: AnalysisResultManifest
    presentation: Optional[PagePresentation] = None


class RefreshPresentationResponse(BaseModel):
    job_id: str
    consumer_key: str
    refreshed: bool = True
    manifest: AnalysisResultManifest
    presentation: PagePresentation


class DiscoverySummary(BaseModel):
    """Lightweight result summary for discovery listing (no page assembly)."""

    job_id: str
    result_id: str = ""
    project_id: Optional[str] = None
    workflow_key: str = ""
    mode: str = "v2_presentation"
    status: str = ""
    result_state: str = ""
    presentation_status: str = ""
    prepared_at: str = ""
    completed_at: str = ""
    restore_available: bool = False
    restore_reason: str = "not_prepared"
    selected_source_thinker_id: Optional[str] = None
    selected_source_thinker_name: Optional[str] = None
    links: AnalysisResultLinks = Field(default_factory=AnalysisResultLinks)


class AttachProjectRequest(BaseModel):
    """Request to attach a project_id to an existing job."""

    project_id: str = Field(min_length=1)


class AttachProjectResponse(BaseModel):
    job_id: str
    project_id: str
    attached: bool = True
    idempotent: bool = False


class RunLinks(BaseModel):
    result_url: str = ""
    presentation_url: str = ""


class RunProgress(BaseModel):
    current_phase: float = 0
    total_phases: int = 0
    phase_name: str = ""
    detail: str = ""
    completed_phases: list[str] = Field(default_factory=list)
    phase_statuses: dict[str, str] = Field(default_factory=dict)
    structured_detail: Optional[dict] = None
    current_pass: float = 0
    total_passes: int = 0
    current_pass_name: str = ""


class RunSummary(BaseModel):
    job_id: str
    plan_id: str = ""
    project_id: Optional[str] = None
    workflow_key: str = ""
    consumer_key: str = ""
    status: str = ""
    created_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    progress: RunProgress = Field(default_factory=RunProgress)
    presentation_status: str = ""
    presentation_active: bool = False
    result_state: str = ""
    restore_available: bool = False
    restore_reason: str = "not_prepared"
    selected_source_thinker_id: Optional[str] = None
    selected_source_thinker_name: Optional[str] = None
    links: RunLinks = Field(default_factory=RunLinks)


class RunDetail(RunSummary):
    pass
