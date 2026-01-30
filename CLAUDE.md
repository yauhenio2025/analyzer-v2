# Analyzer v2 - Pure Definitions Service

> Lightweight service serving analytical definitions without execution logic

## Overview

Analyzer v2 extracts pure analytical definitions from the current Analyzer service:
- **Engine definitions**: Prompts, schemas, and metadata for 160+ analysis engines
- **Paradigm definitions**: 4-layer ontology structures (IE schema)
- **Engine chains**: Multi-engine composition specifications

This is the "reversed approach" - instead of moving process code TO Visualizer, we extract definitions OUT of Analyzer into this clean service.

## Tech Stack
- Python 3.11+ with FastAPI
- Pydantic v2 for schemas
- JSON files for definitions (no database)
- Anthropic SDK for LLM features (optional, requires ANTHROPIC_API_KEY)

## Quick Reference
- Start: `./start` or `uvicorn src.api.main:app --reload --port 8001`
- Test: `pytest tests/`
- API Docs: http://localhost:8001/docs

## Architecture Notes

```
analyzer-v2/
├── src/
│   ├── engines/           # Engine definitions
│   │   ├── schemas.py     # EngineDefinition Pydantic model
│   │   ├── registry.py    # EngineRegistry - loads from JSON
│   │   └── definitions/   # 160+ JSON files (one per engine)
│   │
│   ├── paradigms/         # Paradigm definitions (IE 4-layer)
│   │   ├── schemas.py     # ParadigmDefinition model
│   │   ├── registry.py    # ParadigmRegistry
│   │   └── instances/     # JSON files (marxist.json, etc.)
│   │
│   ├── chains/            # Engine chain specifications
│   │   ├── schemas.py     # EngineChainSpec model
│   │   ├── registry.py    # ChainRegistry
│   │   └── definitions/   # JSON files
│   │
│   └── api/               # FastAPI application
│       ├── main.py        # App entry point
│       └── routes/        # Endpoint handlers
│
└── scripts/
    └── extract_engines.py # Script to extract from current Analyzer
```

## API Endpoints

```
GET  /v1/engines                     # List all engines (has_profile flag)
GET  /v1/engines/{key}               # Full engine definition
GET  /v1/engines/{key}/extraction-prompt
GET  /v1/engines/{key}/curation-prompt
GET  /v1/engines/{key}/schema
GET  /v1/engines/{key}/profile       # Get engine profile/about
PUT  /v1/engines/{key}/profile       # Save engine profile
DELETE /v1/engines/{key}/profile     # Delete engine profile
GET  /v1/engines/category/{category}

GET  /v1/paradigms                   # List all paradigms
GET  /v1/paradigms/{key}             # Full paradigm (4-layer)
GET  /v1/paradigms/{key}/primer      # LLM-ready text
GET  /v1/paradigms/{key}/engines
GET  /v1/paradigms/{key}/critique-patterns

GET  /v1/chains                      # List chains
GET  /v1/chains/{key}                # Chain specification

GET  /v1/llm/status                  # Check LLM availability
POST /v1/llm/profile-generate        # Generate profile with AI
POST /v1/llm/profile-suggestions     # Get AI suggestions for profile
POST /v1/chains/recommend            # LLM recommends chain
```

## Documentation
- **CURRENT TASKS**: `docs/CURRENT-TASKS.md` - **READ THIS FIRST** for implementation roadmap
- Feature inventory: `docs/FEATURES.md` (read on demand)
- Change history: `docs/CHANGELOG.md` (read on demand)

## Deployment
- **Live URL**: https://analyzer-v2.onrender.com
- **GitHub**: https://github.com/yauhenio2025/analyzer-v2
- **Auto-deploy**: Push to `master` triggers automatic deployment

## Implementation Roadmap (See docs/CURRENT-TASKS.md for details)

| Phase | Status | Description |
|-------|--------|-------------|
| 1. Create Analyzer v2 | ✓ DONE | FastAPI service, 123 engines, deployed |
| 2. Complete Paradigms | ✓ DONE | 4 paradigms (marxist, brandomian, hegelian_critical, pragmatist_praxis), 12 engines linked |
| 3. Engine Chains | DEFERRED | More chains, LLM recommendation |
| 4. Wire Current Analyzer | ✓ DONE | v2 client added, caching, prompt loading modified |
| 5. Consumer Integration | ✓ DONE | Visualizer MCP paradigm support, IE API client |

**All core phases complete!** The disaggregation is operational.

## Related Projects
- **Current Analyzer**: `/home/evgeny/projects/analyzer` - Will call this v2 API
- **Visualizer**: `/home/evgeny/projects/visualizer` - MCP server, will use paradigms
- **IE**: `/home/evgeny/projects/ie` - Source of paradigm data (mockParadigmData.js)
- **Critic**: Consumer of engine definitions

## Code Conventions
- Use Pydantic v2 models for all data structures
- JSON files for definitions (easy to edit, version control)
- No database - all state from files
- No execution logic - just definitions
