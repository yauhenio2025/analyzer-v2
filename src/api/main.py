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

from src.api.routes import audiences, chains, engines, functions, llm, meta, operations, operationalizations, paradigms, styles, primitives, display, transformations, views, workflows
from src.audiences.registry import get_audience_registry
from src.chains.registry import get_chain_registry
from src.engines.registry import get_engine_registry
from src.functions.registry import get_function_registry
from src.operationalizations.registry import get_operationalization_registry
from src.operations.registry import StanceRegistry
from src.transformations.registry import get_transformation_registry
from src.views.registry import get_view_registry
from src.paradigms.registry import get_paradigm_registry
from src.styles.registry import get_style_registry
from src.primitives.registry import get_primitives_registry
from src.display.registry import DisplayRegistry
from src.workflows.registry import get_workflow_registry

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

    logger.info("Loading style definitions...")
    style_registry = get_style_registry()
    style_stats = style_registry.get_stats()
    logger.info(f"Loaded {style_stats['styles_loaded']} styles, {style_stats['engine_affinities']} engine affinities")

    logger.info("Loading analytical primitives...")
    primitives_registry = get_primitives_registry()
    prim_stats = primitives_registry.get_stats()
    logger.info(f"Loaded {prim_stats['primitives_loaded']} primitives, {prim_stats['engines_with_primitives']} engine associations")

    logger.info("Loading display configuration...")
    display_reg = DisplayRegistry()
    display_formats = display_reg.get_visual_formats()
    logger.info(f"Loaded {len(display_formats.categories)} format categories, {sum(len(c.formats) for c in display_formats.categories)} visual formats")

    logger.info("Loading workflow definitions...")
    workflow_registry = get_workflow_registry()
    logger.info(f"Loaded {workflow_registry.count()} workflows")

    logger.info("Loading audience definitions...")
    audience_registry = get_audience_registry()
    logger.info(f"Loaded {audience_registry.count()} audiences")

    logger.info("Loading view definitions...")
    view_registry = get_view_registry()
    logger.info(f"Loaded {view_registry.count()} view definitions")

    logger.info("Loading function definitions...")
    function_registry = get_function_registry()
    logger.info(f"Loaded {function_registry.count()} functions")

    logger.info("Loading analytical stances...")
    stance_registry = StanceRegistry()
    operations.init_registry(stance_registry)
    # Also make stances available to the capability composer and LLM generation
    from src.stages.capability_composer import init_stance_registry
    init_stance_registry(stance_registry)
    from src.api.routes.llm import init_stance_registry_for_llm
    init_stance_registry_for_llm(stance_registry)
    logger.info(f"Loaded {stance_registry.count} analytical stances")

    logger.info("Loading operationalizations...")
    op_registry = get_operationalization_registry()
    op_registry.load()
    logger.info(f"Loaded {op_registry.count()} engine operationalizations")

    logger.info("Loading transformation templates...")
    transformation_registry = get_transformation_registry()
    logger.info(f"Loaded {transformation_registry.count()} transformation templates")

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
app.include_router(styles.router, prefix="/v1")
app.include_router(primitives.router, prefix="/v1")
app.include_router(display.router, prefix="/v1")
app.include_router(workflows.router, prefix="/v1")
app.include_router(audiences.router, prefix="/v1")
app.include_router(functions.router, prefix="/v1")
app.include_router(views.router, prefix="/v1")
app.include_router(transformations.router, prefix="/v1")
app.include_router(operations.router)
app.include_router(operationalizations.router, prefix="/v1")
app.include_router(llm.router, prefix="/v1")
app.include_router(meta.router, prefix="/v1")


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
            "workflows": "/v1/workflows",
            "audiences": "/v1/audiences",
            "styles": "/v1/styles",
            "primitives": "/v1/primitives",
            "display": "/v1/display",
            "functions": "/v1/functions",
            "views": "/v1/views",
            "transformations": "/v1/transformations",
            "operations": "/v1/operations",
            "operationalizations": "/v1/operationalizations",
        },
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    engine_registry = get_engine_registry()
    paradigm_registry = get_paradigm_registry()
    chain_registry = get_chain_registry()
    workflow_registry = get_workflow_registry()
    audience_registry = get_audience_registry()
    function_registry = get_function_registry()
    style_registry = get_style_registry()
    style_stats = style_registry.get_stats()
    op_registry = get_operationalization_registry()
    view_registry = get_view_registry()
    transformation_registry = get_transformation_registry()

    return {
        "status": "healthy",
        "engines_loaded": engine_registry.count(),
        "paradigms_loaded": paradigm_registry.count(),
        "chains_loaded": chain_registry.count(),
        "workflows_loaded": workflow_registry.count(),
        "audiences_loaded": audience_registry.count(),
        "functions_loaded": function_registry.count(),
        "views_loaded": view_registry.count(),
        "transformations_loaded": transformation_registry.count(),
        "styles_loaded": style_stats["styles_loaded"],
        "style_affinities": style_stats["engine_affinities"],
        "operationalizations_loaded": op_registry.count(),
    }


@app.get("/v1")
async def api_v1_root():
    """API v1 root with available endpoints."""
    engine_registry = get_engine_registry()
    paradigm_registry = get_paradigm_registry()
    chain_registry = get_chain_registry()
    workflow_registry = get_workflow_registry()
    audience_registry = get_audience_registry()
    function_registry = get_function_registry()
    view_registry = get_view_registry()
    style_registry = get_style_registry()
    style_stats = style_registry.get_stats()

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
            "workflows": {
                "count": workflow_registry.count(),
                "endpoints": [
                    "GET /v1/workflows",
                    "GET /v1/workflows/{key}",
                    "GET /v1/workflows/{key}/passes",
                    "GET /v1/workflows/category/{category}",
                ],
            },
            "audiences": {
                "count": audience_registry.count(),
                "endpoints": [
                    "GET /v1/audiences",
                    "GET /v1/audiences/{key}",
                    "GET /v1/audiences/{key}/identity",
                    "GET /v1/audiences/{key}/engine-affinities",
                    "GET /v1/audiences/{key}/visual-style",
                    "GET /v1/audiences/{key}/textual-style",
                    "GET /v1/audiences/{key}/curation",
                    "GET /v1/audiences/{key}/vocabulary",
                    "GET /v1/audiences/{key}/guidance",
                ],
            },
            "functions": {
                "count": function_registry.count(),
                "endpoints": [
                    "GET /v1/functions",
                    "GET /v1/functions/categories",
                    "GET /v1/functions/projects",
                    "GET /v1/functions/{key}",
                    "GET /v1/functions/{key}/prompts",
                    "GET /v1/functions/{key}/implementations",
                    "GET /v1/functions/project/{project}",
                ],
            },
            "views": {
                "count": view_registry.count(),
                "endpoints": [
                    "GET /v1/views",
                    "GET /v1/views/{key}",
                    "GET /v1/views/compose/{app}/{page}",
                    "GET /v1/views/for-workflow/{workflow_key}",
                    "POST /v1/views",
                    "PUT /v1/views/{key}",
                    "DELETE /v1/views/{key}",
                ],
            },
            "styles": {
                "count": style_stats["styles_loaded"],
                "engine_affinities": style_stats["engine_affinities"],
                "format_affinities": style_stats["format_affinities"],
                "endpoints": [
                    "GET /v1/styles",
                    "GET /v1/styles/schools/{key}",
                    "GET /v1/styles/affinities/engine",
                    "GET /v1/styles/affinities/format",
                    "GET /v1/styles/affinities/audience",
                    "GET /v1/styles/engine-mappings",
                    "GET /v1/styles/for-engine/{engine_key}",
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
