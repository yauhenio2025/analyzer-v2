# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

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
