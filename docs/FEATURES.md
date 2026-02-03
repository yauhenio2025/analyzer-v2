# Feature Inventory

> Auto-maintained by Claude Code. Last updated: 2026-02-03

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
- **Description**: Loads and serves 123+ engine definitions from JSON files
- **Entry Points**:
  - `src/engines/registry.py:1-100` - EngineRegistry class
  - `src/engines/schemas.py:1-150` - EngineDefinition Pydantic model
  - `src/engines/definitions/*.json` - 123 engine definition files
- **Dependencies**: Pydantic v2
- **Added**: 2026-01-26

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

## API

### FastAPI Application
- **Status**: Active
- **Description**: REST API serving definitions at /v1/*
- **Entry Points**:
  - `src/api/main.py:1-175` - FastAPI app with CORS, health check
  - `src/api/routes/engines.py` - Engine endpoints (incl. profile CRUD)
  - `src/api/routes/paradigms.py` - Paradigm endpoints
  - `src/api/routes/chains.py` - Chain endpoints
  - `src/api/routes/llm.py` - LLM-powered profile generation
- **Dependencies**: FastAPI, Uvicorn, Pydantic v2, Anthropic SDK (optional)
- **Added**: 2026-01-26 | **Modified**: 2026-01-30
