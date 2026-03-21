from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml

from .errors import ConfigError
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

    return load_config(_load_yaml_mapping(text, source="from text"))


def load_yaml_file(path: str | Path) -> ToolkitConfig:
    """Load toolkit configuration from a YAML file."""

    config_path = Path(path).expanduser().resolve()
    try:
        raw_text = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(
            f"Could not read behave-toolkit config '{config_path}': {exc}"
        ) from exc
    try:
        return load_config(_load_yaml_mapping(raw_text, source=f"at '{config_path}'"))
    except ConfigError as exc:
        message = str(exc)
        if str(config_path) in message:
            raise
        raise ConfigError(
            f"Invalid behave-toolkit config '{config_path}': {message}"
        ) from exc


def _load_yaml_mapping(text: str, *, source: str) -> Mapping[str, Any]:
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(
            f"Could not parse behave-toolkit config {source}: {exc}"
        ) from exc

    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise ConfigError(
            f"The YAML root in behave-toolkit config {source} must be a mapping."
        )
    return raw


def load_config(raw: Mapping[str, Any]) -> ToolkitConfig:
    """Normalize validated config data into dataclasses."""

    version = raw.get("version", 1)
    if not isinstance(version, int):
        raise ConfigError("The config 'version' must be an integer.")

    raw_variables = raw.get("variables", {})
    if not isinstance(raw_variables, Mapping):
        raise ConfigError("The config 'variables' section must be a mapping.")

    raw_objects = raw.get("objects", {})
    if not isinstance(raw_objects, Mapping):
        raise ConfigError("The config 'objects' section must be a mapping.")

    objects: dict[str, ObjectSpec] = {}
    for name, definition in raw_objects.items():
        if not isinstance(definition, Mapping):
            raise ConfigError(f"Object '{name}' must be defined as a mapping.")

        factory = definition.get("factory")
        if not isinstance(factory, str) or not factory.strip():
            raise ConfigError(
                f"Object '{name}' must define a non-empty 'factory' string."
            )

        raw_args = definition.get("args", [])
        raw_kwargs = definition.get("kwargs", {})
        if not isinstance(raw_args, list):
            raise ConfigError(f"Object '{name}' field 'args' must be a list.")
        if not isinstance(raw_kwargs, Mapping):
            raise ConfigError(f"Object '{name}' field 'kwargs' must be a mapping.")

        cleanup = definition.get("cleanup")
        if cleanup is not None and not isinstance(cleanup, str):
            raise ConfigError(
                f"Object '{name}' field 'cleanup' must be a string if provided."
            )

        inject_as = definition.get("inject_as")
        if inject_as is not None and not isinstance(inject_as, str):
            raise ConfigError(
                f"Object '{name}' field 'inject_as' must be a string if provided."
            )

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
