# Feature Inventory

> Auto-maintained by Claude Code. Last updated: 2026-02-23

## Context-Driven Orchestrator

### Orchestrator — LLM-Powered Plan Generation
- **Status**: Active (Milestone 1 complete)
- **Description**: Context-driven orchestrator that takes a thinker + corpus + research question and uses Claude Opus to generate a WorkflowExecutionPlan — a concrete, contextualized plan for executing the 5-phase genealogy workflow. Assembles a capability catalog from all registries (engines, chains, stances, operationalizations, views, workflows) and presents it to the LLM as a structured "menu". Plans are inspectable, editable, and refinable.
- **Entry Points**:
  - `src/orchestrator/__init__.py:1-11` - Module docstring
  - `src/orchestrator/schemas.py:1-246` - Pydantic models: TargetWork, PriorWork, EngineExecutionSpec, PhaseExecutionSpec (incl. supplementary_chains, max_context_chars_override), ViewRecommendation, OrchestratorPlanRequest, PlanRefinementRequest, WorkflowExecutionPlan
  - `src/orchestrator/catalog.py:1-540` - Parameterized catalog assembly from all registries (app/page/workflow_key filters), includes sub-renderers and view patterns, dynamic catalog_to_text()
  - `src/orchestrator/planner.py:1-560` - LLM-powered plan generation with templated system prompt (generic rules + workflow planner_strategy), plan refinement, file-based plan storage
  - `src/api/routes/orchestrator.py:1-155` - REST API: plan generation, CRUD, refinement, catalog
  - `src/api/main.py:16` - Router registration
  - `src/orchestrator/plans/` - File-based plan storage (JSON)
- **Key Schemas**:
  - `WorkflowExecutionPlan` — plan_id, thinker context, strategy_summary, phases (list of PhaseExecutionSpec), recommended_views, estimated_llm_calls, status
  - `PhaseExecutionSpec` — phase_number, depth, skip, engine_overrides (dict of EngineExecutionSpec), context_emphasis, rationale, model_hint, requires_full_documents, per_work_overrides, supplementary_chains, max_context_chars_override
  - `EngineExecutionSpec` — engine_key, depth, focus_dimensions, focus_capabilities, rationale
  - `ViewRecommendation` — view_key, priority (primary/secondary/optional), rationale
- **Capability Catalog**: Assembled from 11 capability engines, 23 chains, 13 stances, 7 workflows, 21 views, 11 sub-renderers, 6 view patterns, 16+ transformation templates, 11 operationalizations. Parameterized by app/page/workflow_key. System prompt composed from generic planning rules + workflow-specific planner_strategy field. Views section enriched with planner_hint, planner_eligible, has_transformation_template tags. Transformation templates section shows template_key, applicable_engines, applicable_renderers, domain, generation_mode. Planner prompt notes dynamic generation capability.
- **API Endpoints**:
  - `GET /v1/orchestrator/capability-catalog` - Full capability catalog (?format=text for markdown)
  - `POST /v1/orchestrator/plan` - Generate new plan (Claude Opus, ~20s)
  - `GET /v1/orchestrator/plans` - List all plans (summary)
  - `GET /v1/orchestrator/plans/{plan_id}` - Get full plan
  - `PUT /v1/orchestrator/plans/{plan_id}` - Manual edit (no LLM)
  - `POST /v1/orchestrator/plans/{plan_id}/refine` - LLM-assisted refinement
  - `PATCH /v1/orchestrator/plans/{plan_id}/status` - Update plan status
  - `GET /v1/orchestrator/plans/{plan_id}/pipeline-visualization` - Full pipeline tree for visualization
- **Tested**: Varoufakis plan generated with 5 phases (deep profiling, standard classification, deep scanning, deep synthesis, deep final), 42 estimated LLM calls, 10 view recommendations (4 primary, 4 secondary, 2 optional), engine-specific focus dimensions
- **Added**: 2026-02-19

### Pipeline Visualization Endpoint
- **Status**: Active
- **Description**: Assembles a complete hierarchical tree of the execution pipeline from in-memory registries (plan → phases → chains → engines → passes → stances → dimensions). No LLM/DB calls. Powers the Critic's dynamic pipeline visualization component.
- **Entry Points**:
  - `src/orchestrator/visualization.py:1-280` - assemble_pipeline_visualization() + helpers for phase/chain/engine/pass viz
  - `src/api/routes/orchestrator.py:113-131` - GET endpoint registration
- **API Endpoints**:
  - `GET /v1/orchestrator/plans/{plan_id}/pipeline-visualization` - Full pipeline tree
- **Data Sources**: WorkflowRegistry, ChainRegistry, EngineRegistry (capability defs), OperationalizationRegistry, StanceRegistry
- **Added**: 2026-02-20

## Execution Engine (Milestone 2)

### Executor — Plan-Driven Workflow Execution
- **Status**: Active (Milestone 2 complete)
- **Description**: Full executor module that takes a WorkflowExecutionPlan and runs it: calling LLMs, threading context between phases, persisting outputs to Postgres, and tracking progress. Replaces The Critic's hardcoded pipeline with plan-driven model selection, depth, and focus. Supports dependency-aware parallel phases (1.0 || 1.5), per-work iteration (Phases 1.5, 2.0), multi-pass operationalization-driven prompts, and cancellation.
- **Entry Points**:
  - `src/executor/__init__.py:1-20` - Module architecture docstring
  - `src/executor/schemas.py:1-170` - JobStatus, PhaseStatus, EngineCallResult, PhaseResult, JobProgress, ExecutorJob, StartJobRequest, JobStatusResponse, PhaseOutputSummary, DocumentUpload, DocumentRecord
  - `src/executor/db.py:1-283` - Dual-backend DB abstraction (Postgres via psycopg2 + SQLite), init_db(), execute(), 4 tables
  - `src/executor/engine_runner.py:1-887` - Atomic LLM call: MODEL_CONFIGS (opus/sonnet/haiku), PHASE_MODEL_DEFAULTS, sync API by default (PREFER_SYNC=true, 100x faster on Render), streaming with adaptive thinking when ENABLE_STREAMING=true, smart 1M context avoidance (prefer standard 200K by reducing max_tokens), auto-fallback to 1M beta for both sync and streaming, dynamic effort scaling for large inputs, partial output salvage on connection drop, heartbeat monitoring with [std]/[1M] tags, exponential backoff retry (5 attempts), document chunking (CHUNK_THRESHOLD=200K chars, re-enabled — O(n²) attention is model-side)
  - `src/executor/context_broker.py:1-200` - Cross-phase context assembly with emphasis injection, inner-pass context threading, chain context forwarding, phase_max_chars_override (M5)
  - `src/executor/chain_runner.py:1-494` - Sequential chain execution using capability_composer, multi-pass operationalization support, run_chain() + run_single_engine()
  - `src/executor/phase_runner.py:1-610` - Phase resolution (chain_key/engine_key), per-work iteration with ThreadPoolExecutor, plan override application, supplementary chain execution (M5), _combine_with_distilled_analysis (M5)
  - `src/executor/workflow_runner.py:1-481` - Top-level DAG execution, dependency-aware parallel phases, progress tracking, context_char_overrides threading (M5), execute_plan() + start_execution_thread()
  - `src/executor/job_manager.py:1-420` - Job lifecycle (create/update/cancel/delete), progress updates, in-memory cancellation flags, DB persistence, recover_orphaned_jobs() for startup cleanup, check_stale_job() for on-read detection (>3h running → failed)
  - `src/executor/output_store.py:1-256` - Incremental prose output persistence with lineage, presentation cache with source_hash freshness
  - `src/executor/document_store.py:1-97` - Store/retrieve uploaded document texts
  - `src/api/routes/executor.py:1-200` - 11 REST endpoints for jobs, documents
  - `src/api/main.py:16` - Router registration and DB init in lifespan
- **Database**: Render Postgres (4 tables: executor_jobs, phase_outputs, presentation_cache, executor_documents). Dual-backend: Postgres for production, SQLite for local dev.
- **Model Selection**: Plan-driven via model_hint → PHASE_MODEL_DEFAULTS → depth heuristic. Opus for profiling/synthesis, Sonnet for scanning/classification, Haiku disabled by default.
- **PDF Export**: `GET /v1/executor/jobs/{job_id}/export/pdf` returns professional A4 PDF with cover page, TOC, per-phase prose sections, and execution stats appendix. WeasyPrint + markdown libraries. ([`src/executor/pdf_export.py`](src/executor/pdf_export.py))
- **Resumable Jobs**: Jobs persist `plan_data` (full WorkflowExecutionPlan JSONB) and `document_ids` to Postgres. On instance restart, `recover_orphaned_jobs()` resumes jobs with plan_data via `start_resume_thread()`. Three-level resume: phase-level (skip completed phases), engine-level (skip completed engines), pass-level (skip completed passes). Pre-resume jobs fail cleanly.
- **Sync API Default**: `PREFER_SYNC=true` by default (100x faster on Render). Disables extended thinking but avoids SSE buffering bottleneck. Set `ENABLE_STREAMING=true` for local dev with thinking.
- **Document Chunking**: Re-enabled (`CHUNK_THRESHOLD=200K chars`). O(n²) attention is model-side — at 183K tokens, generation drops to 0.5 tok/s. Documents >200K chars are split into ~180K char chunks, extracted per-chunk, then synthesized.
- **API Endpoints**:
  - `POST /v1/executor/jobs` - Start execution from plan_id
  - `GET /v1/executor/jobs` - List jobs
  - `GET /v1/executor/jobs/{job_id}` - Poll status + progress
  - `POST /v1/executor/jobs/{job_id}/cancel` - Cancel running job
  - `GET /v1/executor/jobs/{job_id}/results` - Phase output summaries
  - `GET /v1/executor/jobs/{job_id}/phases/{phase}` - Full phase prose
  - `DELETE /v1/executor/jobs/{job_id}` - Delete completed job
  - `POST /v1/executor/documents` - Upload document text
  - `GET /v1/executor/documents` - List documents
  - `GET /v1/executor/documents/{doc_id}` - Retrieve document
  - `DELETE /v1/executor/documents/{doc_id}` - Delete document
- **PhaseExecutionSpec additions**: model_hint (opus/sonnet/None), requires_full_documents (1M context), per_work_overrides (differential depth per prior work), supplementary_chains (additional chains after primary, Milestone 5), max_context_chars_override (per-phase context cap override, Milestone 5)
- **Milestone 5 Enhancements**: Supplementary chain execution in `_run_standard_phase()`, distilled analysis path in `_combine_with_distilled_analysis()` for per-work phases, `phase_max_chars_override` in context broker, `context_char_overrides` threaded from workflow_runner. Phase 1.5 now depends on Phase 1.0 (sequential, not parallel).
- **Added**: 2026-02-19

## Presenter — Adaptive View Selection & Presentation Bridge (Milestone 3)

### Post-Execution View Refinement (3A)
- **Status**: Active (Milestone 3 complete)
- **Description**: LLM-driven post-execution view refinement that inspects phase result summaries + output previews and adjusts the planner's recommended_views. Uses Sonnet for lightweight curatorial decisions. Adjusts priorities (primary/secondary/optional/hidden), stances, data quality assessments based on actual output quality. Falls back to passthrough if no LLM available.
- **Entry Points**:
  - `src/presenter/view_refiner.py:1-273` - refine_views() with LLM call, _build_refinement_context(), _passthrough_result()
  - `src/presenter/store.py:1-90` - save_view_refinement(), load_view_refinement() — DB persistence for view_refinements table
  - `src/presenter/schemas.py:1-175` - RefinedViewRecommendation, ViewRefinementResult, RefineViewsRequest
  - `src/api/routes/presenter.py:28-47` - POST /v1/presenter/refine-views endpoint
- **Refinement Triggers**: Phase failed → hide views; rich output → upgrade to primary; thin output → downgrade; stance adjustments based on content type
- **Added**: 2026-02-19

### Presentation Bridge (3B)
- **Status**: Active (Milestone 3 complete)
- **Description**: Automated transformation pipeline connecting executor prose outputs → presentation_cache. For each recommended view: resolves data_source → finds phase_outputs → checks cache → tries curated template (by engine_key + renderer_type) → if none, composes dynamic extraction prompt from engine metadata + renderer shape + stance → runs TransformationExecutor → persists to presentation_cache. Curated templates are optional quality overrides; dynamic extraction makes every engine renderable without hand-authored templates.
- **Entry Points**:
  - `src/presenter/presentation_bridge.py:1-686` - prepare_presentation(), _build_transformation_tasks() (curated + dynamic fallback), _execute_tasks_async/sync(), _save_and_report()
  - `src/presenter/dynamic_prompt.py:1-260` - compose_dynamic_extraction_prompt(): composes extraction system prompt from engine canonical_schema + renderer config_schema + stance prose
  - `src/presenter/schemas.py:67-116` - TransformationTask (template_key now Optional, new dynamic_config field), TransformationTaskResult (new extraction_source field), PresentationBridgeResult (new dynamic_extractions counter)
  - `src/api/routes/presenter.py:50-69` - POST /v1/presenter/prepare endpoint
- **Added**: 2026-02-19 | **Modified**: 2026-02-23

### Presentation API (3C)
- **Status**: Active (Milestone 3 complete)
- **Description**: Consumer-facing presentation assembly. Combines view definitions, structured data (from presentation_cache), and raw prose (from phase_outputs) into a single PagePresentation that The Critic can render directly. Builds parent-child view tree with nested children sorted by position. Now chain-aware: resolves chain_key → engine_keys for data loading and template search, concatenates all engine outputs per work_key for chain-backed per_item views.
- **Entry Points**:
  - `src/presenter/presentation_api.py:1-467` - assemble_page(), assemble_single_view(), get_presentation_status(), _build_view_payload(), _load_aggregated_data(), _load_per_item_data(), _build_view_tree()
  - `src/presenter/schemas.py:120-175` - ViewPayload, PagePresentation, ComposeRequest
  - `src/api/routes/presenter.py:72-182` - GET /page/{job_id}, GET /view/{job_id}/{view_key}, GET /status/{job_id}, POST /compose
- **API Endpoints**:
  - `POST /v1/presenter/refine-views` - Refine view recommendations post-execution (LLM)
  - `POST /v1/presenter/prepare` - Run transformations and populate presentation_cache
  - `GET /v1/presenter/page/{job_id}` - Full render-ready PagePresentation
  - `GET /v1/presenter/view/{job_id}/{view_key}` - Single view data (lazy loading)
  - `GET /v1/presenter/status/{job_id}` - Presentation readiness (ready/prose_only/empty per view)
  - `POST /v1/presenter/compose` - All-in-one: refine + prepare + assemble
- **Database**: view_refinements table (Postgres + SQLite) for persisting refined recommendations
- **Added**: 2026-02-19

### View Polishing (3D)
- **Status**: Active
- **Description**: LLM-powered visual enhancement of renderer configs. The "Present" button calls Sonnet 4.6 to polish a view's renderer_config and produce style_overrides — CSS-like dicts applied at defined injection points (section_header, card, chip, badge, prose, etc.). Uses the resolved style school's color palette, typography, and layout principles as design input. Results are cached per (job_id, view_key, style_school) in the polish_cache table.
- **Entry Points**:
  - `src/presenter/polisher.py:1-260` - polish_view() main entry, _resolve_style_school(), _gather_polish_context(), _compose_system_prompt(), _compose_user_message()
  - `src/presenter/polish_store.py:1-90` - save_polish_cache(), load_polish_cache() — DB persistence
  - `src/presenter/schemas.py:215-255` - PolishRequest, StyleOverrides, PolishedViewPayload, PolishResult
  - `src/executor/db.py` - polish_cache table DDL (both Postgres + SQLite)
  - `src/api/routes/presenter.py:189-260` - POST /v1/presenter/polish endpoint with cache check
- **Frontend**:
  - `the-critic/webapp/src/pages/GenealogyPage.tsx` - V2TabContent: Present/Reset buttons, polishResult state, ANALYZER_V2_URL fetch, config override
  - `the-critic/webapp/src/components/renderers/AccordionRenderer.tsx` - Reads config._style_overrides, applies to section headers/content, threads down to sub-renderers
  - `the-critic/webapp/src/components/renderers/ConditionCards.tsx` - Reads config._style_overrides, applies to cards, chips, badges, prose
- **Style Override Injection Points**: section_header, section_content, card, chip, badge, timeline_node, prose, accent_color, view_wrapper
- **Added**: 2026-02-23

### All-in-One Analysis Pipeline (Milestone 4A)
- **Status**: Active (Milestone 4A complete)
- **Description**: All-in-one orchestration endpoint that chains documents -> plan generation -> execution -> presentation into a single async job. Accepts inline document texts + thinker context, uploads documents, generates a WorkflowExecutionPlan, starts execution, and returns immediately with job_id for polling. Auto-presentation trigger in workflow_runner runs view refinement + transformation bridge when execution completes. Supports autonomous mode (default) and checkpoint mode (skip_plan_review=false returns plan_id for review).
- **Entry Points**:
  - `src/orchestrator/pipeline_schemas.py:1-80` - AnalyzeRequest, PriorWorkWithText, AnalyzeResponse
  - `src/orchestrator/pipeline.py:1-275` - run_analysis_pipeline(), _run_checkpoint_mode(), _run_autonomous_mode(), _pipeline_thread(), _upload_documents(), _store_plan_and_docs(), _build_plan_request()
  - `src/executor/workflow_runner.py:404-449` - _run_auto_presentation() — non-fatal auto view refinement + transformation bridge on completion
  - `src/api/routes/orchestrator.py:204-296` - POST /analyze, GET /analyze/{job_id}
- **API Endpoints**:
  - `POST /v1/orchestrator/analyze` - All-in-one: documents + plan + execution (returns {job_id, plan_id, status})
  - `GET /v1/orchestrator/analyze/{job_id}` - Convenience: progress while running, PagePresentation when complete
- **Key Schemas**:
  - `AnalyzeRequest` — thinker_name, target_work, target_work_text, prior_works (with text), research_question, skip_plan_review
  - `AnalyzeResponse` — job_id, plan_id, document_ids, status, message
- **Added**: 2026-02-19

## View Definitions (Rendering Layer)

### View Definitions
- **Status**: Active
- **Description**: Declarative specs for how analytical outputs become UI. A ViewDefinition declares: data source -> renderer type -> position in consumer app. Consumer apps fetch view trees for their pages and dispatch to their own component registries. No execution logic — just definitions. Supports nested views (subtabs within tabs), presentation stances for LLM transformation guidance, audience overrides, and `generation_mode` tracking ("curated"/"generated"/"hybrid").
- **Entry Points**:
  - `src/views/schemas.py:1-220` - Pydantic models: ViewDefinition (incl. generation_mode), DataSourceRef, TransformationSpec, ViewSummary, ComposedView, ComposedPageResponse
  - `src/views/registry.py:1-195` - ViewRegistry: load, get, list_summaries (with app/page filters), compose_tree, for_workflow, save, delete, reload
  - `src/views/generator.py:1-370` - LLM-powered view generation from patterns: ViewGenerateRequest/Response, engine/renderer/page context assembly, Claude Sonnet generation
  - `src/views/definitions/*.json` - 21 view definition JSON files
  - `src/api/routes/views.py:1-233` - Full REST API with compose + generate endpoints
  - `src/api/main.py:16` - Router registration and lifespan loading
- **Schema**:
  - `ViewDefinition` — Identity (view_key, view_name, version), WHERE (target_app, target_page, target_section), WHAT component (renderer_type, renderer_config), WHAT data (data_source, secondary_sources), HOW to transform (transformation, presentation_stance), LAYOUT (position, parent_view_key, tab_count_field), VISIBILITY, AUDIENCE overrides, METADATA
  - `DataSourceRef` — workflow_key, phase_number, engine_key, chain_key, result_path (JSONPath), scope (aggregated/per_item)
  - `TransformationSpec` — type (none/schema_map/llm_extract/llm_summarize/aggregate), field_mapping, llm_extraction_schema, llm_prompt_template, stance_key override
  - `planner_hint` — Free-text guidance for the LLM planner about when/how to recommend this view
  - `planner_eligible` — Boolean flag (default true) controlling whether the planner considers this view
- **Genealogy Views** (21 total):
  - **Top-level views**:
    - `genealogy_relationship_landscape` (card_grid, diagnostic) — Pass 1.5 relationship classifications
    - `genealogy_target_profile` (accordion, diagnostic) — Pass 1 target profiling chain, container for 4 per-engine views
    - `genealogy_idea_evolution` (tab, comparison) — Pass 1+2+3 idea evolution traces
    - `genealogy_tactics` (card_grid, evidence) — Pass 3 evolution tactics
    - `genealogy_conditions` (accordion, narrative) — Pass 3 conditions of possibility, container for 7 sub-component views
    - `genealogy_portrait` (prose, narrative) — Pass 4 final synthesis
  - **Target Work Profile children** (4, per-engine):
    - `genealogy_tp_conceptual_framework` (accordion, 7 sections) — frameworks, vocabulary maps, metaphors, cross-domain transfers
    - `genealogy_tp_semantic_constellation` (accordion, 6 sections) — core concepts, clusters, load-bearing terms, tensions
    - `genealogy_tp_inferential_commitments` (accordion, 7 sections) — ideas, commitments, backings, hidden premises
    - `genealogy_tp_concept_evolution` (accordion, 6 sections) — concepts, trajectories, definitional variations, Koselleck
  - **Conditions of Possibility children** (7, all engine output sections):
    - `genealogy_cop_enabling_conditions` (card_grid, evidence) — typed condition cards with essentiality and evidence
    - `genealogy_cop_constraining_conditions` (card_grid, evidence) — constraint cards with binding force ratings
    - `genealogy_cop_counterfactual` (prose, narrative) — counterfactual analysis of path-independence
    - `genealogy_cop_synthesis` (prose, narrative) — evaluative judgment on path-dependence
    - `genealogy_cop_path_dependencies` (timeline, narrative) — causal chains of path-dependent reasoning
    - `genealogy_cop_unacknowledged_debts` (card_grid, evidence) — intellectual debts not acknowledged by author
    - `genealogy_cop_alternative_paths` (card_grid, narrative) — branching points and roads not taken
  - **Other nested children**:
    - `genealogy_per_work_scan` (card, comparison) — nested under idea_evolution, Pass 2 per-work results
    - `genealogy_author_profile` (stat_summary, summary) — nested under portrait, Pass 4 extracted
  - **On-demand debug**:
    - `genealogy_raw_output` (raw_json, diagnostic) — raw engine JSON, visibility=on_demand
    - `genealogy_chain_log` (table, diagnostic) — execution metadata, visibility=on_demand
- **API Endpoints**:
  - `GET /v1/views` - List all views (with ?app=X&page=Y filters)
  - `GET /v1/views/{key}` - Single view definition
  - `GET /v1/views/compose/{app}/{page}` - **Primary consumer endpoint**: sorted tree with nested children
  - `GET /v1/views/for-workflow/{workflow_key}` - All views referencing a workflow
  - `POST /v1/views` - Create view
  - `PUT /v1/views/{key}` - Update view
  - `DELETE /v1/views/{key}` - Delete view
  - `POST /v1/views/reload` - Force reload from disk
  - `POST /v1/views/generate` - LLM-powered view generation from pattern + engine + workflow context
- **Dynamic View Generation**:
  - Takes pattern_key + engine_key + workflow/phase context → generates complete ViewDefinition
  - Uses engine canonical_schema, renderer config_schema, existing page views for position context
  - Supports wiring existing transformation templates via transformation_template_key
  - View key collision handling: appends "_gen" suffix
  - Parent view validation: warns if parent_view_key doesn't exist
  - Generated views auto-tagged: `generation_mode="generated"`, `status="draft"`
- **Consumer Usage Pattern**: `GET /v1/views/compose/the-critic/genealogy` returns tree → app renders tabs from top-level views → dispatches to component by renderer_type → nests children → uses presentation_stance for LLM transforms
- **Added**: 2026-02-18 | **Modified**: 2026-02-23

## Renderer Definitions (Rendering Layer)

### Renderer Catalog
- **Status**: Active
- **Description**: First-class renderer definitions cataloging rendering strategies with capabilities, stance affinities, ideal data shapes, and configuration schemas. Consumer apps use these to select appropriate renderers. The view refiner uses the catalog to recommend renderer configurations.
- **Entry Points**:
  - `src/renderers/schemas.py:1-103` - Pydantic models: RendererDefinition, RendererSummary, SectionRendererHint
  - `src/renderers/registry.py:1-180` - RendererRegistry: load, get, list_all, list_summaries, for_stance, for_data_shape, for_app, save, delete, reload
  - `src/renderers/definitions/*.json` - 8 renderer definition JSON files
  - `src/api/routes/renderers.py:1-170` - Full REST API with stance/app query endpoints
  - `src/api/main.py` - Router registration and lifespan loading
- **Renderers** (8):
  - `accordion` (container) — expandable sections, hosts sub-renderers
  - `card_grid` (list) — responsive grid of cards
  - `prose` (narrative) — formatted long-form with section anchors
  - `table` (list) — sortable data table
  - `stat_summary` (diagnostic) — stat cards with metrics
  - `timeline` (narrative) — chronological visualization
  - `tab` (container) — tabbed organization
  - `raw_json` (diagnostic) — developer JSON inspector
- **Section Sub-Renderers** (10, for accordion): chip_grid, mini_card_list, key_value_table, prose_block, stat_row, comparison_panel, timeline_strip, evidence_trail, enabling_conditions, constraining_conditions
- **API Endpoints**:
  - `GET /v1/renderers` - List all (summary)
  - `GET /v1/renderers/{key}` - Full definition with config schema
  - `GET /v1/renderers/for-stance/{stance}` - By stance affinity (sorted)
  - `GET /v1/renderers/for-app/{app}` - By consumer app support
  - `POST /v1/renderers/recommend` - LLM-powered renderer recommendation (Claude Sonnet)
  - `POST /v1/renderers` - Create
  - `PUT /v1/renderers/{key}` - Update
  - `DELETE /v1/renderers/{key}` - Delete
- **Added**: 2026-02-21 | **Modified**: 2026-02-23

### Intelligent Renderer Selector
- **Status**: Active
- **Description**: Two-layer intelligence for selecting renderers in the Views editor. Layer 1: deterministic frontend scoring ranks all renderers by stance affinity (0.35), data shape match (0.30), container fit (0.20), app support (0.15). Layer 2: LLM recommendation via Claude Sonnet analyzes full view context and returns top 5 with reasoning and config migration hints. Includes a **Wiring Explainer** panel that narrates in plain English how data source → data shape → stance → renderer need chain together.
- **Entry Points**:
  - `src/renderers/schemas.py:137-185` - Request/response schemas: RendererRecommendRequest, RendererRecommendation, ConfigMigrationHint, RendererRecommendResponse
  - `src/api/routes/renderers.py:197-310` - POST /v1/renderers/recommend endpoint with catalog assembly and LLM call
  - `analyzer-mgmt/frontend/src/pages/views/[key].tsx` - WiringExplainer component + redesigned RendererTab: scored list + AI panel with [Apply] buttons
  - `analyzer-mgmt/frontend/src/lib/api.ts` - renderers.recommend() API client method
  - `analyzer-mgmt/frontend/src/types/index.ts` - RendererRecommendRequest/Response types
- **Added**: 2026-02-22

## Sub-Renderer Definitions (First-Class Entity)

### Sub-Renderers
- **Status**: Active
- **Description**: 11 sub-renderer definitions as first-class entities. Previously scattered strings in accordion config, now browsable and queryable. Each defines a reusable atomic UI component within container renderers (accordion, tab). Includes category (atomic/composite/specialized/meta), ideal_data_shapes, config_schema (JSON Schema), stance_affinities, and parent_renderer_types.
- **Entry Points**:
  - `src/sub_renderers/schemas.py:1-50` - SubRendererDefinition and SubRendererSummary Pydantic models
  - `src/sub_renderers/registry.py:1-150` - SubRendererRegistry with for_parent(), for_data_shape(), CRUD
  - `src/sub_renderers/definitions/*.json` - 11 JSON files (chip_grid, mini_card_list, key_value_table, prose_block, stat_row, comparison_panel, timeline_strip, evidence_trail, enabling_conditions, constraining_conditions, nested_sections)
  - `src/api/routes/sub_renderers.py:1-180` - REST API endpoints
- **API Endpoints**:
  - `GET /v1/sub-renderers` - List summaries
  - `GET /v1/sub-renderers/{key}` - Full definition
  - `GET /v1/sub-renderers/for-parent/{renderer_type}` - Compatible sub-renderers
  - `GET /v1/sub-renderers/for-data-shape/{shape}` - By data shape
  - `POST/PUT/DELETE /v1/sub-renderers/{key}` - CRUD
  - `POST /v1/sub-renderers/reload` - Force reload
- **Added**: 2026-02-23

## Consumer Capabilities (First-Class Entity)

### Consumer Definitions
- **Status**: Active
- **Description**: 3 consumer definitions (the-critic, visualizer, analyzer-mgmt) that declare supported_renderers and supported_sub_renderers. Inverts the renderer→app coupling — apps declare what they can render, not renderers declaring which apps they work in. Renderer `for_app()` now queries ConsumerRegistry first.
- **Entry Points**:
  - `src/consumers/schemas.py:1-60` - ConsumerDefinition, ConsumerPage, ConsumerSummary models
  - `src/consumers/registry.py:1-150` - ConsumerRegistry with consumers_for_renderer(), renderers_for_consumer()
  - `src/consumers/definitions/*.json` - 3 JSON files
  - `src/api/routes/consumers.py:1-150` - REST API endpoints
  - `src/renderers/registry.py:120-140` - for_app() queries ConsumerRegistry
- **API Endpoints**:
  - `GET /v1/consumers` - List summaries
  - `GET /v1/consumers/{key}` - Full definition
  - `GET /v1/consumers/{key}/renderers` - Supported renderer definitions
  - `POST/PUT/DELETE /v1/consumers/{key}` - CRUD
  - `POST /v1/consumers/reload` - Force reload
- **Added**: 2026-02-23

## View Patterns (Reusable Templates)

### View Pattern Definitions
- **Status**: Active
- **Description**: 6 reusable view pattern templates extracted from existing concrete views. Each captures renderer + config + sub-renderer combinations with instantiation hints for LLM orchestrators. Patterns: accordion_sections, card_grid_grouped, tab_with_children, prose_narrative, card_grid_simple, timeline_sequential.
- **Entry Points**:
  - `src/views/pattern_schemas.py:1-60` - ViewPattern, ViewPatternSummary models
  - `src/views/pattern_registry.py:1-150` - PatternRegistry with for_renderer(), for_data_shape()
  - `src/views/patterns/*.json` - 6 JSON files
  - `src/api/routes/view_patterns.py:1-180` - REST API endpoints
- **API Endpoints**:
  - `GET /v1/views/patterns` - List summaries
  - `GET /v1/views/patterns/{key}` - Full definition
  - `GET /v1/views/patterns/for-renderer/{type}` - By renderer type
  - `GET /v1/views/patterns/for-data-shape/{shape}` - By data shape
  - `POST/PUT/DELETE /v1/views/patterns/{key}` - CRUD
  - `POST /v1/views/patterns/reload` - Force reload
- **Added**: 2026-02-23

## Analytical & Presentation Stances (Operations)

### Stances Library
- **Status**: Active
- **Description**: Two types of stances: (1) Analytical stances (7) describe HOW an LLM should think in a given pass — discovery, inference, confrontation, architecture, integration, reflection, dialectical. (2) Presentation stances (6) describe HOW to render output for display — summary, evidence, comparison, narrative, interactive, diagnostic. Both are prose descriptions; analytical stances are injected into LLM prompts, presentation stances guide LLM transformations from prose to structured formats. Distinguished by `stance_type` field.
- **Entry Points**:
  - `src/operations/schemas.py:1-70` - AnalyticalStance (with stance_type, ui_pattern fields) and StanceSummary Pydantic models
  - `src/operations/definitions/stances.yaml:1-360` - 13 stance definitions (7 analytical + 6 presentation)
  - `src/operations/registry.py:1-90` - StanceRegistry class (get, list with stance_type filter, filter by position)
  - `src/api/routes/operations.py:1-82` - API routes with ?type= query parameter
  - `src/api/main.py:82-90` - Stance registry loading in lifespan, init_stance_registry for capability composer
- **Analytical Stances** (7 total, stance_type="analytical"):
  - `discovery` (early, divergent) — Cast the widest net, surface everything without filtering
  - `inference` (early, deductive) — Trace what follows from what, map logical chains
  - `confrontation` (middle, adversarial) — Pit findings against each other, test robustness
  - `architecture` (middle, structural) — Map load-bearing skeleton, classify structures
  - `integration` (late, convergent) — Synthesize across dimensions into unified narrative
  - `reflection` (late, meta-cognitive) — Assess the assessment, identify blindspots
  - `dialectical` (middle, generative-contradictory) — Inhabit contradictions productively
- **Presentation Stances** (6 total, stance_type="presentation"):
  - `summary` — Distill to headlines and key points (stat cards, bullet lists, executive briefs)
  - `evidence` — Foreground sources, quotes, traceability (quote cards, citation trails)
  - `comparison` — Side-by-side differential highlighting (split panels, diff views)
  - `narrative` — Flowing prose with structure markers (formatted long-form, section anchors)
  - `interactive` — Drill-down affordances (expandable cards, nested tabs, filter controls)
  - `diagnostic` — Expose methodology, confidence, gaps (confidence meters, coverage matrices)
- **API Endpoints**:
  - `GET /v1/operations/stances` - List stance summaries (with ?type=analytical or ?type=presentation filter)
  - `GET /v1/operations/stances/full` - List all stances with full prose (with ?type= filter)
  - `GET /v1/operations/stances/{key}` - Get single stance
  - `GET /v1/operations/stances/{key}/text` - Get just the stance prose for prompt injection
  - `GET /v1/operations/stances/position/{position}` - Filter by typical position (early/middle/late)
- **Added**: 2026-02-17 | **Modified**: 2026-02-18

## Capability Definition History Tracking

### Auto-Detection History System
- **Status**: Active
- **Description**: File-based JSON history system that detects YAML capability definition changes on startup. Computes stable SHA-256 hashes, generates field-level diffs across all 6 sections (top_level, intellectual_lineage, analytical_dimensions, capabilities, composability, depth_levels), stores baseline + change entries committed to git for persistence across deploys.
- **Entry Points**:
  - `src/engines/history_schemas.py:1-55` - Pydantic models: ChangeAction, FieldChange, HistoryEntry, CapabilityHistory
  - `src/engines/history_tracker.py:1-320` - Core logic: compute_definition_hash, diff_definitions, generate_summary, check_and_record_changes, file I/O
  - `src/engines/registry.py:261-271` - Integration into _load_capability_definitions() (try/except wrapped)
  - `src/api/routes/engines.py:509-537` - GET /{key}/capability-definition/history endpoint
  - `src/engines/capability_history/` - 11 JSON history files + 11 snapshot files (auto-populated)
- **API Endpoints**: `GET /v1/engines/{key}/capability-definition/history?limit=50`
- **Added**: 2026-02-17

## Capability Engine Definitions (v2 Format)

### Capability-Driven Engine Definitions
- **Status**: Active (11 engines with capability definitions, 61 enriched capabilities, all 11 with operationalizations; 4 engines use dialectical stance in deep mode; all lineage enriched with bios/descriptions/definitions)
- **Description**: New engine definition format describing WHAT an engine investigates (problematique, analytical dimensions, capabilities, composability) rather than HOW it formats output (fixed schemas, extraction steps). Part of the schema-on-read architecture. Now includes PassDefinition for explicit multi-pass structure with analytical stances. All 11 engines have enriched intellectual lineage with ThinkerReference (name + bio), TraditionEntry (name + description), KeyConceptEntry (name + definition) — union types for backwards compatibility. Four engines use the dialectical stance in their deep analysis mode. All 11 engines have 0 orphaned dimensions and genuine multi-pass at deep depth. All 61 capabilities enriched with extended_description, intellectual_grounding (thinker/concept/method), indicators, and depth_scaling.
- **Entry Points**:
  - `src/engines/schemas_v2.py:1-350` - Pydantic models (CapabilityEngineDefinition, AnalyticalDimension, EngineCapability, CapabilityGrounding, ComposabilitySpec, DepthLevel, PassDefinition, IntellectualLineage, ThinkerReference, TraditionEntry, KeyConceptEntry, CapabilityEngineSummary)
  - `scripts/enrich_capabilities.py:1-315` - Generation script using Claude API to enrich capabilities with intellectual grounding
  - `scripts/enrich_lineage.py:1-210` - Generation script using Claude API to enrich lineage with bios, descriptions, definitions
  - `src/engines/capability_definitions/conditions_of_possibility_analyzer.yaml:1-314` - First capability definition (8 dimensions, 8 capabilities, composability, 3 depth levels)
  - `src/engines/capability_definitions/concept_evolution.yaml:1-253` - Concept Evolution Tracker (6 dimensions: vocabulary/methodology/metaphor/framing evolution, concept trajectory, dimensional comparison matrix; Koselleck/Skinner/Kuhn lineage; first engine in Pass 2 scanning chain)
  - `src/engines/capability_definitions/concept_appropriation_tracker.yaml:1-261` - Concept Appropriation Tracker (6 dimensions: migration paths, semantic mutations, appropriation patterns, distortion map, recombination, acknowledgment status; Derrida/Said/Bakhtin/Bloom lineage; second engine in Pass 2 scanning chain)
  - `src/engines/registry.py:216-268` - Capability definition loading from YAML, registry methods
  - `src/api/routes/engines.py:155-175` - List endpoint `/v1/engines/capability-definitions`
  - `src/api/routes/engines.py:483-503` - Detail endpoint `/{key}/capability-definition`
- **API Endpoints**: `GET /v1/engines/capability-definitions`, `GET /v1/engines/{key}/capability-definition`
- **Architecture Docs**: `docs/refactoring_engines.md`, `docs/plain_text_architecture.md`
- **Added**: 2026-02-16

### Capability-Based Prompt Composer
- **Status**: Active
- **Description**: Composes prose-focused prompts from capability definitions. Two modes: (1) whole-engine prompts for backward compatibility, (2) per-pass prompts using analytical stances. Always asks for prose, never JSON.
- **Entry Points**:
  - `src/stages/capability_composer.py:1-401` - CapabilityPrompt, PassPrompt models; compose_capability_prompt(), compose_pass_prompt(), compose_all_pass_prompts()
  - `src/api/routes/engines.py:505-540` - Whole-engine prompt endpoint `/{key}/capability-prompt`
  - `src/api/routes/engines.py` - Per-pass endpoints `/{key}/pass-prompts`, `/{key}/pass-prompts/{pass_number}`
- **API Endpoints**:
  - `GET /v1/engines/{key}/capability-prompt?depth=standard&dimensions=...` - Whole-engine prompt
  - `GET /v1/engines/{key}/pass-prompts?depth=deep` - All pass prompts for a depth level
  - `GET /v1/engines/{key}/pass-prompts/{pass_number}?depth=deep` - Single pass prompt
- **Added**: 2026-02-16 | **Modified**: 2026-02-17

## Operationalization Layer (Stance-Engine Bridge)

### Operationalization Registry
- **Status**: Active
- **Description**: Third layer bridging abstract stances (HOW to think) and concrete engines (WHAT to think about). Each engine gets an operationalization YAML specifying how each stance applies (label, description, focus dimensions/capabilities) and what depth sequences are available. Pre-generated artifacts that are inspectable, editable, version-controlled, and LLM-(re)generatable. All 11 engines now have operationalizations with 0 orphaned dimensions and genuine multi-pass depth escalation.
- **Entry Points**:
  - `src/operationalizations/schemas.py:1-140` - StanceOperationalization, DepthPassEntry, DepthSequence, EngineOperationalization, summary/coverage models
  - `src/operationalizations/registry.py:1-170` - OperationalizationRegistry with CRUD, coverage_matrix(), get_stance_for_engine(), get_depth_sequence()
  - `src/operationalizations/definitions/*.yaml` - 11 engine operationalization files (all capability engines covered)
  - `src/api/routes/operationalizations.py:1-200` - Full CRUD API with compose-preview endpoint
  - `src/api/routes/llm.py:410-840` - LLM generation endpoints for single, bulk, and sequence generation
  - `src/stages/capability_composer.py:196-290` - compose_all_pass_prompts() with operationalization-first fallback pattern
  - `scripts/extract_operationalizations.py` - One-time extraction script
- **API Endpoints**:
  - `GET /v1/operationalizations/` - List summaries
  - `GET /v1/operationalizations/coverage` - Engine x Stance coverage matrix
  - `GET /v1/operationalizations/{engine_key}` - Full engine operationalization
  - `GET/PUT /v1/operationalizations/{engine_key}/stances/{stance_key}` - Single stance op CRUD
  - `GET/PUT /v1/operationalizations/{engine_key}/depths/{depth_key}` - Depth sequence CRUD
  - `POST /v1/operationalizations/{engine_key}/compose-preview` - Preview composed prompt
  - `POST /v1/llm/operationalization-generate` - LLM generate single stance op
  - `POST /v1/llm/operationalization-generate-all` - LLM generate all stances for engine
  - `POST /v1/llm/operationalization-generate-sequence` - LLM generate depth sequence with data flow
- **Frontend** (analyzer-mgmt):
  - `frontend/src/pages/operationalizations/index.tsx` - Coverage grid + engine list
  - `frontend/src/pages/operationalizations/[key].tsx` - Interactive editor: drag-and-drop depth sequence editing, add/remove stance passes, per-stance Generate/Preview buttons, save/reset with dirty tracking
  - `frontend/src/types/index.ts` - TypeScript types for operationalization entities
  - `frontend/src/lib/api.ts` - API client methods incl. full PUT update (direct fetch to ANALYZER_V2_URL)
  - `frontend/src/components/Layout.tsx` - Navigation item
- **Operationalization Files** (11 total):
  - `conditions_of_possibility_analyzer.yaml` - 4 stances (discovery/architecture/confrontation/integration), deep=4 passes
  - `inferential_commitment_mapper.yaml` - 4 stances, deep=4 passes
  - `concept_semantic_constellation.yaml` - 4 stances, deep=4 passes
  - `concept_synthesis.yaml` - 4 stances, deep=4 passes
  - `concept_taxonomy_argumentative_function.yaml` - 4 stances, deep=3 passes
  - `conceptual_framework_extraction.yaml` - 4 stances, deep=3 passes
  - `concept_evolution.yaml` - 4 stances (discovery/inference/architecture/integration), deep=3 passes
  - `concept_appropriation_tracker.yaml` - 4 stances (discovery/inference/architecture/integration), deep=3 passes
  - `evolution_tactics_detector.yaml` - 3 stances, deep=3 passes
  - `genealogy_relationship_classification.yaml` - 4 stances (discovery/inference/architecture/confrontation), deep=3 passes (discovery→architecture→confrontation)
  - `genealogy_final_synthesis.yaml` - 3 stances (discovery/architecture/integration), deep=3 passes (discovery→architecture→integration)
- **Added**: 2026-02-17 | **Modified**: 2026-02-18

## Transformation Templates (LLM Transformation Service)

### Transformation Template Entity
- **Status**: Active
- **Description**: Named, reusable transformation recipes for schema-on-read data transformation. 5 types: none (passthrough), schema_map (field renaming), llm_extract (structured extraction from prose via Claude Haiku), llm_summarize (summarization via Claude Haiku), aggregate (group-by/count/sort). Templates can be applied to view definitions as one-time copies. Includes in-memory TTL cache for LLM results. Each template tagged with `generation_mode` ("curated" for hand-authored, "generated" for LLM-generated, "hybrid" for generated then refined).
- **Entry Points**:
  - `src/transformations/schemas.py:1-80` - Pydantic models: AggregateConfig, TransformationTemplate, TransformationTemplateSummary (incl. generation_mode field)
  - `src/transformations/registry.py:1-150` - TransformationRegistry: load from JSON, singleton, CRUD, filter by type/tag/engine
  - `src/transformations/executor.py:1-200` - TransformationExecutor: executes all 5 types, TTL cache, Claude Haiku with Sonnet fallback
  - `src/transformations/generator.py:1-370` - LLM-powered template generation: exemplar selection, rich engine/renderer context building, Claude Sonnet generation
  - `src/transformations/definitions/*.json` - 17 template files
  - `src/api/routes/transformations.py:1-478` - Full REST API: CRUD + execute + generate + for-engine + for-renderer + for-pattern + reload
  - `src/api/main.py:18` - Router registration and lifespan loading
  - `src/llm/client.py:1-100` - Shared LLM utilities: get_anthropic_client, parse_llm_json_response, call_extraction_model
- **Templates** (17 total, 1 deprecated):
  - `conditions_extraction` (llm_extract) - Extract structured conditions from genealogy prose
  - `tactics_extraction` (llm_extract) - Extract evolution tactics from genealogy prose
  - `functional_extraction` (llm_extract) - Extract functional analysis from genealogy prose
  - `synthesis_extraction` (llm_extract) - Extract synthesis structure from genealogy prose
  - `chain_log_field_map` (schema_map) - Rename chain execution log fields for display
  - `target_profile_extraction` (llm_extract, **DEPRECATED**) - Old monolithic target profile extraction
  - `tp_conceptual_framework_extraction` (llm_extract, 20k tokens) - Rich frameworks, vocabulary maps, metaphors
  - `tp_semantic_constellation_extraction` (llm_extract, 18k tokens) - Core concepts, clusters, load-bearing terms
  - `tp_inferential_commitments_extraction` (llm_extract, 20k tokens) - Commitments, hidden premises, argumentative structure
  - `tp_concept_evolution_extraction` (llm_extract, 16k tokens) - Evolution trajectories, Koselleckian analysis
- **Domain Metadata**: All templates tagged with `domain` (genealogy/generic), `pattern_type` (section_extraction, table_extraction, etc.), `data_shape_out` (object_array, nested_sections, etc.), `compatible_sub_renderers` (sub-renderer keys)
- **API Endpoints**:
  - `GET /v1/transformations` - List summaries (?type=&tag=)
  - `GET /v1/transformations/{template_key}` - Full template
  - `POST /v1/transformations` - Create
  - `PUT /v1/transformations/{template_key}` - Update
  - `DELETE /v1/transformations/{template_key}` - Delete
  - `POST /v1/transformations/reload` - Reload from disk
  - `GET /v1/transformations/for-engine/{engine_key}` - By engine
  - `GET /v1/transformations/for-renderer/{renderer_type}` - By renderer
  - `GET /v1/transformations/for-pattern?domain=&data_shape=&renderer_type=` - Cross-domain pattern query
  - `POST /v1/transformations/generate` - LLM-powered template generation (v2: rich engine metadata + renderer specs + exemplars)
  - `POST /v1/transformations/execute` - Execute transformation (inline spec or template reference)
- **Dynamic Generation** (v2):
  - Exemplar selection: scores existing templates by renderer_type match (+3), data_shape match (+2), pattern_type (+1), llm_extract type (+1); top 3 used as few-shot context
  - Engine context: canonical_schema (100% coverage), extraction_focus (82%), key_fields, core_question, extraction_steps, key_relationships, special_instructions
  - Renderer context: ideal_data_shapes, config_schema.properties, input_data_schema, available_section_renderers
  - Generated templates auto-tagged: `generation_mode="generated"`, `status="draft"`
- **Frontend** (analyzer-mgmt):
  - `frontend/src/pages/transformations/index.tsx` - List page with type-colored badges, search, type filter
  - `frontend/src/pages/transformations/[key].tsx` - Detail page: 6 tabs (Identity, Specification, Applicability, Execution Config, Test, Preview)
  - `frontend/src/types/index.ts` - TypeScript types for transformation entities
  - `frontend/src/lib/api.ts` - API client methods (direct fetch to ANALYZER_V2_URL)
  - `frontend/src/components/Layout.tsx` - Navigation item
- **Added**: 2026-02-18 | **Modified**: 2026-02-23

## Schema-on-Read / Prose Pipeline (the-critic)

### Prose Output Infrastructure
- **Status**: Active — All 4 sections (conditions, tactics, functional, synthesis) via analyzer-v2 delegation
- **Description**: Full prose-mode pipeline where LLM outputs analytical prose instead of forced JSON. Structured data extracted at presentation time via analyzer-v2's transformation service (Phase 5), with local Claude Haiku fallback when v2 is unreachable. The Critic is a thin orchestrator: load prose → check DB cache → delegate to v2 → cache result.
- **Entry Points** (in the-critic project):
  - `analyzer/output_store.py` - Persistent storage for prose outputs with lineage tracking and presentation cache
  - `analyzer/context_broker.py` - Cross-pass prose context assembly for LLM prompts
  - `analyzer/presentation.py` - Generic SECTION_CONFIG-driven extraction: v2-first with local fallback, ~454 lines (refactored from ~700)
  - `analyzer/concept_analyzer/analyzer_v2_client.py` - `execute_transformation()` + sync wrapper for v2 delegation
  - `analyzer/analyze_genealogy.py` - output_mode="prose" parameter, capability-based prompts, prose output saving
  - `api/server.py` - `POST /api/genealogy/{job_id}/present/{section}` generic endpoint (replaces 4 hardcoded), pre-extraction on job completion
  - `webapp/src/pages/GenealogyPage.tsx` - ConditionsTab dual-mode rendering (legacy JSON or prose extraction)
  - `webapp/src/pages/GenealogyPage.css` - Prose mode UI styles (spinner, badges, error states)
- **Modified**: 2026-02-18
- **Data Flow**: analyze_genealogy (prose output) → analysis_outputs DB → presentation.py (Haiku extraction) → presentation_cache DB → frontend
- **Added**: 2026-02-16

## Functions (First-Class Entity)

### Function Definitions
- **Status**: Active
- **Description**: First-class LLM function entities from decider-v2. 24 functions with prompt templates, model config, I/O contracts, implementation locations, and DAG relationships.
- **Entry Points**:
  - `src/functions/schemas.py:1-305` - Pydantic models (FunctionDefinition, FunctionSummary, PromptTemplate, ModelConfigSpec, IOContract, Implementation)
  - `src/functions/registry.py:1-140` - FunctionRegistry with search, filter, and reload
  - `src/functions/definitions/` - 24 JSON files (coordinator_decision, question_generation, emergent_synthesis, etc.)
  - `src/api/routes/functions.py:1-172` - Full REST API (list, get, categories, projects, prompts, implementations)
  - `src/api/main.py:16` - Router registration and lifespan loading
- **Categories**: coordination (3), generation (3), analysis (2), synthesis (2), tool (11), infrastructure (3)
- **Tiers**: strategic (Opus, 3), tactical (Sonnet, 16), lightweight (Haiku, 5)
- **Schema Features**:
  - `prompt_templates[]` - Full prompt text with {variable} placeholders per role
  - `model_config_spec` - Model name, max_tokens, thinking_budget, streaming, temperature
  - `io_contract` - Input/output descriptions with optional JSON schemas
  - `implementations[]` - Code locations with file path, symbol, line numbers, GitHub URLs
  - `depends_on_functions[]` / `feeds_into_functions[]` - DAG edges between functions
  - `invocation_pattern` - every_question, periodic, on_demand, once_per_session, per_vector
- **API Endpoints**: `/v1/functions`, `/v1/functions/{key}`, `/v1/functions/categories`, `/v1/functions/projects`, `/v1/functions/{key}/prompts`, `/v1/functions/{key}/implementations`, `/v1/functions/project/{project}`
- **Added**: 2026-02-12

### Decider Workflow Definitions (3 new)
- **Status**: Active
- **Description**: Function-backed workflow definitions for decider-v2's main loops using `function_key` instead of `engine_key`
- **Entry Points**:
  - `src/workflows/definitions/decider_question_lifecycle.json` - 5-phase: coordinator → question gen → quality check → synthesis → implications
  - `src/workflows/definitions/decider_onboarding.json` - 4-phase: vector init (IDEAS + PROCESS) → dedup → grid analysis
  - `src/workflows/definitions/decider_answer_processing.json` - 6-phase: category → synthesis → implications → handoff → weight → grid
- **Category**: DECISION_SUPPORT (new WorkflowCategory)
- **Schema Extension**: `WorkflowPhase.function_key` field added alongside `engine_key`
- **Added**: 2026-02-12

## Audiences (First-Class Entity)

### Audience Definitions
- **Status**: Active
- **Description**: First-class audience entities with rich multi-section definitions. 5 audiences (analyst, executive, researcher, activist, social_movements) extracted from analyzer's monolithic audience_profiles.py into individual JSON files.
- **Entry Points**:
  - `src/audiences/schemas.py:1-230` - Pydantic models (AudienceDefinition, 8 sub-models, AudienceSummary)
  - `src/audiences/registry.py:1-230` - AudienceRegistry with CRUD + utility methods
  - `src/audiences/definitions/` - 5 JSON files (analyst.json, executive.json, researcher.json, activist.json, social_movements.json)
  - `src/api/routes/audiences.py:1-250` - Full REST API (list, get, per-section getters, CRUD, guidance, translate, engine-weight)
  - `src/api/main.py:16` - Router registration and lifespan loading
  - `src/stages/composer.py:177-232` - StageComposer integration (registry-first guidance, global vocab merge)
  - `scripts/extract_audiences.py` - Migration script from analyzer
- **Sections per Audience**:
  - Identity (core_questions, priorities, deprioritize, detail_level)
  - Engine Affinities (preferred_categories, high/low affinity engines, category_weights)
  - Visual Style (aesthetic, color palette, typography, layout, density, tone)
  - Textual Style (voice, structure, evidence handling, word count guidance)
  - Curation Guidance (curation emphasis, fidelity constraint)
  - Strategist Guidance (num visualizations, table purposes, narrative focus)
  - Pattern Discovery (pattern types priority, meta insight focus, significance)
  - Vocabulary (1,599 technical→audience translations, guidance intro/outro)
- **API Endpoints**: `/v1/audiences`, `/v1/audiences/{key}`, per-section getters, `/guidance`, `/translate/{term}`, `/engine-weight/{engine_key}`
- **Added**: 2026-02-12

## Concept Analysis Tabs

### New Concept Analysis Engines (3 new tab types)
- **Status**: Active
- **Description**: Three new concept analysis types for multi-tab breakdown alongside Inferential Role, Logical Structure, and Assumption Excavator
- **Entry Points**:
  - `src/engines/definitions/concept_semantic_field.json` - Semantic Field tab
  - `src/engines/definitions/concept_causal_architecture.json` - Causal Architecture tab
  - `src/engines/definitions/concept_metaphorical_ground.json` - Metaphorical Ground tab
- **Tab Strategy**:
  - **Semantic Field**: What does this concept mean? Maps boundaries, neighbors, definitional variations
  - **Causal Architecture**: How does it figure in causal claims? Maps causes, effects, mechanisms, conditions
  - **Metaphorical Ground**: What metaphors structure understanding? Maps root metaphors, source domains, framings
- **Each Engine Includes**:
  - Rich canonical_schema with multiple output sections
  - Detailed extraction_steps for the LLM
  - Audience vocabulary calibration
  - Concretization examples
- **Category**: CONCEPTS
- **Added**: 2026-02-08

## Engine Upgrade System

### Engine Upgrade Script
- **Status**: Active
- **Description**: CLI tool to generate advanced engine definitions using Claude API with extended thinking
- **Entry Points**:
  - `scripts/upgrade_engine.py` - Main upgrade script with CLI interface
  - `engine_upgrade_context/system_prompt.md` - Comprehensive system prompt for engine generation
  - `engine_upgrade_context/methodology_database.yaml` - Database of 10 priority engines with theorists, concepts
  - `engine_upgrade_context/examples/*.json` - Example advanced engines for few-shot learning
  - `outputs/upgraded_engines/` - Output directory for generated definitions
- **Dependencies**: Anthropic SDK, PyYAML, Pydantic v2
- **Usage**:
  - `python scripts/upgrade_engine.py causal_inference_auditor` - Generate advanced version
  - `python scripts/upgrade_engine.py engine_key --dry-run` - Preview prompt without API call
  - `python scripts/upgrade_engine.py engine_key --estimate-tokens` - Show token estimate
- **Priority Engines in Database**: causal_inference_auditor, intelligence_requirements_mapper, authenticity_forensics, counterfactual_analyzer, complexity_threshold_detector, charitable_reconstruction, absent_center, motte_bailey_detector, competing_explanations_analyzer, path_dependency_analyzer
- **Added**: 2026-01-31

## Engine Definitions

### Engine Registry
- **Status**: Active
- **Description**: Loads and serves 178+ engine definitions from JSON files
- **Entry Points**:
  - `src/engines/registry.py:1-100` - EngineRegistry class
  - `src/engines/schemas.py:1-150` - EngineDefinition Pydantic model
  - `src/engines/definitions/*.json` - 178 engine definition files
- **Categories**: 14 categories (ARGUMENT, EPISTEMOLOGY, METHODOLOGY, SYSTEMS, CONCEPTS, EVIDENCE, TEMPORAL, POWER, INSTITUTIONAL, MARKET, RHETORIC, SCHOLARLY, VULNERABILITY, OUTLINE)
- **Dependencies**: Pydantic v2
- **Added**: 2026-01-26 | **Modified**: 2026-02-06

### Engine Profile (About Section)
- **Status**: Active
- **Description**: Rich "About" section for engines with theoretical foundations, methodology, use cases
- **Entry Points**:
  - `src/engines/schemas.py:216-359` - EngineProfile and related Pydantic models
  - `src/api/routes/engines.py:310-370` - Profile CRUD endpoints (GET/PUT/DELETE)
  - `src/api/routes/llm.py:1-300` - LLM-powered profile generation endpoints
  - `src/engines/registry.py:123-180` - save_profile/delete_profile methods
- **Dependencies**: Anthropic SDK (optional, for LLM generation)
- **Added**: 2026-01-30

### Engine Extraction Script
- **Status**: Active
- **Description**: Extracts engine definitions from current Analyzer to JSON
- **Entry Points**:
  - `scripts/extract_engines.py:1-100` - Main extraction script
- **Dependencies**: Current Analyzer at /home/evgeny/projects/analyzer
- **Added**: 2026-01-26

### App Tagging System
- **Status**: Active
- **Description**: Filter engines by consuming application (e.g., "critic", "visualizer")
- **Entry Points**:
  - `src/engines/schemas.py:152-157` - `apps` field on EngineDefinition
  - `src/engines/schemas.py:210` - `apps` field on EngineSummary
  - `src/api/routes/engines.py:50-51` - `app` query parameter on list endpoint
  - `src/api/routes/engines.py:103-110` - `/v1/engines/apps` endpoint
  - `scripts/tag_critic_engines.py` - Bulk tagging script
- **API Usage**:
  - `GET /v1/engines?app=critic` - Filter to engines used by The Critic
  - `GET /v1/engines/apps` - List all unique app tags
- **Tagged Apps**: `critic` (63 engines)
- **Added**: 2026-02-07

## Advanced Engines

Ten advanced engines with deep theoretical foundations, cross-referencing ID systems, relationship graphs, and rich stage contexts.

### Inferential Commitment Mapper Advanced
- **Status**: Active
- **Description**: Advanced Brandomian inferentialism analysis with commitment/entitlement tracking, backing hierarchies
- **Entry Points**:
  - `src/engines/definitions/inferential_commitment_mapper_advanced.json`
- **Theoretical Foundations**: Brandom, Sellars, McDowell
- **Added**: 2026-01-29

### Dialectical Structure Advanced
- **Status**: Active
- **Description**: Hegelian dialectics with thesis/antithesis/synthesis, sublation patterns, master-slave dynamics
- **Entry Points**:
  - `src/engines/definitions/dialectical_structure_advanced.json`
- **Theoretical Foundations**: Hegel, Marx, Adorno
- **Added**: 2026-01-30

### Assumption Excavation Advanced
- **Status**: Active
- **Description**: Epistemological archaeology with hinge propositions, webs of belief, presuppositional depth
- **Entry Points**:
  - `src/engines/definitions/assumption_excavation_advanced.json`
- **Theoretical Foundations**: Wittgenstein, Quine, Collingwood
- **Added**: 2026-01-30

### Conditions of Possibility Advanced
- **Status**: Active
- **Description**: Foucauldian archaeology/genealogy with epistemes, discursive formations, apparatus analysis
- **Entry Points**:
  - `src/engines/definitions/conditions_of_possibility_advanced.json`
- **Theoretical Foundations**: Foucault, Deleuze, Agamben
- **Added**: 2026-01-30

### Epistemic Rupture Tracer Advanced
- **Status**: Active
- **Description**: History of science with paradigm shifts, epistemological obstacles, research programme dynamics
- **Entry Points**:
  - `src/engines/definitions/epistemic_rupture_tracer_advanced.json`
- **Theoretical Foundations**: Bachelard, Kuhn, Lakatos, Canguilhem
- **Added**: 2026-01-30

### Rhetorical Strategy Advanced
- **Status**: Active
- **Description**: Dramatistic pentad, identification/division, terministic screens, presence techniques
- **Entry Points**:
  - `src/engines/definitions/rhetorical_strategy_advanced.json`
- **Theoretical Foundations**: Burke, Aristotle, Perelman, Booth
- **Added**: 2026-01-30

### Metaphor Network Advanced
- **Status**: Active
- **Description**: Conceptual metaphor theory with image schemas, entailment chains, metaphor competitions
- **Entry Points**:
  - `src/engines/definitions/metaphor_network_advanced.json`
- **Theoretical Foundations**: Lakoff, Johnson, Ricoeur, Black
- **Added**: 2026-01-30

### Argument Architecture Advanced
- **Status**: Active
- **Description**: Toulmin model + argumentation schemes, critical questions, dialectical obligations
- **Entry Points**:
  - `src/engines/definitions/argument_architecture_advanced.json`
- **Theoretical Foundations**: Toulmin, Walton, van Eemeren, pragma-dialectics
- **Added**: 2026-01-30

### Intellectual Genealogy Advanced
- **Status**: Active
- **Description**: History of ideas with creative misreadings, transmission paths, unit-ideas
- **Entry Points**:
  - `src/engines/definitions/intellectual_genealogy_advanced.json`
- **Theoretical Foundations**: Foucault, Lovejoy, Bloom, Skinner
- **Added**: 2026-01-30

### Incentive Structure Mapper Advanced
- **Status**: Active
- **Description**: Institutional economics with game theory, principal-agent problems, perverse incentives
- **Entry Points**:
  - `src/engines/definitions/incentive_structure_mapper_advanced.json`
- **Theoretical Foundations**: Ostrom, Buchanan, Tullock, Olson
- **Added**: 2026-01-30

### Feedback Loop Mapper Advanced
- **Status**: Active
- **Description**: Systems dynamics with stocks/flows, leverage points, system archetypes, tipping points
- **Entry Points**:
  - `src/engines/definitions/feedback_loop_mapper_advanced.json`
- **Theoretical Foundations**: Meadows, Senge, Sterman, Forrester
- **Added**: 2026-01-30

## Paradigm Definitions

### Paradigm Registry
- **Status**: Active
- **Description**: Loads and serves paradigm definitions with 4-layer ontology
- **Entry Points**:
  - `src/paradigms/registry.py:1-150` - ParadigmRegistry class with primer generation
  - `src/paradigms/schemas.py:1-250` - ParadigmDefinition with 4-layer ontology
  - `src/paradigms/instances/*.json` - Paradigm instance files
- **Dependencies**: Pydantic v2
- **Added**: 2026-01-26

### Marxist Paradigm
- **Status**: Active
- **Description**: Full 4-layer ontology for Marxist analysis
- **Entry Points**:
  - `src/paradigms/instances/marxist.json` - Complete paradigm definition
- **Added**: 2026-01-26

### Brandomian Paradigm
- **Status**: Active
- **Description**: Full 4-layer ontology for inferentialist analysis
- **Entry Points**:
  - `src/paradigms/instances/brandomian.json` - Complete paradigm definition
- **Added**: 2026-01-26

## Chain Definitions

### Chain Registry
- **Status**: Active
- **Description**: Loads and serves engine chain specifications
- **Entry Points**:
  - `src/chains/registry.py:1-100` - ChainRegistry class
  - `src/chains/schemas.py:1-100` - EngineChainSpec model
  - `src/chains/definitions/*.json` - Chain definition files
- **Dependencies**: Pydantic v2
- **Added**: 2026-01-26

### Concept Analysis Suite Chain
- **Status**: Active
- **Description**: Multi-engine concept analysis with LLM selection
- **Entry Points**:
  - `src/chains/definitions/concept_analysis_suite.json`
- **Added**: 2026-01-26

### Critical Analysis Chain
- **Status**: Active
- **Description**: Sequential critical analysis pipeline
- **Entry Points**:
  - `src/chains/definitions/critical_analysis_chain.json`
- **Added**: 2026-01-26

### 12-Phase Concept Analysis Chain
- **Status**: Active
- **Description**: Comprehensive 12-phase deep concept analysis pipeline from The Critic
- **Entry Points**:
  - `src/chains/definitions/concept_analysis_12_phase.json`
- **Phases**: semantic_constellation → structural_landscape → argument_formalization → chain_building → taxonomy → causal → conditional → weight → vulnerability → cross_text → quotes → synthesis
- **Added**: 2026-02-06

## The Critic Extraction

### Rhetoric Engines (7 new)
- **Status**: Active
- **Description**: Debate response analysis engines from The Critic
- **Entry Points**:
  - `src/engines/definitions/rhetoric_deflection_analyzer.json` - Claims of misunderstanding when engaged
  - `src/engines/definitions/rhetoric_contradiction_detector.json` - Position changes between original & response
  - `src/engines/definitions/rhetoric_leap_finder.json` - Phantom premise attribution
  - `src/engines/definitions/rhetoric_silence_mapper.json` - Unanswered challenges
  - `src/engines/definitions/rhetoric_concession_tracker.json` - Silent position shifts
  - `src/engines/definitions/rhetoric_retreat_detector.json` - Clarifications that weaken claims
  - `src/engines/definitions/rhetoric_cherrypick_analyzer.json` - Selective quotation out of context
- **Source**: The Critic analyzer/analyze_*.py
- **Added**: 2026-02-06

### Vulnerability Engines (9 new)
- **Status**: Active
- **Description**: Counter-response self-analysis engines for identifying weaknesses
- **Entry Points**:
  - `src/engines/definitions/vulnerability_strawman_risk.json` - Potential mischaracterization
  - `src/engines/definitions/vulnerability_inconsistency.json` - Internal contradictions
  - `src/engines/definitions/vulnerability_logic_gap.json` - Non-sequiturs
  - `src/engines/definitions/vulnerability_unanswered.json` - Valid points not addressed
  - `src/engines/definitions/vulnerability_overconcession.json` - Conceding too much ground
  - `src/engines/definitions/vulnerability_overreach.json` - Claims beyond evidence
  - `src/engines/definitions/vulnerability_undercitation.json` - Lacking textual grounding
  - `src/engines/definitions/vulnerability_weak_authority.json` - Authorities that don't support claims
  - `src/engines/definitions/vulnerability_exposed_flank.json` - Tu quoque vulnerabilities
- **Category**: VULNERABILITY (new)
- **Source**: The Critic analyzer
- **Added**: 2026-02-06

### Outline Editor Engines (5 new)
- **Status**: Active
- **Description**: Essay construction operations from The Critic
- **Entry Points**:
  - `src/engines/definitions/outline_talking_point_generator.json` - Transform annotations to talking points
  - `src/engines/definitions/outline_notes_extractor.json` - Extract structured points from notes
  - `src/engines/definitions/outline_talking_point_upgrader.json` - Improve points with outline context
  - `src/engines/definitions/outline_document_summarizer.json` - Create document summaries
  - `src/engines/definitions/outline_synthesis_generator.json` - Synthesize outlines into narratives
- **Category**: OUTLINE (new)
- **Source**: The Critic api/prompts.py
- **Added**: 2026-02-06

### Big Picture Engine
- **Status**: Active
- **Description**: Pre-conceptual document-level analysis for core theses, commitments, tensions
- **Entry Points**:
  - `src/engines/definitions/big_picture_inferential.json`
- **Source**: The Critic analyzer
- **Added**: 2026-02-06

## Workflows

### Workflow Registry
- **Status**: Active
- **Description**: Multi-phase analysis pipelines that differ from chains (intermediate state, caching, resumability). Workflow-level steps are "phases"; engine-level stance iterations are "passes".
- **Entry Points**:
  - `src/workflows/schemas.py:1-194` - WorkflowDefinition, WorkflowPhase, WorkflowCategory (backwards compat: WorkflowPass alias)
  - `src/workflows/registry.py:1-203` - WorkflowRegistry class with save/update_phase/delete methods
  - `src/workflows/definitions/*.json` - 7 workflow definitions
  - `src/api/routes/workflows.py:1-420` - Workflow API endpoints with full CRUD + extension points
- **Workflows** (7 total):
  - `lines_of_attack` - Extract targeted critiques from external thinkers (2 phases)
  - `anxiety_of_influence` - Analyze intellectual debt fidelity (5 phases, engine-backed)
  - `outline_editor` - AI-assisted essay construction (4 phases, engine-backed)
  - `intellectual_genealogy` - **v3**: 11 capability engines, 3 chains, 5 workflow phases. Traces how an author's ideas evolved across prior works. Target profiling → relationship classification → per-work scanning → analysis/synthesis → final synthesis
  - `decider_question_lifecycle` - Function-backed: coordinator → question gen → quality check → synthesis → implications
  - `decider_onboarding` - Function-backed: vector init → dedup → grid analysis
  - `decider_answer_processing` - Function-backed: category → synthesis → implications → handoff → weight → grid
- **API Endpoints**:
  - `GET /v1/workflows` - List all workflows
  - `GET /v1/workflows/{key}` - Get workflow definition
  - `GET /v1/workflows/{key}/phases` - Get workflow phases
  - `GET /v1/workflows/{key}/phase/{n}` - Get specific phase
  - `GET /v1/workflows/{key}/phase/{n}/prompt` - Get composed prompt for a phase
  - `GET /v1/workflows/{key}/extension-points` - Analyze extension opportunities per phase
  - `GET /v1/workflows/category/{category}` - Filter by category
  - `POST /v1/workflows` - Create new workflow
  - `PUT /v1/workflows/{key}` - Update workflow definition
  - `PUT /v1/workflows/{key}/phase/{n}` - Update single phase
  - `DELETE /v1/workflows/{key}` - Delete workflow
  - `POST /v1/workflows/reload` - Force reload from disk
  - Deprecated aliases: `/passes`, `/pass/{n}`, `/pass/{n}/prompt` still work
- **Dependencies**: Pydantic v2
- **Source**: The Critic
- **Added**: 2026-02-06 | **Modified**: 2026-02-18

### Extension Points System
- **Status**: Active
- **Description**: Analyzes WHERE in a workflow additional engines could be plugged in. Scores all engines for composability fit using a 5-tier weighted algorithm (synergy 0.30, dimension production 0.25, dimension novelty 0.20, capability gap 0.15, category affinity 0.10). Returns ranked candidates with human-readable rationale. Graceful degradation for engines without v2 capability definitions.
- **Entry Points**:
  - `src/workflows/extension_points.py:1-130` - Pydantic schemas (DimensionCoverage, CapabilityGap, CandidateEngine, PhaseExtensionPoint, WorkflowExtensionAnalysis)
  - `src/workflows/extension_scorer.py:1-400` - 5-tier scoring algorithm, phase context builder, dimension coverage analysis
  - `src/api/routes/workflows.py:88-110` - GET extension-points endpoint
  - `src/api/routes/workflows.py:114-240` - POST add-engine-to-phase endpoint
  - `src/chains/registry.py:106-140` - ChainRegistry.save() with file-path tracking
- **Scoring Tiers**:
  - Synergy (0.30 weight) — explicit synergy_engines match, bidirectional
  - Dimension production (0.25) — produces dimensions consumed by phase engines
  - Dimension novelty (0.20) — covers dimensions no current engine covers
  - Capability gap (0.15) — fills capabilities the phase lacks
  - Category affinity (0.10) — same analytical category/kind
- **Recommendation Tiers**: strong (>=0.65), moderate (>=0.40), exploratory (>=0.20), tangential (<0.20, filtered)
- **API Endpoints**:
  - `GET /v1/workflows/{key}/extension-points?depth=standard&phase_number=1.0&min_score=0.20&max_candidates=15`
  - `POST /v1/workflows/{key}/phases/{phase_num}/add-engine` — mutates chain/workflow to add engine
- **Added**: 2026-02-18 | **Modified**: 2026-02-18

### Dynamic Propagation System
- **Status**: Active
- **Description**: When engines are added to workflow phases via the UI, changes persist permanently via GitHub commits, descriptions auto-update from engine lists, and cascade to all dependent workflows. Consumer cache versioning via SHA-256 fingerprint endpoint.
- **Entry Points**:
  - `src/persistence/__init__.py` - Persistence package init
  - `src/persistence/github_client.py:1-180` - GitHubPersistence class: atomic multi-file commits via Git Data API, graceful degradation without token
  - `src/workflows/description_generator.py:1-100` - Template-based description generation: `generate_chain_description()`, `generate_phase_description()`
  - `src/api/routes/meta.py:1-80` - Definitions version endpoint: SHA-256 hash, last-modified, counts, persistence status
  - `src/api/routes/workflows.py:114-240` - Add-engine endpoint with description regeneration, cascade, and GitHub commit
  - `src/workflows/registry.py:175-190` - `find_by_chain_key()` method for cross-workflow cascade
  - `src/chains/schemas.py:25-30` - `base_description` field on `EngineChainSpec`
  - `src/workflows/schemas.py:30-35` - `base_phase_description` field on `WorkflowPhase`
- **API Endpoints**:
  - `GET /v1/meta/definitions-version` - Cache validation: version hash, last modified, counts, persistence status
  - `POST /v1/workflows/{key}/phases/{phase_num}/add-engine` - (Enhanced) Now auto-generates descriptions, cascades, commits to GitHub
- **Dependencies**: httpx (GitHub API), GITHUB_TOKEN + GITHUB_REPO env vars (optional — graceful degradation)
- **Added**: 2026-02-18

### Influence Pass Engines (5 new)
- **Status**: Active
- **Description**: Engine definitions for the anxiety_of_influence workflow passes
- **Entry Points**:
  - `src/engines/definitions/influence_pass1_thinker_identification.json` - Identify cited thinkers
  - `src/engines/definitions/influence_pass2_hypothesis_generation.json` - Generate usage hypotheses
  - `src/engines/definitions/influence_pass3_textual_sampling.json` - Sample original texts
  - `src/engines/definitions/influence_pass4_deep_engagement.json` - Compare usage vs actual
  - `src/engines/definitions/influence_pass5_report_generation.json` - Synthesize final report
- **Category**: SCHOLARLY
- **Source**: The Critic prompts_influence.py
- **Added**: 2026-02-08

## Stage Prompt Composition

### Stage Templates
- **Status**: Active
- **Description**: Generic Jinja2 templates for extraction, curation, and concretization stages
- **Entry Points**:
  - `src/stages/templates/extraction.md.j2` - Generic extraction template
  - `src/stages/templates/curation.md.j2` - Generic curation template
  - `src/stages/templates/concretization.md.j2` - Generic concretization template
- **Dependencies**: Jinja2
- **Added**: 2026-01-29

### Stage Composer
- **Status**: Active
- **Description**: Composes prompts at runtime from templates + engine context + frameworks
- **Entry Points**:
  - `src/stages/composer.py:1-200` - StageComposer class with Jinja2 rendering
  - `src/stages/schemas.py:1-200` - StageContext, ExtractionContext, etc.
  - `src/stages/registry.py:1-100` - StageRegistry for templates/frameworks
- **Dependencies**: Jinja2, Pydantic v2
- **Added**: 2026-01-29

### Shared Frameworks
- **Status**: Active
- **Description**: Reusable methodological primers for template injection
- **Entry Points**:
  - `src/stages/frameworks/brandomian.json` - Brandomian inferentialism primer
  - `src/stages/frameworks/dennett.json` - Dennett's critical toolkit
  - `src/stages/frameworks/toulmin.json` - Toulmin model of argumentation
- **Added**: 2026-01-29

### Engine Migration Script
- **Status**: Active
- **Description**: Migrates engines from old prompt format to new stage_context format
- **Entry Points**:
  - `scripts/migrate_engines_to_stages.py` - Migration script with dry-run support
- **Added**: 2026-01-29

## Semantic Visual Intent

### Visual Intent Schema
- **Status**: Active
- **Description**: Schema for specifying semantic visual intent - bridges analytical MEANING to visual FORM
- **Entry Points**:
  - `src/stages/schemas.py:280-350` - SemanticVisualIntent, VisualGrammar, VisualElement, RecommendedForm models
- **Dependencies**: Pydantic v2
- **Added**: 2026-02-03

### Visual Intent API Endpoint
- **Status**: Active
- **Description**: Returns semantic visual intent for visualization systems
- **Entry Points**:
  - `src/api/routes/engines.py:380-410` - GET /v1/engines/{key}/visual-intent endpoint
- **API Response**: `{engine_key, has_semantic_intent, semantic_visual_intent, legacy_visual_patterns}`
- **Added**: 2026-02-03

### Engines with Semantic Visual Intent
- **Status**: Active (5 engines)
- **Description**: Priority engines enriched with semantic visual intent specifications
- **Engines**:
  - `feedback_loop_mapper` - feedback_dynamics → causal loop diagrams, stock-flow diagrams
  - `dialectical_structure` - dialectical_movement → dialectical spirals, force fields
  - `inferential_commitment_mapper` - inferential_chain → commitment cascades, either-or landscapes
  - `causal_inference_auditor` - causal_identification → causal DAGs, threat assessment maps
  - `path_dependency_analyzer` - path_dependency → path branching trees, lock-in diagrams
- **Each Intent Includes**:
  - Visual grammar (core metaphor, key visual elements, anti-patterns, design principles)
  - Recommended forms with Gemini prompt templates
  - Form selection logic (conditional rules)
  - Style affinities (dataviz school recommendations)
- **Added**: 2026-02-03

## Analytical Primitives

### Primitives Registry
- **Status**: Active
- **Description**: Trading zone between engines and visual styles - bridges analytical meaning to visual form
- **Entry Points**:
  - `src/primitives/schemas.py:1-60` - AnalyticalPrimitive, PrimitiveSummary models
  - `src/primitives/registry.py:1-100` - PrimitivesRegistry class
  - `src/primitives/definitions/primitives.json` - 12 primitive definitions
  - `src/api/routes/primitives.py:1-80` - Primitives API endpoints
- **Primitives** (12 total):
  - `cyclical_causation` - Feedback loops, self-reinforcement
  - `hierarchical_support` - Argument trees, warrant structures
  - `dialectical_tension` - Contradictions, thesis-antithesis-synthesis
  - `branching_foreclosure` - Path dependency, lock-in
  - `inferential_bundling` - Commitment chains, package deals
  - `strategic_interaction` - Game theory, payoff structures
  - `epistemic_layering` - Assumptions, presuppositions
  - `temporal_evolution` - Change over time, genealogy
  - `comparative_positioning` - Quadrants, landscapes
  - `flow_transformation` - Sankeys, value streams
  - `rhetorical_architecture` - Persuasion structures
  - `network_influence` - Citation networks, influence graphs
- **API Endpoints**:
  - `GET /v1/primitives` - List primitives
  - `GET /v1/primitives/{key}` - Get primitive details
  - `GET /v1/primitives/for-engine/{key}` - Primitives for an engine
  - `GET /v1/primitives/for-engine/{key}/guidance` - Gemini guidance text
- **Purpose**: Soft guidance for Gemini about visual approaches
- **Added**: 2026-02-05

## Display Configuration

### Display Registry
- **Status**: Active
- **Description**: Centralized display formatting rules, hidden fields, and visual format typology from Visualizer
- **Entry Points**:
  - `src/display/schemas.py:1-80` - DisplayConfig, VisualFormat, DataTypeMapping models
  - `src/display/registry.py:1-140` - DisplayRegistry class
  - `src/display/definitions/display_config.json` - Display configuration (hidden fields, instructions)
  - `src/display/definitions/visual_formats.json` - 40 visual formats in 8 categories
  - `src/api/routes/display.py:1-220` - Display API endpoints
- **Configuration Includes**:
  - Display instructions for Gemini (branding rules, label formatting, numeric display)
  - 23 hidden field names + 5 hidden suffixes (confidence, score, weight, etc.)
  - Numeric-to-label rules (0.85 → "Strong", 0.45 → "Weak")
  - Acronyms that stay uppercase in Title Case
- **Visual Format Categories** (8 total, 40 formats):
  - Relational/Network (5): network_graph, chord_diagram, hierarchical_tree, radial_tree, force_directed
  - Flow/Process (5): sankey_diagram, alluvial_diagram, flowchart, process_flow, value_stream_map
  - Temporal (5): timeline, gantt_chart, parallel_timelines, cycle_diagram, sparklines
  - Comparative (6): matrix_heatmap, quadrant_chart, radar_chart, bar_chart, grouped_bar_chart, dot_plot
  - Part-of-Whole (5): treemap, sunburst, stacked_bar, waterfall_chart, marimekko
  - Spatial/Set (4): venn_diagram, euler_diagram, positioning_map, bubble_chart
  - Evidence/Analytical (5): ach_matrix, confidence_thermometer, evidence_quality_matrix, indicator_dashboard, gap_analysis
  - Argumentative/Logical (5): argument_tree, toulmin_diagram, dialectical_map, assumption_web, scenario_cone
- **Data Type Mappings**: 11 data structure → format recommendations
- **API Endpoints**:
  - `GET /v1/display/config` - Complete display configuration
  - `GET /v1/display/instructions` - Display instructions for Gemini
  - `GET /v1/display/instructions/text` - Plain text instructions
  - `GET /v1/display/hidden-fields` - Hidden fields and suffixes
  - `POST /v1/display/check-field` - Check if field should be hidden
  - `POST /v1/display/numeric-label` - Convert numeric to descriptive label
  - `GET /v1/display/formats` - List format categories
  - `GET /v1/display/formats/all` - All formats flat list
  - `GET /v1/display/formats/category/{key}` - Category with all formats
  - `GET /v1/display/formats/{key}` - Specific format
  - `GET /v1/display/formats/{key}/prompt` - Gemini prompt pattern for format
  - `GET /v1/display/mappings` - Data type → format mappings
  - `GET /v1/display/quality-criteria` - Must-have, should-have, avoid lists
  - `GET /v1/display/stats` - Display statistics
- **Purpose**: Centralize Gemini formatting rules from Visualizer for transparency
- **Added**: 2026-02-05

## Visual Styles

### Style Registry
- **Status**: Active
- **Description**: Serves visual style definitions (6 dataviz schools) and affinity mappings
- **Entry Points**:
  - `src/styles/schemas.py:1-110` - StyleSchool enum, StyleGuide, StyleInfluences, ColorPalette, Typography models
  - `src/styles/registry.py:1-190` - StyleRegistry class for loading definitions
  - `src/styles/definitions/schools/*.json` - 6 style school definition files
  - `src/styles/definitions/affinities.json` - Engine/format/audience affinity mappings
  - `src/api/routes/styles.py:1-145` - Style API endpoints
- **Dataviz Schools** (independent names, proper attribution via influences):
  - `minimalist_precision` - Data-ink ratio maximization, chartjunk elimination
  - `explanatory_narrative` - Reader-friendly annotations, teaching moments
  - `restrained_elegance` - Financial journalism aesthetic, warm signature palette
  - `humanist_craft` - Organic hand-crafted feel, data as human stories
  - `emergent_systems` - Complex networks, structure revelation
  - `mobilization` - Activist graphics, high contrast provocation
- **Influences System** (each style includes):
  - `tradition_note` - How the style draws from broader design traditions
  - `exemplars` - People/organizations who exemplify this approach (with contributions)
  - `key_works` - Foundational texts and projects
- **Affinity Mappings**:
  - 37 engine-to-style affinities
  - 32 format-to-style affinities
  - 11 audience-to-style affinities
- **API Endpoints**:
  - `GET /v1/styles` - List all style schools
  - `GET /v1/styles/schools/{key}` - Get full style guide
  - `GET /v1/styles/affinities/engine` - Engine affinity mappings
  - `GET /v1/styles/affinities/format` - Format affinity mappings
  - `GET /v1/styles/affinities/audience` - Audience affinity mappings
  - `GET /v1/styles/engine-mappings` - All engines with their style affinities
  - `GET /v1/styles/for-engine/{key}` - Preferred styles for an engine
- **Dependencies**: Pydantic v2
- **Added**: 2026-02-05 | **Modified**: 2026-02-06

## API

### FastAPI Application
- **Status**: Active
- **Description**: REST API serving definitions at /v1/*
- **Entry Points**:
  - `src/api/main.py:1-180` - FastAPI app with CORS, health check
  - `src/api/routes/engines.py` - Engine endpoints (incl. profile CRUD)
  - `src/api/routes/paradigms.py` - Paradigm endpoints
  - `src/api/routes/chains.py` - Chain endpoints
  - `src/api/routes/styles.py` - Visual style endpoints
  - `src/api/routes/llm.py` - LLM-powered profile generation
- **Dependencies**: FastAPI, Uvicorn, Pydantic v2, Anthropic SDK (optional)
- **Added**: 2026-01-26 | **Modified**: 2026-02-05
