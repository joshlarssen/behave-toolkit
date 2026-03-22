from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from functools import wraps
import inspect
from pathlib import Path
import pkgutil
import re
from typing import Any, cast

from behave.matchers import get_step_matcher_factory, register_type, use_step_matcher

from .config import PARSER_TYPE_MATCHERS, ParserTypeSpec, load_yaml_file
from .errors import ConfigError
from .internal import callable_source_info, snapshot_type_registries

_SOURCE_FILE_ATTRIBUTE = "__behave_toolkit_source_file__"
_SOURCE_LINE_ATTRIBUTE = "__behave_toolkit_source_line__"
_ENUM_CONVERTER_NAME_PATTERN = re.compile(r"[^0-9a-zA-Z_]+")


def configure_parsers(config_path: str | Path) -> dict[str, Callable[[str], Any]]:
    """Configure Behave custom parsers and the default step matcher from YAML."""

    resolved_path = Path(config_path).expanduser().resolve()
    config = load_yaml_file(resolved_path)
    parser_config = config.parsers
    if not parser_config.types and parser_config.step_matcher is None:
        return {}

    previous_matcher_name, previous_registries = _snapshot_matcher_state()
    try:
        if parser_config.step_matcher is not None:
            _use_step_matcher(
                parser_config.step_matcher,
                config_path=resolved_path,
                field_name="parsers.step_matcher",
            )

        registered: dict[str, Callable[[str], Any]] = {}
        current_matcher_name = _current_matcher_name()
        for spec in parser_config.types.values():
            matcher_name = spec.matcher or parser_config.step_matcher or current_matcher_name
            if matcher_name not in PARSER_TYPE_MATCHERS:
                raise ConfigError(
                    f"Invalid behave-toolkit config '{resolved_path}': Parser type "
                    f"'{spec.name}' cannot register against matcher '{matcher_name}'. "
                    "Custom parser types require 'parse' or 'cfparse'."
                )

            _use_step_matcher(
                matcher_name,
                config_path=resolved_path,
                field_name=f"parsers.types.{spec.name}.matcher",
            )

            converter = _build_converter(spec, resolved_path)
            register_type(**{spec.name: converter})
            registered[spec.name] = converter

        final_matcher_name = parser_config.step_matcher or previous_matcher_name
        _use_step_matcher(
            final_matcher_name,
            config_path=resolved_path,
            field_name="parsers.step_matcher",
        )
        return registered
    except Exception:
        _restore_matcher_state(previous_matcher_name, previous_registries)
        raise


def _snapshot_matcher_state() -> tuple[str, list[tuple[dict[str, Any], dict[str, Any]]]]:
    current_matcher_name = _current_matcher_name()
    return current_matcher_name, snapshot_type_registries()


def _restore_matcher_state(
    matcher_name: str,
    registries: list[tuple[dict[str, Any], dict[str, Any]]],
) -> None:
    factory = get_step_matcher_factory()
    factory.clear_registered_types()
    for registry, values in registries:
        registry.update(values)
    use_step_matcher(matcher_name)


def _current_matcher_name() -> str:
    factory = get_step_matcher_factory()
    name = getattr(factory.current_matcher, "NAME", None)
    if isinstance(name, str) and name:
        return name
    return "parse"


def _use_step_matcher(name: str, *, config_path: Path, field_name: str) -> None:
    try:
        use_step_matcher(name)
    except KeyError as exc:
        raise ConfigError(
            f"Invalid behave-toolkit config '{config_path}': Field '{field_name}' "
            f"uses unsupported step matcher '{name}'."
        ) from exc


def _build_converter(spec: ParserTypeSpec, config_path: Path) -> Callable[[str], Any]:
    if spec.enum is not None:
        return _build_enum_converter(spec, config_path)

    converter = _resolve_converter(spec, config_path)
    if spec.pattern is not None or spec.regex_group_count is not None:
        pattern = spec.pattern or getattr(converter, "pattern", None)
        converter = _clone_converter(
            converter,
            pattern=pattern,
            regex_group_count=spec.regex_group_count,
        )

    if getattr(converter, "pattern", None) is None:
        raise ConfigError(
            f"Invalid behave-toolkit config '{config_path}': Parser type "
            f"'{spec.name}' must define 'pattern' in config or use a converter "
            "with a 'pattern' attribute."
        )
    return converter


def _resolve_converter(spec: ParserTypeSpec, config_path: Path) -> Callable[[str], Any]:
    if spec.converter is None:
        raise ConfigError(
            f"Invalid behave-toolkit config '{config_path}': Parser type "
            f"'{spec.name}' is missing a converter."
        )

    try:
        resolved = pkgutil.resolve_name(spec.converter)
    except (ImportError, AttributeError, ValueError) as exc:
        raise ConfigError(
            f"Invalid behave-toolkit config '{config_path}': Parser type "
            f"'{spec.name}' references converter '{spec.converter}', but it is "
            "not importable."
        ) from exc

    if not callable(resolved):
        raise ConfigError(
            f"Invalid behave-toolkit config '{config_path}': Parser type "
            f"'{spec.name}' converter '{spec.converter}' is not callable."
        )
    return cast(Callable[[str], Any], resolved)


def _build_enum_converter(spec: ParserTypeSpec, config_path: Path) -> Callable[[str], Any]:
    enum_type = _resolve_enum_type(spec, config_path)
    tokens_by_key, display_tokens, accepted_values = _enum_tokens(
        spec,
        enum_type,
        config_path,
    )
    function_name = _enum_converter_name(spec.name)

    def parse_enum_token(text: str) -> Any:
        lookup_key = text if spec.case_sensitive else text.lower()
        try:
            return tokens_by_key[lookup_key]
        except KeyError as exc:
            raise ValueError(
                f"Unknown {spec.name} value {text!r}. Expected one of: "
                f"{accepted_values}"
            ) from exc

    parse_enum_token.__name__ = function_name
    parse_enum_token.__qualname__ = function_name
    parse_enum_token.__module__ = enum_type.__module__
    parse_enum_token.__annotations__ = {"text": str, "return": enum_type}
    parse_enum_token.__doc__ = (
        f"Parse textual values into `{enum_type.__qualname__}`.\n\n"
        "Args:\n"
        "    text: Raw token from the feature file.\n\n"
        "Returns:\n"
        f"    {enum_type.__qualname__}: Matching enum value.\n\n"
        "Raises:\n"
        f"    ValueError: If the token does not map to a known {spec.name} value."
    )

    source_file, source_line = callable_source_info(enum_type)
    if source_file is not None:
        setattr(parse_enum_token, _SOURCE_FILE_ATTRIBUTE, source_file)
    if source_line is not None:
        setattr(parse_enum_token, _SOURCE_LINE_ATTRIBUTE, source_line)

    pattern = spec.pattern or _enum_pattern(display_tokens, case_sensitive=spec.case_sensitive)
    return _clone_converter(
        parse_enum_token,
        pattern=pattern,
        regex_group_count=spec.regex_group_count,
    )


def _resolve_enum_type(spec: ParserTypeSpec, config_path: Path) -> type[Enum]:
    if spec.enum is None:
        raise ConfigError(
            f"Invalid behave-toolkit config '{config_path}': Parser type "
            f"'{spec.name}' is missing an enum reference."
        )

    try:
        resolved = pkgutil.resolve_name(spec.enum)
    except (ImportError, AttributeError, ValueError) as exc:
        raise ConfigError(
            f"Invalid behave-toolkit config '{config_path}': Parser type "
            f"'{spec.name}' references enum '{spec.enum}', but it is not importable."
        ) from exc

    if not inspect.isclass(resolved) or not issubclass(resolved, Enum):
        raise ConfigError(
            f"Invalid behave-toolkit config '{config_path}': Parser type "
            f"'{spec.name}' enum '{spec.enum}' is not an Enum class."
        )
    return resolved


def _enum_tokens(
    spec: ParserTypeSpec,
    enum_type: type[Enum],
    config_path: Path,
) -> tuple[dict[str, Enum], list[str], str]:
    tokens_by_key: dict[str, Enum] = {}
    display_tokens: list[str] = []
    for member in enum_type:
        raw_token = member.value if spec.lookup == "value" else member.name
        token_text = str(raw_token)
        normalized = token_text if spec.case_sensitive else token_text.lower()
        existing = tokens_by_key.get(normalized)
        if existing is not None and existing is not member:
            raise ConfigError(
                f"Invalid behave-toolkit config '{config_path}': Parser type "
                f"'{spec.name}' defines duplicate enum token '{token_text}' for "
                "the selected lookup mode."
            )
        tokens_by_key[normalized] = member
        display_tokens.append(token_text)

    if not tokens_by_key:
        raise ConfigError(
            f"Invalid behave-toolkit config '{config_path}': Parser type "
            f"'{spec.name}' cannot be built from an empty enum."
        )

    accepted_values = ", ".join(repr(token) for token in display_tokens)
    return tokens_by_key, display_tokens, accepted_values


def _clone_converter(
    converter: Callable[[str], Any],
    *,
    pattern: str | None,
    regex_group_count: int | None,
) -> Callable[[str], Any]:
    @wraps(converter)
    def wrapped(text: str) -> Any:
        return converter(text)

    try:
        wrapped.__annotations__ = inspect.get_annotations(converter, eval_str=True)
    except (AttributeError, NameError, TypeError):
        pass

    if pattern is not None:
        setattr(wrapped, "pattern", pattern)

    existing_group_count = getattr(converter, "regex_group_count", None)
    group_count = regex_group_count if regex_group_count is not None else existing_group_count
    if group_count is not None:
        setattr(wrapped, "regex_group_count", group_count)

    source_file = getattr(converter, _SOURCE_FILE_ATTRIBUTE, None)
    source_line = getattr(converter, _SOURCE_LINE_ATTRIBUTE, None)
    if source_file is None or source_line is None:
        fallback_file, fallback_line = callable_source_info(converter)
        source_file = source_file or fallback_file
        source_line = source_line or fallback_line

    if source_file is not None:
        setattr(wrapped, _SOURCE_FILE_ATTRIBUTE, source_file)
    if source_line is not None:
        setattr(wrapped, _SOURCE_LINE_ATTRIBUTE, source_line)
    return wrapped


def _enum_converter_name(type_name: str) -> str:
    normalized = _ENUM_CONVERTER_NAME_PATTERN.sub("_", type_name).strip("_").lower()
    normalized = normalized or "type"
    return f"parse_{normalized}"


def _enum_pattern(tokens: list[str], *, case_sensitive: bool) -> str:
    escaped = "|".join(re.escape(token) for token in tokens)
    if case_sensitive:
        return escaped
    return f"(?i:{escaped})"
