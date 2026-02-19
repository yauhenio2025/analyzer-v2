"""Execution engine for the context-driven orchestrator.

Takes a WorkflowExecutionPlan and executes it — calling LLMs, threading
context between phases, persisting outputs, and tracking progress.

Architecture (bottom-up):
- engine_runner: Single LLM call with retry, streaming, model selection
- context_broker: Assembles cross-phase context as markdown
- chain_runner: Sequential engine execution within a chain
- phase_runner: Runs a single phase (chain or engine), handles per-work iteration
- workflow_runner: Top-level DAG execution respecting phase dependencies
- job_manager: Job lifecycle, progress tracking, cancellation
- output_store: Persist prose outputs to DB
- document_store: Store/retrieve uploaded document texts
"""
