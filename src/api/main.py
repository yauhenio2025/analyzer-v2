"""Analyzer v2 API - Pure Definitions Service.

This API serves analytical definitions without execution logic:
- Engine definitions (prompts, schemas, metadata)
- Paradigm definitions (4-layer ontology)
- Engine chains (multi-engine compositions)
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import chains, engines, llm, paradigms
from src.chains.registry import get_chain_registry
from src.engines.registry import get_engine_registry
from src.paradigms.registry import get_paradigm_registry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup: Pre-load all registries
    logger.info("Loading engine definitions...")
    engine_registry = get_engine_registry()
    logger.info(f"Loaded {engine_registry.count()} engines")

    logger.info("Loading paradigm definitions...")
    paradigm_registry = get_paradigm_registry()
    logger.info(f"Loaded {paradigm_registry.count()} paradigms")

    logger.info("Loading chain definitions...")
    chain_registry = get_chain_registry()
    logger.info(f"Loaded {chain_registry.count()} chains")

    logger.info("Analyzer v2 API ready")
    yield
    # Shutdown
    logger.info("Shutting down Analyzer v2 API")


# Create FastAPI app
app = FastAPI(
    title="Analyzer v2 API",
    description="""
## Pure Definitions Service

This API serves analytical definitions without execution logic.
Consumers (Critic, Visualizer, IE) call this API to fetch:

- **Engine definitions**: Prompts, schemas, and metadata for 160+ analysis engines
- **Paradigm definitions**: 4-layer ontology structures for philosophical frameworks
- **Engine chains**: Multi-engine composition specifications

### Key Endpoints

- `GET /v1/engines` - List all engines
- `GET /v1/engines/{key}` - Get full engine definition
- `GET /v1/engines/{key}/extraction-prompt` - Get extraction prompt
- `GET /v1/paradigms` - List all paradigms
- `GET /v1/paradigms/{key}/primer` - Get LLM-ready primer text
- `GET /v1/chains` - List all chains
""",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers with /v1 prefix
app.include_router(engines.router, prefix="/v1")
app.include_router(paradigms.router, prefix="/v1")
app.include_router(chains.router, prefix="/v1")
app.include_router(llm.router, prefix="/v1")


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "service": "Analyzer v2 API",
        "version": "0.1.0",
        "description": "Pure analytical definitions service",
        "docs": "/docs",
        "endpoints": {
            "engines": "/v1/engines",
            "paradigms": "/v1/paradigms",
            "chains": "/v1/chains",
        },
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    engine_registry = get_engine_registry()
    paradigm_registry = get_paradigm_registry()
    chain_registry = get_chain_registry()

    return {
        "status": "healthy",
        "engines_loaded": engine_registry.count(),
        "paradigms_loaded": paradigm_registry.count(),
        "chains_loaded": chain_registry.count(),
    }


@app.get("/v1")
async def api_v1_root():
    """API v1 root with available endpoints."""
    engine_registry = get_engine_registry()
    paradigm_registry = get_paradigm_registry()
    chain_registry = get_chain_registry()

    return {
        "version": "v1",
        "resources": {
            "engines": {
                "count": engine_registry.count(),
                "endpoints": [
                    "GET /v1/engines",
                    "GET /v1/engines/{key}",
                    "GET /v1/engines/{key}/extraction-prompt",
                    "GET /v1/engines/{key}/curation-prompt",
                    "GET /v1/engines/{key}/schema",
                    "GET /v1/engines/category/{category}",
                ],
            },
            "paradigms": {
                "count": paradigm_registry.count(),
                "endpoints": [
                    "GET /v1/paradigms",
                    "GET /v1/paradigms/{key}",
                    "GET /v1/paradigms/{key}/primer",
                    "GET /v1/paradigms/{key}/engines",
                    "GET /v1/paradigms/{key}/critique-patterns",
                ],
            },
            "chains": {
                "count": chain_registry.count(),
                "endpoints": [
                    "GET /v1/chains",
                    "GET /v1/chains/{key}",
                    "GET /v1/chains/category/{category}",
                    "POST /v1/chains/recommend",
                ],
            },
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )
