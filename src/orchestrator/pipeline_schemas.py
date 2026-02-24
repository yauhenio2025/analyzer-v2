"""Schemas for the all-in-one analysis pipeline.

The pipeline chains document upload -> plan generation -> execution -> presentation
into a single async job. These schemas define the request/response for that flow.
"""

from typing import Optional

from pydantic import BaseModel, Field

from src.orchestrator.schemas import TargetWork, PriorWork


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
        "Keys: 'target' for target work, prior work titles for prior works.",
    )
    cancel_token: Optional[str] = Field(
        default=None,
        description="Token required to cancel this job. Only returned on job creation.",
    )
    status: str = Field(
        description="'executing' if autonomous, 'plan_generated' if checkpoint mode",
    )
    message: str = ""
