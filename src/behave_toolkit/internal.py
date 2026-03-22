from __future__ import annotations

import inspect
import logging
from typing import Any

from behave.matchers import get_step_matcher_factory


def snapshot_type_registries() -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Capture custom type registries for all matcher classes."""

    factory = get_step_matcher_factory()
    registries: list[tuple[dict[str, Any], dict[str, Any]]] = []
    seen_registry_ids: set[int] = set()
    for matcher_class in factory.step_matcher_class_mapping.values():
        type_registry = getattr(matcher_class, "TYPE_REGISTRY", None)
        if not isinstance(type_registry, dict):
            continue

        registry_id = id(type_registry)
        if registry_id in seen_registry_ids:
            continue
        seen_registry_ids.add(registry_id)
        registries.append((type_registry, dict(type_registry)))
    return registries


def callable_source_info(callable_obj: Any) -> tuple[str | None, int | None]:
    """Return the source file and line for a callable or class when available."""

    try:
        source_file = inspect.getsourcefile(callable_obj) or inspect.getfile(callable_obj)
    except (OSError, TypeError):
        return None, None

    try:
        _, line_number = inspect.getsourcelines(callable_obj)
    except (OSError, TypeError):
        line_number = None
    return source_file, line_number


def normalize_logging_level(level: int | str) -> int:
    """Normalize a logging level expressed as an int or level name."""

    if isinstance(level, int):
        return level

    candidate = getattr(logging, level.upper(), None)
    if isinstance(candidate, int):
        return candidate

    raise ValueError(f"Unsupported logging level: {level!r}")
