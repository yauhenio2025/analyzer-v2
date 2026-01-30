# Feature Inventory

> Auto-maintained by Claude Code. Last updated: 2026-01-30

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
