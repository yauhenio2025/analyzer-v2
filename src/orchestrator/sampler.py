"""Book sampler — lightweight LLM-based profiling of each work in a corpus.

Extracts representative excerpts from each book and uses a fast LLM call
to classify genre, domain, reasoning modes, and engine affinities.
This information feeds into the adaptive planner's decisions.

Cost: ~$0.01-0.02 per book (Sonnet, ~15K input, ~2K output).
"""

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from .sampler_schemas import BookSample

logger = logging.getLogger(__name__)


def extract_book_excerpt(text: str, max_chars: int = 13000) -> str:
    """Extract a representative excerpt from a book text.
    
    Strategy: First 5K + mid-section 5K + last 3K + detected headings.
    This gives the LLM a taste of the opening, body, and conclusion
    while staying under ~15K input tokens.
    """
    if len(text) <= max_chars:
        return text
    
    # First 5K
    first_section = text[:5000]
    
    # Mid-section 5K
    mid_start = len(text) // 2 - 2500
    mid_section = text[mid_start:mid_start + 5000]
    
    # Last 3K
    last_section = text[-3000:]
    
    # Detect headings (lines that look like chapter/section headers)
    headings = []
    for line in text.split('\n'):
        stripped = line.strip()
        if (stripped and len(stripped) < 100 and 
            (stripped.isupper() or 
             stripped.startswith('#') or
             stripped.startswith('Chapter') or
             stripped.startswith('Part') or
             stripped.startswith('Section'))):
            headings.append(stripped)
    
    heading_text = ""
    if headings:
        heading_text = "\n\n[DETECTED HEADINGS/STRUCTURE]:\n" + "\n".join(headings[:30])
    
    return (
        f"[OPENING SECTION (~5K chars)]:\n{first_section}\n\n"
        f"[MID-SECTION (~5K chars)]:\n{mid_section}\n\n"
        f"[CLOSING SECTION (~3K chars)]:\n{last_section}"
        f"{heading_text}"
    )


def _get_category_descriptions() -> dict[str, str]:
    """Get engine category descriptions for the sampling prompt.
    
    This grounds the affinity scores in what's actually available
    in the engine catalog.
    """
    try:
        from src.engines.registry import get_engine_registry
        registry = get_engine_registry()
        cap_defs = registry.list_capability_definitions()
        
        categories: dict[str, list[str]] = {}
        for cap_def in cap_defs:
            cat = cap_def.category.value if hasattr(cap_def.category, 'value') else str(cap_def.category)
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(f"{cap_def.engine_name}: {cap_def.problematique[:100]}")
        
        return {
            cat: f"{len(engines)} engines: " + "; ".join(engines[:5])
            for cat, engines in categories.items()
        }
    except Exception as e:
        logger.warning(f"Could not load category descriptions: {e}")
        return {
            "concepts": "Concept extraction, semantic fields, vocabulary mapping",
            "argument": "Argument structure, logical analysis, reasoning patterns",
            "temporal": "Evolution tracking, chronological analysis",
            "epistemology": "Knowledge claims, methodology detection",
            "methodology": "Research methods, analytical approaches",
        }


def sample_book(
    excerpt: str,
    title: str,
    role: str,
    full_text_length: int,
    category_descriptions: Optional[dict[str, str]] = None,
) -> BookSample:
    """Sample a single book using a fast LLM call.
    
    Args:
        excerpt: Representative excerpt from extract_book_excerpt()
        title: Work title
        role: 'target' or 'prior_work'
        full_text_length: Total character count of the full text
        category_descriptions: Engine category descriptions for grounding
    
    Returns:
        BookSample with genre, domain, reasoning modes, etc.
    """
    if category_descriptions is None:
        category_descriptions = _get_category_descriptions()
    
    categories_text = "\n".join(
        f"  - {cat}: {desc}" for cat, desc in category_descriptions.items()
    )
    
    system_prompt = """You are a literary and intellectual classifier. Given an excerpt from a book,
produce a structured profile classifying its genre, domain, argumentative style, reasoning modes,
and relevance to different analytical engine categories.

Return ONLY valid JSON matching this schema (no markdown fences):
{
  "genre": "academic_monograph|essay_collection|memoir|polemic|textbook|fiction|dialogue|manifesto|other",
  "domain": "primary intellectual domain",
  "argumentative_style": "analytical|polemical|narrative|dialogical|aphoristic|systematic|comparative",
  "technical_level": "highly_technical|moderate|accessible|mixed",
  "reasoning_modes": ["list of reasoning approaches: deductive, dialectical, game_theoretic, modal, comparative, historical, genealogical, phenomenological, pragmatic, etc."],
  "key_vocabulary_sample": ["10-20 distinctive terms"],
  "structural_notes": "brief notes on structure",
  "engine_category_affinities": {"category": 0.0-1.0},
  "rationale": "1-2 sentences explaining your classifications"
}"""

    user_prompt = f"""# Book to Profile

**Title**: {title}
**Role**: {role}
**Full text length**: {full_text_length:,} characters

## Available Engine Categories (score each 0.0-1.0 for relevance):
{categories_text}

## Excerpt:
{excerpt}

Produce the JSON profile."""

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("No ANTHROPIC_API_KEY — returning default BookSample")
        return BookSample(
            title=title,
            role=role,
            estimated_length_chars=full_text_length,
        )

    try:
        import httpx
        from anthropic import Anthropic
        client = Anthropic(
            timeout=httpx.Timeout(connect=30.0, read=120.0, write=30.0, pool=30.0),
        )
        
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        
        raw_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                raw_text = block.text
                break
        
        # Parse JSON
        content = raw_text.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        
        data = json.loads(content.strip())
        
        return BookSample(
            title=title,
            role=role,
            genre=data.get("genre", "academic_monograph"),
            domain=data.get("domain", ""),
            argumentative_style=data.get("argumentative_style", "analytical"),
            technical_level=data.get("technical_level", "moderate"),
            reasoning_modes=data.get("reasoning_modes", []),
            key_vocabulary_sample=data.get("key_vocabulary_sample", []),
            structural_notes=data.get("structural_notes", ""),
            estimated_length_chars=full_text_length,
            engine_category_affinities=data.get("engine_category_affinities", {}),
            rationale=data.get("rationale", ""),
        )
        
    except Exception as e:
        logger.error(f"Book sampling failed for '{title}': {e}")
        return BookSample(
            title=title,
            role=role,
            estimated_length_chars=full_text_length,
            rationale=f"Sampling failed: {e}",
        )


def sample_all_books(
    target_work_text: str,
    target_work_title: str,
    prior_works: list[dict],
    max_workers: int = 5,
    target_chapters: Optional[list[dict]] = None,
) -> list[BookSample]:
    """Sample all books in a corpus in parallel.

    Also runs chapter detection on each work so the planner has
    chapter structure available for chapter-targeting decisions.

    Args:
        target_work_text: Full text of the target work
        target_work_title: Title of the target work
        prior_works: List of dicts with 'title' and 'text' keys
        max_workers: Max parallel sampling calls
        target_chapters: Pre-uploaded chapter metadata for the target work.
            When provided, skips regex detection for the target and uses
            these instead. Each entry: {chapter_id, title, char_count}.

    Returns:
        List of BookSamples (target first, then prior works)
    """
    category_descriptions = _get_category_descriptions()
    samples: list[BookSample] = []

    def _sample_one(
        title: str,
        text: str,
        role: str,
        pre_uploaded_chapters: Optional[list[dict]] = None,
    ) -> BookSample:
        excerpt = extract_book_excerpt(text)
        sample = sample_book(
            excerpt=excerpt,
            title=title,
            role=role,
            full_text_length=len(text),
            category_descriptions=category_descriptions,
        )

        # Use pre-uploaded chapter metadata if provided (skips regex detection)
        if pre_uploaded_chapters:
            sample.chapter_structure = pre_uploaded_chapters
            logger.info(
                f"Using {len(pre_uploaded_chapters)} pre-uploaded chapters "
                f"for '{title}' (skipping regex detection)"
            )
            return sample

        # Fall back to regex-based chapter detection
        try:
            from src.executor.chapter_splitter import detect_chapters, get_chapter_summary_for_sample
            structure = detect_chapters(text, doc_id=title)
            sample.chapter_structure = get_chapter_summary_for_sample(structure)
            if sample.chapter_structure:
                logger.info(
                    f"Detected {len(sample.chapter_structure)} chapters in '{title}'"
                )
        except Exception as e:
            logger.warning(f"Chapter detection failed for '{title}': {e}")
        return sample
    
    # Build work list: (title, text, role, pre_uploaded_chapters)
    work_items = [
        (target_work_title, target_work_text, "target", target_chapters),
    ]
    for pw in prior_works:
        work_items.append((pw["title"], pw["text"], "prior_work", None))

    logger.info(f"Sampling {len(work_items)} books in parallel (max_workers={max_workers})")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_sample_one, title, text, role, chapters): title
            for title, text, role, chapters in work_items
        }
        
        results = {}
        for future in as_completed(futures):
            title = futures[future]
            try:
                sample = future.result()
                results[title] = sample
                logger.info(f"Sampled '{title}': {sample.genre}, {sample.domain}")
            except Exception as e:
                logger.error(f"Failed to sample '{title}': {e}")
                results[title] = BookSample(
                    title=title,
                    role="prior_work",
                    rationale=f"Sampling failed: {e}",
                )
    
    # Return in order: target first, then prior works
    for title, text, role in work_items:
        if title in results:
            samples.append(results[title])
    
    logger.info(f"Book sampling complete: {len(samples)} samples")
    return samples
