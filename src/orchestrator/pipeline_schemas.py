"""Schemas for the all-in-one analysis pipeline.

The pipeline chains document upload -> plan generation -> execution -> presentation
into a single async job. These schemas define the request/response for that flow.
"""

from typing import Optional

from pydantic import BaseModel, Field

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

    # Workflow selection
    workflow_key: Optional[str] = Field(
        default=None,
        description="Workflow key for this analysis. Default: 'intellectual_genealogy'.",
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
