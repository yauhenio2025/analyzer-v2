"""Renderer contract validation — validates data and config against renderer schemas.

Uses jsonschema Draft7Validator to check structured data against each
renderer's input_data_schema before caching (bridge) and before serving
(assembly). Default mode is WARN — never blocks the pipeline.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from jsonschema import Draft7Validator, ValidationError

from src.renderers.registry import get_renderer_registry

logger = logging.getLogger(__name__)

MAX_ERRORS = 10


class ValidationMode(str, Enum):
    """How to handle validation failures."""

    WARN = "warn"  # Log warning, don't block (default everywhere in pipeline)
    STRICT = "strict"  # Raise ValueError (only for /validate API with strict=true)
    SILENT = "silent"  # Skip validation entirely


@dataclass
class ValidationResult:
    """Result of validating data or config against a renderer schema."""

    renderer_key: str
    valid: bool
    errors: list[dict[str, Any]] = field(default_factory=list)
    schema_available: bool = True


def _summarize_oneof_error(error: ValidationError) -> str:
    """Summarize verbose oneOf/anyOf errors into a readable message."""
    if error.validator in ("oneOf", "anyOf"):
        # Instead of dumping all sub-schema failures, show the top-level message
        path = ".".join(str(p) for p in error.absolute_path) if error.absolute_path else "(root)"
        n_options = len(error.schema.get(error.validator, []))
        return f"At {path}: value did not match any of {n_options} allowed forms"
    return error.message


def _error_to_dict(error: ValidationError) -> dict[str, Any]:
    """Convert a ValidationError to a serializable dict."""
    return {
        "message": _summarize_oneof_error(error),
        "path": list(error.absolute_path),
        "schema_path": list(error.absolute_schema_path),
    }


def validate_renderer_data(
    renderer_key: str,
    data: Any,
    mode: ValidationMode = ValidationMode.WARN,
) -> ValidationResult:
    """Validate structured data against a renderer's input_data_schema.

    Args:
        renderer_key: The renderer to validate against.
        data: The structured data to validate.
        mode: WARN (log), STRICT (raise), or SILENT (skip).

    Returns:
        ValidationResult with valid flag and error details.
    """
    if mode == ValidationMode.SILENT:
        return ValidationResult(renderer_key=renderer_key, valid=True)

    registry = get_renderer_registry()
    renderer = registry.get(renderer_key)

    if renderer is None:
        return ValidationResult(
            renderer_key=renderer_key,
            valid=True,
            schema_available=False,
        )

    schema = renderer.input_data_schema
    if schema is None:
        return ValidationResult(
            renderer_key=renderer_key,
            valid=True,
            schema_available=False,
        )

    # Empty schema ({}) always validates — intentional for raw_json
    if not schema:
        return ValidationResult(renderer_key=renderer_key, valid=True)

    validator = Draft7Validator(schema)
    errors = []
    for i, error in enumerate(validator.iter_errors(data)):
        if i >= MAX_ERRORS:
            errors.append({
                "message": f"... and more errors (capped at {MAX_ERRORS})",
                "path": [],
                "schema_path": [],
            })
            break
        errors.append(_error_to_dict(error))

    valid = len(errors) == 0
    result = ValidationResult(
        renderer_key=renderer_key,
        valid=valid,
        errors=errors,
    )

    if not valid and mode == ValidationMode.STRICT:
        error_summary = "; ".join(e["message"] for e in errors[:3])
        raise ValueError(
            f"Renderer '{renderer_key}' data validation failed: {error_summary}"
        )

    return result


def validate_renderer_config(
    renderer_key: str,
    config: Any,
    mode: ValidationMode = ValidationMode.WARN,
) -> ValidationResult:
    """Validate renderer_config against a renderer's config_schema.

    Args:
        renderer_key: The renderer to validate against.
        config: The config dict to validate.
        mode: WARN (log), STRICT (raise), or SILENT (skip).

    Returns:
        ValidationResult with valid flag and error details.
    """
    if mode == ValidationMode.SILENT:
        return ValidationResult(renderer_key=renderer_key, valid=True)

    registry = get_renderer_registry()
    renderer = registry.get(renderer_key)

    if renderer is None:
        return ValidationResult(
            renderer_key=renderer_key,
            valid=True,
            schema_available=False,
        )

    schema = renderer.config_schema
    if not schema:
        return ValidationResult(
            renderer_key=renderer_key,
            valid=True,
            schema_available=False,
        )

    validator = Draft7Validator(schema)
    errors = []
    for i, error in enumerate(validator.iter_errors(config)):
        if i >= MAX_ERRORS:
            errors.append({
                "message": f"... and more errors (capped at {MAX_ERRORS})",
                "path": [],
                "schema_path": [],
            })
            break
        errors.append(_error_to_dict(error))

    valid = len(errors) == 0
    result = ValidationResult(
        renderer_key=renderer_key,
        valid=valid,
        errors=errors,
    )

    if not valid and mode == ValidationMode.STRICT:
        error_summary = "; ".join(e["message"] for e in errors[:3])
        raise ValueError(
            f"Renderer '{renderer_key}' config validation failed: {error_summary}"
        )

    return result


def validate_all_schemas() -> dict[str, Any]:
    """Health check: validate that all renderer schemas are themselves valid JSON Schema.

    Returns a dict with per-renderer status, usable as a CI check or /health endpoint.
    """
    registry = get_renderer_registry()
    results: dict[str, Any] = {}

    for renderer in registry.list_all():
        key = renderer.renderer_key
        entry: dict[str, Any] = {
            "has_input_schema": renderer.input_data_schema is not None,
            "has_config_schema": bool(renderer.config_schema),
            "input_schema_valid": True,
            "config_schema_valid": True,
        }

        # Validate input_data_schema is valid JSON Schema
        if renderer.input_data_schema is not None:
            try:
                Draft7Validator.check_schema(renderer.input_data_schema)
            except Exception as e:
                entry["input_schema_valid"] = False
                entry["input_schema_error"] = str(e)

        # Validate config_schema is valid JSON Schema
        if renderer.config_schema:
            try:
                Draft7Validator.check_schema(renderer.config_schema)
            except Exception as e:
                entry["config_schema_valid"] = False
                entry["config_schema_error"] = str(e)

        results[key] = entry

    return results
