# Feature Inventory

> Auto-maintained by Claude Code. Last updated: 2026-02-08

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
- **Description**: Multi-pass analysis pipelines that differ from chains (intermediate state, caching, resumability)
- **Entry Points**:
  - `src/workflows/schemas.py:1-123` - WorkflowDefinition, WorkflowPass, WorkflowCategory
  - `src/workflows/registry.py:1-175` - WorkflowRegistry class with save/update/delete methods
  - `src/workflows/definitions/*.json` - 3 workflow definitions
  - `src/api/routes/workflows.py:1-230` - Workflow API endpoints with full CRUD
- **Workflows** (3 total):
  - `lines_of_attack` - Extract targeted critiques from external thinkers (2 passes)
  - `anxiety_of_influence` - Analyze intellectual debt fidelity (5 passes, engine-backed)
  - `outline_editor` - AI-assisted essay construction (4 passes, engine-backed)
- **API Endpoints**:
  - `GET /v1/workflows` - List all workflows
  - `GET /v1/workflows/{key}` - Get workflow definition
  - `GET /v1/workflows/{key}/passes` - Get workflow passes
  - `GET /v1/workflows/{key}/pass/{n}` - Get specific pass
  - `GET /v1/workflows/{key}/pass/{n}/prompt` - Get composed prompt for a pass
  - `GET /v1/workflows/category/{category}` - Filter by category
  - `POST /v1/workflows` - Create new workflow
  - `PUT /v1/workflows/{key}` - Update workflow definition
  - `PUT /v1/workflows/{key}/pass/{n}` - Update single pass
  - `DELETE /v1/workflows/{key}` - Delete workflow
  - `POST /v1/workflows/reload` - Force reload from disk
- **Dependencies**: Pydantic v2
- **Source**: The Critic
- **Added**: 2026-02-06 | **Modified**: 2026-02-08

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
