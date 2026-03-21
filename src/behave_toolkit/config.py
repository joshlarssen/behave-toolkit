from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml

from .errors import ConfigError
from .scopes import Scope

PARSER_TYPE_MATCHERS = frozenset({"parse", "cfparse"})
ENUM_LOOKUPS = frozenset({"name", "value"})


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
# pylint: disable=too-many-instance-attributes
class ParserTypeSpec:
    """Configuration for one registered Behave custom type."""

    name: str
    converter: str | None = None
    enum: str | None = None
    pattern: str | None = None
    regex_group_count: int | None = None
    matcher: str | None = None
    case_sensitive: bool = True
    lookup: str = "value"


@dataclass(frozen=True, slots=True)
class ParserConfig:
    """Configuration for parser/type registration helpers."""

    step_matcher: str | None = None
    types: dict[str, ParserTypeSpec] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolkitConfig:
    """Normalized project configuration."""

    version: int
    variables: dict[str, Any] = field(default_factory=dict)
    objects: dict[str, ObjectSpec] = field(default_factory=dict)
    parsers: ParserConfig = field(default_factory=ParserConfig)

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

    raw_parsers = raw.get("parsers", {})
    if not isinstance(raw_parsers, Mapping):
        raise ConfigError("The config 'parsers' section must be a mapping.")

    return ToolkitConfig(
        version=version,
        variables=dict(raw_variables),
        objects=_load_object_specs(raw_objects),
        parsers=_load_parser_config(raw_parsers),
    )


def _load_object_specs(raw_objects: Mapping[str, Any]) -> dict[str, ObjectSpec]:
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
    return objects


def _load_parser_config(raw_parsers: Mapping[str, Any]) -> ParserConfig:
    step_matcher = raw_parsers.get("step_matcher")
    if step_matcher is not None:
        if not isinstance(step_matcher, str) or not step_matcher.strip():
            raise ConfigError(
                "The config 'parsers.step_matcher' field must be a non-empty "
                "string if provided."
            )
        step_matcher = step_matcher.strip()

    raw_parser_types = raw_parsers.get("types", {})
    if not isinstance(raw_parser_types, Mapping):
        raise ConfigError("The config 'parsers.types' section must be a mapping.")

    parser_types = {
        str(raw_name): _load_parser_type_spec(str(raw_name), raw_definition)
        for raw_name, raw_definition in raw_parser_types.items()
    }
    return ParserConfig(step_matcher=step_matcher, types=parser_types)


def _load_parser_type_spec(type_name: str, raw_definition: Any) -> ParserTypeSpec:
    parser_definition = _normalize_parser_type_definition(type_name, raw_definition)

    converter = _normalized_optional_string(
        parser_definition,
        "converter",
        type_name=type_name,
    )
    enum = _normalized_optional_string(
        parser_definition,
        "enum",
        type_name=type_name,
    )
    if bool(converter) == bool(enum):
        raise ConfigError(
            f"Parser type '{type_name}' must define exactly one of "
            "'converter' or 'enum'."
        )

    pattern = _normalized_optional_string(
        parser_definition,
        "pattern",
        type_name=type_name,
    )

    regex_group_count = parser_definition.get("regex_group_count")
    if regex_group_count is not None and (
        not isinstance(regex_group_count, int) or regex_group_count < 0
    ):
        raise ConfigError(
            f"Parser type '{type_name}' field 'regex_group_count' must be "
            "a non-negative integer if provided."
        )

    matcher = _normalized_optional_string(
        parser_definition,
        "matcher",
        type_name=type_name,
    )
    if matcher is not None and matcher not in PARSER_TYPE_MATCHERS:
        supported_matchers = ", ".join(sorted(PARSER_TYPE_MATCHERS))
        raise ConfigError(
            f"Parser type '{type_name}' field 'matcher' must be one of "
            f"{supported_matchers}."
        )

    case_sensitive = parser_definition.get("case_sensitive", True)
    if not isinstance(case_sensitive, bool):
        raise ConfigError(
            f"Parser type '{type_name}' field 'case_sensitive' must be a bool."
        )

    lookup = parser_definition.get("lookup", "value")
    if not isinstance(lookup, str) or lookup not in ENUM_LOOKUPS:
        supported_lookups = ", ".join(sorted(ENUM_LOOKUPS))
        raise ConfigError(
            f"Parser type '{type_name}' field 'lookup' must be one of "
            f"{supported_lookups}."
        )

    if converter is not None and "case_sensitive" in parser_definition:
        raise ConfigError(
            f"Parser type '{type_name}' cannot set 'case_sensitive' unless "
            "it uses 'enum'."
        )
    if converter is not None and "lookup" in parser_definition:
        raise ConfigError(
            f"Parser type '{type_name}' cannot set 'lookup' unless it uses "
            "'enum'."
        )

    return ParserTypeSpec(
        name=type_name,
        converter=converter,
        enum=enum,
        pattern=pattern,
        regex_group_count=regex_group_count,
        matcher=matcher,
        case_sensitive=case_sensitive,
        lookup=lookup,
    )


def _normalize_parser_type_definition(
    type_name: str,
    raw_definition: Any,
) -> Mapping[str, Any]:
    if isinstance(raw_definition, str):
        return {"converter": raw_definition}
    if isinstance(raw_definition, Mapping):
        return raw_definition
    raise ConfigError(
        f"Parser type '{type_name}' must be defined as a mapping or converter "
        "string."
    )


def _normalized_optional_string(
    definition: Mapping[str, Any],
    field_name: str,
    *,
    type_name: str,
) -> str | None:
    value = definition.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(
            f"Parser type '{type_name}' field '{field_name}' must be a non-empty "
            "string if provided."
        )
    return value.strip()
