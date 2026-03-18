import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from src.presenter.presentation_bridge import prepare_presentation
from src.presenter.schemas import ViewPayload
from src.presenter.presentation_api import (
    _build_view_tree,
    _build_view_payload,
    _build_presentation_freshness,
    _get_recommendations,
    _load_aggregated_data,
    _load_per_item_data,
    _normalize_relationship_card,
    _normalize_view_structured_data,
    assemble_page,
    get_presentation_status,
    materialize_stage1_artifacts,
)
from src.presenter.scaffold_generator import (
    READING_SCAFFOLD_ARTIFACT_VERSION,
    SCAFFOLD_PROMPT_VERSIONS,
    compute_scaffold_input_hash,
)
from src.presenter.schemas import TransformationTask
from src.transformations.executor import TransformationResult


class _FakeTransformRegistry:
    def for_engine(self, engine_key):
        return [SimpleNamespace(template_key="tp_concept_evolution_extraction")]


def test_prepare_presentation_sync_can_run_inside_active_event_loop():
    task = TransformationTask(
        view_key="genealogy_tp_deep_summary",
        output_id="po-1",
        template_key="tp_deep_summary",
        engine_key="deep_summarization",
        renderer_type="accordion",
        section="deep_summary",
    )
    template = SimpleNamespace(
        transformation_type="llm_extract",
        field_mapping=None,
        llm_extraction_schema={"type": "object"},
        llm_prompt_template="Return JSON.",
        stance_key=None,
        model="test-model",
        model_fallback="test-fallback",
        max_tokens=2000,
    )

    class _FakeExecutor:
        async def execute(self, **kwargs):
            return TransformationResult(
                success=True,
                data={"summary": "ready"},
                transformation_type=kwargs["transformation_type"],
                model_used="test-model",
                execution_time_ms=12,
            )

    async def _run_under_active_loop():
        with patch(
            "src.presenter.presentation_bridge._build_transformation_tasks",
            return_value=([task], 0, []),
        ), patch(
            "src.presenter.presentation_bridge._load_output_by_id",
            return_value={"id": "po-1", "content": "Source prose"},
        ), patch(
            "src.presenter.presentation_bridge._prepare_task_content",
            return_value=("Source prose", "Source prose"),
        ), patch(
            "src.presenter.presentation_bridge.load_presentation_cache",
            return_value=None,
        ), patch(
            "src.presenter.presentation_bridge.get_transformation_executor",
            return_value=_FakeExecutor(),
        ), patch(
            "src.presenter.presentation_bridge.get_transformation_registry",
            return_value=SimpleNamespace(get=lambda key: template if key == "tp_deep_summary" else None),
        ), patch(
            "src.presenter.presentation_bridge.save_presentation_cache",
        ), patch(
            "src.presenter.presentation_bridge._validate_transform_output",
        ):
            return prepare_presentation("job-1", consumer_key="the-critic", force=True)

    result = asyncio.run(_run_under_active_loop())

    assert result.tasks_planned == 1
    assert result.tasks_completed == 1
    assert result.tasks_failed == 0
    assert result.details[0].success is True


def test_materialize_stage1_artifacts_backfills_latest_aoi_outputs():
    outputs_by_phase = {
        (1.0, "aoi_thematic_synthesis"): [
            {"id": "po-theme-old", "pass_number": 1, "created_at": "2026-03-18T12:00:00Z", "metadata": {"normalized": {"themes": ["old"]}}},
            {"id": "po-theme-new", "pass_number": 2, "created_at": "2026-03-18T12:05:00Z", "metadata": {"normalized": {"themes": ["new"]}}},
        ],
        (2.0, "aoi_engagement_mapping"): [
            {"id": "po-engagement", "pass_number": 1, "created_at": "2026-03-18T12:06:00Z", "metadata": {"normalized": {"map": []}}},
        ],
        (3.0, "aoi_sin_findings"): [
            {"id": "po-findings", "pass_number": 1, "created_at": "2026-03-18T12:07:00Z", "metadata": {"normalized": {"findings": []}}},
        ],
    }

    def _load_outputs(*, job_id, phase_number, engine_key):
        return list(outputs_by_phase.get((phase_number, engine_key), []))

    with patch(
        "src.presenter.presentation_api.get_job",
        return_value={"workflow_key": "anxiety_of_influence_thematic_single_thinker"},
    ), patch(
        "src.presenter.presentation_api.load_phase_outputs",
        side_effect=_load_outputs,
    ), patch(
        "src.analysis_products.store.record_aoi_artifact_from_metadata",
    ) as record_artifact:
        materialize_stage1_artifacts("job-aoi")

    assert record_artifact.call_count == 3
    assert record_artifact.call_args_list[0].kwargs["source_output_id"] == "po-theme-new"
    assert record_artifact.call_args_list[0].kwargs["output_metadata"] == {"normalized": {"themes": ["new"]}}
    assert record_artifact.call_args_list[1].kwargs["source_output_id"] == "po-engagement"
    assert record_artifact.call_args_list[2].kwargs["source_output_id"] == "po-findings"


def test_get_recommendations_falls_back_to_workflow_page_defaults_for_legacy_plan():
    legacy_plan = SimpleNamespace(recommended_views=[])

    with patch("src.presenter.presentation_api.load_view_refinement", return_value=None), patch(
        "src.presenter.presentation_api.load_effective_plan",
        return_value=legacy_plan,
    ), patch(
        "src.presenter.presentation_api.get_default_recommendations_for_workflow",
        return_value=[{"view_key": "genealogy_target_profile", "priority": "primary", "rationale": "Workflow page default"}],
    ) as defaults:
        rows = _get_recommendations(
            "job-legacy",
            "plan-legacy",
            workflow_key="intellectual_genealogy",
            consumer_key="analyzer-mgmt",
        )

    assert rows == [
        {
            "view_key": "genealogy_target_profile",
            "priority": "primary",
            "rationale": "Workflow page default",
        }
    ]
    defaults.assert_called_once_with(
        "intellectual_genealogy",
        consumer_key="analyzer-mgmt",
    )


def test_load_per_item_data_repairs_sluggy_work_titles_from_plan_metadata():
    outputs = [
        {
            "id": "po-1",
            "work_key": "Markus_Language_Production_md",
            "pass_number": 1,
            "content": "Per-work prose",
            "metadata": {},
        }
    ]
    cached_structured = {
        "work_title": "Markus_Language_Production_md",
        "concepts": [],
    }

    with patch(
        "src.presenter.presentation_api.load_phase_outputs",
        return_value=outputs,
    ), patch(
        "src.transformations.registry.get_transformation_registry",
        return_value=_FakeTransformRegistry(),
    ), patch(
        "src.presenter.presentation_api.load_presentation_cache",
        return_value=cached_structured,
    ), patch(
        "src.presenter.presentation_api._resolve_work_metadata",
        return_value={"display_title": "Markus Language Production", "year": 1986},
    ):
        items = _load_per_item_data(
            job_id="job-markus",
            phase_number=2.0,
            engine_key="concept_evolution",
            slim=True,
        )

    assert len(items) == 1
    assert items[0]["work_title"] == "Markus Language Production"
    assert items[0]["work_year"] == 1986
    assert items[0]["structured_data"]["work_title"] == "Markus Language Production"
    assert items[0]["structured_data"]["work_year"] == 1986


def test_load_per_item_data_overrides_wrong_model_work_title_with_plan_metadata():
    outputs = [
        {
            "id": "po-1",
            "work_key": "Markus_Language_Production_md",
            "pass_number": 1,
            "content": "Per-work prose",
            "metadata": {},
        }
    ]
    cached_structured = {
        "work_title": "Marxism and Anthropology",
        "work_year": 1978,
        "summary": "Wrong title leaked from cited predecessor.",
    }

    with patch(
        "src.presenter.presentation_api.load_phase_outputs",
        return_value=outputs,
    ), patch(
        "src.transformations.registry.get_transformation_registry",
        return_value=_FakeTransformRegistry(),
    ), patch(
        "src.presenter.presentation_api.load_presentation_cache",
        return_value=cached_structured,
    ), patch(
        "src.presenter.presentation_api._resolve_work_metadata",
        return_value={"display_title": "Markus Language Production", "year": 1986},
    ):
        items = _load_per_item_data(
            job_id="job-markus",
            phase_number=2.0,
            engine_key="concept_evolution",
            slim=True,
        )

    assert items[0]["work_title"] == "Markus Language Production"
    assert items[0]["work_year"] == 1986
    assert items[0]["structured_data"]["work_title"] == "Markus Language Production"
    assert items[0]["structured_data"]["work_year"] == 1986


def test_load_per_item_data_prefers_newest_duplicate_output_version():
    outputs = [
        {
            "id": "po-old",
            "work_key": "Markus_Language_Production_md",
            "pass_number": 2,
            "created_at": "2026-03-10T06:00:00",
            "content": "Old prose",
            "metadata": {},
        },
        {
            "id": "po-new",
            "work_key": "Markus_Language_Production_md",
            "pass_number": 2,
            "created_at": "2026-03-10T07:00:00",
            "content": "New prose",
            "metadata": {},
        },
    ]

    def _cache_lookup(output_id, section, source_content=None):
        return {
            "po-old": {"work_title": "Old Title", "summary": "old"},
            "po-new": {"work_title": "New Title", "summary": "new"},
        }.get(output_id)

    with patch(
        "src.presenter.presentation_api.load_phase_outputs",
        return_value=outputs,
    ), patch(
        "src.transformations.registry.get_transformation_registry",
        return_value=_FakeTransformRegistry(),
    ), patch(
        "src.presenter.presentation_api.load_presentation_cache",
        side_effect=_cache_lookup,
    ), patch(
        "src.presenter.presentation_api._resolve_work_metadata",
        return_value={"display_title": "Markus Language Production", "year": 1986},
    ):
        items = _load_per_item_data(
            job_id="job-markus",
            phase_number=2.0,
            engine_key="concept_evolution",
            slim=True,
        )

    assert items[0]["structured_data"]["summary"] == "new"


def test_get_presentation_status_includes_preparation_state():
    with patch(
        "src.presenter.presentation_api.get_job",
        return_value={"plan_id": "plan-1"},
    ), patch(
        "src.presenter.presentation_api._get_recommendations",
        return_value=[],
    ), patch(
        "src.presenter.presentation_api._prepare_page_payloads",
        return_value={
            "payloads": {},
            "all_outputs": [],
            "job": {"created_at": "2026-03-13T00:00:00"},
            "plan_id": "plan-1",
            "thinker_name": "",
            "strategy_summary": "",
        },
    ), patch(
        "src.presenter.presentation_api.build_effective_manifest",
        return_value=SimpleNamespace(
            presentation_contract_version=1,
            presentation_hash="hash",
            presentation_content_hash="content-hash",
            prepared_at="2026-03-13T00:00:00+00:00",
            artifacts_ready=False,
            manifest_schema_version=1,
            trace_schema_version=1,
            resolver_version="test",
        ),
    ), patch(
        "src.presenter.presentation_api.get_view_registry",
        return_value=SimpleNamespace(),
    ), patch(
        "src.presenter.presentation_bridge._build_transformation_tasks",
        return_value=([], 0, []),
    ), patch(
        "src.presenter.preparation_coordinator.get_preparation_state",
        return_value={"status": "running", "detail": "Preparing structured view data", "active": True},
    ):
        status = get_presentation_status("job-1", consumer_key="the-critic")

    assert status["preparation"]["status"] == "running"
    assert status["preparation"]["active"] is True


def test_get_presentation_status_marks_per_item_view_ready_from_cached_tasks():
    relationship_view = SimpleNamespace(
        view_key="genealogy_relationship_landscape",
        data_source=SimpleNamespace(
            phase_number=1.5,
            engine_key="genealogy_relationship_classification",
            chain_key=None,
            scope="per_item",
        ),
        transformation=SimpleNamespace(type="curated"),
        parent_view_key=None,
        status="active",
    )
    task = SimpleNamespace(
        view_key="genealogy_relationship_landscape",
        output_id="po-1",
        section="relationship_extraction:work-a",
        content_override=None,
    )

    with patch(
        "src.presenter.presentation_api.get_job",
        return_value={"plan_id": "plan-1"},
    ), patch(
        "src.presenter.presentation_api._get_recommendations",
        return_value=[{"view_key": "genealogy_relationship_landscape", "priority": "secondary"}],
    ), patch(
        "src.presenter.presentation_api._prepare_page_payloads",
        return_value={
            "payloads": {},
            "all_outputs": [],
            "job": {"created_at": "2026-03-13T00:00:00"},
            "plan_id": "plan-1",
            "thinker_name": "",
            "strategy_summary": "",
        },
    ), patch(
        "src.presenter.presentation_api.build_effective_manifest",
        return_value=SimpleNamespace(
            presentation_contract_version=1,
            presentation_hash="hash",
            presentation_content_hash="content-hash",
            prepared_at="2026-03-13T00:00:00+00:00",
            artifacts_ready=False,
            manifest_schema_version=1,
            trace_schema_version=1,
            resolver_version="test",
        ),
    ), patch(
        "src.presenter.presentation_api.get_view_registry",
        return_value=SimpleNamespace(
            get=lambda key: relationship_view if key == relationship_view.view_key else None,
            list_all=lambda: [relationship_view],
        ),
    ), patch(
        "src.presenter.preparation_coordinator.get_preparation_state",
        return_value={"status": "completed", "active": False},
    ), patch(
        "src.presenter.presentation_bridge._build_transformation_tasks",
        return_value=([task], 0, []),
    ), patch(
        "src.presenter.presentation_bridge._load_output_by_id",
        return_value={"id": "po-1", "content": "Prior work prose"},
    ), patch(
        "src.presenter.presentation_bridge._prepare_task_content",
        return_value=("Prior work prose", "Prior work prose"),
    ), patch(
        "src.presenter.presentation_api.load_presentation_cache",
        return_value={"summary": "cached"},
    ):
        status = get_presentation_status("job-1", consumer_key="the-critic")

    row = status["views"][0]
    assert row["status"] == "ready"
    assert row["has_structured_data"] is True


def test_get_presentation_status_marks_chain_container_ready_from_children():
    parent_view = SimpleNamespace(
        view_key="genealogy_target_profile",
        data_source=SimpleNamespace(
            phase_number=1.0,
            engine_key=None,
            chain_key="genealogy_target_profiling",
            scope="aggregated",
        ),
        transformation=SimpleNamespace(type="none"),
        parent_view_key=None,
        status="active",
    )
    child_view = SimpleNamespace(
        view_key="genealogy_tp_semantic_constellation",
        data_source=SimpleNamespace(
            phase_number=1.0,
            engine_key="concept_semantic_constellation",
            chain_key=None,
            scope="aggregated",
        ),
        transformation=SimpleNamespace(type="curated"),
        parent_view_key="genealogy_target_profile",
        status="active",
    )
    child_task = SimpleNamespace(
        view_key="genealogy_tp_semantic_constellation",
        output_id="po-child",
        section="tp_semantic_constellation_extraction",
        content_override=None,
    )

    fake_registry = SimpleNamespace(
        get=lambda key: {
            parent_view.view_key: parent_view,
            child_view.view_key: child_view,
        }.get(key),
        list_all=lambda: [parent_view, child_view],
    )

    with patch(
        "src.presenter.presentation_api.get_job",
        return_value={"plan_id": "plan-1"},
    ), patch(
        "src.presenter.presentation_api._get_recommendations",
        return_value=[
            {"view_key": "genealogy_target_profile", "priority": "secondary"},
            {"view_key": "genealogy_tp_semantic_constellation", "priority": "secondary"},
        ],
    ), patch(
        "src.presenter.presentation_api._prepare_page_payloads",
        return_value={
            "payloads": {},
            "all_outputs": [],
            "job": {"created_at": "2026-03-13T00:00:00"},
            "plan_id": "plan-1",
            "thinker_name": "",
            "strategy_summary": "",
        },
    ), patch(
        "src.presenter.presentation_api.build_effective_manifest",
        return_value=SimpleNamespace(
            presentation_contract_version=1,
            presentation_hash="hash",
            presentation_content_hash="content-hash",
            prepared_at="2026-03-13T00:00:00+00:00",
            artifacts_ready=False,
            manifest_schema_version=1,
            trace_schema_version=1,
            resolver_version="test",
        ),
    ), patch(
        "src.presenter.presentation_api.get_view_registry",
        return_value=fake_registry,
    ), patch(
        "src.presenter.preparation_coordinator.get_preparation_state",
        return_value={"status": "completed", "active": False},
    ), patch(
        "src.presenter.presentation_bridge._build_transformation_tasks",
        return_value=([child_task], 1, []),
    ), patch(
        "src.presenter.presentation_bridge._load_output_by_id",
        return_value={"id": "po-child", "content": "Child prose"},
    ), patch(
        "src.presenter.presentation_bridge._prepare_task_content",
        return_value=("Child prose", "Child prose"),
    ), patch(
        "src.presenter.presentation_api.load_presentation_cache",
        return_value={"summary": "cached"},
    ):
        status = get_presentation_status("job-1", consumer_key="the-critic")

    rows = {row["view_key"]: row for row in status["views"]}
    assert rows["genealogy_tp_semantic_constellation"]["status"] == "ready"
    assert rows["genealogy_target_profile"]["status"] == "ready"
    assert rows["genealogy_target_profile"]["derived_from_children"] is True


def test_get_presentation_status_marks_result_path_child_ready_from_parent():
    parent_view = SimpleNamespace(
        view_key="genealogy_conditions",
        data_source=SimpleNamespace(
            phase_number=3.0,
            engine_key="conditions_of_possibility_analyzer",
            chain_key=None,
            scope="aggregated",
            result_path=None,
        ),
        transformation=SimpleNamespace(type="curated"),
        parent_view_key=None,
        status="active",
    )
    child_view = SimpleNamespace(
        view_key="genealogy_cop_path_dependencies",
        data_source=SimpleNamespace(
            phase_number=3.0,
            engine_key="conditions_of_possibility_analyzer",
            chain_key=None,
            scope="aggregated",
            result_path="path_dependencies",
        ),
        transformation=SimpleNamespace(type="none"),
        parent_view_key="genealogy_conditions",
        status="active",
    )
    parent_task = SimpleNamespace(
        view_key="genealogy_conditions",
        output_id="po-parent",
        section="conditions_extraction",
        content_override=None,
    )

    fake_registry = SimpleNamespace(
        get=lambda key: {
            parent_view.view_key: parent_view,
            child_view.view_key: child_view,
        }.get(key),
        list_all=lambda: [parent_view, child_view],
    )

    with patch(
        "src.presenter.presentation_api.get_job",
        return_value={"plan_id": "plan-1"},
    ), patch(
        "src.presenter.presentation_api._get_recommendations",
        return_value=[
            {"view_key": "genealogy_conditions", "priority": "primary"},
            {"view_key": "genealogy_cop_path_dependencies", "priority": "secondary"},
        ],
    ), patch(
        "src.presenter.presentation_api._prepare_page_payloads",
        return_value={
            "payloads": {},
            "all_outputs": [],
            "job": {"created_at": "2026-03-13T00:00:00"},
            "plan_id": "plan-1",
            "thinker_name": "",
            "strategy_summary": "",
        },
    ), patch(
        "src.presenter.presentation_api.build_effective_manifest",
        return_value=SimpleNamespace(
            presentation_contract_version=1,
            presentation_hash="hash",
            presentation_content_hash="content-hash",
            prepared_at="2026-03-13T00:00:00+00:00",
            artifacts_ready=False,
            manifest_schema_version=1,
            trace_schema_version=1,
            resolver_version="test",
        ),
    ), patch(
        "src.presenter.presentation_api.get_view_registry",
        return_value=fake_registry,
    ), patch(
        "src.presenter.preparation_coordinator.get_preparation_state",
        return_value={"status": "completed", "active": False},
    ), patch(
        "src.presenter.presentation_bridge._build_transformation_tasks",
        return_value=([parent_task], 0, []),
    ), patch(
        "src.presenter.presentation_bridge._load_output_by_id",
        return_value={"id": "po-parent", "content": "Parent prose"},
    ), patch(
        "src.presenter.presentation_bridge._prepare_task_content",
        return_value=("Parent prose", "Parent prose"),
    ), patch(
        "src.presenter.presentation_api.load_presentation_cache",
        return_value={"synthetic_judgment": "cached"},
    ):
        status = get_presentation_status("job-1", consumer_key="the-critic")

    rows = {row["view_key"]: row for row in status["views"]}
    assert rows["genealogy_conditions"]["status"] == "ready"
    assert rows["genealogy_cop_path_dependencies"]["status"] == "ready"
    assert rows["genealogy_cop_path_dependencies"]["derived_from_parent"] == "genealogy_conditions"


def test_build_presentation_freshness_ignores_unstable_output_metadata():
    payload = SimpleNamespace(
        view_key="genealogy_tp_inferential_commitments",
        renderer_type="accordion",
        presentation_stance="diagnostic",
        position=1.3,
        visibility="if_data_exists",
        source_parent_view_key="genealogy_target_profile",
        promoted_to_top_level=False,
        top_level_group=None,
        renderer_config={"sections": [{"key": "commitments"}, {"key": "backings"}]},
        children=[],
        structured_data={"commitments": [{"commitment": "A"}]},
        raw_prose=None,
        items=None,
        reading_scaffold={"surface_type": "argument_map", "brief": "Guide"},
        has_structured_data=True,
        phase_number=1.0,
        engine_key="inferential_commitment_mapper",
        chain_key=None,
        scope="aggregated",
    )
    payloads = {payload.view_key: payload}

    first = _build_presentation_freshness(
        job_id="job-1",
        payloads=payloads,
        all_outputs=[{
            "id": "po-1",
            "phase_number": 1.0,
            "engine_key": "inferential_commitment_mapper",
            "pass_number": 1,
            "created_at": "2026-03-13T01:00:00",
            "content_hash": "same-hash",
        }],
        job={"created_at": "2026-03-13T00:00:00"},
    )
    second = _build_presentation_freshness(
        job_id="job-1",
        payloads=payloads,
        all_outputs=[{
            "id": "po-999",
            "phase_number": 1.0,
            "engine_key": "inferential_commitment_mapper",
            "pass_number": 99,
            "created_at": "2026-03-13T09:00:00",
            "content_hash": "same-hash",
        }],
        job={"created_at": "2026-03-13T08:00:00"},
    )

    assert first["presentation_hash"] == second["presentation_hash"]
    assert first["presentation_content_hash"] == second["presentation_content_hash"]


def test_assemble_page_includes_freshness_fields():
    payload = ViewPayload(
        view_key="genealogy_tp_inferential_commitments",
        renderer_type="accordion",
        view_name="Inferential Commitments",
        description="",
        presentation_stance="diagnostic",
        position=1.3,
        visibility="if_data_exists",
        source_parent_view_key=None,
        promoted_to_top_level=False,
        top_level_group=None,
        renderer_config={"sections": [{"key": "commitments"}]},
        children=[],
        structured_data={"commitments": [{"commitment": "A"}]},
        raw_prose=None,
        items=None,
        reading_scaffold=None,
        has_structured_data=True,
        phase_number=1.0,
        engine_key="inferential_commitment_mapper",
        chain_key=None,
        scope="aggregated",
    )

    with patch(
        "src.presenter.presentation_api._prepare_page_payloads",
        return_value={
            "payloads": {payload.view_key: payload},
            "top_level": [payload],
            "job": {"created_at": "2026-03-13T00:00:00"},
            "plan_id": "plan-1",
            "thinker_name": "Markus",
            "strategy_summary": "summary",
            "all_outputs": [],
        },
    ), patch(
        "src.presenter.presentation_api._attach_reading_scaffolds",
        return_value=None,
    ), patch(
        "src.presenter.presentation_api._build_execution_summary",
        return_value={},
    ), patch(
        "src.presenter.presentation_api.load_view_refinement",
        return_value=None,
    ):
        page = assemble_page("job-1", consumer_key="the-critic", slim=True)

    assert page.presentation_contract_version == 1
    assert page.presentation_hash
    assert page.presentation_content_hash
    assert page.prepared_at
    assert page.artifacts_ready is True


def test_assemble_page_preserves_markus_child_contract_and_attaches_scaffold():
    parent = ViewPayload(
        view_key="genealogy_target_profile",
        view_name="Target Profile",
        description="",
        renderer_type="tab",
        renderer_config={"sections": [{"key": "inferential_commitments"}]},
        presentation_stance="summary",
        position=1.0,
        visibility="if_data_exists",
        source_parent_view_key=None,
        promoted_to_top_level=False,
        top_level_group=None,
        children=[],
        structured_data={"inferential_commitments": True},
        raw_prose=None,
        items=None,
        reading_scaffold=None,
        has_structured_data=True,
        phase_number=1.0,
        engine_key=None,
        chain_key="genealogy_target_profiling",
        scope="aggregated",
    )
    child = ViewPayload(
        view_key="genealogy_tp_inferential_commitments",
        view_name="Inferential Commitments",
        description="",
        renderer_type="accordion",
        renderer_config={
            "sections": [
                {"key": "commitments"},
                {"key": "backings"},
                {"key": "hidden_premises"},
                {"key": "argumentative_structure"},
            ]
        },
        presentation_stance="diagnostic",
        position=1.3,
        visibility="if_data_exists",
        source_parent_view_key="genealogy_target_profile",
        promoted_to_top_level=False,
        top_level_group=None,
        children=[],
        structured_data={
            "commitments": [{"commitment": "Labor is constitutive", "type": "ontological"}],
            "backings": [{"backing": "Marx", "type": "authoritative"}],
            "hidden_premises": [{"premise": "Sociality grounds normativity"}],
            "argumentative_structure": "A dense inferential architecture.",
        },
        raw_prose=None,
        items=None,
        reading_scaffold=None,
        has_structured_data=True,
        phase_number=1.0,
        engine_key="inferential_commitment_mapper",
        chain_key=None,
        scope="aggregated",
    )
    parent.children = [child]
    payloads = {
        parent.view_key: parent,
        child.view_key: child,
    }
    child_scaffold = {
        "surface_type": "argument_map",
        "brief": "A guide to the inferential structure.",
        "how_to_read": "Start with commitments, then read the backings.",
        "blocks": [],
        "section_intros": [],
    }

    fake_registry = SimpleNamespace(
        get=lambda key: {
            "genealogy_target_profile": SimpleNamespace(
                view_key="genealogy_target_profile",
                scaffold_contract=None,
                surface_archetype=None,
            ),
            "genealogy_tp_inferential_commitments": SimpleNamespace(
                view_key="genealogy_tp_inferential_commitments",
                scaffold_contract=SimpleNamespace(type="argument_map"),
                surface_archetype=None,
            ),
        }.get(key)
    )
    child_hash = compute_scaffold_input_hash(child, payloads)
    artifact_batch = {
        (
            child.view_key,
            READING_SCAFFOLD_ARTIFACT_VERSION,
            SCAFFOLD_PROMPT_VERSIONS["argument_map"],
            child_hash,
        ): child_scaffold
    }

    with patch(
        "src.presenter.presentation_api._prepare_page_payloads",
        return_value={
            "payloads": payloads,
            "top_level": [parent],
            "job": {"created_at": "2026-03-13T00:00:00"},
            "plan_id": "plan-markus",
            "thinker_name": "Markus",
            "strategy_summary": "summary",
            "all_outputs": [],
        },
    ), patch(
        "src.presenter.presentation_api.get_view_registry",
        return_value=fake_registry,
    ), patch(
        "src.presenter.presentation_api.load_presentation_artifact_batch",
        return_value=artifact_batch,
    ), patch(
        "src.presenter.presentation_api._build_execution_summary",
        return_value={},
    ), patch(
        "src.presenter.presentation_api.load_view_refinement",
        return_value=None,
    ), patch(
        "src.presenter.presentation_api.resolve_scaffold_type",
        side_effect=lambda payload, *_args, **_kwargs: (
            "argument_map"
            if payload.view_key == "genealogy_tp_inferential_commitments"
            else None
        ),
    ):
        page = assemble_page("job-markus", consumer_key="the-critic", slim=True)

    assembled_parent = page.views[0]
    assembled_child = assembled_parent.children[0]

    assert assembled_child.renderer_type == "accordion"
    assert assembled_child.reading_scaffold == child_scaffold


def test_build_view_payload_preserves_root_when_renderer_declares_items_path():
    view_def = SimpleNamespace(
        view_key="genealogy_tactics",
        view_name="Tactics",
        description="",
        renderer_type="card_grid",
        renderer_config={
            "items_path": "tactics_detected",
            "summary": {"data_path": "tactic_patterns"},
        },
        presentation_stance="evidence",
        visibility="if_data_exists",
        position=1.0,
        data_source=SimpleNamespace(
            phase_number=3.0,
            engine_key="evolution_tactics_detector",
            chain_key=None,
            scope="aggregated",
            result_path="tactics_detected",
        ),
    )

    with patch(
        "src.presenter.presentation_api.resolve_effective_render_contract",
        return_value=SimpleNamespace(
            renderer_type="card_grid",
            renderer_config={
                "items_path": "tactics_detected",
                "summary": {"data_path": "tactic_patterns"},
            },
            presentation_stance="evidence",
            data_quality="rich",
        ),
    ), patch(
        "src.presenter.presentation_api._load_aggregated_data",
        return_value=(
            {
                "tactics_detected": [{"tactic_name": "A shift"}],
                "tactic_patterns": {"most_frequent_tactic": "scope_expansion"},
            },
            None,
        ),
    ), patch(
        "src.presenter.presentation_api._validate_payload_data",
        return_value=None,
    ):
        payload = _build_view_payload(
            view_def=view_def,
            rec={"view_key": "genealogy_tactics"},
            job_id="job-1",
            consumer_key="the-critic",
        )

    assert payload.structured_data == {
        "tactics_detected": [{"tactic_name": "A shift"}],
        "tactic_patterns": {"most_frequent_tactic": "scope_expansion"},
    }
    assert payload.has_structured_data is True


def test_build_view_payload_normalizes_timeline_result_path_items():
    view_def = SimpleNamespace(
        view_key="genealogy_cop_path_dependencies",
        view_name="Path Dependencies",
        description="",
        renderer_type="timeline",
        renderer_config={"label_field": "description"},
        presentation_stance="narrative",
        visibility="if_data_exists",
        position=1.0,
        data_source=SimpleNamespace(
            phase_number=3.0,
            engine_key="conditions_of_possibility_analyzer",
            chain_key=None,
            scope="aggregated",
            result_path="path_dependencies",
        ),
    )

    with patch(
        "src.presenter.presentation_api.resolve_effective_render_contract",
        return_value=SimpleNamespace(
            renderer_type="timeline",
            renderer_config={"label_field": "description"},
            presentation_stance="narrative",
            data_quality="rich",
        ),
    ), patch(
        "src.presenter.presentation_api._load_aggregated_data",
        return_value=(
            {
                "path_dependencies": [
                    {
                        "description": "From aporia to language turn",
                        "chain": ["1979 aporia", "1986 language turn"],
                        "if_absent": "The project would stay anthropological",
                    }
                ]
            },
            None,
        ),
    ), patch(
        "src.presenter.presentation_api._validate_payload_data",
        return_value=None,
    ):
        payload = _build_view_payload(
            view_def=view_def,
            rec={"view_key": "genealogy_cop_path_dependencies"},
            job_id="job-1",
            consumer_key="the-critic",
        )

    assert payload.structured_data == [
        {
            "description": "From aporia to language turn",
            "chain": ["1979 aporia", "1986 language turn"],
            "if_absent": "The project would stay anthropological",
            "label": "From aporia to language turn",
            "date": 1,
        }
    ]


def test_build_view_payload_defers_chain_container_structured_data_to_children():
    parent_view = SimpleNamespace(
        view_key="genealogy_target_profile",
        view_name="Target Work Profile",
        description="",
        renderer_type="accordion",
        renderer_config={"sections": [{"key": "conceptual_framework", "title": "Conceptual Framework"}]},
        presentation_stance="diagnostic",
        visibility="if_data_exists",
        position=1.0,
        transformation=SimpleNamespace(type="none"),
        data_source=SimpleNamespace(
            phase_number=1.0,
            engine_key=None,
            chain_key="genealogy_target_profiling",
            scope="aggregated",
            result_path="",
        ),
    )
    child_view = SimpleNamespace(
        view_key="genealogy_tp_conceptual_framework",
        view_name="Conceptual Framework",
        parent_view_key="genealogy_target_profile",
        status="active",
    )
    fake_registry = SimpleNamespace(
        list_all=lambda: [parent_view, child_view],
    )

    with patch(
        "src.presenter.presentation_api.resolve_effective_render_contract",
        return_value=SimpleNamespace(
            renderer_type="accordion",
            renderer_config={"sections": [{"key": "conceptual_framework", "title": "Conceptual Framework"}]},
            presentation_stance="diagnostic",
            data_quality="rich",
        ),
    ), patch(
        "src.presenter.presentation_api._load_aggregated_data",
        return_value=({"frameworks": [{"name": "Wrong child blob"}]}, "raw prose"),
    ):
        payload = _build_view_payload(
            view_def=parent_view,
            rec={"view_key": "genealogy_target_profile", "priority": "primary"},
            job_id="job-1",
            consumer_key="the-critic",
            view_registry=fake_registry,
        )

    assert payload.structured_data is None
    assert payload.has_structured_data is False
    assert payload.raw_prose == "raw prose"


def test_build_view_payload_emits_phase2a_structuring_semantics_for_chain_container_parent():
    parent_view = SimpleNamespace(
        view_key="genealogy_target_profile",
        view_name="Target Work Profile",
        description="",
        renderer_type="accordion",
        renderer_config={"sections": [{"key": "conceptual_framework", "title": "Conceptual Framework"}]},
        presentation_stance="diagnostic",
        visibility="if_data_exists",
        position=1.0,
        transformation=SimpleNamespace(type="none"),
        surface_archetype="composite_overview",
        surface_role="parent_surface",
        child_display_mode="deep_dives",
        data_source=SimpleNamespace(
            phase_number=1.0,
            engine_key=None,
            chain_key="genealogy_target_profiling",
            scope="aggregated",
            result_path="",
        ),
    )
    child_view = SimpleNamespace(
        view_key="genealogy_tp_conceptual_framework",
        view_name="Conceptual Framework",
        parent_view_key="genealogy_target_profile",
        status="active",
    )
    fake_registry = SimpleNamespace(
        list_all=lambda: [parent_view, child_view],
    )

    with patch(
        "src.presenter.presentation_api.resolve_effective_render_contract",
        return_value=SimpleNamespace(
            renderer_type="accordion",
            renderer_config={"sections": [{"key": "conceptual_framework", "title": "Conceptual Framework"}]},
            presentation_stance="diagnostic",
            data_quality="rich",
        ),
    ), patch(
        "src.presenter.presentation_api._load_aggregated_data",
        return_value=({"frameworks": [{"name": "Ignored"}]}, None),
    ):
        payload = _build_view_payload(
            view_def=parent_view,
            rec={"view_key": "genealogy_target_profile", "priority": "primary"},
            job_id="job-1",
            consumer_key="the-critic",
            view_registry=fake_registry,
        )

    assert payload.structuring_policy == "overview_parent"
    assert payload.derivation_kind == "child_synthesized"


def test_build_view_payload_defers_structuring_semantics_for_non_activated_parent():
    parent_view = SimpleNamespace(
        view_key="genealogy_conditions",
        view_name="Conditions of Possibility",
        description="",
        renderer_type="accordion",
        renderer_config={"sections": [{"key": "path_dependencies", "title": "Path Dependencies"}]},
        presentation_stance="diagnostic",
        visibility="if_data_exists",
        position=1.0,
        transformation=SimpleNamespace(type="none"),
        surface_archetype="composite_overview",
        surface_role="parent_surface",
        child_display_mode="deep_dives",
        data_source=SimpleNamespace(
            phase_number=3.0,
            engine_key="conditions_of_possibility_analyzer",
            chain_key=None,
            scope="aggregated",
            result_path="",
        ),
    )
    child_view = SimpleNamespace(
        view_key="genealogy_cop_path_dependencies",
        view_name="Path Dependencies",
        parent_view_key="genealogy_conditions",
        status="active",
    )
    fake_registry = SimpleNamespace(
        list_all=lambda: [parent_view, child_view],
    )

    with patch(
        "src.presenter.presentation_api.resolve_effective_render_contract",
        return_value=SimpleNamespace(
            renderer_type="accordion",
            renderer_config={"sections": [{"key": "path_dependencies", "title": "Path Dependencies"}]},
            presentation_stance="diagnostic",
            data_quality="rich",
        ),
    ), patch(
        "src.presenter.presentation_api._load_aggregated_data",
        return_value=({"conditions": [{"name": "A"}]}, None),
    ):
        payload = _build_view_payload(
            view_def=parent_view,
            rec={"view_key": "genealogy_conditions", "priority": "primary"},
            job_id="job-1",
            consumer_key="the-critic",
            view_registry=fake_registry,
        )

    assert payload.structuring_policy is None
    assert payload.derivation_kind is None


def test_build_view_payload_inherits_parent_section_renderer_contract():
    parent_view = SimpleNamespace(
        view_key="genealogy_conditions",
        view_name="Conditions of Possibility",
        renderer_config={
            "sections": [{"key": "path_dependencies", "title": "Path Dependencies"}],
            "section_renderers": {
                "path_dependencies": {
                    "renderer_type": "timeline_strip",
                    "config": {
                        "label_field": "description",
                        "stages_field": "chain",
                        "section_description": "Inherited renderer contract",
                    },
                }
            },
        },
        status="active",
    )
    child_view = SimpleNamespace(
        view_key="genealogy_cop_path_dependencies",
        view_name="Path Dependencies",
        description="",
        renderer_type="timeline",
        renderer_config={"counterfactual_field": "if_absent"},
        presentation_stance="narrative",
        visibility="if_data_exists",
        position=1.0,
        parent_view_key="genealogy_conditions",
        data_source=SimpleNamespace(
            phase_number=3.0,
            engine_key="conditions_of_possibility_analyzer",
            chain_key=None,
            scope="aggregated",
            result_path="path_dependencies",
        ),
    )
    fake_registry = SimpleNamespace(
        get=lambda key: {
            parent_view.view_key: parent_view,
            child_view.view_key: child_view,
        }.get(key),
        list_all=lambda: [parent_view, child_view],
    )

    with patch(
        "src.presenter.presentation_api._load_aggregated_data",
        return_value=(
            {
                "path_dependencies": [
                    {
                        "description": "From critique to ecological reconstruction",
                        "chain": ["1979", "1986", "ecological reconstruction"],
                        "if_absent": "The ecological turn would not land",
                    }
                ]
            },
            None,
        ),
    ), patch(
        "src.presenter.presentation_api._validate_payload_data",
        return_value=None,
    ), patch(
        "src.presenter.composition_resolver.load_selected_variants",
        return_value=[],
    ):
        payload = _build_view_payload(
            view_def=child_view,
            rec={"view_key": "genealogy_cop_path_dependencies"},
            job_id="job-1",
            consumer_key="the-critic",
            view_registry=fake_registry,
        )

    assert payload.renderer_type == "timeline_strip"
    assert payload.renderer_config["stages_field"] == "chain"
    assert payload.renderer_config["counterfactual_field"] == "if_absent"
    assert payload.renderer_config["_parentSectionKey"] == "path_dependencies"
    assert payload.renderer_config["_parentSectionTitle"] == "Path Dependencies"
    assert payload.structured_data == [
        {
            "description": "From critique to ecological reconstruction",
            "chain": ["1979", "1986", "ecological reconstruction"],
            "if_absent": "The ecological turn would not land",
        }
    ]


def test_load_aggregated_data_prefers_view_key_structured_payload_over_cache_lookup():
    outputs = [
        {
            "id": "po-aoi",
            "pass_number": 1,
            "content": "{\"findings\":[]}",
            "metadata": {
                "structured_payloads": {
                    "aoi_by_theme": {
                        "Ecological Constraints": {
                            "overview": {"summary": "Theme overview"},
                            "engagement": {"engagement_level": "partial"},
                            "findings": [],
                        }
                    }
                }
            },
        }
    ]
    cache_calls = []

    def _cache_lookup(*, output_id, section, source_content=None):
        cache_calls.append((output_id, section))
        return {"wrong": "template cache should not win"}

    with patch(
        "src.presenter.presentation_api.load_phase_outputs",
        return_value=outputs,
    ), patch(
        "src.presenter.presentation_api.load_presentation_cache",
        side_effect=_cache_lookup,
    ):
        structured_data, raw_prose = _load_aggregated_data(
            job_id="job-aoi",
            phase_number=3.0,
            engine_key="aoi_sin_findings",
            chain_key=None,
            view_key="aoi_by_theme",
            slim=False,
        )

    assert structured_data == {
        "Ecological Constraints": {
            "overview": {"summary": "Theme overview"},
            "engagement": {"engagement_level": "partial"},
            "findings": [],
        }
    }
    assert raw_prose == "{\"findings\":[]}"
    assert cache_calls == []


def test_build_view_payload_derives_dynamic_accordion_sections_from_structured_payload():
    view_def = SimpleNamespace(
        view_key="aoi_by_theme",
        view_name="By Theme",
        description="",
        renderer_type="accordion",
        renderer_config={"expand_first": True},
        presentation_stance="comparison",
        visibility="if_data_exists",
        position=1.2,
        data_source=SimpleNamespace(
            phase_number=3.0,
            engine_key="aoi_sin_findings",
            chain_key=None,
            scope="aggregated",
            result_path="",
        ),
    )

    with patch(
        "src.presenter.presentation_api.resolve_effective_render_contract",
        return_value=SimpleNamespace(
            renderer_type="accordion",
            renderer_config={
                "expand_first": True,
                "section_renderers": {
                    "_default": {
                        "sub_renderers": {
                            "overview": {"renderer_type": "annotated_prose"},
                            "findings": {"renderer_type": "mini_card_list"},
                        }
                    },
                    "sin_findings": {"renderer_type": "mini_card_list"},
                },
            },
            presentation_stance="comparison",
            data_quality="rich",
        ),
    ), patch(
        "src.presenter.presentation_api._load_aggregated_data",
        return_value=(
            {
                "_section_order": ["theme_ecological_constraints"],
                "_section_titles": {
                    "theme_ecological_constraints": (
                        "Ecological Constraints, Growth and Physical Embeddedness"
                    )
                },
                "theme_ecological_constraints": {
                    "overview": "Theme overview",
                    "engagement": "Engagement level: partial.",
                    "findings": [],
                }
            },
            None,
        ),
    ), patch(
        "src.presenter.presentation_api._validate_payload_data",
        return_value=None,
    ):
        payload = _build_view_payload(
            view_def=view_def,
            rec={"view_key": "aoi_by_theme"},
            job_id="job-aoi",
            consumer_key="the-critic",
        )

    assert payload.has_structured_data is True
    assert payload.renderer_config["sections"] == [
        {
            "key": "theme_ecological_constraints",
            "title": "Ecological Constraints, Growth and Physical Embeddedness",
        }
    ]
    assert payload.renderer_config["section_renderers"] == {
        "_default": {
            "sub_renderers": {
                "overview": {"renderer_type": "annotated_prose"},
                "findings": {"renderer_type": "mini_card_list"},
            }
        }
    }


def test_build_view_tree_synthesizes_container_structured_data_from_children():
    parent_view = SimpleNamespace(
        view_key="genealogy_target_profile",
        view_name="Target Work Profile",
        parent_view_key=None,
        position=1.0,
        status="active",
        renderer_config={
            "sections": [
                {"key": "conceptual_framework", "title": "Conceptual Framework"},
                {"key": "semantic_constellation", "title": "Semantic Constellation"},
            ]
        },
        transformation=SimpleNamespace(type="none"),
        data_source=SimpleNamespace(
            phase_number=1.0,
            engine_key=None,
            chain_key="genealogy_target_profiling",
            scope="aggregated",
        ),
    )
    conceptual_child_def = SimpleNamespace(
        view_key="genealogy_tp_conceptual_framework",
        view_name="Conceptual Framework",
        parent_view_key="genealogy_target_profile",
        position=1.1,
        status="active",
    )
    semantic_child_def = SimpleNamespace(
        view_key="genealogy_tp_semantic_constellation",
        view_name="Semantic Constellation",
        parent_view_key="genealogy_target_profile",
        position=1.2,
        status="active",
    )
    fake_registry = SimpleNamespace(
        get=lambda key: {
            parent_view.view_key: parent_view,
            conceptual_child_def.view_key: conceptual_child_def,
            semantic_child_def.view_key: semantic_child_def,
        }.get(key),
        list_all=lambda: [parent_view, conceptual_child_def, semantic_child_def],
    )

    payloads = {
        "genealogy_target_profile": SimpleNamespace(
            view_key="genealogy_target_profile",
            position=1.0,
            structured_data=None,
            has_structured_data=False,
            children=[],
        ),
        "genealogy_tp_conceptual_framework": SimpleNamespace(
            view_key="genealogy_tp_conceptual_framework",
            position=1.1,
            source_parent_view_key="genealogy_target_profile",
            structured_data={"frameworks": [{"framework_name": "Objectivation"}]},
            has_structured_data=True,
            children=[],
        ),
        "genealogy_tp_semantic_constellation": SimpleNamespace(
            view_key="genealogy_tp_semantic_constellation",
            position=1.2,
            source_parent_view_key="genealogy_target_profile",
            structured_data={"core_concepts": [{"term": "objectivation"}]},
            has_structured_data=True,
            children=[],
        ),
    }

    top_level = _build_view_tree(payloads, fake_registry)

    assert len(top_level) == 1
    parent_payload = top_level[0]
    assert parent_payload.has_structured_data is True
    assert parent_payload.structured_data == {
        "conceptual_framework": {"frameworks": [{"framework_name": "Objectivation"}]},
        "semantic_constellation": {"core_concepts": [{"term": "objectivation"}]},
    }


def test_build_view_tree_preserves_child_specific_payload_when_parent_is_synthesized():
    parent_view = SimpleNamespace(
        view_key="genealogy_target_profile",
        view_name="Target Work Profile",
        parent_view_key=None,
        position=1.0,
        status="active",
        renderer_config={
            "sections": [
                {"key": "semantic_constellation", "title": "Semantic Constellation"},
            ]
        },
        transformation=SimpleNamespace(type="none"),
        data_source=SimpleNamespace(
            phase_number=1.0,
            engine_key=None,
            chain_key="genealogy_target_profiling",
            scope="aggregated",
        ),
    )
    child_view = SimpleNamespace(
        view_key="genealogy_tp_semantic_constellation",
        view_name="Semantic Constellation",
        parent_view_key="genealogy_target_profile",
        position=1.2,
        status="active",
    )
    fake_registry = SimpleNamespace(
        get=lambda key: {
            parent_view.view_key: parent_view,
            child_view.view_key: child_view,
        }.get(key),
        list_all=lambda: [parent_view, child_view],
    )

    child_structured = {
        "core_concepts": [{"term": "objectivation"}],
        "semantic_architecture": "The concept-space is layered rather than flat.",
    }
    payloads = {
        "genealogy_target_profile": SimpleNamespace(
            view_key="genealogy_target_profile",
            position=1.0,
            source_parent_view_key=None,
            structured_data=None,
            has_structured_data=False,
            children=[],
        ),
        "genealogy_tp_semantic_constellation": SimpleNamespace(
            view_key="genealogy_tp_semantic_constellation",
            position=1.2,
            source_parent_view_key="genealogy_target_profile",
            structured_data=child_structured,
            has_structured_data=True,
            children=[],
        ),
    }

    top_level = _build_view_tree(payloads, fake_registry)

    assert len(top_level) == 1
    parent_payload = top_level[0]
    assert parent_payload.structured_data == {
        "semantic_constellation": child_structured,
    }
    assert len(parent_payload.children) == 1
    assert parent_payload.children[0].view_key == "genealogy_tp_semantic_constellation"
    assert parent_payload.children[0].structured_data == child_structured
    assert parent_payload.children[0].has_structured_data is True


def test_build_view_tree_promotes_child_to_top_level():
    parent_view = SimpleNamespace(
        view_key="genealogy_target_profile",
        view_name="Target Work Profile",
        parent_view_key=None,
        position=1.0,
        status="active",
    )
    child_view = SimpleNamespace(
        view_key="genealogy_tp_semantic_constellation",
        view_name="Semantic Constellation",
        parent_view_key="genealogy_target_profile",
        position=1.2,
        status="active",
    )
    fake_registry = SimpleNamespace(
        get=lambda key: {
            parent_view.view_key: parent_view,
            child_view.view_key: child_view,
        }.get(key),
        list_all=lambda: [parent_view, child_view],
    )

    payloads = {
        "genealogy_target_profile": SimpleNamespace(
            view_key="genealogy_target_profile",
            position=1.0,
            source_parent_view_key=None,
            structured_data=None,
            has_structured_data=False,
            promoted_to_top_level=False,
            children=[],
        ),
        "genealogy_tp_semantic_constellation": SimpleNamespace(
            view_key="genealogy_tp_semantic_constellation",
            position=0.9,
            source_parent_view_key="genealogy_target_profile",
            structured_data={"core_concepts": [{"term": "labor"}]},
            has_structured_data=True,
            promoted_to_top_level=True,
            children=[],
        ),
    }

    top_level = _build_view_tree(payloads, fake_registry)

    assert [payload.view_key for payload in top_level] == [
        "genealogy_tp_semantic_constellation",
        "genealogy_target_profile",
    ]
    assert top_level[1].children == []


def test_build_view_tree_keeps_promoted_child_in_parent_synthesis():
    parent_view = SimpleNamespace(
        view_key="genealogy_target_profile",
        view_name="Target Work Profile",
        parent_view_key=None,
        position=1.0,
        status="active",
        renderer_config={
            "sections": [
                {"key": "semantic_constellation", "title": "Semantic Constellation"},
            ]
        },
        transformation=SimpleNamespace(type="none"),
        data_source=SimpleNamespace(
            phase_number=1.0,
            engine_key=None,
            chain_key="genealogy_target_profiling",
            scope="aggregated",
        ),
    )
    child_view = SimpleNamespace(
        view_key="genealogy_tp_semantic_constellation",
        view_name="Semantic Constellation",
        parent_view_key="genealogy_target_profile",
        position=1.2,
        status="active",
    )
    fake_registry = SimpleNamespace(
        get=lambda key: {
            parent_view.view_key: parent_view,
            child_view.view_key: child_view,
        }.get(key),
        list_all=lambda: [parent_view, child_view],
    )

    payloads = {
        "genealogy_target_profile": SimpleNamespace(
            view_key="genealogy_target_profile",
            position=1.0,
            source_parent_view_key=None,
            structured_data=None,
            has_structured_data=False,
            promoted_to_top_level=False,
            children=[],
        ),
        "genealogy_tp_semantic_constellation": SimpleNamespace(
            view_key="genealogy_tp_semantic_constellation",
            position=0.9,
            source_parent_view_key="genealogy_target_profile",
            structured_data={"core_concepts": [{"term": "labor"}]},
            has_structured_data=True,
            promoted_to_top_level=True,
            children=[],
        ),
    }

    top_level = _build_view_tree(payloads, fake_registry)

    assert [payload.view_key for payload in top_level] == [
        "genealogy_tp_semantic_constellation",
        "genealogy_target_profile",
    ]
    assert top_level[1].children == []
    assert top_level[1].structured_data == {
        "semantic_constellation": {"core_concepts": [{"term": "labor"}]},
    }


def test_build_view_tree_dedupes_child_raw_prose_against_parent():
    parent_view = SimpleNamespace(
        view_key="genealogy_portrait",
        view_name="Genealogical Portrait",
        parent_view_key=None,
        position=5.0,
        status="active",
        renderer_config={},
        transformation=SimpleNamespace(type="none"),
        data_source=SimpleNamespace(
            phase_number=4.0,
            engine_key="genealogical_portrait",
            chain_key=None,
            scope="aggregated",
        ),
    )
    child_view = SimpleNamespace(
        view_key="genealogy_author_profile",
        view_name="Author Profile",
        parent_view_key="genealogy_portrait",
        position=5.1,
        status="active",
    )
    fake_registry = SimpleNamespace(
        get=lambda key: {
            parent_view.view_key: parent_view,
            child_view.view_key: child_view,
        }.get(key),
        list_all=lambda: [parent_view, child_view],
    )

    payloads = {
        "genealogy_portrait": SimpleNamespace(
            view_key="genealogy_portrait",
            position=5.0,
            source_parent_view_key=None,
            structured_data={"summary": "Portrait"},
            has_structured_data=True,
            raw_prose="Shared portrait prose",
            phase_number=4.0,
            engine_key="genealogical_portrait",
            chain_key=None,
            scope="aggregated",
            children=[],
        ),
        "genealogy_author_profile": SimpleNamespace(
            view_key="genealogy_author_profile",
            position=5.1,
            source_parent_view_key="genealogy_portrait",
            structured_data={"stats": []},
            has_structured_data=True,
            raw_prose="Shared portrait prose",
            phase_number=4.0,
            engine_key="genealogical_portrait",
            chain_key=None,
            scope="aggregated",
            children=[],
        ),
    }

    top_level = _build_view_tree(payloads, fake_registry)

    assert [payload.view_key for payload in top_level] == ["genealogy_portrait"]
    child_payload = top_level[0].children[0]
    assert child_payload.raw_prose is None
    assert child_payload.prose_ref_view_key == "genealogy_portrait"


def test_build_view_payload_respects_hierarchy_overrides():
    simple_view = SimpleNamespace(
        view_key="genealogy_portrait",
        view_name="Genealogical Portrait",
        description="Portrait",
        renderer_type="prose",
        renderer_config={},
        presentation_stance="narrative",
        position=6.0,
        parent_view_key=None,
        visibility="if_data_exists",
        data_source=SimpleNamespace(
            phase_number=4.0,
            engine_key="genealogical_portrait",
            chain_key=None,
            result_path="",
            scope="aggregated",
        ),
    )

    with patch(
        "src.presenter.presentation_api._load_aggregated_data",
        return_value=({"summary": "portrait"}, "portrait prose"),
    ), patch(
        "src.presenter.presentation_api._validate_payload_data",
        return_value=None,
    ), patch(
        "src.presenter.composition_resolver.load_selected_variants",
        return_value=[],
    ):
        payload = _build_view_payload(
            view_def=simple_view,
            rec={
                "view_key": "genealogy_portrait",
                "display_label_override": "Synthetic Portrait",
                "collapse_into_parent": True,
                "top_level_group": "synthesis",
                "top_level_position_override": 2.5,
                "promote_to_top_level": True,
            },
            job_id="job-1",
            consumer_key="the-critic",
        )

    assert payload.view_name == "Synthetic Portrait"
    assert payload.visibility == "on_demand"
    assert payload.top_level_group == "synthesis"
    assert payload.position == 2.5
    assert payload.promoted_to_top_level is True


def test_normalize_view_structured_data_repairs_legacy_dimensional_comparisons():
    normalized = _normalize_view_structured_data(
        "genealogy_tp_concept_evolution",
        {"dimensional_comparisons": "Dense prose about temporalization and politicization."},
    )

    assert isinstance(normalized["dimensional_comparisons"], list)
    assert normalized["dimensional_comparisons"][0]["dimension"] == "overall dimensional shift"


def test_normalize_view_structured_data_splits_legacy_dimensional_comparisons_into_rows():
    normalized = _normalize_view_structured_data(
        "genealogy_tp_concept_evolution",
        {
            "dimensional_comparisons": [
                {
                    "dimension": "overall dimensional shift",
                    "comparison": "**Temporalization** Concepts acquire historical depth.\n\n**Politicization** Categories become politically contested.",
                    "significance": "legacy cached synthesis",
                    "exemplar_concepts": [],
                }
            ]
        },
    )

    rows = normalized["dimensional_comparisons"]
    assert len(rows) == 2
    assert rows[0]["dimension"] == "Temporalization"
    assert "historical depth" in rows[0]["comparison"]
    assert rows[1]["dimension"] == "Politicization"
    assert "politically contested" in rows[1]["comparison"]


def test_normalize_view_structured_data_repairs_idea_evolution_pattern_drift():
    normalized = _normalize_view_structured_data(
        "genealogy_idea_evolution",
        {
            "ideas": [
                {
                    "idea_id": "objectification",
                    "evolution_pattern": "genuine_transformation",
                    "description": "Objectification shifts from production category to broader social process.",
                    "evolution_narrative": "The concept undergoes foundational revision rather than mere reframing.",
                },
                {
                    "idea_id": "praxis",
                    "evolution_pattern": "concept_death",
                    "description": "Praxis recedes as a positive horizon.",
                    "evolution_narrative": "The project abandons the old normative center.",
                },
            ],
            "cross_cutting_patterns": {
                "dominant_evolution_pattern": (
                    "The dominant pattern across all ideas is neither simple deepening nor mere reframing "
                    "but methodological radicalization generating foundational revision."
                ),
                "audience_calibration": "The corpus stays inside critical-theory audiences.",
            },
        },
    )

    assert normalized["ideas"][0]["evolution_pattern"] == "radical_transformation"
    assert normalized["ideas"][1]["evolution_pattern"] == "radical_transformation"
    assert normalized["cross_cutting_patterns"]["dominant_evolution_pattern"] == "radical_transformation"
    assert "methodological radicalization" in normalized["cross_cutting_patterns"]["overall_trajectory"]


def test_normalize_relationship_card_demotes_method_only_direct_precursor():
    normalized = _normalize_relationship_card(
        {
            "relationship_type": "direct_precursor",
            "secondary_relationship_type": "methodological_ancestor",
            "summary": "The earlier work is primarily a methodological prior work that provides the analytical instrument for a new domain absent from the prior work.",
            "mechanism_of_inheritance": "The dominant pathway is vocabulary carryover and immanent critique procedure rather than transmission of the target's starting problem.",
            "what_would_be_lost": "The critique would lose its internal vocabulary.",
        }
    )

    assert normalized["relationship_type"] == "methodological_ancestor"
    assert normalized["secondary_relationship_type"] == "direct_precursor"
    assert normalized["counterfactual_loss"] == "The critique would lose its internal vocabulary."


def test_normalize_relationship_card_preserves_direct_precursor_for_problem_transmission():
    normalized = _normalize_relationship_card(
        {
            "relationship_type": "direct_precursor",
            "secondary_relationship_type": "methodological_ancestor",
            "summary": "The earlier essay supplies the target's immediate problem-space and unresolved aporia.",
            "mechanism_of_inheritance": (
                "The inheritance operates through problem transmission rather than solution carryover: "
                "the target takes over the starting problem and forcing function diagnosed by the prior work."
            ),
            "centrality_assessment": "This is the immediate predecessor that sets the architectural problem.",
        }
    )

    assert normalized["relationship_type"] == "direct_precursor"
    assert normalized["secondary_relationship_type"] == "methodological_ancestor"


def test_normalize_relationship_card_demotes_same_program_development_to_conceptual_sibling():
    normalized = _normalize_relationship_card(
        {
            "relationship_type": "direct_precursor",
            "secondary_relationship_type": None,
            "summary": "The earlier work contains in embryonic form the target's critical architecture and is best understood as authorial self-development rather than an external influence.",
            "mechanism_of_inheritance": (
                "The inheritance operates within a single developing body of thought: "
                "the target extends and formalizes arguments whose skeleton already appears in the earlier installment."
            ),
            "centrality_assessment": "This is an adjacent installment in the same research program, not the target's specific forcing problem.",
            "influence_channels": [
                {"channel": "framework", "description": "Carries over the conceptual architecture."},
                {"channel": "methodology", "description": "Preserves the analytical method."},
            ],
        }
    )

    assert normalized["relationship_type"] == "conceptual_sibling"
    assert normalized["secondary_relationship_type"] == "methodological_ancestor"
