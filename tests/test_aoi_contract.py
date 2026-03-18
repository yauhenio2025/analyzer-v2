import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.aoi.constants import AOI_WORKFLOW_KEY
from src.aoi.contract import (
    AOI_SIN_FINDINGS_ENGINE,
    _build_by_theme_payload,
    _normalize_representative_quotes,
    _normalize_source_document_ref,
    build_aoi_output_metadata,
)
from src.aoi.fixture_profiles import get_fixture_profile
from src.engines.registry import EngineRegistry
from src.objectives.registry import get_objective
from src.operationalizations.registry import get_operationalization_registry
from src.orchestrator.pipeline_schemas import AnalyzeRequest
from src.orchestrator.schemas import TargetWork
from src.presenter.composition_resolver import resolve_effective_render_contract
from src.presenter.manifest_builder import adapt_renderer_for_consumer
from src.stages.capability_composer import compose_capability_prompt
from src.transformations.registry import get_transformation_registry
from src.views.registry import get_view_registry
from src.workflows.registry import get_workflow_registry


def test_aoi_analyze_request_requires_selected_thinker_identity():
    with pytest.raises(ValueError, match="selected_source_thinker_id"):
        AnalyzeRequest(
            thinker_name="Aaron Benanav",
            target_work=TargetWork(title="Beyond Capitalism", description="target"),
            target_work_text="Target text",
            prior_works=[
                {
                    "title": "The Market: Ethics, Knowledge and Politics",
                    "text": "Source text",
                    "source_thinker_id": "john_oneill",
                    "source_thinker_name": "John O'Neill",
                    "source_document_id": "the_market_ethics_knowledge_and_politics",
                }
            ],
            workflow_key=AOI_WORKFLOW_KEY,
        )


def test_aoi_analyze_request_requires_source_document_id():
    with pytest.raises(ValueError, match="source_document_id"):
        AnalyzeRequest(
            thinker_name="Aaron Benanav",
            target_work=TargetWork(title="Beyond Capitalism", description="target"),
            target_work_text="Target text",
            prior_works=[
                {
                    "title": "The Market: Ethics, Knowledge and Politics",
                    "text": "Source text",
                    "source_thinker_id": "john_oneill",
                    "source_thinker_name": "John O'Neill",
                }
            ],
            workflow_key=AOI_WORKFLOW_KEY,
            selected_source_thinker_id="john_oneill",
            selected_source_thinker_name="John O'Neill",
        )


def test_aoi_registries_load_workflow_views_templates_and_analyzer_mgmt_contracts():
    workflow = get_workflow_registry().get(AOI_WORKFLOW_KEY)
    assert workflow is not None
    assert workflow.workflow_key == AOI_WORKFLOW_KEY
    assert [phase.engine_key for phase in workflow.phases] == [
        "aoi_thematic_synthesis",
        "aoi_engagement_mapping",
        "aoi_sin_findings",
        "aoi_thematic_report",
    ]

    engine_registry = EngineRegistry()
    assert engine_registry.get_capability_definition("aoi_thematic_synthesis") is not None
    assert engine_registry.get_capability_definition("aoi_engagement_mapping") is not None
    assert engine_registry.get_capability_definition("aoi_sin_findings") is not None
    assert engine_registry.get_capability_definition("aoi_thematic_report") is not None

    expected_view_keys = {
        "aoi_thematic_analysis",
        "aoi_source_documents",
        "aoi_by_theme",
        "aoi_by_sin_type",
        "aoi_thematic_report",
    }
    view_registry = get_view_registry()
    actual_view_keys = {view.view_key for view in view_registry.for_workflow(AOI_WORKFLOW_KEY)}
    assert expected_view_keys.issubset(actual_view_keys)

    transform_registry = get_transformation_registry()
    for template_key in (
        "aoi_source_documents_cards",
        "aoi_by_theme_nested_sections",
        "aoi_by_sin_type_cards",
        "aoi_thematic_report_sections",
    ):
        assert transform_registry.get(template_key) is not None

    objective = get_objective("influence_thematic")
    assert objective is not None
    assert objective.baseline_workflow_key == AOI_WORKFLOW_KEY
    assert objective.preferred_engine_functions == ["influence"]
    assert objective.preferred_views == ["aoi_thematic_analysis"]

    op_registry = get_operationalization_registry()
    for engine_key in (
        "aoi_thematic_synthesis",
        "aoi_engagement_mapping",
        "aoi_sin_findings",
        "aoi_thematic_report",
    ):
        op = op_registry.get(engine_key)
        assert op is not None
        assert set(op.depth_keys) == {"surface", "standard", "deep"}
        assert "discovery" in op.stance_keys

    consumer_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "consumers"
        / "definitions"
        / "analyzer-mgmt.json"
    )
    consumer = json.loads(consumer_path.read_text())
    supported = set(consumer["supported_renderers"]) | set(consumer["supported_sub_renderers"])

    for view_key in expected_view_keys:
        view_def = view_registry.get(view_key)
        effective = resolve_effective_render_contract(
            view_def=view_def,
            rec={},
            consumer_key="analyzer-mgmt",
            view_registry=view_registry,
        )
        renderer_type, renderer_config, _ = adapt_renderer_for_consumer(
            renderer_type=effective.renderer_type,
            renderer_config=effective.renderer_config,
            consumer_key="analyzer-mgmt",
        )
        assert renderer_type in supported
        for section_spec in (renderer_config.get("section_renderers") or {}).values():
            renderer_key = section_spec.get("renderer_type")
            if renderer_key is not None:
                assert renderer_key in supported
            for sub_spec in (section_spec.get("sub_renderers") or {}).values():
                assert sub_spec.get("renderer_type") in supported


def test_aoi_capability_prompt_injects_taxonomy_context():
    engine_registry = EngineRegistry()
    cap_def = engine_registry.get_capability_definition("aoi_sin_findings")

    prompt = compose_capability_prompt(cap_def, depth="standard")

    assert "AOI Sin Type Enum" in prompt.prompt
    assert "misreading" in prompt.prompt
    assert "`strategic_silence`" in prompt.prompt
    assert "Assign exactly one dominant sin type per finding." in prompt.prompt


def test_benanav_neurath_profile_owns_canonical_document_ids_and_page_hints():
    profile = get_fixture_profile("benanav_neurath")

    assert profile.selected_source_thinker_id == "otto_neurath"
    assert [doc.source_document_id for doc in profile.source_documents] == [
        "through_war_economy_to_economy_in_kind",
        "international_planning_for_freedom",
        "economic_plan_and_calculation_in_kind",
        "socialist_utility_calculation_and_capitalist_profit_calculation",
    ]
    assert all(doc.page_range_hint for doc in profile.source_documents)
    assert all(doc.title_anchors for doc in profile.source_documents)
    assert all(doc.additional_anchors for doc in profile.source_documents)
    assert "International Planning & Freedom" in profile.source_documents[1].title_aliases


def test_aoi_metadata_builds_grouped_payloads_and_stable_finding_ids():
    plan_context = {
        "workflow_key": AOI_WORKFLOW_KEY,
        "selected_source_thinker": {
            "thinker_id": "john_oneill",
            "thinker_name": "John O'Neill",
        },
        "source_documents": [
            {
                "source_document_id": "the_market_ethics_knowledge_and_politics",
                "title": "The Market: Ethics, Knowledge and Politics",
                "subtitle": "John O'Neill | 1998",
                "description": "Market ethics and political economy.",
                "badge": "John O'Neill",
            }
        ],
    }
    themes = {
        "selected_source_thinker": plan_context["selected_source_thinker"],
        "source_documents": plan_context["source_documents"],
        "themes": [
            {
                "theme_id": "theme_ecological_constraints_growth_and_physical_embeddedness",
                "theme_name": "Ecological Constraints, Growth and Physical Embeddedness",
            }
        ]
    }
    engagements = {
        "engagements": [
            {
                "theme_id": "theme_ecological_constraints_growth_and_physical_embeddedness",
                "engagement_level": "partial",
                "divergence_description": "Benanav foregrounds productivity and underplays the ecological embedding argument.",
                "severity": "medium",
                "severity_rationale": "The theme is present but materially narrowed.",
            }
        ]
    }
    content = json.dumps(
        {
            "findings": [
                {
                    "theme_id": "ecological_constraints_growth_and_physical_embeddedness",
                    "sin_type": "selective_citation",
                    "severity": "medium",
                    "severity_rationale": "The engagement is selective rather than absent.",
                    "title": "Selective use of O'Neill's ecological embeddedness argument",
                    "summary": "Benanav cites the planning debate without retaining the ecological-embedding premise.",
                    "target_chapter_key": "nlr_153",
                    "target_document_label": "NLR 153",
                    "target_locator": "pp. 14-15",
                    "target_quote": "The planning debate matters because markets cannot coordinate long-range coordination problems.",
                    "source_work_title": "The Market: Ethics, Knowledge and Politics",
                    "source_locator": "p. 88",
                    "source_quote": "Economic activity is physically embedded and cannot be assessed by price alone.",
                    "discrepancy_analysis": "The target retains the planning conclusion while trimming the ecological premise.",
                    "what_benanav_misses": "That ecological embeddedness is not an optional add-on but a constitutive part of the argument.",
                    "implication_for_argument": "The planning claim is made to look narrower and more technocratic than O'Neill's own position."
                }
            ]
        }
    )

    with patch("src.aoi.contract._load_plan_context", return_value=plan_context), patch(
        "src.aoi.contract._load_previous_normalized",
        side_effect=[themes, engagements, themes, engagements],
    ):
        first = build_aoi_output_metadata(
            job_id="job-aoi",
            phase_number=3.0,
            engine_key=AOI_SIN_FINDINGS_ENGINE,
            content=content,
        )
        second = build_aoi_output_metadata(
            job_id="job-aoi",
            phase_number=3.0,
            engine_key=AOI_SIN_FINDINGS_ENGINE,
            content=content,
        )

    first_finding = first["normalized"]["findings"][0]
    second_finding = second["normalized"]["findings"][0]

    assert first_finding["finding_id"] == second_finding["finding_id"]
    assert first_finding["theme_id"] == "theme_ecological_constraints_growth_and_physical_embeddedness"
    assert first_finding["source_document_id"] == "the_market_ethics_knowledge_and_politics"
    assert first_finding["target_chapter_key"] == "nlr_153"
    by_theme_payload = first["structured_payloads"]["aoi_by_theme"]
    assert by_theme_payload["_section_order"] == [
        "theme_ecological_constraints_growth_and_physical_embeddedness"
    ]
    assert by_theme_payload["_section_titles"] == {
        "theme_ecological_constraints_growth_and_physical_embeddedness": (
            "Ecological Constraints, Growth and Physical Embeddedness"
        )
    }
    theme_payload = by_theme_payload["theme_ecological_constraints_growth_and_physical_embeddedness"]
    assert theme_payload["overview"] == ""
    assert list(theme_payload.keys()) == [
        "overview",
        "engagement",
        "key_claims",
        "philosophical_commitments",
        "argumentative_moves",
        "source_documents",
        "findings",
    ]
    assert theme_payload["source_documents"] == []
    assert "Engagement level: partial." in theme_payload["engagement"]
    assert theme_payload["key_claims"] == []
    assert theme_payload["philosophical_commitments"] == []
    assert theme_payload["argumentative_moves"] == []
    assert theme_payload["findings"][0]["sin_type_label"] == "Selective Citation"

    by_sin_payload = first["structured_payloads"]["aoi_by_sin_type"]
    assert by_sin_payload["_section_order"] == ["selective_citation"]
    assert by_sin_payload["_section_titles"]["selective_citation"] == "Selective Citation"
    assert by_sin_payload["selective_citation"][0]["theme_name"] == (
        "Ecological Constraints, Growth and Physical Embeddedness"
    )


def test_build_by_theme_payload_uses_theme_ids_as_stable_keys_even_when_names_collide():
    themes = {
        "themes": [
            {
                "theme_id": "theme_planning_1",
                "theme_name": "Planning and Ecology",
                "overview": "First variant",
                "key_claims": ["Planning abolishes the price form"],
                "philosophical_commitments": ["Use-value is not reducible to price"],
                "argumentative_moves": ["Benanav recasts a structural claim as feasibility"],
                "source_documents": [],
            },
            {
                "theme_id": "theme_planning_2",
                "theme_name": "Planning and Ecology",
                "overview": "Second variant",
                "key_claims": ["Coordination requires social accounting"],
                "philosophical_commitments": ["Planning remains politically mediated"],
                "argumentative_moves": ["A later concession narrows the earlier claim"],
                "source_documents": [],
            },
        ]
    }
    engagements = {
        "engagements": [
            {"theme_id": "theme_planning_1", "engagement_level": "engaged"},
            {"theme_id": "theme_planning_2", "engagement_level": "partial"},
        ]
    }
    findings = {
        "findings_by_theme": {
            "theme_planning_1": [{"title": "First", "sin_type": "flattening"}],
            "theme_planning_2": [{"title": "Second", "sin_type": "strategic_silence"}],
        }
    }

    payload = _build_by_theme_payload(
        themes=themes,
        engagements=engagements,
        findings=findings,
    )

    assert payload["_section_order"] == ["theme_planning_1", "theme_planning_2"]
    assert payload["_section_titles"] == {
        "theme_planning_1": "Planning and Ecology",
        "theme_planning_2": "Planning and Ecology",
    }
    assert payload["theme_planning_1"]["overview"] == "First variant"
    assert payload["theme_planning_2"]["overview"] == "Second variant"
    assert payload["theme_planning_1"]["key_claims"] == [
        {"title": "Claim 1", "description": "Planning abolishes the price form"}
    ]
    assert payload["theme_planning_1"]["philosophical_commitments"] == [
        {"title": "Commitment 1", "description": "Use-value is not reducible to price"}
    ]
    assert payload["theme_planning_1"]["argumentative_moves"] == [
        {"title": "Move 1", "description": "Benanav recasts a structural claim as feasibility"}
    ]
    assert "theme_name" not in payload["theme_planning_1"]
    assert "theme_id" not in payload["theme_planning_2"]


def test_aoi_findings_resolve_source_document_id_from_available_inventory_when_llm_omits_it():
    plan_context = {
        "workflow_key": AOI_WORKFLOW_KEY,
        "selected_source_thinker": {
            "thinker_id": "otto_neurath",
            "thinker_name": "Otto Neurath",
        },
        "source_documents": [
            {
                "source_document_id": "international_planning_for_freedom",
                "title": "International Planning for Freedom",
                "subtitle": "Otto Neurath",
                "description": "Neurath on planning and freedom.",
                "badge": "Otto Neurath",
            }
        ],
    }
    themes = {
        "selected_source_thinker": plan_context["selected_source_thinker"],
        "source_documents": plan_context["source_documents"],
        "themes": [
            {
                "theme_id": "theme_planning",
                "theme_name": "Planning and Freedom",
            }
        ],
    }
    engagements = {"engagements": [{"theme_id": "theme_planning", "engagement_level": "partial"}]}
    content = json.dumps(
        {
            "findings": [
                {
                    "theme_id": "theme_planning",
                    "sin_type": "flattening",
                    "target_chapter_key": "nlr_153",
                    "target_quote": "Benanav treats planning as coordination only.",
                    "source_work_title": "International Planning for Freedom",
                    "title": "Planning reduced to coordination",
                    "summary": "The political stakes are narrowed away.",
                }
            ]
        }
    )

    with patch("src.aoi.contract._load_plan_context", return_value=plan_context), patch(
        "src.aoi.contract._load_previous_normalized",
        side_effect=[themes, engagements],
    ):
        metadata = build_aoi_output_metadata(
            job_id="job-aoi-neurath",
            phase_number=3.0,
            engine_key=AOI_SIN_FINDINGS_ENGINE,
            content=content,
        )

    finding = metadata["normalized"]["findings"][0]
    assert finding["source_document_id"] == "international_planning_for_freedom"


def test_source_document_ref_uses_profile_aliases_instead_of_slug_fallback():
    available_documents = [
        {
            "source_document_id": "international_planning_for_freedom",
            "title": "International Planning for Freedom",
            "subtitle": "Otto Neurath",
            "description": "Planning essay.",
            "badge": "Otto Neurath",
        }
    ]

    resolved = _normalize_source_document_ref(
        "International Planning & Freedom",
        available_documents,
        "otto_neurath",
    )

    assert resolved["source_document_id"] == "international_planning_for_freedom"
    assert resolved["title"] == "International Planning for Freedom"


def test_unmatched_source_document_ref_stays_unknown_not_title_slugified():
    resolved = _normalize_source_document_ref(
        "International Planning & Freedom",
        [],
        "john_oneill",
    )

    assert resolved["source_document_id"] == "unknown"
    assert resolved["title"] == "International Planning & Freedom"


def test_representative_quotes_use_canonical_source_document_ids_or_unknown():
    quotes = _normalize_representative_quotes(
        [
            {"source_work_title": "International Planning & Freedom", "quote": "Quoted text"},
            {"source_work_title": "Unmatched Text", "quote": "Other quote"},
        ],
        [],
        "otto_neurath",
    )

    assert quotes[0]["source_document_id"] == "international_planning_for_freedom"
    assert quotes[1]["source_document_id"] == "unknown"
