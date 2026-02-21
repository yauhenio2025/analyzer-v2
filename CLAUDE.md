# Analyzer v2 - Pure Definitions Service

> Lightweight service serving analytical definitions without execution logic

## Overview

Analyzer v2 extracts pure analytical definitions from the current Analyzer service:
- **Engine definitions**: Prompts, schemas, and metadata for 160+ analysis engines
- **Paradigm definitions**: 4-layer ontology structures (IE schema)
- **Engine chains**: Multi-engine composition specifications
- **Audience definitions**: Rich multi-section profiles for 5 audience types

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
│   ├── audiences/         # Audience definitions (first-class entity)
│   │   ├── schemas.py     # AudienceDefinition model (8 sub-models)
│   │   ├── registry.py    # AudienceRegistry (CRUD + guidance/vocab/weight)
│   │   └── definitions/   # 5 JSON files (analyst, executive, researcher, activist, social_movements)
│   │
│   ├── views/             # View definitions (rendering layer)
│   │   ├── schemas.py     # ViewDefinition, DataSourceRef, TransformationSpec
│   │   ├── registry.py    # ViewRegistry (CRUD + compose_tree)
│   │   └── definitions/   # 10 JSON files (genealogy views)
│   │
│   ├── renderers/         # Renderer definitions (first-class catalog)
│   │   ├── schemas.py     # RendererDefinition, RendererSummary, SectionRendererHint
│   │   ├── registry.py    # RendererRegistry (CRUD + for_stance/for_data_shape/for_app)
│   │   └── definitions/   # 8 JSON files (accordion, card_grid, prose, table, etc.)
│   │
│   ├── orchestrator/      # LLM-powered plan generation (Milestone 1)
│   │   ├── schemas.py     # WorkflowExecutionPlan, PhaseExecutionSpec
│   │   ├── catalog.py     # Capability catalog assembly
│   │   ├── planner.py     # Claude Opus plan generation
│   │   └── plans/         # File-based plan storage (JSON)
│   │
│   ├── executor/          # Plan-driven workflow execution (Milestone 2)
│   │   ├── schemas.py     # ExecutorJob, PhaseResult, EngineCallResult
│   │   ├── db.py          # Dual-backend DB (Postgres + SQLite)
│   │   ├── engine_runner.py  # Atomic LLM calls with streaming/retry
│   │   ├── context_broker.py # Cross-phase context assembly
│   │   ├── chain_runner.py   # Sequential chain execution
│   │   ├── phase_runner.py   # Phase resolution + per-work iteration
│   │   ├── workflow_runner.py # DAG execution with parallel phases
│   │   ├── job_manager.py    # Job lifecycle + cancellation
│   │   ├── output_store.py   # Prose output persistence
│   │   └── document_store.py # Document text storage
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

GET  /v1/audiences                   # List all audiences
GET  /v1/audiences/{key}             # Full audience definition
GET  /v1/audiences/{key}/identity    # Identity/profile section
GET  /v1/audiences/{key}/engine-affinities
GET  /v1/audiences/{key}/visual-style
GET  /v1/audiences/{key}/textual-style
GET  /v1/audiences/{key}/curation
GET  /v1/audiences/{key}/vocabulary
GET  /v1/audiences/{key}/guidance    # Composed guidance block
GET  /v1/audiences/{key}/translate/{term}
GET  /v1/audiences/{key}/engine-weight/{engine_key}
PUT  /v1/audiences/{key}             # Update audience
POST /v1/audiences                   # Create audience
DELETE /v1/audiences/{key}           # Delete audience

GET  /v1/views                         # List all views (with ?app=X&page=Y)
GET  /v1/views/{key}                   # Single view definition
GET  /v1/views/compose/{app}/{page}    # Tree of views for a page (primary consumer endpoint)
GET  /v1/views/for-workflow/{wf_key}   # Views referencing a workflow
POST /v1/views                         # Create view
PUT  /v1/views/{key}                   # Update view
DELETE /v1/views/{key}                 # Delete view

GET  /v1/renderers                       # List all renderers (summary)
GET  /v1/renderers/{key}                 # Full renderer definition
GET  /v1/renderers/for-stance/{stance}   # Renderers by stance affinity
GET  /v1/renderers/for-app/{app}         # Renderers supported by app
POST /v1/renderers                       # Create renderer
PUT  /v1/renderers/{key}                 # Update renderer
DELETE /v1/renderers/{key}               # Delete renderer

GET  /v1/operations/stances            # List stances (with ?type=analytical|presentation)
GET  /v1/operations/stances/{key}      # Get stance
GET  /v1/operations/stances/{key}/renderers  # Preferred renderers for a stance

GET  /v1/llm/status                  # Check LLM availability
POST /v1/llm/profile-generate        # Generate profile with AI
POST /v1/llm/profile-suggestions     # Get AI suggestions for profile
POST /v1/chains/recommend            # LLM recommends chain

# Orchestrator
GET  /v1/orchestrator/capability-catalog  # Full capability catalog
POST /v1/orchestrator/plan                # Generate new plan (Claude Opus)
GET  /v1/orchestrator/plans               # List plans
GET  /v1/orchestrator/plans/{plan_id}     # Get plan
PUT  /v1/orchestrator/plans/{plan_id}     # Update plan
POST /v1/orchestrator/plans/{plan_id}/refine  # LLM-assisted refinement

# Executor
POST /v1/executor/jobs                    # Start execution from plan_id
GET  /v1/executor/jobs                    # List jobs
GET  /v1/executor/jobs/{job_id}           # Poll status + progress
POST /v1/executor/jobs/{job_id}/cancel    # Cancel running job
GET  /v1/executor/jobs/{job_id}/results   # Phase output summaries
GET  /v1/executor/jobs/{job_id}/phases/{n}  # Full phase prose
DELETE /v1/executor/jobs/{job_id}         # Delete completed job
POST /v1/executor/documents               # Upload document text
GET  /v1/executor/documents               # List documents
GET  /v1/executor/documents/{doc_id}      # Retrieve document
DELETE /v1/executor/documents/{doc_id}    # Delete document
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
