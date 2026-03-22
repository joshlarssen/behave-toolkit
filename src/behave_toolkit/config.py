from __future__ import annotations

from dataclasses import dataclass, field
import logging
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
class LoggerSpec:
    """Configuration for one named test logger."""

    name: str
    path: Any
    level: int | str = "INFO"
    logger_name: str | None = None
    console: bool = True
    mode: str = "w"
    inject_as: str | None = None

    @property
    def context_name(self) -> str:
        return self.inject_as or self.name

    @property
    def scope(self) -> Scope:
        return Scope.GLOBAL

    @property
    def effective_logger_name(self) -> str:
        return self.logger_name or self.name


@dataclass(frozen=True, slots=True)
class LoggingConfig:
    """Configuration for named test loggers."""

    loggers: dict[str, LoggerSpec] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolkitConfig:
    """Normalized project configuration."""

    version: int
    variables: dict[str, Any] = field(default_factory=dict)
    objects: dict[str, ObjectSpec] = field(default_factory=dict)
    parsers: ParserConfig = field(default_factory=ParserConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

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
    """Load toolkit configuration from a YAML file or config directory."""

    config_path = Path(path).expanduser().resolve()
    try:
        if config_path.is_dir():
            return load_config(_load_yaml_directory(config_path))
        return load_config(_load_yaml_file_mapping(config_path))
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


def _load_yaml_file_mapping(path: Path) -> Mapping[str, Any]:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(
            f"Could not read behave-toolkit config '{path}': {exc}"
        ) from exc
    return _load_yaml_mapping(raw_text, source=f"at '{path}'")


def _load_yaml_directory(directory: Path) -> Mapping[str, Any]:
    yaml_files = sorted(
        [
            *directory.rglob("*.yaml"),
            *directory.rglob("*.yml"),
        ],
        key=lambda path: str(path.relative_to(directory)).lower(),
    )
    if not yaml_files:
        raise ConfigError(
            f"Could not find any YAML files in behave-toolkit config directory "
            f"'{directory}'."
        )

    merged: dict[str, Any] = {
        "version": 1,
        "variables": {},
        "objects": {},
        "parsers": {"types": {}},
        "logging": {},
    }
    version_source: Path | None = None
    variable_sources: dict[str, Path] = {}
    object_sources: dict[str, Path] = {}
    parser_type_sources: dict[str, Path] = {}
    logger_sources: dict[str, Path] = {}
    parser_step_matcher_source: Path | None = None

    for yaml_file in yaml_files:
        raw = _load_yaml_file_mapping(yaml_file)
        if "version" in raw:
            version = raw["version"]
            if version_source is None:
                merged["version"] = version
                version_source = yaml_file
            elif merged["version"] != version:
                raise ConfigError(
                    "Invalid behave-toolkit config directory "
                    f"'{directory}': 'version' is defined more than once with "
                    f"different values in '{version_source}' and '{yaml_file}'."
                )

        _merge_named_section(
            merged_section=merged["variables"],
            raw_root=raw,
            section_name="variables",
            file_path=yaml_file,
            root_path=directory,
            sources=variable_sources,
        )
        _merge_named_section(
            merged_section=merged["objects"],
            raw_root=raw,
            section_name="objects",
            file_path=yaml_file,
            root_path=directory,
            sources=object_sources,
        )
        _merge_parser_section(
            merged_parsers=merged["parsers"],
            raw_root=raw,
            file_path=yaml_file,
            root_path=directory,
            parser_type_sources=parser_type_sources,
            parser_step_matcher_source=parser_step_matcher_source,
        )
        if "parsers" in raw and isinstance(raw.get("parsers"), Mapping):
            step_matcher = raw["parsers"].get("step_matcher")
            if step_matcher is not None:
                parser_step_matcher_source = yaml_file
        _merge_named_section(
            merged_section=merged["logging"],
            raw_root=raw,
            section_name="logging",
            file_path=yaml_file,
            root_path=directory,
            sources=logger_sources,
        )

    return merged


def _merge_named_section(  # pylint: disable=too-many-arguments
    *,
    merged_section: dict[str, Any],
    raw_root: Mapping[str, Any],
    section_name: str,
    file_path: Path,
    root_path: Path,
    sources: dict[str, Path],
) -> None:
    raw_section = raw_root.get(section_name)
    if raw_section is None:
        return
    if not isinstance(raw_section, Mapping):
        raise ConfigError(
            "Invalid behave-toolkit config directory "
            f"'{root_path}': Section '{section_name}' in '{file_path}' must be a "
            "mapping."
        )

    for name, value in raw_section.items():
        normalized_name = str(name)
        previous_source = sources.get(normalized_name)
        if previous_source is not None:
            raise ConfigError(
                "Invalid behave-toolkit config directory "
                f"'{root_path}': Section '{section_name}' defines '{normalized_name}' "
                f"more than once in '{previous_source}' and '{file_path}'."
            )
        merged_section[normalized_name] = value
        sources[normalized_name] = file_path


def _merge_parser_section(  # pylint: disable=too-many-arguments
    *,
    merged_parsers: dict[str, Any],
    raw_root: Mapping[str, Any],
    file_path: Path,
    root_path: Path,
    parser_type_sources: dict[str, Path],
    parser_step_matcher_source: Path | None,
) -> None:
    raw_parsers = raw_root.get("parsers")
    if raw_parsers is None:
        return
    if not isinstance(raw_parsers, Mapping):
        raise ConfigError(
            "Invalid behave-toolkit config directory "
            f"'{root_path}': Section 'parsers' in '{file_path}' must be a mapping."
        )

    step_matcher = raw_parsers.get("step_matcher")
    if step_matcher is not None:
        if parser_step_matcher_source is not None:
            raise ConfigError(
                "Invalid behave-toolkit config directory "
                f"'{root_path}': 'parsers.step_matcher' is defined more than once "
                f"in '{parser_step_matcher_source}' and '{file_path}'."
            )
        merged_parsers["step_matcher"] = step_matcher

    raw_parser_types = raw_parsers.get("types")
    if raw_parser_types is None:
        return
    if not isinstance(raw_parser_types, Mapping):
        raise ConfigError(
            "Invalid behave-toolkit config directory "
            f"'{root_path}': Section 'parsers.types' in '{file_path}' must be a "
            "mapping."
        )

    merged_types = merged_parsers["types"]
    for name, value in raw_parser_types.items():
        normalized_name = str(name)
        previous_source = parser_type_sources.get(normalized_name)
        if previous_source is not None:
            raise ConfigError(
                "Invalid behave-toolkit config directory "
                f"'{root_path}': Section 'parsers.types' defines "
                f"'{normalized_name}' more than once in '{previous_source}' and "
                f"'{file_path}'."
            )
        merged_types[normalized_name] = value
        parser_type_sources[normalized_name] = file_path


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

    raw_logging = raw.get("logging", {})
    if not isinstance(raw_logging, Mapping):
        raise ConfigError("The config 'logging' section must be a mapping.")

    return ToolkitConfig(
        version=version,
        variables=dict(raw_variables),
        objects=_load_object_specs(raw_objects),
        parsers=_load_parser_config(raw_parsers),
        logging=_load_logging_config(raw_logging),
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


def _load_logging_config(raw_logging: Mapping[str, Any]) -> LoggingConfig:
    logger_specs = {
        str(raw_name): _load_logger_spec(str(raw_name), raw_definition)
        for raw_name, raw_definition in raw_logging.items()
    }
    return LoggingConfig(loggers=logger_specs)


def _load_logger_spec(logger_name: str, raw_definition: Any) -> LoggerSpec:
    if not isinstance(raw_definition, Mapping):
        raise ConfigError(f"Logger '{logger_name}' must be defined as a mapping.")

    path = raw_definition.get("path")
    if path is None:
        raise ConfigError(f"Logger '{logger_name}' must define a 'path'.")
    if isinstance(path, str) and not path.strip():
        raise ConfigError(f"Logger '{logger_name}' field 'path' must not be empty.")

    logger_target_name = _normalized_optional_string(
        raw_definition,
        "logger_name",
        type_name=logger_name,
        label="Logger",
    )
    inject_as = _normalized_optional_string(
        raw_definition,
        "inject_as",
        type_name=logger_name,
        label="Logger",
    )
    mode = _normalized_optional_string(
        raw_definition,
        "mode",
        type_name=logger_name,
        label="Logger",
    )
    if mode is None:
        mode = "w"

    console = raw_definition.get("console", True)
    if not isinstance(console, bool):
        raise ConfigError(f"Logger '{logger_name}' field 'console' must be a bool.")

    level = raw_definition.get("level", "INFO")
    if not isinstance(level, (int, str)) or (isinstance(level, str) and not level.strip()):
        raise ConfigError(
            f"Logger '{logger_name}' field 'level' must be an integer or non-empty string."
        )
    if isinstance(level, str):
        level = level.strip()
        candidate = getattr(logging, level.upper(), None)
        if not isinstance(candidate, int):
            raise ConfigError(
                f"Logger '{logger_name}' field 'level' uses unsupported value '{level}'."
            )

    return LoggerSpec(
        name=logger_name,
        path=path,
        level=level,
        logger_name=logger_target_name,
        console=console,
        mode=mode,
        inject_as=inject_as,
    )


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
    label: str = "Parser type",
) -> str | None:
    value = definition.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(
            f"{label} '{type_name}' field '{field_name}' must be a non-empty "
            "string if provided."
        )
    return value.strip()
