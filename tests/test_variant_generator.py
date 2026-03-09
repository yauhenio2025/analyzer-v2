"""Tests for Tier 3b variant generation logic."""

import hashlib
from unittest.mock import MagicMock, patch

import pytest

from src.presenter.variant_generator import (
    _compute_variant_set_id,
    _generate_renderer_type_variants,
    _generate_sub_renderer_variants,
    _score_candidate,
    _validate_against_schema,
)
from src.renderers.schemas import RendererDefinition


def _make_renderer(
    key: str,
    shapes: list[str] | None = None,
    stances: dict[str, float] | None = None,
    section_renderers: list[str] | None = None,
    category: str = "container",
    status: str = "active",
    input_data_schema: dict | None = None,
    supported_apps: list[str] | None = None,
) -> RendererDefinition:
    return RendererDefinition(
        renderer_key=key,
        renderer_name=key.replace("_", " ").title(),
        category=category,
        ideal_data_shapes=shapes or [],
        stance_affinities=stances or {},
        available_section_renderers=section_renderers or [],
        status=status,
        input_data_schema=input_data_schema,
        supported_apps=supported_apps or ["the-critic"],
    )


class TestComputeVariantSetId:
    def test_deterministic(self):
        id1 = _compute_variant_set_id("job-1", "view_a", "renderer_type", "accordion", "")
        id2 = _compute_variant_set_id("job-1", "view_a", "renderer_type", "accordion", "")
        assert id1 == id2

    def test_different_inputs_different_ids(self):
        id1 = _compute_variant_set_id("job-1", "view_a", "renderer_type", "accordion", "")
        id2 = _compute_variant_set_id("job-2", "view_a", "renderer_type", "accordion", "")
        assert id1 != id2

    def test_format(self):
        result = _compute_variant_set_id("job-abc123", "genealogy_tactics", "renderer_type", "accordion", "")
        assert result.startswith("vs-")
        parts = result.split("-", 2)  # vs, jid_prefix, rest
        assert len(parts) >= 3

    def test_view_key_truncated(self):
        long_key = "a_very_long_view_key_that_exceeds_twenty_characters"
        result = _compute_variant_set_id("job-1", long_key, "renderer_type", "accordion", "")
        # view_key prefix should be truncated to 20 chars
        assert long_key[:20] in result

    def test_style_school_affects_id(self):
        id1 = _compute_variant_set_id("job-1", "view_a", "renderer_type", "accordion", "")
        id2 = _compute_variant_set_id("job-1", "view_a", "renderer_type", "accordion", "minimalist")
        assert id1 != id2


class TestScoreCandidate:
    def test_full_shape_overlap(self):
        base = _make_renderer("accordion", shapes=["nested_sections", "object_array"])
        candidate = _make_renderer("card_grid", shapes=["nested_sections", "object_array"])
        score = _score_candidate(candidate, base, None)
        # shape_score=1.0, stance_score=0.3 (default)
        assert score == round(0.6 * 1.0 + 0.4 * 0.3, 3)

    def test_partial_shape_overlap(self):
        base = _make_renderer("accordion", shapes=["nested_sections", "object_array"])
        candidate = _make_renderer("card_grid", shapes=["object_array"])
        score = _score_candidate(candidate, base, None)
        assert score == round(0.6 * 0.5 + 0.4 * 0.3, 3)

    def test_no_shape_overlap(self):
        base = _make_renderer("accordion", shapes=["nested_sections"])
        candidate = _make_renderer("card_grid", shapes=["flat_list"])
        score = _score_candidate(candidate, base, None)
        assert score == round(0.6 * 0.0 + 0.4 * 0.3, 3)

    def test_stance_affinity_boost(self):
        base = _make_renderer("accordion", shapes=["nested_sections"])
        candidate = _make_renderer("card_grid", shapes=["nested_sections"], stances={"analytical": 0.9})
        score = _score_candidate(candidate, base, "analytical")
        assert score == round(0.6 * 1.0 + 0.4 * 0.9, 3)

    def test_no_base_shapes(self):
        base = _make_renderer("accordion", shapes=[])
        candidate = _make_renderer("card_grid", shapes=["object_array"])
        score = _score_candidate(candidate, base, None)
        # shape_score=0.5 (unknown), stance_score=0.3
        assert score == round(0.6 * 0.5 + 0.4 * 0.3, 3)


class TestValidateAgainstSchema:
    def test_no_schema_passes(self):
        renderer = _make_renderer("test", input_data_schema=None)
        assert _validate_against_schema(renderer, {"any": "data"}) is True

    def test_valid_data_passes(self):
        schema = {"type": "object", "properties": {"items": {"type": "array"}}}
        renderer = _make_renderer("test", input_data_schema=schema)
        assert _validate_against_schema(renderer, {"items": [1, 2, 3]}) is True

    def test_invalid_data_fails(self):
        pytest.importorskip("jsonschema")
        schema = {"type": "object", "required": ["items"], "properties": {"items": {"type": "array"}}}
        renderer = _make_renderer("test", input_data_schema=schema)
        assert _validate_against_schema(renderer, {"wrong_key": "value"}) is False


class TestGenerateRendererTypeVariants:
    def test_finds_compatible_renderers(self):
        base = _make_renderer("accordion", shapes=["nested_sections", "object_array"])
        alt1 = _make_renderer("card_grid", shapes=["object_array"])
        alt2 = _make_renderer("timeline", shapes=["nested_sections"])

        mock_registry = MagicMock()
        mock_registry.for_data_shape.side_effect = lambda s: {
            "nested_sections": [base, alt2],
            "object_array": [base, alt1],
        }.get(s, [])
        mock_registry.for_app.return_value = [base, alt1, alt2]

        with patch("src.presenter.variant_generator.get_renderer_registry", return_value=mock_registry):
            variants = _generate_renderer_type_variants(
                base_renderer=base,
                structured_data={"items": []},
                base_stance=None,
                max_variants=3,
                base_renderer_config={},
            )

        assert len(variants) <= 2  # max_variants - 1
        for v in variants:
            assert v["renderer_type"] != "accordion"
            assert v["compatibility_score"] > 0

    def test_no_compatible_returns_empty(self):
        base = _make_renderer("accordion", shapes=["unique_shape"])

        mock_registry = MagicMock()
        mock_registry.for_data_shape.return_value = [base]  # Only base matches
        mock_registry.for_app.return_value = [base]

        with patch("src.presenter.variant_generator.get_renderer_registry", return_value=mock_registry):
            variants = _generate_renderer_type_variants(
                base_renderer=base,
                structured_data={"items": []},
                base_stance=None,
                max_variants=3,
                base_renderer_config={},
            )

        assert variants == []

    def test_filters_by_app_support(self):
        base = _make_renderer("accordion", shapes=["object_array"])
        alt = _make_renderer("card_grid", shapes=["object_array"])
        unsupported = _make_renderer("internal_only", shapes=["object_array"])

        mock_registry = MagicMock()
        mock_registry.for_data_shape.return_value = [base, alt, unsupported]
        mock_registry.for_app.return_value = [base, alt]  # unsupported not in app

        with patch("src.presenter.variant_generator.get_renderer_registry", return_value=mock_registry):
            variants = _generate_renderer_type_variants(
                base_renderer=base,
                structured_data={"items": []},
                base_stance=None,
                max_variants=3,
                base_renderer_config={},
            )

        renderer_types = [v["renderer_type"] for v in variants]
        assert "internal_only" not in renderer_types


class TestGenerateSubRendererVariants:
    def test_generates_variants_with_section_renderers(self):
        base = _make_renderer(
            "accordion",
            section_renderers=["chip_grid", "mini_card_list", "key_value_table"],
        )
        config = {
            "section_renderer_hints": [
                {"section_key": "s1", "renderer_type": "chip_grid"},
            ],
        }

        variants = _generate_sub_renderer_variants(base, config, max_variants=3)

        assert len(variants) >= 1
        for v in variants:
            assert v["renderer_type"] == "accordion"  # Same base renderer
            assert v["compatibility_score"] == 0.8

    def test_not_enough_section_renderers(self):
        base = _make_renderer("accordion", section_renderers=["chip_grid"])
        variants = _generate_sub_renderer_variants(base, {}, max_variants=3)
        assert variants == []

    def test_no_section_renderers(self):
        base = _make_renderer("accordion", section_renderers=[])
        variants = _generate_sub_renderer_variants(base, {}, max_variants=3)
        assert variants == []

    def test_empty_existing_hints(self):
        base = _make_renderer(
            "accordion",
            section_renderers=["chip_grid", "mini_card_list"],
        )
        variants = _generate_sub_renderer_variants(base, {}, max_variants=3)

        assert len(variants) >= 1
        for v in variants:
            config = v["renderer_config"]
            assert "section_renderer_hints" in config
