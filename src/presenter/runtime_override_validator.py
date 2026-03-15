"""Bound runtime and variant override values before effective composition is resolved."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from src.consumers.registry import get_consumer_registry
from src.renderers.registry import get_renderer_registry
from src.sub_renderers.registry import get_sub_renderer_registry


NESTED_SECTIONS_RENDERER = "nested_sections"


@dataclass
class DroppedOverride:
    field: str
    value: Any
    reason: str


@dataclass
class RuntimeOverrideValidationResult:
    renderer_type_override: Optional[str]
    renderer_config_overrides: dict[str, Any] = field(default_factory=dict)
    dropped_overrides: list[DroppedOverride] = field(default_factory=list)


def validate_runtime_overrides(
    *,
    view_def: Any,
    rec: Optional[dict[str, Any]],
    consumer_key: str,
) -> RuntimeOverrideValidationResult:
    """Validate recommendation/runtime overrides against bounded registry inputs."""

    rec = rec or {}
    return _validate_override_payload(
        view_def=view_def,
        renderer_type_override=rec.get("renderer_type_override"),
        renderer_config_overrides=rec.get("renderer_config_overrides") or {},
        consumer_key=consumer_key,
        field_prefix="renderer_config_overrides",
    )


def validate_variant_patch(
    *,
    view_def: Any,
    renderer_type_override: Optional[str],
    renderer_config_overrides: Optional[dict[str, Any]],
    consumer_key: str,
) -> RuntimeOverrideValidationResult:
    """Validate selected variant patches against the same bounded contract rules."""

    return _validate_override_payload(
        view_def=view_def,
        renderer_type_override=renderer_type_override,
        renderer_config_overrides=renderer_config_overrides or {},
        consumer_key=consumer_key,
        field_prefix="variant_renderer_config",
    )


def _validate_override_payload(
    *,
    view_def: Any,
    renderer_type_override: Optional[str],
    renderer_config_overrides: dict[str, Any],
    consumer_key: str,
    field_prefix: str,
) -> RuntimeOverrideValidationResult:
    renderer_registry = get_renderer_registry()
    consumer = get_consumer_registry().get(consumer_key)

    dropped: list[DroppedOverride] = []
    cleaned_renderer_override: Optional[str] = None

    if renderer_type_override:
        renderer_def = renderer_registry.get(renderer_type_override)
        if renderer_def is None:
            dropped.append(
                DroppedOverride(
                    field="renderer_type_override",
                    value=renderer_type_override,
                    reason="unknown_renderer_type",
                )
            )
        elif consumer and renderer_type_override not in (consumer.supported_renderers or []):
            dropped.append(
                DroppedOverride(
                    field="renderer_type_override",
                    value=renderer_type_override,
                    reason=f"renderer_not_supported_by_consumer:{consumer_key}",
                )
            )
        else:
            cleaned_renderer_override = renderer_type_override

    target_renderer = cleaned_renderer_override or getattr(view_def, "renderer_type", "")
    cleaned_config = _validate_renderer_config_patch(
        renderer_type=target_renderer,
        config_patch=renderer_config_overrides,
        consumer_key=consumer_key,
        field_prefix=field_prefix,
        dropped=dropped,
    )

    return RuntimeOverrideValidationResult(
        renderer_type_override=cleaned_renderer_override,
        renderer_config_overrides=cleaned_config,
        dropped_overrides=dropped,
    )


def _validate_renderer_config_patch(
    *,
    renderer_type: str,
    config_patch: Any,
    consumer_key: str,
    field_prefix: str,
    dropped: list[DroppedOverride],
) -> dict[str, Any]:
    if not isinstance(config_patch, dict):
        if config_patch:
            dropped.append(
                DroppedOverride(
                    field=field_prefix,
                    value=config_patch,
                    reason=f"override_config_not_object:{renderer_type}",
                )
            )
        return {}

    renderer_def = get_renderer_registry().get(renderer_type)
    allowed_keys = _schema_property_keys(getattr(renderer_def, "config_schema", None))

    cleaned: dict[str, Any] = {}
    for key, value in config_patch.items():
        field_path = f"{field_prefix}.{key}"
        if key not in allowed_keys:
            dropped.append(
                DroppedOverride(
                    field=field_path,
                    value=value,
                    reason=f"override_key_not_allowed_for_renderer:{renderer_type}",
                )
            )
            continue

        if key == "section_renderers":
            cleaned[key] = _validate_section_renderer_map(
                section_renderers=value,
                parent_renderer_type=renderer_type,
                consumer_key=consumer_key,
                field_prefix=field_path,
                dropped=dropped,
            )
            continue

        cleaned[key] = value

    return cleaned


def _validate_section_renderer_map(
    *,
    section_renderers: Any,
    parent_renderer_type: str,
    consumer_key: str,
    field_prefix: str,
    dropped: list[DroppedOverride],
) -> dict[str, Any]:
    if not isinstance(section_renderers, dict):
        dropped.append(
            DroppedOverride(
                field=field_prefix,
                value=section_renderers,
                reason=f"section_renderers_not_object:{parent_renderer_type}",
            )
        )
        return {}

    cleaned: dict[str, Any] = {}
    for section_key, spec in section_renderers.items():
        spec_prefix = f"{field_prefix}.{section_key}"
        if not isinstance(spec, dict):
            dropped.append(
                DroppedOverride(
                    field=spec_prefix,
                    value=spec,
                    reason="section_renderer_spec_not_object",
                )
            )
            continue

        renderer_type = spec.get("renderer_type")
        if not isinstance(renderer_type, str) or not renderer_type:
            dropped.append(
                DroppedOverride(
                    field=f"{spec_prefix}.renderer_type",
                    value=renderer_type,
                    reason="missing_section_renderer_type",
                )
            )
            continue

        if renderer_type == NESTED_SECTIONS_RENDERER:
            if not _consumer_supports_sub_renderer(
                consumer_key=consumer_key,
                renderer_type=renderer_type,
            ):
                dropped.append(
                    DroppedOverride(
                        field=f"{spec_prefix}.renderer_type",
                        value=renderer_type,
                        reason=f"sub_renderer_not_supported_by_consumer:{consumer_key}",
                    )
                )
                continue
            cleaned_spec = _validate_nested_sections_spec(
                spec=spec,
                consumer_key=consumer_key,
                field_prefix=spec_prefix,
                dropped=dropped,
            )
            if cleaned_spec:
                cleaned[section_key] = cleaned_spec
            continue

        if _is_valid_sub_renderer(renderer_type, parent_renderer_type):
            if not _consumer_supports_sub_renderer(
                consumer_key=consumer_key,
                renderer_type=renderer_type,
            ):
                dropped.append(
                    DroppedOverride(
                        field=f"{spec_prefix}.renderer_type",
                        value=renderer_type,
                        reason=f"sub_renderer_not_supported_by_consumer:{consumer_key}",
                    )
                )
                continue
            config = spec.get("config") or {}
            cleaned_config = _validate_sub_renderer_config_patch(
                renderer_type=renderer_type,
                config_patch=config,
                field_prefix=f"{spec_prefix}.config",
                dropped=dropped,
            )
            cleaned_spec: dict[str, Any] = {"renderer_type": renderer_type}
            if cleaned_config:
                cleaned_spec["config"] = cleaned_config
            cleaned[section_key] = cleaned_spec
            continue

        renderer_def = get_renderer_registry().get(renderer_type)
        if renderer_def is not None:
            if not _consumer_supports_renderer(
                consumer_key=consumer_key,
                renderer_type=renderer_type,
            ):
                dropped.append(
                    DroppedOverride(
                        field=f"{spec_prefix}.renderer_type",
                        value=renderer_type,
                        reason=f"renderer_not_supported_by_consumer:{consumer_key}",
                    )
                )
                continue
            config = spec.get("config") or {}
            cleaned_config = _validate_renderer_config_patch(
                renderer_type=renderer_type,
                config_patch=config,
                consumer_key=consumer_key,
                field_prefix=f"{spec_prefix}.config",
                dropped=dropped,
            )
            cleaned_spec = {"renderer_type": renderer_type}
            if cleaned_config:
                cleaned_spec["config"] = cleaned_config
            cleaned[section_key] = cleaned_spec
            continue

        dropped.append(
            DroppedOverride(
                field=f"{spec_prefix}.renderer_type",
                value=renderer_type,
                reason=f"unknown_section_renderer_type:{parent_renderer_type}",
            )
        )

    return cleaned


def _validate_nested_sections_spec(
    *,
    spec: dict[str, Any],
    consumer_key: str,
    field_prefix: str,
    dropped: list[DroppedOverride],
) -> dict[str, Any]:
    cleaned_spec: dict[str, Any] = {"renderer_type": NESTED_SECTIONS_RENDERER}

    config = spec.get("config")
    if config is not None and not isinstance(config, dict):
        dropped.append(
            DroppedOverride(
                field=f"{field_prefix}.config",
                value=config,
                reason="nested_sections_config_not_object",
            )
        )
        config = {}

    config = dict(config or {})
    sub_renderers = spec.get("sub_renderers")
    if sub_renderers is None and isinstance(config.get("sub_renderers"), dict):
        sub_renderers = config.pop("sub_renderers")
    cleaned_sub_renderers = _validate_nested_sub_renderer_map(
        sub_renderers=sub_renderers or {},
        consumer_key=consumer_key,
        field_prefix=f"{field_prefix}.sub_renderers",
        dropped=dropped,
    )
    if cleaned_sub_renderers:
        cleaned_spec["sub_renderers"] = cleaned_sub_renderers
    if config:
        cleaned_spec["config"] = config
    return cleaned_spec


def _validate_nested_sub_renderer_map(
    *,
    sub_renderers: Any,
    consumer_key: str,
    field_prefix: str,
    dropped: list[DroppedOverride],
) -> dict[str, Any]:
    if not isinstance(sub_renderers, dict):
        dropped.append(
            DroppedOverride(
                field=field_prefix,
                value=sub_renderers,
                reason="nested_sub_renderers_not_object",
            )
        )
        return {}

    cleaned: dict[str, Any] = {}
    for section_key, spec in sub_renderers.items():
        spec_prefix = f"{field_prefix}.{section_key}"
        if not isinstance(spec, dict):
            dropped.append(
                DroppedOverride(
                    field=spec_prefix,
                    value=spec,
                    reason="nested_sub_renderer_spec_not_object",
                )
            )
            continue

        renderer_type = spec.get("renderer_type")
        if not isinstance(renderer_type, str) or not renderer_type:
            dropped.append(
                DroppedOverride(
                    field=f"{spec_prefix}.renderer_type",
                    value=renderer_type,
                    reason="missing_nested_sub_renderer_type",
                )
            )
            continue

        if not _is_valid_sub_renderer(renderer_type, NESTED_SECTIONS_RENDERER):
            dropped.append(
                DroppedOverride(
                    field=f"{spec_prefix}.renderer_type",
                    value=renderer_type,
                    reason=f"unknown_nested_sub_renderer_type:{renderer_type}",
                )
            )
            continue

        if not _consumer_supports_sub_renderer(
            consumer_key=consumer_key,
            renderer_type=renderer_type,
        ):
            dropped.append(
                DroppedOverride(
                    field=f"{spec_prefix}.renderer_type",
                    value=renderer_type,
                    reason=f"sub_renderer_not_supported_by_consumer:{consumer_key}",
                )
            )
            continue

        config = spec.get("config") or {}
        cleaned_config = _validate_sub_renderer_config_patch(
            renderer_type=renderer_type,
            config_patch=config,
            field_prefix=f"{spec_prefix}.config",
            dropped=dropped,
        )
        cleaned_spec: dict[str, Any] = {"renderer_type": renderer_type}
        if cleaned_config:
            cleaned_spec["config"] = cleaned_config
        cleaned[section_key] = cleaned_spec

    return cleaned


def _validate_sub_renderer_config_patch(
    *,
    renderer_type: str,
    config_patch: Any,
    field_prefix: str,
    dropped: list[DroppedOverride],
) -> dict[str, Any]:
    if not isinstance(config_patch, dict):
        if config_patch:
            dropped.append(
                DroppedOverride(
                    field=field_prefix,
                    value=config_patch,
                    reason=f"sub_renderer_config_not_object:{renderer_type}",
                )
            )
        return {}

    sub_renderer = get_sub_renderers().get(renderer_type)
    allowed_keys = _schema_property_keys(getattr(sub_renderer, "config_schema", None))

    cleaned: dict[str, Any] = {}
    for key, value in config_patch.items():
        if key not in allowed_keys:
            dropped.append(
                DroppedOverride(
                    field=f"{field_prefix}.{key}",
                    value=value,
                    reason=f"override_key_not_allowed_for_sub_renderer:{renderer_type}",
                )
            )
            continue
        cleaned[key] = value
    return cleaned


def _schema_property_keys(schema: Any) -> set[str]:
    if not isinstance(schema, dict):
        return set()
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return set()
    return set(properties.keys())


def _is_valid_sub_renderer(renderer_type: str, parent_renderer_type: str) -> bool:
    definition = get_sub_renderers().get(renderer_type)
    if definition is None:
        return False
    return parent_renderer_type in (definition.parent_renderer_types or [])


def _consumer_supports_renderer(*, consumer_key: str, renderer_type: str) -> bool:
    consumer = get_consumer_registry().get(consumer_key)
    if consumer is None:
        return True
    return renderer_type in (consumer.supported_renderers or [])


def _consumer_supports_sub_renderer(*, consumer_key: str, renderer_type: str) -> bool:
    consumer = get_consumer_registry().get(consumer_key)
    if consumer is None:
        return True
    return renderer_type in (consumer.supported_sub_renderers or [])


def get_sub_renderers():
    return get_sub_renderer_registry()
