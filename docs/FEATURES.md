# Feature Inventory

> Auto-maintained by Claude Code. Last updated: 2026-02-18

## Analytical Stances (Operations)

### Analytical Stances Library
- **Status**: Active
- **Description**: Shared cognitive postures for multi-pass analysis. 7 stances describing HOW an LLM should think in a given pass — discovery, inference, confrontation, architecture, integration, reflection, dialectical. Stances are prose descriptions injected into prompts, NOT output templates.
- **Entry Points**:
  - `src/operations/schemas.py:1-30` - AnalyticalStance and StanceSummary Pydantic models
  - `src/operations/definitions/stances.yaml:1-230` - 7 stance definitions with prose descriptions, cognitive modes, typical positions
  - `src/operations/registry.py:1-80` - StanceRegistry class (get, list, filter by position)
  - `src/api/routes/operations.py:1-82` - API routes for stances
  - `src/api/main.py:78-84` - Stance registry loading in lifespan, init_stance_registry for capability composer
- **Stances** (7 total):
  - `discovery` (early, divergent) — Cast the widest net, surface everything without filtering
  - `inference` (early, deductive) — Trace what follows from what, map logical chains
  - `confrontation` (middle, adversarial) — Pit findings against each other, test robustness
  - `architecture` (middle, structural) — Map load-bearing skeleton, classify structures
  - `integration` (late, convergent) — Synthesize across dimensions into unified narrative
  - `reflection` (late, meta-cognitive) — Assess the assessment, identify blindspots
  - `dialectical` (middle, generative-contradictory) — Inhabit contradictions productively; Hegelian Aufhebung, determinate negation, concrete universals
- **API Endpoints**:
  - `GET /v1/operations/stances` - List stance summaries
  - `GET /v1/operations/stances/full` - List all stances with full prose
  - `GET /v1/operations/stances/{key}` - Get single stance
  - `GET /v1/operations/stances/{key}/text` - Get just the stance prose for prompt injection
  - `GET /v1/operations/stances/position/{position}` - Filter by typical position (early/middle/late)
- **Added**: 2026-02-17

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

## Schema-on-Read / Prose Pipeline (the-critic)

### Prose Output Infrastructure
- **Status**: Active (PoC — conditions_of_possibility engine only)
- **Description**: Full prose-mode pipeline where LLM outputs analytical prose instead of forced JSON. Structured data extracted at presentation time using Claude Haiku.
- **Entry Points** (in the-critic project):
  - `analyzer/output_store.py` - Persistent storage for prose outputs with lineage tracking and presentation cache
  - `analyzer/context_broker.py` - Cross-pass prose context assembly for LLM prompts
  - `analyzer/presentation.py` - Schema-on-read extraction using Claude Haiku, with caching
  - `analyzer/analyze_genealogy.py` - output_mode="prose" parameter, capability-based prompts, prose output saving
  - `api/server.py` - `POST /api/genealogy/{job_id}/present/conditions` endpoint, pre-extraction on job completion
  - `webapp/src/pages/GenealogyPage.tsx` - ConditionsTab dual-mode rendering (legacy JSON or prose extraction)
  - `webapp/src/pages/GenealogyPage.css` - Prose mode UI styles (spinner, badges, error states)
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
  - `src/api/routes/workflows.py:88-110` - GET endpoint with depth, phase_number, min_score, max_candidates params
- **Scoring Tiers**:
  - Synergy (0.30 weight) — explicit synergy_engines match, bidirectional
  - Dimension production (0.25) — produces dimensions consumed by phase engines
  - Dimension novelty (0.20) — covers dimensions no current engine covers
  - Capability gap (0.15) — fills capabilities the phase lacks
  - Category affinity (0.10) — same analytical category/kind
- **Recommendation Tiers**: strong (>=0.65), moderate (>=0.40), exploratory (>=0.20), tangential (<0.20, filtered)
- **API Endpoint**: `GET /v1/workflows/{key}/extension-points?depth=standard&phase_number=1.0&min_score=0.20&max_candidates=15`
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
