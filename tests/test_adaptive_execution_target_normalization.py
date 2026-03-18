from uuid import uuid4

from src.aoi.constants import AOI_WORKFLOW_KEY
from src.executor.db import execute, init_db
from src.executor.job_manager import create_job, get_job, save_phase_result
from src.executor.phase_runner import _resolve_execution_target
from src.executor.workflow_runner import execute_plan
from src.orchestrator.adaptive_planner import normalize_plan_execution_targets
from src.orchestrator.schemas import (
    PhaseExecutionSpec,
    PriorWork,
    TargetWork,
    WorkflowExecutionPlan,
)


def _make_aoi_plan() -> WorkflowExecutionPlan:
    return WorkflowExecutionPlan(
        plan_id=f"plan-{uuid4().hex[:10]}",
        workflow_key=AOI_WORKFLOW_KEY,
        thinker_name="Aaron Benanav",
        target_work=TargetWork(
            title="Beyond Capitalism",
            author="Aaron Benanav",
            description="Target work",
        ),
        prior_works=[
            PriorWork(
                title="Knowledge, Planning, and Markets",
                author="John O'Neill",
                description="Source work",
                relationship_hint="selected_source_thinker_corpus",
                source_thinker_id="john-oneill",
                source_thinker_name="John O'Neill",
                source_document_id="oneill_2006_knowledgeplanningandmarkets",
            )
        ],
        selected_source_thinker_id="john-oneill",
        selected_source_thinker_name="John O'Neill",
        objective_key="influence_thematic",
        strategy_summary="summary",
        phases=[
            PhaseExecutionSpec(
                phase_number=0.5,
                phase_name="Deep Text Profiling",
                engine_key="deep_text_profiling",
                depends_on=[],
                rationale="Adaptive profiling phase",
            ),
            PhaseExecutionSpec(
                phase_number=1.0,
                phase_name="Source Thematic Synthesis",
                engine_key="aoi_thematic_synthesis",
                depends_on=[],
                rationale="AOI source synthesis",
            ),
        ],
        recommended_views=[],
        estimated_llm_calls=2,
        estimated_depth_profile="standard",
    )


def test_normalize_plan_execution_targets_moves_chain_like_engine_key():
    plan = _make_aoi_plan()

    normalize_plan_execution_targets(plan)

    phase = plan.phases[0]
    assert phase.chain_key == "deep_text_profiling"
    assert phase.engine_key is None


def test_resolve_execution_target_treats_chain_like_engine_as_chain():
    chain_key, engine_key = _resolve_execution_target(
        workflow_chain_key=None,
        workflow_engine_key=None,
        plan_chain_key=None,
        plan_engine_key="deep_text_profiling",
    )

    assert chain_key == "deep_text_profiling"
    assert engine_key is None


def test_execute_plan_resume_skips_completed_phase_and_runs_chain_for_stored_engine_key(
    monkeypatch,
):
    init_db()
    plan = _make_aoi_plan()
    job_id = f"job-{uuid4().hex[:10]}"
    document_ids = {"target": "doc-target"}

    try:
        create_job(
            job_id,
            plan.plan_id,
            plan_data=plan.model_dump(),
            document_ids=document_ids,
            workflow_key=AOI_WORKFLOW_KEY,
        )
        save_phase_result(
            job_id,
            1.0,
            {
                "phase_number": 1.0,
                "phase_name": "Source Thematic Synthesis",
                "status": "completed",
                "duration_ms": 12,
                "total_tokens": 34,
                "error": None,
                "final_output_preview": "already done",
            },
        )

        chain_calls: list[tuple[str, float]] = []

        def fake_run_chain(chain_key: str, document_text: str, **kwargs):
            chain_calls.append((chain_key, kwargs["phase_number"]))
            return {
                "engine_results": {},
                "final_output": "profiled",
                "total_tokens": 1,
                "duration_ms": 1,
            }

        def fail_run_single_engine(*args, **kwargs):
            raise AssertionError("deep_text_profiling should execute as a chain")

        monkeypatch.setattr(
            "src.executor.phase_runner._get_standard_phase_document_text",
            lambda **kwargs: "target text",
        )
        monkeypatch.setattr("src.executor.phase_runner.run_chain", fake_run_chain)
        monkeypatch.setattr(
            "src.executor.phase_runner.run_single_engine",
            fail_run_single_engine,
        )
        monkeypatch.setattr(
            "src.executor.workflow_runner._run_auto_presentation",
            lambda *args, **kwargs: None,
        )

        execute_plan(
            job_id=job_id,
            plan_id=plan.plan_id,
            document_ids=document_ids,
            plan_object=plan,
        )

        job = get_job(job_id)
        assert chain_calls == [("deep_text_profiling", 0.5)]
        assert job is not None
        assert job["status"] == "completed"
        assert job["phase_results"]["1.0"]["status"] == "completed"
        assert job["phase_results"]["0.5"]["status"] == "completed"
    finally:
        execute("DELETE FROM executor_jobs WHERE job_id = %s", (job_id,))
