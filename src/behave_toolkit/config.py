from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml

from .scopes import Scope


@dataclass(frozen=True, slots=True)
class ObjectSpec:
    """Configuration for one named object in the toolkit container."""

    name: str
    factory: str
    scope: Scope = Scope.SCENARIO
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)
    cleanup: str | None = None
    inject_as: str | None = None

    @property
    def context_name(self) -> str:
        return self.inject_as or self.name


@dataclass(frozen=True, slots=True)
class ToolkitConfig:
    """Normalized project configuration."""

    version: int
    variables: dict[str, Any] = field(default_factory=dict)
    objects: dict[str, ObjectSpec] = field(default_factory=dict)

    def require(self, name: str) -> ObjectSpec:
        try:
            return self.objects[name]
        except KeyError as exc:
            known = ", ".join(sorted(self.objects)) or "<none>"
            raise KeyError(f"Unknown object '{name}'. Known objects: {known}") from exc

    def require_variable(self, name: str) -> Any:
        try:
            return self.variables[name]
        except KeyError as exc:
            known = ", ".join(sorted(self.variables)) or "<none>"
            raise KeyError(f"Unknown variable '{name}'. Known variables: {known}") from exc


def load_yaml_text(text: str) -> ToolkitConfig:
    """Load toolkit configuration from a YAML string."""

    raw = yaml.safe_load(text) or {}
    if not isinstance(raw, Mapping):
        raise TypeError("The YAML root must be a mapping.")
    return load_config(raw)


def load_yaml_file(path: str | Path) -> ToolkitConfig:
    """Load toolkit configuration from a YAML file."""

    config_path = Path(path)
    raw_text = config_path.read_text(encoding="utf-8")
    return load_yaml_text(raw_text)


def load_config(raw: Mapping[str, Any]) -> ToolkitConfig:
    """Normalize validated config data into dataclasses."""

    version = raw.get("version", 1)
    if not isinstance(version, int):
        raise TypeError("The config 'version' must be an integer.")

    raw_variables = raw.get("variables", {})
    if not isinstance(raw_variables, Mapping):
        raise TypeError("The config 'variables' section must be a mapping.")

    raw_objects = raw.get("objects", {})
    if not isinstance(raw_objects, Mapping):
        raise TypeError("The config 'objects' section must be a mapping.")

    objects: dict[str, ObjectSpec] = {}
    for name, definition in raw_objects.items():
        if not isinstance(definition, Mapping):
            raise TypeError(f"Object '{name}' must be defined as a mapping.")

        factory = definition.get("factory")
        if not isinstance(factory, str) or not factory.strip():
            raise ValueError(f"Object '{name}' must define a non-empty 'factory' string.")

        raw_args = definition.get("args", [])
        raw_kwargs = definition.get("kwargs", {})
        if not isinstance(raw_args, list):
            raise TypeError(f"Object '{name}' field 'args' must be a list.")
        if not isinstance(raw_kwargs, Mapping):
            raise TypeError(f"Object '{name}' field 'kwargs' must be a mapping.")

        cleanup = definition.get("cleanup")
        if cleanup is not None and not isinstance(cleanup, str):
            raise TypeError(f"Object '{name}' field 'cleanup' must be a string if provided.")

        inject_as = definition.get("inject_as")
        if inject_as is not None and not isinstance(inject_as, str):
            raise TypeError(f"Object '{name}' field 'inject_as' must be a string if provided.")

        objects[str(name)] = ObjectSpec(
            name=str(name),
            factory=factory.strip(),
            scope=Scope.parse(definition.get("scope", Scope.SCENARIO.value)),
            args=tuple(raw_args),
            kwargs=dict(raw_kwargs),
            cleanup=cleanup,
            inject_as=inject_as,
        )

    return ToolkitConfig(version=version, variables=dict(raw_variables), objects=objects)
