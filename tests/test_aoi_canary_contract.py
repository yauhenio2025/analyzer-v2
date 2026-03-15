import json
from pathlib import Path

from src.presenter.composition_resolver import resolve_effective_render_contract
from src.presenter.manifest_builder import adapt_renderer_for_consumer
from src.views.registry import get_view_registry


ROOT = Path(__file__).resolve().parents[1]
CONSUMER_PATH = ROOT / "src" / "consumers" / "definitions" / "aoi-canary.json"

EXPECTED_VIEW_RENDERERS = {
    "aoi_thematic_analysis": "tab",
    "aoi_source_documents": "card_grid",
    "aoi_by_theme": "accordion",
    "aoi_by_sin_type": "card_grid",
    "aoi_thematic_report": "accordion",
}

EXPECTED_REPORT_SECTION_RENDERERS = {
    "summary": "annotated_prose",
    "engagement_pattern": "annotated_prose",
    "key_divergences": "mini_card_list",
    "sin_distribution": "mini_card_list",
    "reading_implications": "annotated_prose",
}

EXPECTED_THEME_DEFAULT_SUB_RENDERERS = {
    "overview": "annotated_prose",
    "key_claims": "chip_grid",
    "philosophical_commitments": "chip_grid",
    "argumentative_moves": "chip_grid",
    "source_documents": "chip_grid",
    "engagement": "annotated_prose",
    "findings": "mini_card_list",
}


def _supported_contracts() -> set[str]:
    consumer = json.loads(CONSUMER_PATH.read_text(encoding="utf-8"))
    return set(consumer["supported_renderers"]) | set(consumer["supported_sub_renderers"])


def test_aoi_canary_supports_pinned_neurath_aoi_surface_without_raw_json_adaptation():
    supported = _supported_contracts()
    view_registry = get_view_registry()

    for view_key, expected_renderer in EXPECTED_VIEW_RENDERERS.items():
        view_def = view_registry.get(view_key)
        effective = resolve_effective_render_contract(
            view_def=view_def,
            rec={},
            consumer_key="aoi-canary",
            view_registry=view_registry,
        )
        renderer_type, renderer_config, _ = adapt_renderer_for_consumer(
            renderer_type=effective.renderer_type,
            renderer_config=effective.renderer_config,
            consumer_key="aoi-canary",
        )

        assert renderer_type == expected_renderer
        assert renderer_type in supported
        assert renderer_type != "raw_json"

        if view_key == "aoi_by_theme":
            default_section = (renderer_config.get("section_renderers") or {}).get("_default") or {}
            actual_sub_renderers = {
                field_key: spec.get("renderer_type")
                for field_key, spec in (default_section.get("sub_renderers") or {}).items()
                if isinstance(spec, dict)
            }
            assert actual_sub_renderers == EXPECTED_THEME_DEFAULT_SUB_RENDERERS
            assert set(actual_sub_renderers.values()) <= supported

        if view_key != "aoi_thematic_report":
            continue

        actual_sections = {
            section_key: spec.get("renderer_type")
            for section_key, spec in (renderer_config.get("section_renderers") or {}).items()
            if isinstance(spec, dict)
        }
        assert actual_sections == EXPECTED_REPORT_SECTION_RENDERERS
        assert set(actual_sections.values()) <= supported
