"""Schemas for the all-in-one analysis pipeline.

The pipeline chains document upload -> plan generation -> execution -> presentation
into a single async job. These schemas define the request/response for that flow.
"""

from typing import Optional

from pydantic import BaseModel, Field, model_validator

from src.aoi import AOI_WORKFLOW_KEY
from src.orchestrator.schemas import TargetWork, PriorWork


class ChapterUpload(BaseModel):
    """A pre-split chapter of any work (target or prior).

    When the user already has individual chapters as separate files,
    they can upload them alongside the full document. Each chapter is
    stored as its own document in the store and made available for
    chapter-targeted execution without char-offset extraction.

    Uploading chapters does NOT force their use — they're simply
    available if the planner or mid-course revision decides to target
    specific chapters.
    """

    chapter_id: str = Field(
        description="Chapter identifier, unique within this work. "
        "e.g. 'ch1', 'ch7', 'appendix_a'",
    )
    title: str = Field(
        default="",
        description="Chapter title",
    )
    text: str = Field(
        description="Full text of this chapter",
    )


class PriorWorkWithText(BaseModel):
    """Prior work metadata + full text for inline upload."""

    title: str
    author: Optional[str] = None
    year: Optional[int] = None
    description: str = Field(
        default="",
        description="Brief description of the work",
    )
    relationship_hint: str = Field(
        default="",
        description="User's hint about relationship to target",
    )
    source_thinker_id: Optional[str] = Field(
        default=None,
        description="Optional thinker identifier for the source corpus this work belongs to. "
        "Required for the single-thinker AOI workflow.",
    )
    source_thinker_name: Optional[str] = Field(
        default=None,
        description="Optional thinker display name for the source corpus this work belongs to. "
        "Required for the single-thinker AOI workflow.",
    )
    source_document_id: Optional[str] = Field(
        default=None,
        description="Stable source-document identifier for this work. "
        "Required for the single-thinker AOI workflow.",
    )
    text: str = Field(
        description="Full text of the prior work",
    )
    chapters: list[ChapterUpload] = Field(
        default_factory=list,
        description="Pre-split chapters of this prior work. Optional — when provided, "
        "each chapter is stored as its own document and available for "
        "chapter-targeted execution if the planner decides to use them.",
    )


class AnalyzeRequest(BaseModel):
    """All-in-one analysis request with inline documents.

    Accepts thinker context + document texts, chains the full pipeline:
    document upload -> plan generation -> execution -> presentation.
    """

    thinker_name: str
    target_work: TargetWork
    target_work_text: str = Field(
        description="Full text of the target work",
    )
    target_work_chapters: list[ChapterUpload] = Field(
        default_factory=list,
        description="Pre-split chapters of the target work. Optional — when provided, "
        "each chapter is stored as its own document and made available for "
        "chapter-targeted execution. The full target_work_text should still be "
        "provided alongside chapters for whole-document phases.",
    )
    prior_works: list[PriorWorkWithText] = Field(
        default_factory=list,
        description="Prior works with full text for genealogical scanning",
    )
    research_question: Optional[str] = None
    depth_preference: Optional[str] = Field(
        default=None,
        description="surface, standard, deep, or None (let orchestrator decide)",
    )
    focus_hint: Optional[str] = None
    selected_source_thinker_id: Optional[str] = Field(
        default=None,
        description="Explicit thinker identifier for the AOI source corpus. "
        "Required for anxiety_of_influence_thematic_single_thinker.",
    )
    selected_source_thinker_name: Optional[str] = Field(
        default=None,
        description="Human-readable thinker name for the AOI source corpus. "
        "Required for anxiety_of_influence_thematic_single_thinker.",
    )

    # Workflow selection
    workflow_key: Optional[str] = Field(
        default=None,
        description="Workflow key for this analysis. Default: 'intellectual_genealogy'.",
    )
    project_id: Optional[str] = Field(
        default=None,
        description="Optional project identifier to associate with the executor job. "
        "Useful for feedback capture and variant-learning loops even when the "
        "caller owns the higher-level project workspace.",
    )

    # Pipeline control
    skip_plan_review: bool = Field(
        default=True,
        description="True = autonomous (default): generate plan and immediately execute. "
        "False = generate plan only, return plan_id for review before execution.",
    )

    # Adaptive orchestrator
    objective_key: Optional[str] = Field(
        default=None,
        description="If set, enables adaptive mode with this objective. "
        "The orchestrator will sample books, load the objective's goals, "
        "and generate a bespoke pipeline. "
        "Valid keys: 'genealogical', 'logical', etc.",
    )

    # Plan revision control
    skip_plan_revision: bool = Field(
        default=False,
        description="If True, skip both pre-execution and mid-course plan revision. "
        "Useful for quick runs or when the plan has been manually reviewed.",
    )

    # Model selection
    planning_model: Optional[str] = Field(
        default=None,
        description="Model for plan generation: 'claude-opus-4-6' or 'gemini-3.1-pro-preview'. "
        "Default: claude-opus-4-6.",
    )
    execution_model: Optional[str] = Field(
        default=None,
        description="Default model for phase execution: 'claude-sonnet-4-6' or 'gemini-3.1-pro-preview'. "
        "Default: per-phase model_hint from plan. Overrides plan defaults.",
    )

    @model_validator(mode="after")
    def _validate_aoi_single_thinker_contract(self) -> "AnalyzeRequest":
        """Require explicit thinker identity for the bounded AOI workflow."""
        if self.workflow_key != AOI_WORKFLOW_KEY:
            return self

        if not self.selected_source_thinker_id or not self.selected_source_thinker_name:
            raise ValueError(
                "AOI single-thinker workflow requires selected_source_thinker_id "
                "and selected_source_thinker_name."
            )

        if not self.prior_works:
            raise ValueError(
                "AOI single-thinker workflow requires prior_works for the selected source thinker."
            )

        mismatched_titles: list[str] = []
        missing_source_document_ids: list[str] = []
        matching_count = 0
        for prior_work in self.prior_works:
            if (
                prior_work.source_thinker_id == self.selected_source_thinker_id
                and prior_work.source_thinker_name == self.selected_source_thinker_name
            ):
                matching_count += 1
                if not prior_work.source_document_id:
                    missing_source_document_ids.append(prior_work.title)
                continue
            mismatched_titles.append(prior_work.title)

        if matching_count == 0:
            raise ValueError(
                "AOI single-thinker workflow requires at least one prior work whose "
                "source thinker matches the selected source thinker."
            )

        if mismatched_titles:
            raise ValueError(
                "AOI single-thinker workflow currently expects all prior works to belong "
                f"to the selected source thinker. Mismatched works: {mismatched_titles}"
            )
        if missing_source_document_ids:
            raise ValueError(
                "AOI single-thinker workflow requires source_document_id on all selected "
                f"prior works. Missing on: {missing_source_document_ids}"
            )

        return self


class AnalyzeResponse(BaseModel):
    """Response from the all-in-one analyze endpoint."""

    job_id: Optional[str] = Field(
        default=None,
        description="Execution job ID (None if skip_plan_review=False)",
    )
    plan_id: Optional[str] = Field(
        default=None,
        description="Plan ID (None until plan is generated in async mode)",
    )
    document_ids: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of role/title -> document ID. "
        "Keys: 'target' for target work, prior work titles for prior works, "
        "'chapter:target:{chapter_id}' for target chapters, "
        "'chapter:{prior_work_title}:{chapter_id}' for prior work chapters.",
    )
    cancel_token: Optional[str] = Field(
        default=None,
        description="Token required to cancel this job. Only returned on job creation.",
    )
    status: str = Field(
        description="'executing' if autonomous, 'plan_generated' if checkpoint mode",
    )
    message: str = ""


class PriorWorkByRef(BaseModel):
    """Analysis-specific prior-work metadata when the text is already registered."""

    external_doc_key: str
    description: str = Field(
        default="",
        description="Brief description of the work for planning context.",
    )
    relationship_hint: str = Field(
        default="",
        description="User's hint about the relationship to the target.",
    )


class TargetChapterByRef(BaseModel):
    """Reference to a registered target chapter binding plus its semantic chapter id."""

    external_doc_key: str
    chapter_id: str


class AnalyzeByRefRequest(BaseModel):
    """Launch request against previously registered documents."""

    consumer_key: str
    external_project_id: str
    thinker_name: str
    target_work: TargetWork
    target_external_doc_key: str
    target_chapter_external_doc_keys: list[str] = Field(default_factory=list)
    target_chapters: list[TargetChapterByRef] = Field(default_factory=list)
    prior_works: list[PriorWorkByRef] = Field(default_factory=list)
    context_external_doc_keys: list[str] = Field(default_factory=list)
    research_question: Optional[str] = None
    depth_preference: Optional[str] = Field(
        default=None,
        description="surface, standard, deep, or None (let orchestrator decide)",
    )
    focus_hint: Optional[str] = None
    selected_source_thinker_id: Optional[str] = None
    selected_source_thinker_name: Optional[str] = None
    workflow_key: Optional[str] = Field(
        default="intellectual_genealogy",
        description="Supports intellectual_genealogy and the bounded AOI single-thinker workflow.",
    )
    project_id: Optional[str] = Field(
        default=None,
        description="Optional project identifier to associate with the executor job.",
    )
    skip_plan_review: bool = Field(
        default=True,
        description="True = autonomous launch, False = plan-only checkpoint mode.",
    )
    objective_key: Optional[str] = None
    skip_plan_revision: bool = Field(
        default=False,
        description="If True, skip pre-execution plan revision in adaptive mode.",
    )
    planning_model: Optional[str] = None
    execution_model: Optional[str] = None

    @model_validator(mode="after")
    def _validate_workflow_contract(self) -> "AnalyzeByRefRequest":
        workflow_key = self.workflow_key or "intellectual_genealogy"
        if workflow_key not in {"intellectual_genealogy", AOI_WORKFLOW_KEY}:
            raise ValueError(
                "analyze-by-ref currently supports intellectual_genealogy and "
                "anxiety_of_influence_thematic_single_thinker only."
            )
        if self.target_chapters and self.target_chapter_external_doc_keys:
            raise ValueError(
                "target_chapter_external_doc_keys and target_chapters are mutually exclusive."
            )
        if workflow_key == AOI_WORKFLOW_KEY:
            if not self.selected_source_thinker_id or not self.selected_source_thinker_name:
                raise ValueError(
                    "AOI single-thinker by-ref launch requires selected_source_thinker_id "
                    "and selected_source_thinker_name."
                )
            if self.target_chapter_external_doc_keys:
                raise ValueError(
                    "AOI single-thinker by-ref launch must use target_chapters, not "
                    "target_chapter_external_doc_keys."
                )
        elif self.target_chapters:
            raise ValueError(
                "intellectual_genealogy by-ref launch must use target_chapter_external_doc_keys, "
                "not target_chapters."
            )
        return self
