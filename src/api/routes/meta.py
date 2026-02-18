"""Meta/system API routes.

Provides definition versioning and cache management endpoints for consumers.
"""

import hashlib
import logging
import time
from typing import Optional

from fastapi import APIRouter

from src.chains.registry import get_chain_registry
from src.engines.registry import get_engine_registry
from src.persistence.github_client import get_github_persistence
from src.views.registry import get_view_registry
from src.workflows.registry import get_workflow_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meta", tags=["meta"])

# Track when definitions were last modified in-memory
_last_modified_at: float = time.time()


def mark_definitions_modified():
    """Call this whenever definitions are modified to update the version."""
    global _last_modified_at
    _last_modified_at = time.time()


def _compute_definitions_hash() -> str:
    """Compute a hash over all definition counts and keys for cache validation.

    This is a lightweight fingerprint — not a full content hash, but enough
    to detect when definitions have changed (engines added/removed, chains modified).
    """
    engine_registry = get_engine_registry()
    chain_registry = get_chain_registry()
    workflow_registry = get_workflow_registry()
    view_registry = get_view_registry()

    # Build a fingerprint from registry contents
    fingerprint_parts = [
        f"engines:{engine_registry.count()}",
        f"chains:{chain_registry.count()}",
        f"workflows:{workflow_registry.count()}",
        f"views:{view_registry.count()}",
        f"chain_keys:{','.join(sorted(chain_registry.list_keys()))}",
        f"workflow_keys:{','.join(sorted(workflow_registry.get_workflow_keys()))}",
        f"view_keys:{','.join(sorted(view_registry.list_keys()))}",
        f"modified:{_last_modified_at}",
    ]

    # Add chain engine_keys to detect composition changes
    for chain in chain_registry.list_all():
        fingerprint_parts.append(
            f"chain:{chain.chain_key}:{','.join(chain.engine_keys)}"
        )

    fingerprint = "|".join(fingerprint_parts)
    return hashlib.sha256(fingerprint.encode()).hexdigest()[:16]


@router.get("/definitions-version")
async def get_definitions_version() -> dict:
    """Get version info for all definitions.

    Consumers can poll this endpoint to detect when definitions have changed
    and invalidate their caches accordingly.

    The version_hash changes whenever:
    - Engines are added/removed from chains
    - Chains or workflows are created/deleted
    - Any definition is modified via the API

    Returns:
        Dictionary with version hash, counts, and persistence status
    """
    engine_registry = get_engine_registry()
    chain_registry = get_chain_registry()
    workflow_registry = get_workflow_registry()
    view_registry = get_view_registry()
    github = get_github_persistence()

    return {
        "version_hash": _compute_definitions_hash(),
        "last_modified": _last_modified_at,
        "engine_count": engine_registry.count(),
        "chain_count": chain_registry.count(),
        "workflow_count": workflow_registry.count(),
        "view_count": view_registry.count(),
        "persistence": {
            "github_enabled": github.enabled,
            "repo": github.repo if github.enabled else None,
            "branch": github.branch if github.enabled else None,
        },
    }
