from types import SimpleNamespace
from unittest.mock import patch

from src.presenter.decision_trace import build_presentation_trace
from src.presenter.manifest_builder import build_effective_manifest
from src.presenter.presentation_api import assemble_page, build_presentation_manifest
from src.presenter.schemas import ViewPayload


def _base_payload() -> ViewPayload:
    return ViewPayload(
        view_key="genealogy_tp_inferential_commitments",
        view_name="Inferential Commitments",
        description="",
        renderer_type="accordion",
        renderer_config={"sections": [{"key": "commitments"}]},
        presentation_stance="diagnostic",
        priority="primary",
        rationale="Rich content",
        data_quality="rich",
        top_level_group=None,
        source_parent_view_key=None,
        promoted_to_top_level=False,
        selection_priority="primary",
        navigation_state="normal",
        semantic_scaffold_type=None,
        scaffold_hosting_mode=None,
        phase_number=1.0,
        engine_key="inferential_commitment_mapper",
        chain_key=None,
        scope="aggregated",
        has_structured_data=True,
        structured_data={"commitments": [{"commitment": "A"}]},
        reading_scaffold={"surface_type": "argument_map", "brief": "Guide"},
        raw_prose=None,
        prose_ref_view_key=None,
        items=None,
        tab_count=None,
        visibility="if_data_exists",
        position=1.3,
        children=[],
    )


def test_effective_manifest_hash_includes_consumer_key():
    payload = _base_payload()
    payloads = {payload.view_key: payload}

    with patch("src.presenter.manifest_builder.resolve_scaffold_type", return_value=None):
        critic_manifest = build_effective_manifest(
            job_id="job-1",
            plan_id="plan-1",
            consumer_key="the-critic",
            thinker_name="Markus",
            strategy_summary="summary",
            payloads=payloads,
            all_outputs=[],
            job={"created_at": "2026-03-13T00:00:00"},
        )
        mgmt_manifest = build_effective_manifest(
            job_id="job-1",
            plan_id="plan-1",
            consumer_key="analyzer-mgmt",
            thinker_name="Markus",
            strategy_summary="summary",
            payloads=payloads,
            all_outputs=[],
            job={"created_at": "2026-03-13T00:00:00"},
        )

    assert critic_manifest.consumer_key == "the-critic"
    assert mgmt_manifest.consumer_key == "analyzer-mgmt"
    assert critic_manifest.presentation_hash != mgmt_manifest.presentation_hash


def test_manifest_reports_phase2_resolver_version():
    payload = _base_payload()
    payloads = {payload.view_key: payload}

    with patch("src.presenter.manifest_builder.resolve_scaffold_type", return_value=None):
        manifest = build_effective_manifest(
            job_id="job-1",
            plan_id="plan-1",
            consumer_key="the-critic",
            thinker_name="Markus",
            strategy_summary="summary",
            payloads=payloads,
            all_outputs=[],
            job={"created_at": "2026-03-13T00:00:00"},
        )

    assert manifest.resolver_version == "bounded-dynamism-phase2"


def test_effective_manifest_adapts_visualizer_unsupported_renderer_contracts():
    card_payload = _base_payload()
    card_payload.view_key = "genealogy_per_work_scan"
    card_payload.view_name = "Per-Work Scan"
    card_payload.renderer_type = "card"
    card_payload.renderer_config = {}

    section_payload = _base_payload()
    section_payload.view_key = "genealogy_cop_path_dependencies"
    section_payload.view_name = "Path Dependencies"
    section_payload.renderer_type = "timeline_strip"
    section_payload.renderer_config = {}

    payloads = {
        card_payload.view_key: card_payload,
        section_payload.view_key: section_payload,
    }

    with patch("src.presenter.manifest_builder.resolve_scaffold_type", return_value=None):
        manifest = build_effective_manifest(
            job_id="job-1",
            plan_id="plan-1",
            consumer_key="visualizer",
            thinker_name="Markus",
            strategy_summary="summary",
            payloads=payloads,
            all_outputs=[],
            job={"created_at": "2026-03-13T00:00:00"},
        )

    by_key = {view.view_key: view for view in manifest.views}
    assert by_key["genealogy_per_work_scan"].renderer_type == "raw_json"
    assert by_key["genealogy_cop_path_dependencies"].renderer_type == "raw_json"


def test_effective_manifest_derives_integrated_scaffold_hosting_from_python_renderer_capability():
    payload = _base_payload()
    payloads = {payload.view_key: payload}

    with patch("src.presenter.manifest_builder.resolve_scaffold_type", return_value="argument_map"):
        manifest = build_effective_manifest(
            job_id="job-1",
            plan_id="plan-1",
            consumer_key="the-critic",
            thinker_name="Markus",
            strategy_summary="summary",
            payloads=payloads,
            all_outputs=[],
            job={"created_at": "2026-03-13T00:00:00"},
        )

    assert manifest.views[0].semantic_scaffold_type == "argument_map"
    assert manifest.views[0].scaffold_hosting_mode == "integrated"


def test_trace_final_stage_matches_manifest_and_page_semantics():
    payload = _base_payload()
    page_inputs = {
        "payloads": {payload.view_key: payload},
        "top_level": [payload],
        "job": {"plan_id": "plan-1", "created_at": "2026-03-13T00:00:00"},
        "plan_id": "plan-1",
        "thinker_name": "Markus",
        "strategy_summary": "summary",
        "all_outputs": [],
    }
    view_def = SimpleNamespace(
        view_key=payload.view_key,
        view_name=payload.view_name,
        description=payload.description,
        renderer_type="accordion",
        renderer_config={"sections": [{"key": "commitments"}]},
        presentation_stance="diagnostic",
        visibility="if_data_exists",
        position=1.3,
        parent_view_key=None,
        data_source=SimpleNamespace(
            phase_number=1.0,
            engine_key="inferential_commitment_mapper",
            chain_key=None,
            scope="aggregated",
            result_path="",
        ),
    )
    fake_registry = SimpleNamespace(get=lambda key: view_def if key == view_def.view_key else None)
    recommendation = {"view_key": payload.view_key, "priority": "primary", "rationale": "Rich content"}
    composition = SimpleNamespace(
        renderer_type="accordion",
        renderer_config={"sections": [{"key": "commitments"}]},
        presentation_stance="diagnostic",
        data_quality="rich",
        dropped_overrides=[],
    )
    styled_payload = payload.model_copy(
        update={
            "semantic_scaffold_type": "argument_map",
            "scaffold_hosting_mode": "integrated",
        }
    )

    with patch(
        "src.presenter.presentation_api._prepare_page_payloads",
        return_value=page_inputs,
    ), patch(
        "src.presenter.presentation_api._attach_reading_scaffolds",
        return_value=None,
    ), patch(
        "src.presenter.presentation_api._build_execution_summary",
        return_value={},
    ), patch(
        "src.presenter.presentation_api._resolve_page_style_school",
        return_value="explanatory_narrative",
    ), patch(
        "src.presenter.presentation_api.apply_cached_polish_to_views",
        return_value=([styled_payload], "polished"),
    ), patch(
        "src.presenter.presentation_api.load_view_refinement",
        return_value=None,
    ), patch(
        "src.presenter.manifest_builder.resolve_scaffold_type",
        return_value="argument_map",
    ), patch(
        "src.presenter.decision_trace.get_job",
        return_value={"plan_id": "plan-1"},
    ), patch(
        "src.presenter.decision_trace.load_plan",
        return_value=SimpleNamespace(recommended_views=[]),
    ), patch(
        "src.presenter.decision_trace._resolve_workflow_key",
        return_value="intellectual_genealogy",
    ), patch(
        "src.presenter.decision_trace._get_recommendations",
        return_value=[recommendation],
    ), patch(
        "src.presenter.decision_trace.get_default_recommendations_for_workflow",
        return_value=[recommendation],
    ), patch(
        "src.presenter.decision_trace.get_view_registry",
        return_value=fake_registry,
    ), patch(
        "src.presenter.decision_trace.resolve_effective_composition",
        return_value=composition,
    ), patch(
        "src.presenter.decision_trace.resolve_effective_render_contract",
        return_value=composition,
    ), patch(
        "src.presenter.decision_trace.load_selected_variants",
        return_value=[],
    ):
        manifest = build_presentation_manifest("job-1", consumer_key="the-critic", slim=True)
        page = assemble_page("job-1", consumer_key="the-critic", slim=True)
        trace = build_presentation_trace("job-1", consumer_key="the-critic")

    assert [view.model_dump() for view in trace.entries[-1].snapshot] == [
        view.model_dump() for view in manifest.views
    ]
    assert trace.final_manifest.model_dump() == manifest.model_dump()
    assert page.style_school == "explanatory_narrative"
    assert page.polish_state == "polished"
    assert manifest.style_school == "explanatory_narrative"
    assert manifest.polish_state == "polished"
    assert trace.style_school == "explanatory_narrative"
    assert trace.polish_state == "polished"
    assert page.views[0].selection_priority == manifest.views[0].selection_priority
    assert page.views[0].navigation_state == manifest.views[0].navigation_state
    assert page.views[0].semantic_scaffold_type == manifest.views[0].semantic_scaffold_type
    assert page.views[0].scaffold_hosting_mode == manifest.views[0].scaffold_hosting_mode
    assert page.views[0].renderer_type == manifest.views[0].renderer_type
    assert page.presentation_hash == manifest.presentation_hash
    assert page.presentation_content_hash == manifest.presentation_content_hash


def test_trace_surfaces_ignored_runtime_overrides():
    payload = _base_payload()
    page_inputs = {
        "payloads": {payload.view_key: payload},
        "top_level": [payload],
        "job": {"plan_id": "plan-1", "created_at": "2026-03-13T00:00:00"},
        "plan_id": "plan-1",
        "thinker_name": "Markus",
        "strategy_summary": "summary",
        "all_outputs": [],
    }
    view_def = SimpleNamespace(
        view_key=payload.view_key,
        view_name=payload.view_name,
        description=payload.description,
        renderer_type="accordion",
        renderer_config={"sections": [{"key": "commitments"}]},
        presentation_stance="diagnostic",
        visibility="if_data_exists",
        position=1.3,
        parent_view_key=None,
        data_source=SimpleNamespace(
            phase_number=1.0,
            engine_key="inferential_commitment_mapper",
            chain_key=None,
            scope="aggregated",
            result_path="",
        ),
    )
    fake_registry = SimpleNamespace(get=lambda key: view_def if key == view_def.view_key else None)
    recommendation = {
        "view_key": payload.view_key,
        "priority": "primary",
        "rationale": "Rich content",
        "renderer_config_overrides": {"bad_key": True},
    }
    composition = SimpleNamespace(
        renderer_type="accordion",
        renderer_config={"sections": [{"key": "commitments"}]},
        presentation_stance="diagnostic",
        data_quality="rich",
        dropped_overrides=[
            {
                "field": "renderer_config_overrides.bad_key",
                "value": True,
                "reason": "override_key_not_allowed_for_renderer:accordion",
            }
        ],
    )

    with patch(
        "src.presenter.presentation_api._prepare_page_payloads",
        return_value=page_inputs,
    ), patch(
        "src.presenter.presentation_api._attach_reading_scaffolds",
        return_value=None,
    ), patch(
        "src.presenter.presentation_api._build_execution_summary",
        return_value={},
    ), patch(
        "src.presenter.presentation_api.load_view_refinement",
        return_value=None,
    ), patch(
        "src.presenter.manifest_builder.resolve_scaffold_type",
        return_value="argument_map",
    ), patch(
        "src.presenter.decision_trace.get_job",
        return_value={"plan_id": "plan-1"},
    ), patch(
        "src.presenter.decision_trace.load_plan",
        return_value=SimpleNamespace(recommended_views=[]),
    ), patch(
        "src.presenter.decision_trace._resolve_workflow_key",
        return_value="intellectual_genealogy",
    ), patch(
        "src.presenter.decision_trace._get_recommendations",
        return_value=[recommendation],
    ), patch(
        "src.presenter.decision_trace.get_default_recommendations_for_workflow",
        return_value=[recommendation],
    ), patch(
        "src.presenter.decision_trace.get_view_registry",
        return_value=fake_registry,
    ), patch(
        "src.presenter.decision_trace.resolve_effective_composition",
        return_value=composition,
    ), patch(
        "src.presenter.decision_trace.resolve_effective_render_contract",
        return_value=composition,
    ), patch(
        "src.presenter.decision_trace.load_selected_variants",
        return_value=[],
    ):
        trace = build_presentation_trace("job-1", consumer_key="the-critic")

    assert any(
        ignored.field == "renderer_config_overrides.bad_key"
        and ignored.reason == "override_key_not_allowed_for_renderer:accordion"
        for entry in trace.entries
        for ignored in entry.ignored_changes
    )


def test_trace_records_consumer_capability_adaptation_reason():
    payload = _base_payload()
    payload.renderer_type = "raw_json"
    payload.renderer_config = {}
    page_inputs = {
        "payloads": {payload.view_key: payload},
        "top_level": [payload],
        "job": {"plan_id": "plan-1", "created_at": "2026-03-13T00:00:00"},
        "plan_id": "plan-1",
        "thinker_name": "Markus",
        "strategy_summary": "summary",
        "all_outputs": [],
    }
    view_def = SimpleNamespace(
        view_key=payload.view_key,
        view_name=payload.view_name,
        description=payload.description,
        renderer_type="accordion",
        renderer_config={"sections": [{"key": "commitments"}]},
        presentation_stance="diagnostic",
        visibility="if_data_exists",
        position=1.3,
        parent_view_key=None,
        data_source=SimpleNamespace(
            phase_number=1.0,
            engine_key="inferential_commitment_mapper",
            chain_key=None,
            scope="aggregated",
            result_path="",
        ),
    )
    fake_registry = SimpleNamespace(get=lambda key: view_def if key == view_def.view_key else None)
    recommendation = {"view_key": payload.view_key, "priority": "primary", "rationale": "Rich content"}
    composition = SimpleNamespace(
        renderer_type="accordion",
        renderer_config={"sections": [{"key": "commitments"}]},
        presentation_stance="diagnostic",
        data_quality="rich",
        dropped_overrides=[],
    )

    with patch(
        "src.presenter.presentation_api._prepare_page_payloads",
        return_value=page_inputs,
    ), patch(
        "src.presenter.presentation_api._attach_reading_scaffolds",
        return_value=None,
    ), patch(
        "src.presenter.presentation_api._build_execution_summary",
        return_value={},
    ), patch(
        "src.presenter.presentation_api.load_view_refinement",
        return_value=None,
    ), patch(
        "src.presenter.manifest_builder.resolve_scaffold_type",
        return_value="argument_map",
    ), patch(
        "src.presenter.decision_trace.get_job",
        return_value={"plan_id": "plan-1"},
    ), patch(
        "src.presenter.decision_trace.load_plan",
        return_value=SimpleNamespace(recommended_views=[]),
    ), patch(
        "src.presenter.decision_trace._resolve_workflow_key",
        return_value="intellectual_genealogy",
    ), patch(
        "src.presenter.decision_trace._get_recommendations",
        return_value=[recommendation],
    ), patch(
        "src.presenter.decision_trace.get_default_recommendations_for_workflow",
        return_value=[recommendation],
    ), patch(
        "src.presenter.decision_trace.get_view_registry",
        return_value=fake_registry,
    ), patch(
        "src.presenter.decision_trace.resolve_effective_composition",
        return_value=composition,
    ), patch(
        "src.presenter.decision_trace.resolve_effective_render_contract",
        return_value=composition,
    ), patch(
        "src.presenter.decision_trace.load_selected_variants",
        return_value=[],
    ):
        trace = build_presentation_trace("job-1", consumer_key="visualizer")

    assert trace.entries[-1].snapshot[0].renderer_type == "raw_json"
    assert any(
        ignored.reason == "renderer_not_supported_by_consumer:visualizer"
        for ignored in trace.entries[-1].ignored_changes
    )


def test_trace_surfaces_selected_variant_rationale_for_variant_driven_changes():
    payload = _base_payload()
    page_inputs = {
        "payloads": {payload.view_key: payload},
        "top_level": [payload],
        "job": {"plan_id": "plan-1", "created_at": "2026-03-13T00:00:00"},
        "plan_id": "plan-1",
        "thinker_name": "Markus",
        "strategy_summary": "summary",
        "all_outputs": [],
    }
    view_def = SimpleNamespace(
        view_key=payload.view_key,
        view_name=payload.view_name,
        description=payload.description,
        renderer_type="accordion",
        renderer_config={"sections": [{"key": "commitments"}]},
        presentation_stance="diagnostic",
        visibility="if_data_exists",
        position=1.3,
        parent_view_key=None,
        data_source=SimpleNamespace(
            phase_number=1.0,
            engine_key="inferential_commitment_mapper",
            chain_key=None,
            scope="aggregated",
            result_path="",
        ),
    )
    fake_registry = SimpleNamespace(get=lambda key: view_def if key == view_def.view_key else None)
    recommendation = {"view_key": payload.view_key, "priority": "primary", "rationale": "Rich content"}
    refinement_composition = SimpleNamespace(
        renderer_type="accordion",
        renderer_config={"sections": [{"key": "commitments"}]},
        presentation_stance="diagnostic",
        data_quality="rich",
        dropped_overrides=[],
        template_selection_reason=None,
    )
    deterministic_composition = SimpleNamespace(
        renderer_type="card_grid",
        renderer_config={"columns": 3},
        presentation_stance="diagnostic",
        data_quality="rich",
        dropped_overrides=[],
        template_selection_reason=None,
    )

    with patch(
        "src.presenter.presentation_api._prepare_page_payloads",
        return_value=page_inputs,
    ), patch(
        "src.presenter.presentation_api._attach_reading_scaffolds",
        return_value=None,
    ), patch(
        "src.presenter.presentation_api._build_execution_summary",
        return_value={},
    ), patch(
        "src.presenter.presentation_api.load_view_refinement",
        return_value=None,
    ), patch(
        "src.presenter.manifest_builder.resolve_scaffold_type",
        return_value="argument_map",
    ), patch(
        "src.presenter.decision_trace.get_job",
        return_value={"plan_id": "plan-1"},
    ), patch(
        "src.presenter.decision_trace.load_plan",
        return_value=SimpleNamespace(recommended_views=[]),
    ), patch(
        "src.presenter.decision_trace._resolve_workflow_key",
        return_value="intellectual_genealogy",
    ), patch(
        "src.presenter.decision_trace._get_recommendations",
        return_value=[recommendation],
    ), patch(
        "src.presenter.decision_trace.get_default_recommendations_for_workflow",
        return_value=[recommendation],
    ), patch(
        "src.presenter.decision_trace.get_view_registry",
        return_value=fake_registry,
    ), patch(
        "src.presenter.decision_trace.resolve_effective_composition",
        return_value=refinement_composition,
    ), patch(
        "src.presenter.decision_trace.resolve_effective_render_contract",
        return_value=deterministic_composition,
    ), patch(
        "src.presenter.decision_trace.load_selected_variants",
        return_value=[
            {
                "dimension": "renderer_type",
                "renderer_type": "card_grid",
                "renderer_config": {"columns": 3},
                "rationale": "User preferred card_grid for this view after comparison",
            }
        ],
    ):
        trace = build_presentation_trace("job-1", consumer_key="the-critic")

    deterministic_entry = next(
        entry for entry in trace.entries if entry.stage == "deterministic_contract_resolution"
    )
    assert any(
        change.field == "renderer_type"
        and change.after == "card_grid"
        and change.reason == "User preferred card_grid for this view after comparison"
        for change in deterministic_entry.applied_changes
    )
