# Feature Inventory

> Auto-maintained by Claude Code. Last updated: 2026-01-26

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

## API

### FastAPI Application
- **Status**: Active
- **Description**: REST API serving definitions at /v1/*
- **Entry Points**:
  - `src/api/main.py:1-150` - FastAPI app with CORS, health check
  - `src/api/routes/engines.py` - Engine endpoints
  - `src/api/routes/paradigms.py` - Paradigm endpoints
  - `src/api/routes/chains.py` - Chain endpoints
- **Dependencies**: FastAPI, Uvicorn, Pydantic v2
- **Added**: 2026-01-26
