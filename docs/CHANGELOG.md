# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Fixed
- **V2 Engines: Missing relationship_graph population instructions** - Added detailed graph-building extraction steps to v2 advanced engines
  - `absent_center.json` - Added STEP 18 with entity-specific node/edge/cluster instructions for Derridean/Foucauldian analysis
  - `motte_bailey_detector.json` - Expanded STEP 16 with detailed instructions for evasion pattern visualization
  - `path_dependency_analyzer.json` - Added STEP 16 with temporal_order support for sequence visualization
  - Each engine now has customized instructions for: creating typed nodes, building relationship edges with strength values, identifying thematic clusters
  - This fixes the visual diversity/depth regression compared to inferential_commitment_mapper_advanced which had explicit graph-building steps (STEP 19)

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
