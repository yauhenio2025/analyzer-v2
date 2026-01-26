# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

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
