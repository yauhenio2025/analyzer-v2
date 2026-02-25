"""Chapter splitting infrastructure for chapter-level targeted analysis.

Detects chapter boundaries in document text using regex-based heading detection
and provides extraction utilities for running analysis on individual chapters.

The detected chapter structure is available to the planner via BookSample.chapter_structure,
enabling chapter-targeting decisions during plan generation. During execution, the phase
runner uses extract_chapter_text() to isolate chapter content for per-chapter analysis.
"""

import logging
import re
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ChapterInfo(BaseModel):
    """Information about a detected chapter."""

    chapter_id: str = Field(..., description="Unique chapter identifier (e.g., 'ch1', 'part2_ch3')")
    chapter_title: str = Field(default="", description="Chapter title text")
    start_char: int = Field(..., description="Start character offset in the document")
    end_char: int = Field(..., description="End character offset in the document")
    char_count: int = Field(default=0, description="Character count of this chapter")


class DocumentStructure(BaseModel):
    """Detected structure of a document."""

    doc_id: str = Field(default="", description="Document identifier")
    title: str = Field(default="", description="Document title")
    total_chars: int = Field(default=0, description="Total character count")
    chapters: list[ChapterInfo] = Field(default_factory=list, description="Detected chapters")
    detection_method: str = Field(
        default="heading_regex",
        description="How chapters were detected: heading_regex | llm_detected | manual",
    )


# Regex patterns for detecting chapter-like headings
_CHAPTER_PATTERNS = [
    # "Chapter N" or "Chapter N:" or "Chapter N."
    re.compile(r"^\s*(Chapter\s+\d+[\.:]?\s*.*)$", re.IGNORECASE | re.MULTILINE),
    # "Part N" or "Part N:"
    re.compile(r"^\s*(Part\s+(?:\d+|[IVXivx]+)[\.:]?\s*.*)$", re.IGNORECASE | re.MULTILINE),
    # "Section N.N" or "Section N"
    re.compile(r"^\s*(Section\s+\d+(?:\.\d+)?[\.:]?\s*.*)$", re.IGNORECASE | re.MULTILINE),
    # Roman numerals on their own line: "I.", "II.", "III." etc.
    re.compile(r"^\s*((?:X{0,3})(?:IX|IV|V?I{0,3}))\.\s*(.*)$", re.MULTILINE),
    # Numbered headings: "1.", "2.", "3." (at start of line, followed by title text)
    re.compile(r"^\s*(\d{1,2})\.\s+([A-Z].{5,80})$", re.MULTILINE),
]

# Pattern for ALL-CAPS headings on their own line (at least 4 chars, max 100)
_ALLCAPS_HEADING = re.compile(r"^\s*([A-Z][A-Z\s\-:]{3,99})$", re.MULTILINE)

# Minimum chapter size to avoid false positives (characters)
_MIN_CHAPTER_CHARS = 2000


def detect_chapters(text: str, doc_id: str = "") -> DocumentStructure:
    """Detect chapter boundaries in document text using regex-based heading detection.

    Matches patterns like:
    - Chapter N, Part N, Section N.N
    - Roman numerals (I., II., III.)
    - ALL-CAPS headings on their own line
    - Numbered headings (1. Title Text)

    Returns a DocumentStructure with chapter boundaries. If no chapters are
    detected (e.g., for short documents), returns an empty chapter list.

    Args:
        text: Full document text
        doc_id: Optional document identifier

    Returns:
        DocumentStructure with detected chapters
    """
    if not text or len(text) < _MIN_CHAPTER_CHARS:
        return DocumentStructure(
            doc_id=doc_id,
            total_chars=len(text) if text else 0,
            chapters=[],
            detection_method="heading_regex",
        )

    # Collect all heading matches with their positions
    heading_matches: list[tuple[int, str]] = []

    for pattern in _CHAPTER_PATTERNS:
        for match in pattern.finditer(text):
            heading_text = match.group(0).strip()
            heading_matches.append((match.start(), heading_text))

    # Also check ALL-CAPS headings, but only if we didn't find enough
    # structured headings (to avoid false positives from emphasis text)
    if len(heading_matches) < 3:
        for match in _ALLCAPS_HEADING.finditer(text):
            heading_text = match.group(0).strip()
            # Filter out likely false positives
            if (
                len(heading_text) >= 8
                and not heading_text.startswith("NOTE")
                and not heading_text.startswith("TABLE")
                and not heading_text.startswith("FIGURE")
                and heading_text not in ("ABSTRACT", "REFERENCES", "BIBLIOGRAPHY", "ACKNOWLEDGMENTS")
            ):
                heading_matches.append((match.start(), heading_text))

    # Sort by position
    heading_matches.sort(key=lambda x: x[0])

    # Deduplicate: remove headings that are very close together (within 100 chars)
    deduped: list[tuple[int, str]] = []
    for pos, heading in heading_matches:
        if not deduped or pos - deduped[-1][0] > 100:
            deduped.append((pos, heading))
    heading_matches = deduped

    # Build chapters from headings
    chapters: list[ChapterInfo] = []
    for i, (pos, heading) in enumerate(heading_matches):
        # End position is start of next heading or end of document
        end_pos = heading_matches[i + 1][0] if i + 1 < len(heading_matches) else len(text)
        char_count = end_pos - pos

        # Skip very small "chapters" (likely false positives)
        if char_count < _MIN_CHAPTER_CHARS and i < len(heading_matches) - 1:
            continue

        chapter_id = f"ch{len(chapters) + 1}"
        chapters.append(
            ChapterInfo(
                chapter_id=chapter_id,
                chapter_title=heading[:200],  # Truncate long headings
                start_char=pos,
                end_char=end_pos,
                char_count=char_count,
            )
        )

    logger.info(
        f"Detected {len(chapters)} chapters in document '{doc_id}' "
        f"({len(text):,} chars) via heading_regex"
    )

    return DocumentStructure(
        doc_id=doc_id,
        title="",
        total_chars=len(text),
        chapters=chapters,
        detection_method="heading_regex",
    )


def extract_chapter_text(text: str, chapter: ChapterInfo) -> str:
    """Extract text for a specific chapter using character offsets.

    Args:
        text: Full document text
        chapter: ChapterInfo with start_char and end_char

    Returns:
        The chapter's text content
    """
    return text[chapter.start_char : chapter.end_char]


def get_chapter_summary_for_sample(structure: DocumentStructure) -> list[dict]:
    """Convert a DocumentStructure to a lightweight summary suitable for BookSample.

    Returns a list of dicts with chapter_id, title, and char_count — the minimum
    information the planner needs to make chapter-targeting decisions.
    """
    return [
        {
            "chapter_id": ch.chapter_id,
            "title": ch.chapter_title,
            "char_count": ch.char_count,
        }
        for ch in structure.chapters
    ]
