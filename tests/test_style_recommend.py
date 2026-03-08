"""Tests for POST /v1/styles/recommend - style recommendation engine."""

import pytest
from src.styles.registry import StyleRegistry
from src.styles.schemas import StyleSchool, StyleRecommendRequest


@pytest.fixture
def registry():
    """Fresh StyleRegistry loaded from real affinity data."""
    return StyleRegistry()


# --- Basic signal tests ---

def test_single_engine_known(registry):
    """Engine with explicit affinity returns that school first."""
    # concept_evolution -> [emergent_systems, humanist_craft]
    result = registry.recommend_styles(engine_keys=["concept_evolution"])
    schools = [r.school for r in result.recommendations]
    assert schools[0] == StyleSchool.EMERGENT_SYSTEMS
    assert result.recommendations[0].rank == 1
    assert result.recommendations[0].score > 0


def test_single_engine_unknown(registry):
    """Unknown engine falls back to hardcoded default schools."""
    # Default: [explanatory_narrative, minimalist_precision]
    result = registry.recommend_styles(engine_keys=["nonexistent_engine"])
    schools = [r.school for r in result.recommendations]
    assert schools[0] == StyleSchool.EXPLANATORY_NARRATIVE
    assert result.context_summary.engines_using_default == 1
    assert result.context_summary.engines_with_explicit_mapping == 0


def test_audience_only(registry):
    """Audience signal works standalone."""
    # academic -> [minimalist_precision, emergent_systems]
    result = registry.recommend_styles(audience="academic")
    schools = [r.school for r in result.recommendations]
    assert schools[0] == StyleSchool.MINIMALIST_PRECISION
    assert result.context_summary.audience_provided == "academic"
    assert result.context_summary.audience_used_default is False


def test_multi_signal_combination(registry):
    """Engines + audience scores combine correctly."""
    # concept_evolution -> [emergent_systems, humanist_craft]
    # academic -> [minimalist_precision, emergent_systems]
    # emergent_systems: 2.0 (engine primary) + 1.0 (audience secondary) = 3.0
    # minimalist_precision: 0 + 2.0 (audience primary) = 2.0
    # humanist_craft: 1.0 (engine secondary) + 0 = 1.0
    result = registry.recommend_styles(
        engine_keys=["concept_evolution"],
        audience="academic",
        limit=6,
    )
    schools = [r.school for r in result.recommendations]
    scores = {r.school: r.raw_score for r in result.recommendations}

    assert schools[0] == StyleSchool.EMERGENT_SYSTEMS
    assert scores[StyleSchool.EMERGENT_SYSTEMS] == 3.0
    assert scores[StyleSchool.MINIMALIST_PRECISION] == 2.0
    assert scores[StyleSchool.HUMANIST_CRAFT] == 1.0

    # Normalized: max_possible = 2.0 * 2 signals = 4.0
    norm = {r.school: r.score for r in result.recommendations}
    assert norm[StyleSchool.EMERGENT_SYSTEMS] == 0.75
    assert norm[StyleSchool.MINIMALIST_PRECISION] == 0.5
    assert norm[StyleSchool.HUMANIST_CRAFT] == 0.25


# --- Renderer type mapping ---

def test_renderer_type_mapped(registry):
    """stat_summary maps to indicator_dashboard/bar_chart and contributes signal."""
    # indicator_dashboard -> [restrained_elegance, explanatory_narrative]
    # bar_chart -> [restrained_elegance, minimalist_precision]
    result = registry.recommend_styles(renderer_types=["stat_summary"], limit=6)
    schools = [r.school for r in result.recommendations]
    assert schools[0] == StyleSchool.RESTRAINED_ELEGANCE  # primary in both formats
    assert result.context_summary.renderer_types_mapped == 1
    assert result.context_summary.effective_signals == 2  # 2 mapped formats


def test_renderer_type_unmapped(registry):
    """raw_json contributes no signal."""
    result = registry.recommend_styles(
        renderer_types=["raw_json"],
        audience="academic",  # need at least one real signal
    )
    assert result.context_summary.renderer_types_mapped == 0
    # Only audience signal counts
    assert result.context_summary.effective_signals == 1


# --- Edge cases ---

def test_tie_breaking(registry):
    """Equal scores break by primary count, then alphabetical."""
    # Two engines that give different schools the same total:
    # emergent_systems primary in one, secondary in another -> same total as reverse
    # But primary_count breaks the tie
    result = registry.recommend_styles(
        engine_keys=["concept_evolution"],  # [emergent_systems, humanist_craft]
        limit=6,
    )
    # emergent_systems gets 2.0 (primary), humanist_craft gets 1.0 (secondary)
    # Rest get 0 - alphabetical tiebreak among them
    zero_schools = [r for r in result.recommendations if r.raw_score == 0.0]
    zero_names = [r.school.value for r in zero_schools]
    assert zero_names == sorted(zero_names)  # alphabetical


def test_limit(registry):
    """limit=1 returns exactly 1 result."""
    result = registry.recommend_styles(engine_keys=["concept_evolution"], limit=1)
    assert len(result.recommendations) == 1
    assert result.recommendations[0].rank == 1


def test_scores_normalized(registry):
    """All scores in 0.0-1.0 range."""
    result = registry.recommend_styles(
        engine_keys=["concept_evolution", "argument_architecture"],
        audience="activist",
        limit=6,
    )
    for rec in result.recommendations:
        assert 0.0 <= rec.score <= 1.0


def test_raw_score_included(registry):
    """raw_score present and matches expected sum."""
    result = registry.recommend_styles(engine_keys=["concept_evolution"], limit=6)
    # emergent_systems is primary -> 2.0 raw
    es = next(r for r in result.recommendations if r.school == StyleSchool.EMERGENT_SYSTEMS)
    assert es.raw_score == 2.0
    # humanist_craft is secondary -> 1.0 raw
    hc = next(r for r in result.recommendations if r.school == StyleSchool.HUMANIST_CRAFT)
    assert hc.raw_score == 1.0


def test_empty_request_validation():
    """No signals raises ValueError."""
    with pytest.raises(Exception):  # Pydantic ValidationError
        StyleRecommendRequest(engine_keys=[], renderer_types=[], audience=None)


def test_only_unmapped_renderer_types(registry):
    """Only unmapped renderer_types -> total_signals=0, all schools score 0, alphabetical."""
    result = registry.recommend_styles(renderer_types=["accordion", "raw_json"], limit=6)
    assert result.context_summary.effective_signals == 0
    assert result.context_summary.renderer_types_mapped == 0
    assert len(result.recommendations) == 6
    for rec in result.recommendations:
        assert rec.score == 0.0
        assert rec.raw_score == 0.0
    # Alphabetical order
    names = [r.school.value for r in result.recommendations]
    assert names == sorted(names)


def test_duplicate_engine_keys(registry):
    """Duplicate engine keys don't inflate scores."""
    single = registry.recommend_styles(engine_keys=["concept_evolution"], limit=6)
    double = registry.recommend_styles(engine_keys=["concept_evolution", "concept_evolution"], limit=6)

    single_scores = {r.school: r.raw_score for r in single.recommendations}
    double_scores = {r.school: r.raw_score for r in double.recommendations}
    assert single_scores == double_scores


def test_context_summary_completeness(registry):
    """Context summary has all expected fields."""
    result = registry.recommend_styles(
        engine_keys=["concept_evolution", "nonexistent"],
        renderer_types=["stat_summary", "accordion"],
        audience="academic",
        limit=3,
    )
    cs = result.context_summary
    assert cs.engines_provided == 2
    assert cs.engines_with_explicit_mapping == 1
    assert cs.engines_using_default == 1
    assert cs.renderer_types_provided == 2
    assert cs.renderer_types_mapped == 1  # stat_summary
    assert cs.audience_provided == "academic"
    assert cs.audience_used_default is False
    assert cs.effective_signals > 0
