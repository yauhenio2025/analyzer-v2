# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- **Per-section polish with user feedback** — New `POST /v1/presenter/polish-section` endpoint polishes a single accordion section with optional natural-language user feedback (e.g., "one path per line, reduce scrolling"). Uses Sonnet 4.6 with narrowed context (only the target section's sub-renderer and data shape). Returns section-specific `style_overrides` + `renderer_config_patch`. Cached per (job_id, view_key, section_key, style_school). Frontend: each accordion section header shows a pencil icon on hover; clicking opens a feedback input row; polished sections show a green checkmark with reset option. Per-section overrides take precedence over view-level polish. Auto-persisted in localStorage, auto-loaded on tab change. ([`src/presenter/polisher.py`](src/presenter/polisher.py), [`src/presenter/schemas.py`](src/presenter/schemas.py), [`src/presenter/polish_store.py`](src/presenter/polish_store.py), [`src/api/routes/presenter.py`](src/api/routes/presenter.py))

- **View polishing ("Present" button)** — New `POST /v1/presenter/polish` endpoint calls Sonnet 4.6 to enhance a view's `renderer_config` and produce `style_overrides` using the resolved style school's color palette, typography, and display rules. Results are cached per (job_id, view_key, style_school) in the new `polish_cache` DB table. Style overrides are CSS-like dicts applied at defined injection points: `section_header`, `card`, `chip`, `badge`, `prose`, etc. The frontend adds a "Present" button to V2TabContent that calls the polish endpoint, applies the polished config, and threads `_style_overrides` down through AccordionRenderer → ConditionCards sub-renderers. A "Reset" button restores original appearance. Playwright-tested end-to-end: +45 styled elements / +16K chars inline CSS on Conditions accordion, clean reset, cache hit at 0ms. ([`src/presenter/polisher.py`](src/presenter/polisher.py), [`src/presenter/polish_store.py`](src/presenter/polish_store.py), [`src/presenter/schemas.py`](src/presenter/schemas.py), [`src/executor/db.py`](src/executor/db.py), [`src/api/routes/presenter.py`](src/api/routes/presenter.py))

### Changed
- **Dynamic extraction fallback — templates are now optional** — The presentation bridge no longer requires curated transformation templates for every view. When no template exists for an engine+renderer combination, it composes an extraction prompt at runtime from engine metadata (canonical_schema, extraction_focus, stage_context), renderer shape (ideal_data_shapes, config_schema fields), and presentation stance prose. Haiku extracts structured JSON using the same pipeline — curated templates become optional quality overrides. Every engine is now renderable in any renderer without authoring a template. New `dynamic_extractions` counter in PresentationBridgeResult. New `extraction_source` field (`"curated"` / `"dynamic"`) on TransformationTaskResult. ([`src/presenter/dynamic_prompt.py`](src/presenter/dynamic_prompt.py), [`src/presenter/presentation_bridge.py`](src/presenter/presentation_bridge.py), [`src/presenter/schemas.py`](src/presenter/schemas.py))

### Added
- **Dynamic transformation generation (v2 — rich metadata)** — Upgraded `POST /v1/transformations/generate` from shallow (engine name only) to rich context: canonical_schema, extraction_focus, key_fields, core_question, extraction_steps, key_relationships + renderer ideal_data_shapes, config_schema, input_data_schema + 3 best-matching existing templates as few-shot exemplars. Extracted into dedicated `src/transformations/generator.py` module. Generated templates auto-tagged with `generation_mode="generated"`, `status="draft"`. ([`src/transformations/generator.py`](src/transformations/generator.py), [`src/api/routes/transformations.py`](src/api/routes/transformations.py))

- **View generation from patterns** — New `POST /v1/views/generate` endpoint: takes a view pattern + engine + workflow context → generates a complete ViewDefinition via Claude Sonnet. Uses engine canonical_schema, renderer config_schema, existing page views for position/structure context, and pattern instantiation hints. Supports wiring an existing transformation template, parent_view_key validation, and view_key collision handling (appends `_gen` suffix). Generated views auto-tagged with `generation_mode="generated"`, `status="draft"`. ([`src/views/generator.py`](src/views/generator.py), [`src/api/routes/views.py`](src/api/routes/views.py))

- **`generation_mode` field on transformations and views** — New field (`"curated"` / `"generated"` / `"hybrid"`) on TransformationTemplate, TransformationTemplateSummary, ViewDefinition, and ViewSummary. Defaults to `"curated"` for backward compatibility — existing 17 templates and 21 views load without changes. Surfaced in all list/summary endpoints. ([`src/transformations/schemas.py`](src/transformations/schemas.py), [`src/views/schemas.py`](src/views/schemas.py), [`src/transformations/registry.py`](src/transformations/registry.py), [`src/views/registry.py`](src/views/registry.py))

- **Transformation templates in orchestrator catalog** — Capability catalog now includes a `transformation_templates` section with template_key, description, applicable_engines, applicable_renderers, domain, generation_mode for all templates. Planner system prompt updated to note that transformations and views can be generated dynamically — plans need not be limited to engines with existing templates. ([`src/orchestrator/catalog.py`](src/orchestrator/catalog.py), [`src/orchestrator/planner.py`](src/orchestrator/planner.py))

- **Prose pipeline architecture memo** — Comprehensive documentation of the full data flow: Engine (prose) → Transformation Bridge (LLM extraction) → Presentation Cache → Views → Renderers. Covers schema-on-read principle, 5 engine→view relationship patterns, stances vs transformations comparison, abstraction path for preventing view/transformation proliferation. ([`docs/MEMO_2026-02-23_prose_pipeline_architecture.md`](docs/MEMO_2026-02-23_prose_pipeline_architecture.md))


- **Sub-renderers as first-class entities** — New `src/sub_renderers/` module with schemas, registry, and 11 JSON definitions (chip_grid, mini_card_list, key_value_table, prose_block, stat_row, comparison_panel, timeline_strip, evidence_trail, enabling_conditions, constraining_conditions, nested_sections). Each has category, ideal_data_shapes, config_schema, stance_affinities, parent_renderer_types. API: `GET /v1/sub-renderers`, `GET /v1/sub-renderers/{key}`, `GET /v1/sub-renderers/for-parent/{type}`, CRUD, reload. ([`src/sub_renderers/`](src/sub_renderers/), [`src/api/routes/sub_renderers.py`](src/api/routes/sub_renderers.py))

- **Consumer capabilities** — New `src/consumers/` module with schemas, registry, and 3 JSON definitions (the-critic, visualizer, analyzer-mgmt). Consumers declare supported_renderers and supported_sub_renderers, inverting the renderer→app coupling. Renderer `for_app()` now queries ConsumerRegistry first. API: `GET /v1/consumers`, `GET /v1/consumers/{key}`, `GET /v1/consumers/{key}/renderers`, CRUD. ([`src/consumers/`](src/consumers/), [`src/api/routes/consumers.py`](src/api/routes/consumers.py))

- **View patterns (reusable templates)** — New `src/views/patterns/` with 6 pattern definitions: accordion_sections, card_grid_grouped, tab_with_children, prose_narrative, card_grid_simple, timeline_sequential. Each captures renderer + config + sub-renderer combinations with instantiation hints for LLM orchestrators. API: `GET /v1/views/patterns`, `GET /v1/views/patterns/{key}`, `GET /v1/views/patterns/for-renderer/{type}`, CRUD. ([`src/views/pattern_schemas.py`](src/views/pattern_schemas.py), [`src/views/pattern_registry.py`](src/views/pattern_registry.py), [`src/views/patterns/`](src/views/patterns/), [`src/api/routes/view_patterns.py`](src/api/routes/view_patterns.py))

- **Domain-tagged transformations + auto-generation** — Added `domain`, `pattern_type`, `data_shape_out`, `compatible_sub_renderers` fields to TransformationTemplate schema. All 17 templates tagged (16 genealogy, 1 generic). New query: `GET /v1/transformations/for-pattern?domain=&data_shape=&renderer_type=`. New LLM endpoint: `POST /v1/transformations/generate` for creating templates from engine + renderer specs. ([`src/transformations/schemas.py`](src/transformations/schemas.py), [`src/transformations/registry.py`](src/transformations/registry.py), [`src/api/routes/transformations.py`](src/api/routes/transformations.py))

- **Parametric catalog + workflow-agnostic planner** — `assemble_full_catalog()` now accepts `app`, `page`, `workflow_key` filters. Catalog includes sub-renderers and view patterns sections. `catalog_to_text()` uses dynamic titles and engine counts. Planner system prompt composed from generic rules + workflow-specific `planner_strategy` field. Added `planner_strategy` field to WorkflowDefinition schema. Genealogy planning rules extracted from hardcoded prompt into `intellectual_genealogy.json`. Capability catalog endpoint now accepts `?app=&page=&workflow_key=` query params. ([`src/orchestrator/catalog.py`](src/orchestrator/catalog.py), [`src/orchestrator/planner.py`](src/orchestrator/planner.py), [`src/workflows/schemas.py`](src/workflows/schemas.py), [`src/workflows/definitions/intellectual_genealogy.json`](src/workflows/definitions/intellectual_genealogy.json), [`src/api/routes/orchestrator.py`](src/api/routes/orchestrator.py))

### Fixed
- **Conditions extraction template only extracting 4 of 7 fields** — `conditions_extraction.json` v1 was written before the `conditions_of_possibility_analyzer` engine added Pass 2 (path dependencies, unacknowledged debts, alternative paths). Updated to v2 with all 7 field schemas and expanded LLM prompt. Increased max_tokens from 8000 to 16000. ([`src/transformations/definitions/conditions_extraction.json`](src/transformations/definitions/conditions_extraction.json))

- **Multi-pass cache lookup failing in page assembly** — `presentation_api.py` computed `raw_prose` from only the latest single pass, but the bridge saved cache with hash of concatenated multi-pass content. Hash mismatch caused "Stale presentation cache" on every read. Fixed to concatenate ALL passes into raw_prose and skip freshness check for multi-pass single-engine views. ([`src/presenter/presentation_api.py`](src/presenter/presentation_api.py))

### Added
- **Force cache bypass on prepare/compose endpoints** — New `force: bool` parameter on `PrepareRequest` and `ComposeRequest` that skips `presentation_cache` check, forcing re-extraction from prose. Threaded through `presentation_bridge` → `_execute_tasks_async/sync`. Use when transformation templates are updated. ([`src/presenter/schemas.py`](src/presenter/schemas.py), [`src/presenter/presentation_bridge.py`](src/presenter/presentation_bridge.py), [`src/api/routes/presenter.py`](src/api/routes/presenter.py))

- **Refresh v2 presentation endpoint** (the-critic) — `POST /api/genealogy/refresh-v2/{v2_job_id}` re-fetches PagePresentation from analyzer-v2's page API and updates both React state and the-critic's DB record. Picks up extraction fixes without re-running the full compose pipeline. Includes frontend "Refresh" button in V2 results header. Timeout set to 300s for large payloads. (`the-critic/api/server.py`, `the-critic/webapp/src/pages/GenealogyPage.tsx`)

### Fixed
- **Target Work Profile detached from Idea Evolution Map** — `genealogy_target_profile` had incorrect `parent_view_key: "genealogy_idea_evolution"` making it appear nested under Idea Evolution Map. These are separate concerns (Phase 1 target profiling vs Phase 3 concept synthesis). Now top-level with its 4 children (Conceptual Framework, Semantic Constellation, Inferential Commitments, Concept Evolution) properly hanging under it. ([`src/views/definitions/genealogy_target_profile.json`](src/views/definitions/genealogy_target_profile.json))

### Added
- **Conditions of Possibility child views** — Created 7 child view definitions surfacing all CoP sub-components as visible lego blocks in the view tree: `genealogy_cop_enabling_conditions` (card_grid), `genealogy_cop_constraining_conditions` (card_grid), `genealogy_cop_counterfactual` (prose), `genealogy_cop_synthesis` (prose), `genealogy_cop_path_dependencies` (timeline), `genealogy_cop_unacknowledged_debts` (card_grid), `genealogy_cop_alternative_paths` (card_grid). Covers all 7 output sections of the `conditions_of_possibility_analyzer` engine. Total views: 14 → 21. ([`src/views/definitions/genealogy_cop_*.json`](src/views/definitions/))

- **Wire path_dependencies, unacknowledged_debts, alternative_paths into accordion** — Added 3 new sections to `genealogy_conditions` v3 accordion config so the-critic actually renders them. Uses existing generic sub-renderers: `timeline_strip` for path dependencies (chain sequences), `mini_card_list` for debts and alternatives. No the-critic code changes needed — the AccordionRenderer auto-dispatches via section_renderers config. ([`src/views/definitions/genealogy_conditions.json`](src/views/definitions/genealogy_conditions.json))

### Changed
- **Conditions of Possibility view refactored to data-driven rendering** — Enriched `genealogy_conditions` view definition (v2) with full `section_renderers` config: `enabling_conditions` and `constraining_conditions` as named domain sub-renderers, `counterfactual_analysis` and `synthetic_judgment` as `prose_block`. Renamed `counterfactuals` section key → `counterfactual_analysis` (matches engine output). Added `synthetic_judgment` as proper accordion section. Removed `path_dependencies` (not reliably in data). Accordion renderer definition updated with 2 new available section renderers. In the-critic: extracted `EnableConditionsSubRenderer` and `ConstrainConditionsSubRenderer` from hardcoded AccordionRenderer into `ConditionCards.tsx`, registered in `SubRenderers.tsx`. AccordionRenderer now fully generic — all sections dispatch through sub-renderer system. ([`src/views/definitions/genealogy_conditions.json`](src/views/definitions/genealogy_conditions.json), [`src/renderers/definitions/accordion.json`](src/renderers/definitions/accordion.json), `the-critic/webapp/src/components/renderers/ConditionCards.tsx`, `the-critic/webapp/src/components/renderers/SubRenderers.tsx`, `the-critic/webapp/src/components/renderers/AccordionRenderer.tsx`)

### Added
- **Evidence Trail sub-renderer** — Extracted the evidence trail UI (dot markers, gradient connectors, quoted content chain) from TacticCardCell into a reusable `EvidenceTrail` component. Works at two levels: (1) direct import by cell renderers, (2) config-driven sub-renderer registered in SubRenderers.tsx for accordion sections. Step mapping configurable via `steps` array with `field`, `variant`, `item_title_field`, `item_quote_field`, `item_cite_field`. New renderer definition in analyzer-v2 with 3 named variants (tactic_evidence, argument_chain, source_critique). Added to accordion's `available_section_renderers`. ([`the-critic/webapp/src/components/renderers/EvidenceTrail.tsx`], [`src/renderers/definitions/evidence_trail.json`](src/renderers/definitions/evidence_trail.json))

- **Editorial-quality Tactics card redesign** (the-critic) — TacticCardCell rewritten with evidence trail as narrative chain (Prior work → gradient connector → Current work → Assessment), severity-scaled visual weight (major: thicker border + tinted bg + bold badge, minor: subdued), cross-reference idea chips with indigo accent, section labels as uppercase markers. Group headers now show typological descriptions ("Repurposing earlier concepts under new theoretical guises") and major tactic counts. Items sorted by severity within groups. Added `TACTIC_DESCRIPTIONS` to genealogyStyles.ts. ([`the-critic/webapp/src/components/renderers/cells/TacticCardCell.tsx`], [`the-critic/webapp/src/components/renderers/CardGridRenderer.tsx`], [`the-critic/webapp/src/constants/genealogyStyles.ts`], [`the-critic/webapp/src/pages/GenealogyPage.css`])

- **Structured renderer config editors** (analyzer-mgmt) — Replaced generic expand_first toggle with renderer-type-aware form editors: card_grid (cell_renderer picker, columns slider 1-4, group_by, group_style_map, items_path, prose_endpoint, expandable toggle), accordion/tab (expand_first, tab_style, default_tab, count badges, prose_endpoint), prose (show_reading_time, show_section_nav, max_preview_lines), timeline (orientation, variant picker, label/date/description fields, group_by), table (sortable, filterable). Unknown renderer types fall back to raw JSON. ([`analyzer-mgmt/frontend/src/pages/views/[key].tsx`])

### Changed
- **Renderer stance affinity recalibration** — card_grid evidence affinity 0.5→0.8 (cards are natural evidence presenters), timeline evidence 0.5→0.65 + narrative 0.7→0.8, tab evidence 0.4→0.55 + comparison 0.5→0.6. Fixes incorrect recommendation of prose over card_grid for evidence-stance views with structured data. ([`src/renderers/definitions/card_grid.json`](src/renderers/definitions/card_grid.json), [`timeline.json`](src/renderers/definitions/timeline.json), [`tab.json`](src/renderers/definitions/tab.json))

- **Adaptive deterministic scoring weights** — Structured renderers (list/diagnostic category: card_grid, table, stat_summary, raw_json) now weight data shape at 0.40 (up from 0.30) and stance at 0.25 (down from 0.35). Prevents stance affinity from overriding clear data shape matches. ([`analyzer-mgmt/frontend/src/pages/views/[key].tsx`])

- **ViewSummary structural hints** — `sections_count`, `has_sub_renderers`, and `config_hints[]` computed from `renderer_config` and included in list endpoint. Config hints surface internal structure: "4 sections", "cell: tactic_card", "grouped by relationship_type", "6 columns, sortable", etc. ([`src/views/schemas.py`](src/views/schemas.py), [`src/views/registry.py`](src/views/registry.py))

- **Views list page redesign** — Tree hierarchy with recursive nesting, clean file-tree style connectors (2px zinc-400 lines with 6px endpoint dots), compact child rows (slim navigation style, no description), parent cards with color pips instead of thick border-l-4, parent+children form unified card, position-ordered interleaving (all views by position, not trees-first/standalone-last). ([`analyzer-mgmt/frontend/src/pages/views/index.tsx`])

### Added
- **Intelligent Renderer Selector** — Two-layer renderer recommendation system for the Views editor. (1) Deterministic scoring on the frontend: ranks all 8 renderers by stance affinity (0.35), data shape match (0.30), container fit (0.20), and app support (0.15) with green/yellow/red visual indicators. Data shape inferred from `result_path` heuristics. (2) LLM-powered recommendation via `POST /v1/renderers/recommend`: Claude Sonnet analyzes full view context + renderer catalog and returns top 5 ranked recommendations with reasoning, stance/shape analysis, and optional config migration hints. Frontend RendererTab redesigned from dumb `<select>` to interactive scored list with clickable renderer cards and AI panel with [Apply] buttons. Includes **Wiring Explainer** panel that narrates in plain English how the view's data source → data shape → stance → renderer need chain together, with stance mode descriptions (e.g. "diagnostic = meta-analytical — expose methodology, confidence, gaps") and structure analysis (child count, container need). ([`src/renderers/schemas.py`](src/renderers/schemas.py), [`src/api/routes/renderers.py`](src/api/routes/renderers.py), [`analyzer-mgmt/frontend/src/pages/views/[key].tsx`], [`analyzer-mgmt/frontend/src/lib/api.ts`], [`analyzer-mgmt/frontend/src/types/index.ts`])

- **Primitive-Renderer-Transformation cross-references** — Renderers and transformations now declare `primitive_affinities` linking them to analytical primitives. Renderers gain `input_data_schema` (formal JSON Schema for expected data shape), `variants` (named config presets like "vertical_evolution"), and the planner can discover renderers/transformations via `GET /v1/renderers/for-primitive/{key}` and `GET /v1/transformations/for-primitive/{key}`. Timeline renderer enriched with 3 variants, data schema, and affinities to `temporal_evolution`/`branching_foreclosure`. Idea evolution transformation now cross-references timeline renderer with config preset. ([`src/renderers/schemas.py`](src/renderers/schemas.py), [`src/transformations/schemas.py`](src/transformations/schemas.py), [`src/renderers/definitions/timeline.json`](src/renderers/definitions/timeline.json), [`src/transformations/definitions/idea_evolution_extraction.json`](src/transformations/definitions/idea_evolution_extraction.json))

- **Renderer Repertoire — first-class renderer catalog** — New `src/renderers/` entity with schemas, registry, 8 JSON definitions (accordion, card_grid, prose, table, stat_summary, timeline, tab, raw_json). Each renderer has stance affinities, ideal data shapes, config schemas, available section renderers. API: `GET /v1/renderers`, `GET /v1/renderers/{key}`, `GET /v1/renderers/for-stance/{stance}`, `GET /v1/renderers/for-app/{app}`, full CRUD. ([`src/renderers/`](src/renderers/), [`src/api/routes/renderers.py`](src/api/routes/renderers.py))

- **Section-level sub-renderers in AccordionRenderer** — 7 new sub-renderer components (chip_grid, mini_card_list, key_value_table, prose_block, stat_row, comparison_panel, timeline_strip) in `SubRenderers.tsx`. AccordionRenderer checks `config.section_renderers[sectionKey]` before falling through to GenericSectionRenderer. Each sub-renderer handles one section's data with appropriate styling. ([`the-critic/webapp/src/components/renderers/SubRenderers.tsx`])

- **Per-view section_renderers seeds** — All 4 Target Work Profile sub-views now include `section_renderers` in renderer_config with type-appropriate sub-renderer hints: mini_card_list for concept lists, chip_grid for tags/clusters, key_value_table for mappings, comparison_panel for tensions/variations, timeline_strip for evolution, prose_block for summaries.

- **Stance-to-renderer mapping** — Presentation stances (`summary`, `evidence`, `comparison`, `narrative`, `interactive`, `diagnostic`) now have `preferred_renderers` with affinity scores. New `RendererAffinity` schema. API: `GET /v1/operations/stances/{key}/renderers`. ([`src/operations/definitions/stances.yaml`](src/operations/definitions/stances.yaml), [`src/operations/schemas.py`](src/operations/schemas.py), [`src/api/routes/operations.py`](src/api/routes/operations.py))

- **View refiner renderer recommendations** — View refiner context now includes the full renderer catalog. System prompt instructs LLM to populate `renderer_config_overrides.section_renderers` per view. ([`src/presenter/view_refiner.py`](src/presenter/view_refiner.py))

- **Dynamic renderer catalog in analyzer-mgmt** — Renderer dropdown in views editor now fetches from `/v1/renderers` API instead of hardcoded list. Shows renderer metadata (description, stance affinities, data shapes, section renderers) when selected. API client methods added. ([`analyzer-mgmt/frontend/src/lib/api.ts`], [`analyzer-mgmt/frontend/src/pages/views/[key].tsx`])

- **Visual section renderers editor in analyzer-mgmt** — Replaced raw JSON editor for `renderer_config` with card-based visual editor. Accordion Sections shows editable rows (key + title). Section Renderers shows colored cards with renderer type dropdowns, sub-renderer cards with field mapping inputs (title_field, subtitle_field, etc.), add/remove buttons, and nested_sections support. Raw JSON toggle available for power users. ([`analyzer-mgmt/frontend/src/pages/views/[key].tsx`])

- **Dramatic sub-renderer visual overhaul** — MiniCardList now renders with colored header bars (gradient background, white text), separated zones (description/scalar fields/chip fields), and box shadows. ProseBlock has purple background with decorative quotation mark and thick indigo left border. ChipGrid uses colored containers with rounded palette-colored chips. KeyValueTable has zebra striping with blue key column. V2 presentations now persist to database and auto-restore on page load. ([`the-critic/webapp/src/components/renderers/SubRenderers.tsx`], [`the-critic/api/server.py`], [`the-critic/webapp/src/pages/GenealogyPage.tsx`])


- **Nested sub_renderers dispatch for accordion sections** — AccordionRenderer now supports `renderer_type: "nested_sections"` with `sub_renderers` map: when a section's data is a nested object, each inner key can dispatch to a specialized sub-renderer (mini_card_list, chip_grid, prose_block, etc.) instead of GenericSectionRenderer. GenericSectionRenderer accepts `subRenderers` prop for per-key dispatch. Fixed data key mismatches between sub_renderer config and actual LLM extraction output. MiniCardList now renders string arrays as inline chip badges instead of JSON.stringify. ([`the-critic/webapp/src/components/renderers/AccordionRenderer.tsx`], [`the-critic/webapp/src/components/renderers/SubRenderers.tsx`], [`src/views/definitions/genealogy_target_profile.json`](src/views/definitions/genealogy_target_profile.json))

- **V2TabContent merges fresh view definitions' renderer_config** — V2TabContent (the V2 presentation rendering path) now fetches fresh view definitions via `useViewDefinitions` and merges renderer_config into the stored PagePresentation. Rendering-specific keys (`section_renderers`, `expand_first`, `sections`) always come from fresh view definitions (source of truth), while stored payload provides data. This means view definition changes in analyzer-mgmt take effect immediately without re-import. ([`the-critic/webapp/src/pages/GenealogyPage.tsx`], [`the-critic/webapp/src/components/renderers/SubRenderers.tsx`])

- **Per-engine Target Work Profile views** — Replaced the single monolithic `genealogy_target_profile` accordion (which squeezed 73k words into 12k max_tokens) with 4 per-engine child views, each with its own rich extraction template: `genealogy_tp_conceptual_framework` (20k max_tokens, 7 sections), `genealogy_tp_semantic_constellation` (18k, 6 sections), `genealogy_tp_inferential_commitments` (20k, 7 sections), `genealogy_tp_concept_evolution` (16k, 6 sections). Target Work Profile is now a tab container with `sub_tabs` layout. Old `target_profile_extraction` template deprecated. ([`src/views/definitions/genealogy_tp_*.json`](src/views/definitions/), [`src/transformations/definitions/tp_*_extraction.json`](src/transformations/definitions/))

- **Multi-pass concatenation for single-engine views** — Presentation API and bridge now concatenate ALL passes for single-engine views (not just the latest). For engines with 3-4 passes, this preserves 100% of content instead of losing 50-75%. `TransformationTask` has new `content_override` field for feeding concatenated prose to the extraction LLM. Cache freshness check skipped for multi-pass content. ([`src/presenter/presentation_api.py`](src/presenter/presentation_api.py), [`src/presenter/presentation_bridge.py`](src/presenter/presentation_bridge.py), [`src/presenter/schemas.py`](src/presenter/schemas.py))

### Changed
- **Transformation registry excludes deprecated templates** — `for_engine()` now filters out templates with `status: "deprecated"`. ([`src/transformations/registry.py`](src/transformations/registry.py))

- **Chain-backed view resolution** — Presentation pipeline now resolves views with `chain_key` but no `engine_key`. `_load_aggregated_data()` and `_load_per_item_data()` resolve chain engine keys via ChainRegistry and search transformation templates for ALL engines in the chain. Concatenates all engine outputs per work_key for per_item scope. Unblocks Target Work Profile and Per-Work Scan Detail views. ([`src/presenter/presentation_api.py`](src/presenter/presentation_api.py), [`src/presenter/presentation_bridge.py`](src/presenter/presentation_bridge.py))

- **Transformation templates for missing views** — Two new extraction templates: (1) `target_profile_extraction.json` for Target Work Profile accordion (concept_evolution engine, extracts conceptual_framework/semantic_constellation/inferential_commitments); (2) `per_work_scan_extraction.json` for Per-Work Scan Detail cards (concept_appropriation_tracker engine, extracts vocabulary/methodology/metaphor/framing subsections). Total templates now 13. ([`src/transformations/definitions/target_profile_extraction.json`](src/transformations/definitions/target_profile_extraction.json), [`src/transformations/definitions/per_work_scan_extraction.json`](src/transformations/definitions/per_work_scan_extraction.json))

- **PDF export** — WeasyPrint-based HTML-to-PDF generation for completed jobs. Cover page with thinker name and strategy summary, table of contents, per-phase sections with rendered markdown prose, execution stats appendix. Uses Crimson Pro + Inter fonts, A4 pages, page numbers. Endpoint: `GET /v1/executor/jobs/{job_id}/export/pdf`. ([`src/executor/pdf_export.py`](src/executor/pdf_export.py), [`src/api/routes/executor.py`](src/api/routes/executor.py))

- **Data-driven planner view selection** — ViewDefinition now has `planner_hint` (free-text LLM guidance) and `planner_eligible` (boolean). All 10 view JSONs annotated. Enriched capability catalog includes `has_transformation_template`, planner hints, `[HAS_TEMPLATE]`/`[NO_TEMPLATE]` tags, `[NOT ELIGIBLE]` markers. Planner system prompt replaced hardcoded view recommendations with data-driven rules. ([`src/views/schemas.py`](src/views/schemas.py), `src/views/definitions/*.json`, [`src/orchestrator/catalog.py`](src/orchestrator/catalog.py), [`src/orchestrator/planner.py`](src/orchestrator/planner.py))

### Changed
- **requirements.txt** — Added `weasyprint>=60.0` and `markdown>=3.5` for PDF export.

- **Pipeline visualization endpoint** — New `GET /v1/orchestrator/plans/{plan_id}/pipeline-visualization` endpoint that assembles a complete hierarchical tree of the execution pipeline from in-memory registries (no DB/LLM calls). Returns plan → phases → chains → engines → passes → stances → dimensions with full metadata. Powers the Critic's dynamic pipeline visualization component. ([`src/orchestrator/visualization.py`](src/orchestrator/visualization.py), [`src/api/routes/orchestrator.py`](src/api/routes/orchestrator.py))

- **Structured progress detail** — `update_job_progress()` now accepts optional `structured_detail` dict with `engine_key`, `pass_number`, `stance_key` fields parsed from detail strings. Enables reliable engine/pass highlighting in the pipeline visualization. ([`src/executor/job_manager.py`](src/executor/job_manager.py), [`src/executor/workflow_runner.py`](src/executor/workflow_runner.py))

### Fixed
- **Deploy race condition: grace period + request snapshot + plan regeneration** — During zero-downtime deploys, the new instance's `recover_orphaned_jobs()` was immediately failing jobs without `plan_data`, even though the old instance was still generating the plan (~2 min). Three fixes: (1) Grace period: jobs created <5 min ago are skipped during recovery. (2) Request snapshot: pipeline stores plan request params + document_ids right after doc upload, BEFORE plan generation. (3) Plan regeneration: recovery detects request snapshots and spawns a background thread to regenerate the plan + resume execution. ([`src/executor/job_manager.py`](src/executor/job_manager.py), [`src/orchestrator/pipeline.py`](src/orchestrator/pipeline.py), [`src/api/main.py`](src/api/main.py))

### Added
- **Resumable jobs — survive Render free tier instance recycling** — Render's free tier recycles instances every ~8-12 minutes, killing daemon execution threads mid-job. Jobs now persist `plan_data` (full WorkflowExecutionPlan as JSONB) and `document_ids` to Postgres at pipeline start. On next instance startup, `recover_orphaned_jobs()` finds running/pending jobs WITH plan_data and resumes them via `start_resume_thread()`. Three-level resume granularity: phase-level (skip completed phases from phase_results), engine-level (skip completed engines from phase_outputs), pass-level (skip completed passes within multi-pass operationalizations). Jobs WITHOUT plan_data (pre-resume-feature) fail cleanly with explanatory error. DB migration adds `plan_data JSONB` and `document_ids JSONB` columns to executor_jobs. ([`src/executor/db.py`](src/executor/db.py), [`src/executor/job_manager.py`](src/executor/job_manager.py), [`src/executor/workflow_runner.py`](src/executor/workflow_runner.py), [`src/executor/chain_runner.py`](src/executor/chain_runner.py), [`src/executor/output_store.py`](src/executor/output_store.py), [`src/orchestrator/pipeline.py`](src/orchestrator/pipeline.py))

- **Document chunking for large inputs** — Transformer attention scales O(n²) with input length: at 183K tokens (725K chars), output speed drops to ~0.5 tokens/s (vs ~43 tokens/s at 50K tokens). This made Phase 1.0 engine calls take 2-3 hours each instead of minutes. Fix: `run_engine_call_auto()` transparently splits documents >200K chars into ~180K char chunks, runs extraction per chunk using the fast standard endpoint, then synthesizes chunk results into one coherent output. Empirical speedup: 72x faster for a 725K char document. Phase 1.0 estimated: ~1.5 hours (was ~30+ hours). Each chunk call completes in <3 min (safe against Render instance recycling). ([`src/executor/engine_runner.py`](src/executor/engine_runner.py), [`src/executor/chain_runner.py`](src/executor/chain_runner.py))

### Changed
- **Sync API by default for all LLM calls** — Render's reverse proxy buffers SSE events, throttling streaming throughput to ~0.5 tokens/s vs ~42 tokens/s for sync API. Default is now sync (`client.messages.create()`) for all calls. Sync disables extended thinking (requires streaming) — acceptable tradeoff since medium-effort thinking on 180K+ token inputs was already disabled by dynamic effort scaling. Set `ENABLE_STREAMING=true` env var to re-enable streaming with thinking for local dev. ([`src/executor/engine_runner.py`](src/executor/engine_runner.py))

- **Re-enabled document chunking** — O(n²) attention slowdown is model-side, not transport-side (affects sync and streaming equally). At 183K tokens, generation drops to ~0.5 tok/s vs ~43 tok/s at 30K tokens. `CHUNK_THRESHOLD` restored to 200K chars. Large documents are split into ~180K char chunks for fast extraction, then synthesized. ([`src/executor/engine_runner.py`](src/executor/engine_runner.py))

- **Planner uses sync API** — Plan generation and refinement switched from streaming to sync API. Structured JSON output doesn't need extended thinking, and sync is 100x faster on Render. ([`src/orchestrator/planner.py`](src/orchestrator/planner.py))

- **1M beta support for sync API calls** — `_execute_sync_call()` now uses `client.beta.messages.create(betas=["context-1m-2025-08-07"])` when input exceeds standard 200K context. Same smart avoidance logic as streaming path: reduce max_tokens to fit standard context when possible, fall back to 1M beta only when necessary. ([`src/executor/engine_runner.py`](src/executor/engine_runner.py))

### Fixed
- **Stale job detection on poll** — If a daemon thread dies while the instance stays alive, jobs stay "running" forever. Now the `GET /v1/executor/jobs/{job_id}` endpoint checks elapsed time and auto-marks jobs running >3h as failed with a helpful retry message. Belt-and-suspenders alongside startup recovery. ([`src/executor/job_manager.py`](src/executor/job_manager.py), [`src/api/routes/executor.py`](src/api/routes/executor.py))

- **Avoid 1M beta endpoint when standard 200K fits** — The 1M context beta endpoint has severely reduced throughput (~0.5 tokens/sec vs 50+ tokens/sec on standard). For our 725K char input (~183K tokens), the standard 200K context window fits with reduced max_tokens (15K instead of 64K). Smart logic: calculate `max_safe_output = 200K - input_tokens - 2K_margin`; if >= 8K, use standard endpoint with reduced max_tokens. Automatic fallback to 1M beta if standard rejects the input. Heartbeat logs now show `[std]`/`[1M]` tags. Expected 25-50x speedup for Phase 1.0 engine calls. ([`src/executor/engine_runner.py`](src/executor/engine_runner.py))

- **Dynamic effort scaling for large inputs** — Extended thinking on 180K+ token inputs is inherently slow regardless of effort level (2-3 chars/sec thinking rate, 0 text for 20+ min). Added dynamic effort scaling in `_execute_streaming_call()`: >400K chars (~100K tokens) disables thinking entirely; 200-400K chars (~50-100K tokens) downgrades to effort="low"; <200K chars uses configured effort. This is critical for Phase 1.0 which processes 725K char documents — thinking adds negligible value for extraction from massive text but adds 20+ min latency. ([`src/executor/engine_runner.py`](src/executor/engine_runner.py))

- **Migrate from deprecated budget_tokens to adaptive thinking** — Sonnet 4.6 deprecates `thinking: {"type": "enabled", "budget_tokens": N}`. Using the deprecated API without `output_config.effort` defaulted to "high" effort, causing 15+ min thinking phases with 0 text output on 180K token inputs. Migrated to GA adaptive thinking: `thinking: {"type": "adaptive"}` with `output_config: {"effort": "medium"}` for ALL tiers. Removed depth-based effort upgrade to "high" (it was defeating the purpose). ([`src/executor/engine_runner.py`](src/executor/engine_runner.py), [`src/orchestrator/planner.py`](src/orchestrator/planner.py))

- **Salvage partial output on connection reset** — Deep Opus calls with 1M context + extended thinking can stream for 2+ hours. If the TCP connection drops (e.g., `[Errno 104] Connection reset by peer` after ~142 min), ALL accumulated output was lost because `_execute_streaming_call()` only extracted text from `stream.get_final_message()` at the end. Fix: accumulate text incrementally from stream delta events during iteration. On connection error, if >5K chars accumulated, return partial output instead of retrying from scratch. Heartbeat logs now show accumulated text/thinking char counts. Result dict includes `partial: True` flag when salvaged. ([`src/executor/engine_runner.py`](src/executor/engine_runner.py))

- **Orphaned job recovery on instance restart** — When Render recycles an instance, daemon execution threads die silently, leaving jobs stuck at `status=running` forever (zombie jobs). Fix: on startup, `recover_orphaned_jobs()` scans for any running/pending jobs and marks them as failed with an explanatory error message. Also: SIGTERM handler registered so graceful shutdown marks jobs as failed before the process exits. Belt-and-suspenders: the lifespan shutdown hook also runs recovery as a fallback. ([`src/executor/job_manager.py`](src/executor/job_manager.py), [`src/api/main.py`](src/api/main.py))

- **Async pipeline: /analyze endpoint returns immediately** — The `POST /v1/orchestrator/analyze` endpoint was blocking for ~2 minutes (document upload + Opus plan generation) before returning `{job_id}`. This caused The Critic's HTTP client to time out. Fix: the endpoint now returns a `job_id` in <1 second, spawning the entire pipeline (doc upload → plan generation → execution) in a background thread. Progress is reported via the existing job polling endpoint. `plan_id` is now Optional in `AnalyzeResponse` (set by background thread once plan generation completes). Added `update_job_plan_id()` to job_manager for deferred plan_id assignment. ([`src/orchestrator/pipeline.py`](src/orchestrator/pipeline.py), [`src/orchestrator/pipeline_schemas.py`](src/orchestrator/pipeline_schemas.py), [`src/executor/job_manager.py`](src/executor/job_manager.py))

### Added
- **Expanded Target Analysis & Distilled Context — Milestone 5** — Addresses a fundamental design flaw discovered during first real Varoufakis execution: per-work phases (1.5, 2.0) concatenated TWO FULL BOOK TEXTS (1.1-1.5M chars each), causing 30+ minute stalls. The fix: expand Phase 1.0 with orchestrator-selected supplementary engines, then feed DISTILLED ANALYSIS (not raw text) to downstream per-work phases.
  - Two new fields on `PhaseExecutionSpec`: `supplementary_chains` (list of additional chain keys to run after primary), `max_context_chars_override` (override 50K per-block context cap for rich analyses)
  - Phase 1.5 now depends on Phase 1.0 (no longer parallel): `depends_on_phases: [1.0]` in workflow definition
  - New execution DAG: Group1=[1.0] → Group2=[1.5] → Group3=[2.0] → Group4=[3.0] → Group5=[4.0]
  - `_run_standard_phase()` extended with supplementary chain execution — runs 1-3 additional chains after primary, merging outputs
  - New `_combine_with_distilled_analysis()` replaces raw target text with distilled multi-engine analysis in per-work phases
  - `assemble_phase_context()` enhanced with `phase_max_chars_override` parameter for per-phase char limits
  - `context_char_overrides` threaded from `workflow_runner` through `phase_runner` to `context_broker`
  - Planner system prompt updated: guidelines for supplementary chain selection, document strategy for per-work phases, updated JSON output format
  - Catalog text updated: note about supplementary chains for Phase 1.0
  - Backward compatible: existing plans without new fields work unchanged
  - Token economy: ~13% reduction in total input tokens, with dramatically improved quality-per-token ratio
  - ([`src/orchestrator/schemas.py`](src/orchestrator/schemas.py), [`src/executor/phase_runner.py`](src/executor/phase_runner.py), [`src/executor/context_broker.py`](src/executor/context_broker.py), [`src/executor/workflow_runner.py`](src/executor/workflow_runner.py), [`src/orchestrator/planner.py`](src/orchestrator/planner.py), [`src/orchestrator/catalog.py`](src/orchestrator/catalog.py), [`src/workflows/definitions/intellectual_genealogy.json`](src/workflows/definitions/intellectual_genealogy.json))

- **Consumer Integration — Milestone 4B** — The Critic rewired to delegate genealogy execution to analyzer-v2's all-in-one orchestrator pipeline. See The Critic's changelog for full details. This milestone completes the 4-milestone orchestrator project: plan (M1) → execute (M2) → present (M3) → integrate (M4). The full pipeline is now: Critic UI → `POST /v1/orchestrator/analyze` → plan + execute + present → PagePresentation → Critic renders ViewPayloads.

- **All-in-One Analysis Pipeline — Milestone 4A** (`src/orchestrator/pipeline.py`, `src/orchestrator/pipeline_schemas.py`) — Top-level orchestration endpoint that chains document upload -> plan generation -> execution -> presentation into a single async job. `POST /v1/orchestrator/analyze` accepts inline document texts + thinker context, uploads to document store, generates WorkflowExecutionPlan via Claude Opus, starts background execution, returns {job_id, plan_id} for polling. Supports autonomous mode (default, skip_plan_review=true) and checkpoint mode (skip_plan_review=false returns plan_id for review). Auto-presentation trigger added to `workflow_runner.execute_plan()` — runs view refinement + transformation bridge on successful completion (non-fatal). Convenience endpoint `GET /v1/orchestrator/analyze/{job_id}` returns progress while running, PagePresentation when complete.
  - New schemas: `AnalyzeRequest` (with `PriorWorkWithText`), `AnalyzeResponse`
  - 2 new REST endpoints under `/v1/orchestrator/`: analyze, analyze/{job_id}
  - ([`src/orchestrator/pipeline_schemas.py`](src/orchestrator/pipeline_schemas.py), [`src/orchestrator/pipeline.py`](src/orchestrator/pipeline.py), [`src/executor/workflow_runner.py`](src/executor/workflow_runner.py), [`src/api/routes/orchestrator.py`](src/api/routes/orchestrator.py), [`src/api/main.py`](src/api/main.py))

- **Presenter — Milestone 3: Adaptive View Selection & Presentation Bridge** (`src/presenter/`) — Three-layer presentation system bridging executor outputs to consumer rendering. (3A) Post-execution LLM-driven view refinement: Sonnet inspects phase results + output previews and adjusts planner's recommended_views with updated priorities, stances, data quality assessments. (3B) Automated transformation pipeline: connects executor prose → transformation templates → presentation_cache structured data, handling both per_item and aggregated scopes. (3C) Consumer-facing presentation API: assembles render-ready PagePresentation with nested view tree, structured data, and raw prose. All-in-one `/compose` endpoint runs refine → prepare → assemble in sequence.
  - `view_refinements` DB table added to both Postgres and SQLite
  - 6 REST endpoints under `/v1/presenter/`: refine-views, prepare, page/{job_id}, view/{job_id}/{view_key}, status/{job_id}, compose
  - ([`src/presenter/`](src/presenter/), [`src/api/routes/presenter.py`](src/api/routes/presenter.py), [`src/executor/db.py`](src/executor/db.py), [`src/api/main.py`](src/api/main.py))

- **Execution Engine — Milestone 2: Plan-Driven Workflow Execution** (`src/executor/`) — Full executor module that takes a WorkflowExecutionPlan and runs it. Architecture layers (bottom-up): engine_runner (atomic LLM calls with streaming, extended thinking, 1M context, heartbeat, retry) → context_broker (cross-phase context assembly with emphasis injection) → chain_runner (sequential multi-engine execution with operationalization-driven multi-pass) → phase_runner (resolves phases to chains/engines, handles per-work iteration) → workflow_runner (dependency-aware parallel DAG execution) → job_manager (DB-persistent lifecycle, cancellation). Database: 4 tables in Render Postgres via dual-backend abstraction (Postgres + SQLite). 11 API endpoints under /v1/executor/ for job CRUD, cancellation, phase output retrieval, and document management. PhaseExecutionSpec extended with model_hint, requires_full_documents, per_work_overrides.
  - ([`src/executor/`](src/executor/), [`src/api/routes/executor.py`](src/api/routes/executor.py), [`src/orchestrator/schemas.py`](src/orchestrator/schemas.py), [`requirements.txt`](requirements.txt), [`src/api/main.py`](src/api/main.py))

- **Context-Driven Orchestrator — Milestone 1: Plan Generation** (`src/orchestrator/`) — LLM-powered orchestrator that takes a thinker + corpus + research question and generates a WorkflowExecutionPlan adapted to the thinker's intellectual profile. Assembles capability catalog from all registries, calls Claude Opus with extended thinking, returns validated plan with per-phase depth, engine overrides, context emphasis, and view recommendations.
  - `WorkflowExecutionPlan` schema with PhaseExecutionSpec, EngineExecutionSpec, ViewRecommendation
  - Capability catalog assembly from 11 capability engines, 23 chains, 13 stances, 10 views, 11 operationalizations
  - `catalog_to_text()` for LLM-readable structured markdown
  - Plan generation via Claude Opus with streaming + extended thinking (10k budget)
  - Plan refinement endpoint (LLM re-plans based on user feedback)
  - File-based plan persistence in `src/orchestrator/plans/`
  - Full REST API: generate, list, get, update, refine, status update
  - Tested with Varoufakis context: 42 estimated LLM calls, differentiated depth per phase, engine-specific focus dimensions
  - ([`src/orchestrator/schemas.py`](src/orchestrator/schemas.py), [`src/orchestrator/catalog.py`](src/orchestrator/catalog.py), [`src/orchestrator/planner.py`](src/orchestrator/planner.py), [`src/api/routes/orchestrator.py`](src/api/routes/orchestrator.py))

- **Transformation Templates — Schema-on-Read Execution Service** (`src/transformations/`) — Reusable transformation recipes that execute the `TransformationSpec` already declared in view definitions. Five types: passthrough (none), field renaming (schema_map), structured extraction from prose (llm_extract), summarization (llm_summarize), and aggregation (group/count/sort). Includes in-memory TTL cache for LLM results.
  - `TransformationTemplate` schema with full execution config (model, fallback, max_tokens), applicability (renderer types, engines), and metadata (tags, status, source)
  - `TransformationRegistry` with JSON-per-file loading, CRUD, filter by type/tag/engine/renderer
  - `TransformationExecutor` with all 5 transformation types, stance resolution, and TTL cache
  - 5 seed templates extracted from The Critic's `presentation.py`: conditions_extraction, tactics_extraction, functional_extraction, synthesis_extraction (all llm_extract), chain_log_field_map (schema_map)
  - Full REST API: CRUD + `/execute` endpoint + `/for-engine/{key}` + `/for-renderer/{type}` + `/reload`
  - ([`src/transformations/schemas.py`](src/transformations/schemas.py), [`src/transformations/registry.py`](src/transformations/registry.py), [`src/transformations/executor.py`](src/transformations/executor.py), [`src/transformations/definitions/*.json`](src/transformations/definitions/), [`src/api/routes/transformations.py`](src/api/routes/transformations.py))
- **Shared LLM Client** (`src/llm/client.py`) — Extracted common LLM utilities from `src/api/routes/llm.py` into reusable module: `get_anthropic_client()`, `parse_llm_json_response()`, `call_extraction_model()` with Haiku→Sonnet fallback. Used by both transformation executor and LLM routes.
- **Transformations Management UI** (analyzer-mgmt) — List page with type-colored badges and search/filter, detail page with 6 tabs (Identity, Specification, Applicability, Execution Config, Test, Preview), create/edit/delete, and live execute testing. Sidebar nav item with Repeat icon between Views and Operationalizations.
  - ([`frontend/src/pages/transformations/index.tsx`], [`frontend/src/pages/transformations/[key].tsx`], [`frontend/src/types/index.ts`], [`frontend/src/lib/api.ts`], [`frontend/src/components/Layout.tsx`])
- **View Apply Template** (analyzer-mgmt) — "Apply Transformation Template" dropdown in views/[key].tsx Transformation tab. One-time copy of a template's spec fields into the view's transformation. Fetches template list from analyzer-v2, applies selected template, shows confirmation banner.
- **Phase 5: The Critic → v2 Delegation** (the-critic) — The Critic's 4 hardcoded presentation endpoints now delegate extraction to analyzer-v2's transformation service (`POST /v1/transformations/execute`), falling back to local Claude Haiku when v2 is unreachable. `presentation.py` refactored from ~700 to ~454 lines; 4 server.py endpoints collapsed to 1 generic `/present/{section}` handler. Zero frontend changes — same URLs, same response format. `AnalyzerV2Client` extended with `execute_transformation()` + sync wrapper.

- **View Definitions — Rendering Layer** (`src/views/`) — Declarative specs for how analytical outputs become UI. A ViewDefinition declares: data source -> renderer type -> position in app. Consumer apps fetch view trees and dispatch to their component registries. No execution logic — just definitions.
  - `ViewDefinition` schema with `DataSourceRef` (workflow/phase/engine/chain pointers) and `TransformationSpec` (none, schema_map, llm_extract, llm_summarize, aggregate)
  - `ViewRegistry` with JSON-per-file loading, CRUD, `compose_tree()` for building nested page layouts, `for_workflow()` lookup
  - 10 genealogy view definitions: 5 top-level tabs (Relationship Landscape, Idea Evolution Map, Tactics & Strategies, Conditions of Possibility, Genealogical Portrait), 3 nested child views (Target Work Profile, Per-Work Scan Detail, Author Intellectual Profile), 2 on-demand debug views (Raw Engine Output, Chain Execution Log)
  - `GET /v1/views/compose/{app}/{page}` — primary consumer endpoint returning sorted tree with nested children
  - Full CRUD: `POST /v1/views`, `PUT /v1/views/{key}`, `DELETE /v1/views/{key}`
  - Views included in version hash (`/v1/meta/definitions-version`), health endpoint, and `/v1` root
  - ([`src/views/schemas.py`](src/views/schemas.py), [`src/views/registry.py`](src/views/registry.py), [`src/views/definitions/*.json`](src/views/definitions/), [`src/api/routes/views.py`](src/api/routes/views.py))
- **Presentation Stances** (6 new) — Alongside the 7 analytical stances, 6 presentation stances guide HOW to render output for display. Each has a UI pattern description.
  - `summary` — Distill to headlines and key points (stat cards, bullet lists, executive briefs)
  - `evidence` — Foreground sources, quotes, traceability (quote cards with attribution, citation trails)
  - `comparison` — Side-by-side differential highlighting (split panels, diff views, parallel timelines)
  - `narrative` — Flowing prose with structure markers (formatted long-form with section anchors)
  - `interactive` — Drill-down affordances (expandable cards, nested tabs, filter controls)
  - `diagnostic` — Expose methodology, confidence, gaps (confidence meters, coverage matrices, debug panels)
  - New `stance_type` field ("analytical" or "presentation") on `AnalyticalStance` schema
  - Filter by type: `GET /v1/operations/stances?type=presentation`
  - ([`src/operations/definitions/stances.yaml`](src/operations/definitions/stances.yaml), [`src/operations/schemas.py`](src/operations/schemas.py), [`src/operations/registry.py`](src/operations/registry.py))

- **Dynamic Propagation System** — When engines are added to workflow phases via the UI, changes now persist permanently via GitHub commits, descriptions auto-update, and cascade to all dependent objects
  - **GitHub Persistence Layer** (`src/persistence/github_client.py`): Atomic multi-file commits via Git Data API (blobs → trees → commits → refs). Graceful degradation when no token configured — changes still work locally but are ephemeral.
  - **Description Auto-Generation** (`src/workflows/description_generator.py`): Template-based description generation from engine lists. Chains get `base_description` (invariant summary) + auto-computed `description` enumerating engines. Workflow phases get `base_phase_description` + auto-computed `phase_description`.
  - **Cascade Updates**: When a chain's engine_keys change, ALL workflow phases referencing that chain get their descriptions regenerated. Cross-workflow: finds all workflows using a modified chain via `find_by_chain_key()`.
  - **Consumer Cache Versioning** (`src/api/routes/meta.py`): `GET /v1/meta/definitions-version` returns SHA-256 fingerprint of all definitions, chain engine_keys, last-modified timestamp, and persistence status. Consumers can poll to invalidate caches.
  - **Enhanced AddEngineResponse**: Now returns `chain_description`, `phase_description`, `git_committed`, `commit_sha`, `cascaded_workflows` — frontend shows "committed to git" indicator.
  - **Schema additions**: `base_description` on `EngineChainSpec`, `base_phase_description` on `WorkflowPhase` (both optional, backwards-compatible). Backfilled across all 23 chains and 7 workflows.
  - ([`src/persistence/github_client.py`](src/persistence/github_client.py), [`src/workflows/description_generator.py`](src/workflows/description_generator.py), [`src/api/routes/meta.py`](src/api/routes/meta.py), [`src/api/routes/workflows.py`](src/api/routes/workflows.py), [`src/chains/schemas.py`](src/chains/schemas.py), [`src/workflows/schemas.py`](src/workflows/schemas.py))

### Changed
- **Workflow "passes" renamed to "phases"** — Workflow-level orchestration steps are now "phases" to eliminate terminology collision with engine-level "passes" (stance iterations within depth levels). Backwards compatibility preserved via Pydantic model validators and deprecated API aliases (`/passes` → `/phases`, `/pass/{num}` → `/phase/{num}`). All 7 workflow JSON definitions updated. Frontend updated across implementations and workflows pages.
  - `WorkflowPass` → `WorkflowPhase` (backwards alias kept)
  - `pass_number` → `phase_number`, `pass_name` → `phase_name`, etc.
  - API: new canonical paths use `/phases`; old `/passes` paths kept as deprecated
  - ([`src/workflows/schemas.py`](src/workflows/schemas.py), [`src/workflows/registry.py`](src/workflows/registry.py), [`src/api/routes/workflows.py`](src/api/routes/workflows.py), all 7 JSON definitions)

### Added
- **Extension Points System** — Analyzes WHERE in a workflow additional engines could be plugged in, scores all engines for composability fit using a 5-tier weighted algorithm, and surfaces ranked candidates with rationale
  - 5-tier scoring: synergy (0.30), dimension production (0.25), dimension novelty (0.20), capability gap (0.15), category affinity (0.10)
  - Recommendation tiers: strong (>=0.65), moderate (>=0.40), exploratory (>=0.20)
  - Graceful degradation: 11 v2 engines get full scoring; ~185 legacy engines scored by category/kind
  - Per-phase analysis: dimension coverage, capability gaps, ranked candidates with rationale
  - Workflow-level insights: underserved dimensions, total candidates, summary
  - API endpoint: `GET /v1/workflows/{key}/extension-points?depth=standard&phase_number=1.0`
  - ([`src/workflows/extension_points.py`](src/workflows/extension_points.py), [`src/workflows/extension_scorer.py`](src/workflows/extension_scorer.py), [`src/api/routes/workflows.py`](src/api/routes/workflows.py))

- **Add Engine to Phase mutation** — `POST /v1/workflows/{key}/phases/{phase_num}/add-engine` lets users add recommended engines directly from the extension points UI
  - If phase uses a chain: appends engine to chain's `engine_keys` and saves chain JSON
  - If phase has standalone `engine_key`: creates new sequential chain with both engines, updates phase to reference it
  - Duplicate prevention (409 if engine already present), engine validation (404 if engine doesn't exist)
  - `ChainRegistry.save()` tracks original file paths to handle `_chain.json` suffix pattern
  - Frontend: "Add to Phase" button on each candidate engine card, 2.5s confirmation before card disappears
  - ([`src/api/routes/workflows.py`](src/api/routes/workflows.py), [`src/chains/registry.py`](src/chains/registry.py))

- **Intellectual Genealogy Workflow v3** — Complete redesign of the genealogy pipeline to exploit the new modular architecture
  - Migrated stale engine keys: `genealogy_pass1b_relationship_classification` → `genealogy_relationship_classification`, `genealogy_pass7_final_synthesis` → `genealogy_final_synthesis`
  - Renumbered legacy pass 7 → pass 4 (sequential numbering)
  - Added `context_parameters` to passes 2, 3, 4 for inter-pass data threading (target_profile, relationship_classifications, prior_work_scans, etc.)
  - Updated final synthesis dependencies from `[1, 3]` to `[1, 1.5, 2, 3]` (receives all upstream)
  - Enriched all pass descriptions with specific engine/dimension/stance details
  - Bumped version 2 → 3
  - ([`src/workflows/definitions/intellectual_genealogy.json`](src/workflows/definitions/intellectual_genealogy.json))

- **Enriched `genealogy_final_synthesis` operationalization** — Was single-pass integration at all depths; now has multi-pass depth escalation matching the engine YAML
  - Added `discovery` stance: "Comprehensive Foundations — Summary & Idea Genealogies" (executive_summary, idea_genealogies, key_findings)
  - Added `architecture` stance: "Genealogical Portrait & Intellectual Character" (genealogical_portrait, author_intellectual_profile)
  - Depth sequences: surface=1 pass (integration), standard=2 passes (discovery→integration), deep=3 passes (discovery→architecture→integration)
  - ([`src/operationalizations/definitions/genealogy_final_synthesis.yaml`](src/operationalizations/definitions/genealogy_final_synthesis.yaml))

- **Enriched `genealogy_relationship_classification` operationalization** — Was 2 stances (discovery/inference); now aligned with engine YAML depth structure
  - Added `architecture` stance: "Channel Mapping & Scanning Strategy" (influence_channels, strategic_relevance)
  - Added `confrontation` stance: "Classification Stress-Testing & Contingency Planning" (strategic_relevance, relationship_type, influence_channels)
  - Depth sequences: surface=1 pass (discovery), standard=2 passes (discovery→architecture), deep=3 passes (discovery→architecture→confrontation)
  - ([`src/operationalizations/definitions/genealogy_relationship_classification.yaml`](src/operationalizations/definitions/genealogy_relationship_classification.yaml))

### Fixed
- **Stale composability references** in 3 capability definition YAMLs:
  - `genealogy_final_synthesis.yaml`: Replaced `intellectual_genealogy` (workflow, not engine) in synergy_engines with `concept_synthesis`; replaced stale `genealogy_deep_target_profiling` consumes_from with accurate chain references
  - `conditions_of_possibility_analyzer.yaml`: Replaced `intellectual_genealogy` in synergy_engines with `concept_taxonomy_argumentative_function`
  - `genealogy_relationship_classification.yaml`: Fixed stale `genealogy_deep_target_profiling` and `genealogy_prior_work_discovery` consumes_from references

### Added
- **Genealogy Pipeline Data Flow Walkthrough** — Comprehensive narrative documentation of the v3 pipeline
  - Pass-by-pass walkthrough: engines, stances, depth levels, data consumed/produced
  - Pipeline overview diagram (ASCII)
  - Depth control table with LLM call estimates
  - Context threading explanation (intra-chain via pass_context, inter-pass via context_parameters)
  - Key architectural decisions documented
  - ([`docs/GENEALOGY_PIPELINE_DATA_FLOW.md`](docs/GENEALOGY_PIPELINE_DATA_FLOW.md))

### Added
- **Enriched intellectual lineage** — All 11 capability engines now have rich lineage objects instead of flat strings:
  - `ThinkerReference`: name + 2-3 sentence bio (primary + secondary thinkers)
  - `TraditionEntry`: name + 2-3 sentence tradition description
  - `KeyConceptEntry`: name + 1-2 sentence working definition
  - New Pydantic models: `ThinkerReference`, `TraditionEntry`, `KeyConceptEntry` in `schemas_v2.py`
  - Union types on `IntellectualLineage` (`ThinkerReference | str`) for backwards compatibility
  - Enrichment script: `scripts/enrich_lineage.py` (uses Claude API with full engine context)
  - Updated `history_tracker.py` for object-based lineage diffs (name-keyed comparison)
  - Updated `capability_composer.py` for `.name` attribute access on traditions/concepts
  - Updated `enrich_capabilities.py` for dict-style lineage extraction

- **Capability definition history tracking** — File-based JSON history system that auto-detects YAML changes on startup
  - Computes stable SHA-256 hashes per definition, generates field-level diffs across all sections (lineage, dimensions, capabilities, depth, composability)
  - `history_schemas.py`: FieldChange, HistoryEntry, CapabilityHistory Pydantic models
  - `history_tracker.py`: hash computation, diff engine, summary generator, check_and_record_changes entry point
  - Storage in `src/engines/capability_history/` (committed to git for persistence across deploys)
  - 11 baseline entries auto-created for all capability engines
  - API endpoint: `GET /v1/engines/{key}/capability-definition/history?limit=50`
  - Registry integration: history checked on every YAML load (failure-safe, never blocks engine loading)

- **Enriched capability definitions for all 61 capabilities across 11 engines** — Each capability now has 4 new fields:
  - `extended_description`: 2-3 paragraphs grounded in the engine's intellectual tradition (~1600-2600 chars each)
  - `intellectual_grounding`: per-capability thinker/concept/method linking (thinkers span Brandom, Foucault, Koselleck, Toulmin, Derrida, Goffman, Saussure, Gadamer, Lakatos, Bloom, Sellars, Kuhn, Lakoff, Skinner, Nietzsche, Berlin, Grafton, Cassirer, Perelman, Walton, Lovejoy)
  - `indicators`: 5 textual signals per capability for when the capability is needed
  - `depth_scaling`: surface/standard/deep output expectations per capability
  - New Pydantic models: `CapabilityGrounding`, enriched `EngineCapability` with optional fields
  - Generation script: `scripts/enrich_capabilities.py` (uses Claude API with full engine context)

### Fixed
- **Orphaned dimensions**: `tactic_evolution` added to evolution_tactics_detector (architecture + reflection stances), `relationship_evidence` added to genealogy_relationship_classification (discovery + inference stances)
- **Missing operationalization**: Created `conditions_of_possibility_analyzer.yaml` with 4 stances (discovery, architecture, confrontation, integration), 8 dimensions, 3 depth levels — completing 11/11 engine coverage
- **Flat depth sequences**: Added depth escalation to concept_appropriation_tracker (3 passes deep), concept_evolution (3 passes deep), genealogy_relationship_classification (2 passes deep) — all engines now have genuine multi-pass at deep depth

### Added
- **Analytical Stances library** — New `src/operations/` module implementing 7 shared cognitive postures for multi-pass analysis
  - Stances describe HOW to think in a given pass, not what output format to produce (preserving prose-first architecture)
  - 7 stances: discovery (divergent), inference (deductive), confrontation (adversarial), architecture (structural), integration (convergent), reflection (meta-cognitive), dialectical (generative-contradictory)
  - **Dialectical stance** — Genuinely Hegelian cognitive posture for inhabiting contradictions productively. Covers Aufhebung (sublation), determinate negation, the negative as equally positive, concrete universals. Sits between confrontation (finds tensions) and integration (resolves them). 5 paragraphs, 3065 chars.
  - `src/operations/schemas.py` - AnalyticalStance and StanceSummary models
  - `src/operations/definitions/stances.yaml` - Stance definitions with rich prose descriptions
  - `src/operations/registry.py` - StanceRegistry with get, list, filter by position
  - `src/api/routes/operations.py` - API routes at `/v1/operations/stances`
  - Stances integrated into capability composer via `init_stance_registry()`

- **PassDefinition schema** — Extended `schemas_v2.py` with explicit pass definitions for multi-pass depth levels
  - `PassDefinition` model: pass_number, label, stance (key), focus_dimensions, focus_capabilities, consumes_from (pass numbers), description (prose)
  - Added `passes` field to `DepthLevel` (optional, backward-compatible)
  - Pass definitions make implicit multi-pass structure explicit: what each pass does, what stance it adopts, how data flows between passes

- **Per-pass prompt composition** — Extended capability composer to generate per-pass prompts
  - `compose_pass_prompt()` — Composes prompt for a single pass: framing + stance + focused dimensions + shared context + pass instructions
  - `compose_all_pass_prompts()` — Preview all passes for a depth level
  - `PassPrompt` model with stance metadata and data flow info
  - New API endpoints: `GET /{key}/pass-prompts`, `GET /{key}/pass-prompts/{pass_number}`

- **Explicit pass definitions for 10 capability definition YAMLs** - Added `passes` field to every depth level in all 10 genealogy engine YAMLs, specifying pass_number, label, stance, focus_dimensions, focus_capabilities, consumes_from, and description:
  - `conceptual_framework_extraction.yaml` - Surface: 1 pass (discovery); Standard: 2 passes (discovery, architecture); Deep: 3 passes (discovery, architecture, integration)
  - `concept_semantic_constellation.yaml` - Surface: 1 pass (discovery); Standard: 2 passes (discovery, architecture); Deep: 3 passes (discovery, architecture, integration)
  - `concept_synthesis.yaml` - Surface: 1 pass (integration); Standard: 2 passes (discovery, integration); Deep: 3 passes (discovery, confrontation, integration)
  - `concept_taxonomy_argumentative_function.yaml` - Surface: 1 pass (discovery); Standard: 2 passes (discovery, architecture); Deep: 3 passes (discovery, architecture, confrontation)
  - `inferential_commitment_mapper.yaml` - Surface: 1 pass (discovery); Standard: 2 passes (discovery, confrontation); Deep: 3 passes (discovery, confrontation, integration)
  - `evolution_tactics_detector.yaml` - Surface: 1 pass (discovery); Standard: 2 passes (discovery, architecture); Deep: 3 passes (discovery, architecture, reflection)
  - `concept_evolution.yaml` - Single-pass at all depths: Surface (discovery); Standard (inference); Deep (inference)
  - `concept_appropriation_tracker.yaml` - Single-pass at all depths: Surface (discovery); Standard (inference); Deep (inference)
  - `genealogy_relationship_classification.yaml` - Single-pass at all depths: Surface (discovery); Standard (inference); Deep (inference)
  - `genealogy_final_synthesis.yaml` - Single-pass capstone at all depths: Surface (integration); Standard (integration); Deep (integration)
  - All 6 analytical stances used: discovery, inference, confrontation, architecture, integration, reflection

- **Operationalization Layer** — New `src/operationalizations/` module decouples stance operationalizations from engine YAML definitions, creating a three-layer architecture: Stances (HOW) x Engines (WHAT) = Operationalizations (bridge)
  - `src/operationalizations/schemas.py` — StanceOperationalization, DepthPassEntry, DepthSequence, EngineOperationalization models + summary/coverage types
  - `src/operationalizations/registry.py` — OperationalizationRegistry with full CRUD, coverage_matrix(), get_stance_for_engine(), get_depth_sequence()
  - `src/operationalizations/definitions/` — 10 extracted YAML files (one per engine with capability definitions)
  - `scripts/extract_operationalizations.py` — Extraction script that migrated inline pass definitions to standalone operationalization files
  - **API routes** at `/v1/operationalizations/`: list, get, update, per-stance CRUD, per-depth CRUD, coverage matrix, compose-preview
  - **LLM generation endpoints**: `POST /v1/llm/operationalization-generate` (single), `operationalization-generate-all` (bulk), `operationalization-generate-sequence` (depth sequence with data flow)
  - **Prompt composer integration**: `compose_all_pass_prompts()` now checks operationalization registry first, falls back to inline passes. Verified byte-identical output for all 10 extracted engines.
  - **Frontend** (analyzer-mgmt): Types, API client, coverage grid list page, engine detail page with stance cards + depth sequence viewer, navigation item
  - **Interactive depth sequence editor** — Drag-and-drop pass reordering with automatic renumbering and consumes_from rewiring, add pass (+) with stance picker dropdown, remove pass (x) on hover, save/reset with dirty tracking and unsaved-changes banner
  - **Per-stance controls** — Individual Generate button (LLM regeneration per stance-engine pair), Compose Preview button showing assembled prompt in dark code panel
  - **Full operationalization PUT** — `api.operationalizations.update()` for saving entire operationalization after edits

- **Dialectical passes added to 4 engines' deep modes** — Engines whose deep analysis most benefits from Hegelian working-through of contradictions now include a dialectical pass:
  - `inferential_commitment_mapper.yaml` — Deep: 4 passes (discovery → confrontation → **dialectical** → integration). Dialectical pass works through commitment conflicts: which are productive (generating insight through irresolution) vs. destructive (genuine flaws), traces cascading contradictions, articulates unstated positions the commitment landscape points toward.
  - `concept_semantic_constellation.yaml` — Deep: 4 passes (discovery → architecture → **dialectical** → integration). Dialectical pass inhabits boundary tensions as generative sites: fuzzy boundaries reveal conceptual limits, competing clusters show double-duty concepts, definition-usage gaps reveal what concepts are trying to become.
  - `concept_synthesis.yaml` — Deep: 4 passes (discovery → confrontation → **dialectical** → integration). Dialectical pass traces how intellectual evolution is driven by internal contradiction: divergences reveal what concepts are trying to become, convergences tested for genuine Aufhebung vs. mere juxtaposition, deepest insights emerge from unstable commitments.
  - `concept_taxonomy_argumentative_function.yaml` — Deep: 4 passes (discovery → architecture → confrontation → **dialectical**). Dialectical pass asks what structural tensions produce: vulnerable load-bearing chains may signal ambition outrunning justification, apparent redundancy may be dialectical triangulation, fragility may be the price of originality.

### Fixed
- **consumes_from field in 2 YAMLs** — `inferential_commitment_mapper.yaml` and `evolution_tactics_detector.yaml` had dimension keys (strings) in `consumes_from` instead of pass numbers (integers). Fixed to use `[1]` and `[1, 2]` per the PassDefinition schema.

### Added
- **10 new capability definitions for all genealogy engines (Phase 3)** - Complete capability-driven YAML definitions for prose-mode analysis across all 3 chains + 2 standalone engines:
  - Target profiling chain: `conceptual_framework_extraction.yaml`, `concept_semantic_constellation.yaml`, `inferential_commitment_mapper.yaml`
  - Prior work scanning chain: `concept_evolution.yaml`, `concept_appropriation_tracker.yaml`
  - Synthesis chain: `concept_synthesis.yaml`, `concept_taxonomy_argumentative_function.yaml`, `evolution_tactics_detector.yaml`
  - Standalone: `genealogy_relationship_classification.yaml`, `genealogy_final_synthesis.yaml`
  - Each definition specifies problematique, intellectual lineage, analytical dimensions with depth guidance, capabilities, and composability specs

- **Capability definitions for Pass 2 genealogy scanning engines** - Two new YAML capability definitions for the prior work scanning chain
  - `src/engines/capability_definitions/concept_evolution.yaml` - Concept Evolution Tracker: 6 analytical dimensions (vocabulary_evolution, methodology_evolution, metaphor_evolution, framing_evolution, concept_trajectory, dimensional_comparison_matrix), 6 capabilities, 3 depth levels. Koselleck/Skinner/Kuhn lineage. First engine in scanning chain.
  - `src/engines/capability_definitions/concept_appropriation_tracker.yaml` - Concept Appropriation Tracker: 6 analytical dimensions (migration_paths, semantic_mutations, appropriation_patterns, distortion_map, recombination, acknowledgment_status), 6 capabilities, 3 depth levels. Derrida/Said/Bakhtin/Bloom lineage. Second engine in scanning chain.

- **Capability Engine Definitions (v2 format)** - New engine definition format describing WHAT an engine investigates, not HOW it formats output
  - `src/engines/schemas_v2.py` - Pydantic models: CapabilityEngineDefinition, AnalyticalDimension, EngineCapability, ComposabilitySpec, DepthLevel, IntellectualLineage
  - `src/engines/capability_definitions/conditions_of_possibility_analyzer.yaml` - First capability definition with 8 analytical dimensions, 8 capabilities, 3 depth levels, composability spec
  - Registry support: `get_capability_definition()`, `list_capability_definitions()`, `list_capability_summaries()` in EngineRegistry
  - API endpoints: `GET /v1/engines/capability-definitions` (list), `GET /v1/engines/{key}/capability-definition` (full definition)

- **Capability-Based Prompt Composer** - Prose-focused prompt composition from capability definitions
  - `src/stages/capability_composer.py` - compose_capability_prompt() generates prompts asking for analytical PROSE, not JSON
  - API endpoint: `GET /v1/engines/{key}/capability-prompt?depth=standard&dimensions=...`
  - Supports depth levels (surface/standard/deep), focused dimensions, shared context injection

- **Analysis Output Tables (Critic DB)** - Schema-on-read infrastructure in the-critic
  - `AnalysisOutputDB` - Plain-text analysis output table with lineage tracking (parent_id tree)
  - `PresentationCacheDB` - Cached structured extractions from prose, keyed by output hash + section

- **Prose Output Path (Critic)** - Full prose-mode pipeline for conditions_of_possibility engine
  - `the-critic/analyzer/output_store.py` - Persistent storage for prose analysis outputs with lineage tracking
  - `the-critic/analyzer/context_broker.py` - Cross-pass prose context assembly for LLM prompts
  - `the-critic/analyzer/presentation.py` - Schema-on-read extraction from prose using Claude Haiku + direct prose fallback
  - `the-critic/analyzer/analyze_genealogy.py` - Added output_mode="prose" parameter, capability-based prompts, prose output saving
  - `the-critic/api/server.py` - Presentation endpoint `POST /api/genealogy/{job_id}/present/conditions`, pre-extraction on job completion, multi-path job_id resolution (in-memory → DB → direct prose extraction)
  - `the-critic/webapp/src/pages/GenealogyPage.tsx` - Dual-mode ConditionsTab: legacy JSON or prose with on-demand extraction

- **Phase 2.5 Quality Validation (Varoufakis PoC)** - Prose mode validated against JSON baseline
  - Prose mode: 6,638 words of connected analytical narrative with full section structure
  - JSON-forced: 83K chars of disconnected fields with empty counterfactual/synthetic judgment sections
  - Prose extraction via Haiku: 12 enabling conditions, 7 constraining, 5K+ chars counterfactual, 5K+ chars synthetic judgment — all fields 100% complete
  - JSON-forced: 12 enabling (missing condition_types), 8 constraining, 0 chars counterfactual, 0 chars synthetic judgment
  - Decision: Prose mode strictly superior. Proceed to Phase 3 (scale to all engines)

- **First-Class Functions** - 24 decider-v2 LLM functions registered as first-class entities
  - New module: `src/functions/` with schemas, registry, and API routes
  - Each function captures: prompt templates (actual text), model config, I/O contracts, implementation locations with GitHub links, DAG relationships
  - 6 categories (coordination, generation, analysis, synthesis, tool, infrastructure), 3 tiers (strategic/tactical/lightweight)
  - Full REST API at `/v1/functions` with per-section getters and filtering
  - FunctionRegistry following EngineRegistry pattern (JSON file storage)
  - 3 new decider workflow definitions (question_lifecycle, onboarding, answer_processing) using `function_key`-backed passes
  - `DECISION_SUPPORT` added to WorkflowCategory enum
  - `function_key` field added to WorkflowPass schema

- **First-Class Audiences** - Audiences are now a proper entity in analyzer-v2
  - 5 audience definitions extracted from analyzer's audience_profiles.py: analyst, executive, researcher, activist, social_movements
  - Rich data model with 8 sections: identity, engine affinities, visual style, textual style, curation, strategist, pattern discovery, vocabulary
  - 1,599 vocabulary translations per audience (pivoted from per-term to per-audience format)
  - Full CRUD API at `/v1/audiences` with per-section getters and utility endpoints
  - `AudienceRegistry` following WorkflowRegistry pattern (JSON file storage)
  - StageComposer updated to load audience guidance from registry (replaces hardcoded blocks)
  - Global vocabulary merges underneath engine-specific vocabulary (engine overrides win)
  - `social_movements` added as 5th audience type across all route files
  - Migration script: `scripts/extract_audiences.py`
  - New files: `src/audiences/` (schemas, registry, 5 JSON definitions)

### Changed
- **Semantic Field Engine v3** - Massively expanded for close textual analysis
  - All quote fields now support multiple quotes per item (arrays instead of strings)
  - Every quote requires 3-6 sentences minimum context
  - Each quote must have detailed close reading analysis (3-5 sentences)
  - Expanded descriptions from brief labels to 2-5 sentence analytical prose
  - New textual_evidence objects with {quote, source, analysis} structure
  - New fields: close_reading (4-8 sentences), tension_analysis (5-8 sentences)
  - New fields: how_surfaced, what_denying_it_costs, evolution_significance
  - 10 critical requirements in special_instructions for rigorous analysis
  - Designed for nuclear-mode analysis: Opus 4.6, 64k tokens, 32k thinking

### Added
- **Concept Analysis Tab Engines** (2 new) - New analysis types for multi-tab concept breakdown
  - `concept_semantic_field` - Maps meaning-space: boundaries, neighbors, definitional variations
  - `concept_metaphorical_ground` - Maps metaphorical understanding: root metaphors, source domains, competing framings
  - Each has rich output schemas (7-9 top-level sections) for multi-faceted display
  - Complements existing Inferential Role, Logical Structure, Assumption Excavator tabs
  - Engine count: 183 -> 185

### Changed
- **Upgraded `concept_causal_mechanisms`** - Existing skeletal engine (used in Logical Structure Phase 6)
  upgraded from empty schema to rich causal architecture with 9 top-level sections:
  as_cause, as_effect, feedback_loops, conditions, causal_mechanisms, counterfactuals, causal_network, meta
  - Version bumped from 1 to 2

- **Influence Pass Engines** (5 new) - Engine definitions for the anxiety_of_influence workflow
  - `influence_pass1_thinker_identification` - Identify all cited thinkers and invocation patterns
  - `influence_pass2_hypothesis_generation` - Generate hypotheses about potential misuse
  - `influence_pass3_textual_sampling` - Sample passages from original thinker works
  - `influence_pass4_deep_engagement` - Compare author usage vs thinker's actual positions
  - `influence_pass5_report_generation` - Synthesize comprehensive influence fidelity report
  - Engine count increased from 178 to 183

- **Workflow CRUD Endpoints** - Full create/read/update/delete operations for workflows
  - `POST /v1/workflows` - Create new workflow
  - `PUT /v1/workflows/{key}` - Update workflow definition
  - `PUT /v1/workflows/{key}/pass/{n}` - Update single pass
  - `DELETE /v1/workflows/{key}` - Delete workflow
  - `GET /v1/workflows/{key}/pass/{n}/prompt` - Get composed prompt for engine-backed passes
  - WorkflowRegistry now has `save()`, `update_pass()`, `delete()`, `reload()` methods

- **The Critic Sections Extraction** - Extracted analytical operations from The Critic into analyzer-v2
  - **New Engine Categories** (2 new):
    - `VULNERABILITY` - Counter-response self-analysis, exposed flanks (9 engines)
    - `OUTLINE` - Essay construction operations (5 engines)
  - **Rhetoric Engines** (7 new): `rhetoric_deflection_analyzer`, `rhetoric_contradiction_detector`, `rhetoric_leap_finder`, `rhetoric_silence_mapper`, `rhetoric_concession_tracker`, `rhetoric_retreat_detector`, `rhetoric_cherrypick_analyzer`
  - **Vulnerability Engines** (9 new): `vulnerability_strawman_risk`, `vulnerability_inconsistency`, `vulnerability_logic_gap`, `vulnerability_unanswered`, `vulnerability_overconcession`, `vulnerability_overreach`, `vulnerability_undercitation`, `vulnerability_weak_authority`, `vulnerability_exposed_flank`
  - **Big Picture Engine** (1 new): `big_picture_inferential` - Pre-conceptual document-level analysis
  - **Outline Editor Engines** (5 new): `outline_talking_point_generator`, `outline_notes_extractor`, `outline_talking_point_upgrader`, `outline_document_summarizer`, `outline_synthesis_generator`
  - Engine count increased from ~156 to 178

- **Workflows Module** - Multi-pass analysis pipelines
  - New `src/workflows/` module for complex multi-pass pipelines
  - `WorkflowDefinition` and `WorkflowPass` schemas
  - `WorkflowRegistry` for loading workflow definitions
  - 3 workflows: `lines_of_attack`, `anxiety_of_influence`, `outline_editor`
  - API endpoints at `/v1/workflows/*`:
    - `GET /v1/workflows` - List all workflows
    - `GET /v1/workflows/{key}` - Get workflow definition
    - `GET /v1/workflows/{key}/passes` - Get workflow passes
    - `GET /v1/workflows/category/{category}` - Filter by category

- **12-Phase Concept Chain** - `concept_analysis_12_phase` chain linking all concept analysis phases from semantic constellation through synthesis

- **App Tagging System** - Filter engines by consuming app
  - New `apps` field on EngineDefinition schema (list of app names)
  - New `apps` field on EngineSummary for API responses
  - New `app` query parameter on `GET /v1/engines?app=critic`
  - New `GET /v1/engines/apps` endpoint lists all unique app tags
  - Tagged 63 Critic-related engines with `"apps": ["critic"]`:
    - 7 debate rhetoric engines
    - 9 vulnerability engines
    - 5 outline editor engines
    - 1 big picture engine
    - 39 concept analysis engines
    - 4 existing rhetoric engines (tu_quoque_tracker, motte_bailey_detector, etc.)
  - `scripts/tag_critic_engines.py` - Script for bulk tagging engines

### Changed
- **Visual Styles Rebranding** - Renamed all 6 dataviz styles to be independent of person/organization names
  - `tufte` → `minimalist_precision` (Minimalist Precision Graphics)
  - `nyt_cox` → `explanatory_narrative` (Explanatory Narrative Graphics)
  - `ft_burn_murdoch` → `restrained_elegance` (Restrained Elegance)
  - `lupi_data_humanism` → `humanist_craft` (Humanist Data Craft)
  - `stefaner_truth_beauty` → `emergent_systems` (Emergent Systems Visualization)
  - `activist_agitprop` → `mobilization` (Mobilization Graphics)
  - Philosophies rewritten to describe the approach independently without implying IP copying
  - New `influences` section with proper attribution:
    - `tradition_note`: Explains how the style draws from broader traditions
    - `exemplars`: Lists people/organizations whose work exemplifies this approach, with contributions
    - `key_works`: Foundational texts and projects in this tradition
  - Updated schema: Added `StyleInfluences` and `StyleExemplar` models
  - Removed old `practitioners` and `references` fields
  - All engine/format/audience affinity mappings updated with new keys

### Added
- **Display Configuration Module** - Centralized Gemini formatting rules from Visualizer
  - New `src/display/` module with schemas, registry, and JSON definitions
  - Display instructions: branding rules, label formatting, numeric display, field cleanup
  - Hidden fields configuration: 23 field names + 5 suffixes that should never appear on visualizations
  - Numeric-to-label conversion: Transforms 0-1 scores to "Very Strong", "Strong", "Moderate", "Weak", "Very Weak"
  - Visual format typology: 40 formats in 8 categories with Gemini prompt patterns
  - Data type mappings: 11 data structure patterns → recommended formats
  - Quality criteria: Must-have, should-have, and avoid lists for visualization quality
  - New API endpoints at `/v1/display/*`:
    - `GET /v1/display/config` - Complete display configuration
    - `GET /v1/display/instructions` - Gemini formatting instructions
    - `GET /v1/display/hidden-fields` - Fields to hide from visualizations
    - `GET /v1/display/formats` - Visual format categories
    - `GET /v1/display/formats/{key}` - Specific format with prompt pattern
    - `GET /v1/display/mappings` - Data type → format recommendations
    - `GET /v1/display/quality-criteria` - Visualization quality checklist
  - Purpose: Make Gemini formatting rules transparent and centrally managed
  - Source: Extracted from visualizer/analyzer/display_utils.py and visualizer/docs/VISUAL_FORMAT_TYPOLOGY.md

- **Analytical Primitives** - Trading zone between engines and visual styles
  - New `src/primitives/` module bridging analytical meaning to visual form
  - 12 primitives: cyclical_causation, hierarchical_support, dialectical_tension,
    branching_foreclosure, inferential_bundling, strategic_interaction,
    epistemic_layering, temporal_evolution, comparative_positioning,
    flow_transformation, rhetorical_architecture, network_influence
  - Each primitive has: description, visual_hint, visual_forms, style_hint,
    style_leanings, gemini_guidance, associated_engines
  - 44 engine associations across primitives
  - API endpoints at `/v1/primitives/*`:
    - `GET /v1/primitives` - List all primitives
    - `GET /v1/primitives/{key}` - Get specific primitive
    - `GET /v1/primitives/for-engine/{key}/guidance` - Get Gemini guidance text
  - Purpose: Soft guidance for Gemini about what visual approaches work

- **Visual Styles System** - Centralized dataviz style definitions and affinity mappings
  - New `src/styles/` module with schemas, registry, and JSON definitions
  - 6 dataviz school definitions with color palettes, typography, layout principles, Gemini modifiers:
    - Minimalist Precision (data-ink ratio maximization)
    - Explanatory Narrative (reader-friendly annotations)
    - Restrained Elegance (financial journalism aesthetic)
    - Humanist Data Craft (organic, human-centered)
    - Emergent Systems (complex networks, structure revelation)
    - Mobilization (activist graphics)
  - Each style includes `influences` section with tradition_note, exemplars, key_works
  - Affinity mappings: 37 engine→style, 32 format→style, 11 audience→style
  - New API endpoints at `/v1/styles/*`:
    - `GET /v1/styles` - List style schools
    - `GET /v1/styles/schools/{key}` - Get full style guide with palette, typography, Gemini modifiers
    - `GET /v1/styles/affinities/engine` - Engine affinity mappings
    - `GET /v1/styles/affinities/format` - Format affinity mappings
    - `GET /v1/styles/affinities/audience` - Audience affinity mappings
    - `GET /v1/styles/engine-mappings` - All engines with style affinities (for UI)
  - Purpose: Centralize style knowledge for Visualizer to consume via API
- **Semantic Visual Intent System** - Bridges analytical meaning to visual form
  - `SemanticVisualIntent` schema in `src/stages/schemas.py` with visual grammar specification
  - New endpoint `GET /v1/engines/{key}/visual-intent` returns semantic intent for visualization
  - Added `semantic_visual_intent` to 5 priority engines:
    - `feedback_loop_mapper` - feedback_dynamics concept → causal loop diagrams
    - `dialectical_structure` - dialectical_movement concept → dialectical spirals
    - `inferential_commitment_mapper` - inferential_chain concept → commitment cascades
    - `causal_inference_auditor` - causal_identification concept → causal DAGs
    - `path_dependency_analyzer` - path_dependency concept → path branching trees
  - Each intent includes: visual grammar (core metaphor, key elements, anti-patterns),
    recommended forms with Gemini templates, form selection logic, style affinities
  - Purpose: Enable Visualizer to select visualizations based on MEANING not just data STRUCTURE
    (e.g., feedback loops → actual loop diagrams, not generic radial layouts)

### Fixed
- **V2 Engines: Missing relationship_graph population instructions** - Added generic graph-building section to shared extraction template
  - Root cause: v2 engines had `relationship_graph` in schema but no instructions telling LLM how to populate it
  - Solution: Added comprehensive "BUILD THE RELATIONSHIP GRAPH" section to `src/stages/templates/extraction.md.j2`
  - Template dynamically uses engine's `key_fields` and `key_relationships` to generate engine-appropriate instructions
  - Removed redundant engine-specific graph steps from all 14 v2 engines:
    - `absent_center`, `argument_architecture`, `assumption_excavation`, `charitable_reconstruction`
    - `conditions_of_possibility`, `dialectical_structure`, `epistemic_rupture_tracer`
    - `feedback_loop_mapper`, `incentive_structure_mapper`, `intellectual_genealogy`
    - `metaphor_network`, `motte_bailey_detector`, `path_dependency_analyzer`, `rhetorical_strategy`
  - All engines now benefit from graph-building guidance without repeating it in each definition
  - This fixes the visual diversity/depth regression compared to inferential_commitment_mapper_advanced

### Added
- **Engine Upgrade System** - Generate advanced engines via Claude API with extended thinking
  - `scripts/upgrade_engine.py` - Main CLI script for engine generation
  - `engine_upgrade_context/system_prompt.md` - Comprehensive engine system explanation
  - `engine_upgrade_context/methodology_database.yaml` - 10 priority engines with theorists/concepts
  - `engine_upgrade_context/examples/` - Example advanced engines for reference
  - `outputs/upgraded_engines/` - Generated engine definitions land here
  - Features: dry-run mode, token estimation, methodology override, Pydantic validation
  - Uses Claude Opus 4.5 with 32k thinking tokens + 64k output tokens
- **10 Advanced Engines** - Deep theoretical frameworks with cross-referencing ID systems
  - `dialectical_structure_advanced.json` - Hegelian dialectics (Hegel, Marx, Adorno)
  - `assumption_excavation_advanced.json` - Epistemological archaeology (Wittgenstein, Quine, Collingwood)
  - `conditions_of_possibility_advanced.json` - Foucauldian archaeology/genealogy
  - `epistemic_rupture_tracer_advanced.json` - History of science (Bachelard, Kuhn, Lakatos)
  - `rhetorical_strategy_advanced.json` - Dramatistic pentad (Burke, Aristotle, Perelman)
  - `metaphor_network_advanced.json` - Conceptual metaphor theory (Lakoff, Johnson, Ricoeur)
  - `argument_architecture_advanced.json` - Toulmin model + argumentation schemes (Walton)
  - `intellectual_genealogy_advanced.json` - History of ideas (Foucault, Lovejoy, Bloom)
  - `incentive_structure_mapper_advanced.json` - Game theory/institutional economics (Ostrom, Buchanan)
  - `feedback_loop_mapper_advanced.json` - Systems dynamics (Meadows, Senge, Sterman)
  - All engines feature: relationship_graph (nodes/edges/clusters), rich stage_context, audience vocabulary calibration, comprehensive meta sections
- **Engine Profile / About Feature** - Rich metadata for engines
  - `EngineProfile` Pydantic model with theoretical foundations, key thinkers, methodology, extracts, use cases, strengths, limitations, related engines, preamble
  - `engine_profile` optional field on `EngineDefinition`
  - `has_profile` field on `EngineSummary` for list endpoints
  - CRUD endpoints: `GET/PUT/DELETE /v1/engines/{key}/profile`
  - LLM endpoints for AI-powered profile generation:
    - `POST /v1/llm/profile-generate` - Generate full profile from engine data
    - `POST /v1/llm/profile-suggestions` - Get suggestions for improving specific fields
    - `GET /v1/llm/status` - Check LLM availability
  - Profiles persist to engine JSON definition files
  - Requires `ANTHROPIC_API_KEY` environment variable for LLM features
- **Stage Prompt Composition System** - Generic templates + engine context injection
  - `src/stages/` module with Jinja2 template composition
  - Generic templates: `extraction.md.j2`, `curation.md.j2`, `concretization.md.j2`
  - Shared frameworks: Brandomian, Dennett, Toulmin primers
  - StageComposer for runtime prompt composition
  - Audience parameter for vocabulary calibration (researcher/analyst/executive/activist)
- Migration script `scripts/migrate_engines_to_stages.py` for converting engines
- Architecture documentation in `docs/STAGE_PROMPTS.md`
- New endpoint: `GET /v1/engines/{key}/stage-context` for debugging

### Changed
- **BREAKING**: EngineDefinition schema restructured
  - Removed: `extraction_prompt`, `curation_prompt`, `concretization_prompt` fields
  - Added: `stage_context` field with injection context for templates
- Prompt endpoints now compose prompts at runtime from templates
- Added `audience` query parameter to prompt endpoints
- EnginePromptResponse includes `audience` and `framework_used` fields

### Migration Required
- Run `python scripts/migrate_engines_to_stages.py` to convert engine JSON files
- Backups saved to `src/engines/definitions_backup_pre_stages/`
- See `docs/STAGE_PROMPTS.md` for full migration guide

---

## [0.1.1] - 2026-01-29

### Added
- Initial Analyzer v2 service structure ([src/](src/))
- Pydantic schemas for engines, paradigms, chains ([src/engines/schemas.py](src/engines/schemas.py), [src/paradigms/schemas.py](src/paradigms/schemas.py), [src/chains/schemas.py](src/chains/schemas.py))
- Registry classes for loading definitions from JSON ([src/engines/registry.py](src/engines/registry.py), [src/paradigms/registry.py](src/paradigms/registry.py), [src/chains/registry.py](src/chains/registry.py))
- FastAPI application with /v1/engines, /v1/paradigms, /v1/chains routes ([src/api/main.py](src/api/main.py))
- Engine extraction script to port from current Analyzer ([scripts/extract_engines.py](scripts/extract_engines.py))
- 123 engine definitions extracted from current Analyzer ([src/engines/definitions/](src/engines/definitions/))
- Marxist paradigm with full 4-layer ontology ([src/paradigms/instances/marxist.json](src/paradigms/instances/marxist.json))
- Brandomian paradigm with full 4-layer ontology ([src/paradigms/instances/brandomian.json](src/paradigms/instances/brandomian.json))
- Concept Analysis Suite chain definition ([src/chains/definitions/concept_analysis_suite.json](src/chains/definitions/concept_analysis_suite.json))
- Critical Analysis Chain definition ([src/chains/definitions/critical_analysis_chain.json](src/chains/definitions/critical_analysis_chain.json))
- Start script for local development ([start](start))
- Requirements file ([requirements.txt](requirements.txt))
- Project documentation ([CLAUDE.md](CLAUDE.md), [docs/FEATURES.md](docs/FEATURES.md))

---

## [0.1.0] - 2026-01-26

Initial release of Analyzer v2 - Pure Definitions Service.

### Core Features
- **Engine Registry**: Load 123+ engine definitions from JSON, serve via API
- **Paradigm Registry**: Load paradigm definitions with 4-layer ontology, generate primers
- **Chain Registry**: Load chain specifications for multi-engine analysis
- **REST API**: FastAPI service with comprehensive endpoints

### Paradigms Included
- Marxist (ported from IE mockParadigmData.js)
- Brandomian (new, for inferential commitment analysis)

### Chains Included
- Concept Analysis Suite (LLM selection, 5 engines)
- Critical Analysis Chain (sequential, 4 engines)
