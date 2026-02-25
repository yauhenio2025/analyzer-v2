"""Schemas for the book sampler — lightweight profiling of each work in a corpus."""

from pydantic import BaseModel, Field


class BookSample(BaseModel):
    """Lightweight profile of a book, produced by LLM sampling.
    
    The adaptive planner uses these to understand the corpus before
    generating a bespoke pipeline. Sampling is cheap (~$0.01/book)
    and provides crucial information about genre, reasoning modes,
    technical level, and engine affinities.
    """
    title: str = Field(..., description="Work title")
    role: str = Field(..., description="'target' or 'prior_work'")
    genre: str = Field(
        default="academic_monograph",
        description="Genre: academic_monograph, essay_collection, memoir, "
        "polemic, textbook, fiction, dialogue, manifesto, etc."
    )
    domain: str = Field(
        default="",
        description="Primary intellectual domain: political_economy, "
        "philosophy, sociology, game_theory, etc."
    )
    argumentative_style: str = Field(
        default="analytical",
        description="Dominant style: analytical, polemical, narrative, "
        "dialogical, aphoristic, systematic, comparative"
    )
    technical_level: str = Field(
        default="moderate",
        description="Technical density: highly_technical, moderate, "
        "accessible, mixed"
    )
    reasoning_modes: list[str] = Field(
        default_factory=list,
        description="Reasoning approaches used: deductive, dialectical, "
        "game_theoretic, modal, comparative, historical, genealogical, "
        "phenomenological, pragmatic, etc."
    )
    key_vocabulary_sample: list[str] = Field(
        default_factory=list,
        description="10-20 distinctive terms that characterize this work"
    )
    structural_notes: str = Field(
        default="",
        description="Notes on structure: chapter organization, use of "
        "examples, formalization level, etc."
    )
    estimated_length_chars: int = Field(
        default=0,
        description="Estimated total character count of the work"
    )
    engine_category_affinities: dict[str, float] = Field(
        default_factory=dict,
        description="Engine category -> 0-1 relevance score. "
        "Categories: concepts, argument, temporal, epistemology, "
        "methodology, rhetoric, etc."
    )
    rationale: str = Field(
        default="",
        description="LLM's reasoning for these classifications"
    )
    chapter_structure: list[dict] = Field(
        default_factory=list,
        description="Detected chapter structure from heading analysis. "
        "Each entry: {chapter_id, title, char_count}. "
        "Available to the planner for chapter-targeting decisions.",
    )
