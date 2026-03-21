"""Generate Sphinx-friendly step documentation for Behave projects."""
# pylint: disable=too-many-lines

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
import inspect
from pathlib import Path
import re
import shutil
import sys
from typing import Any, Iterator

from behave.matchers import (
    CFParseMatcher,
    Matcher,
    ParseMatcher,
    RegexMatcher,
    get_step_matcher_factory,
    register_type,
    use_current_step_matcher_as_default,
    use_default_step_matcher,
    use_step_matcher,
)
from behave.parser import parse_file
from behave.runner_util import PathManager, exec_file
from behave.step_registry import registry, setup_step_decorators

from .errors import DocumentationError

FIELD_PATTERN = re.compile(r"\{([^}]*)\}")
SLUG_PATTERN = re.compile(r"[^a-z0-9]+")
CARDINALITY_LABELS = {
    "+": "one or more",
    "*": "zero or more",
    "?": "optional",
}
PARSE_RUNTIME_TYPE_HINTS = {
    "%": "float",
    "F": "Decimal",
    "b": "int",
    "d": "int",
    "e": "float",
    "f": "float",
    "g": "float",
    "n": "int",
    "o": "int",
    "ta": "datetime",
    "tc": "datetime",
    "te": "datetime",
    "tg": "datetime",
    "th": "datetime",
    "ti": "datetime",
    "ts": "datetime",
    "tt": "time",
    "x": "int",
}
STEP_TYPES = ("given", "when", "then", "step")


@dataclass(frozen=True, slots=True)
# pylint: disable=too-many-instance-attributes
class StepParameterDocumentation:
    name: str
    pattern_syntax: str | None
    type_expression: str | None
    base_type_name: str | None
    cardinality: str | None
    python_type: str | None
    runtime_type: str | None
    type_page: str | None


@dataclass(frozen=True, slots=True)
class StepExample:
    keyword: str
    text: str
    location: str


@dataclass(slots=True)
# pylint: disable=too-many-instance-attributes
class StepDocumentation:
    slug: str
    title: str
    step_type: str
    pattern: str
    matcher: str
    regex_pattern: str
    source_path: str
    source_line: int
    function_name: str
    signature: str | None
    docstring: str | None
    parameters: list[StepParameterDocumentation] = field(default_factory=list)
    examples: list[StepExample] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class EnumMemberDocumentation:
    name: str
    value: str


@dataclass(frozen=True, slots=True)
class StepReference:
    title: str
    page_path: str


@dataclass(slots=True)
# pylint: disable=too-many-instance-attributes
class TypeDocumentation:
    name: str
    slug: str
    converter_name: str
    signature: str | None
    pattern: str | None
    python_type: str | None
    source_path: str | None
    source_line: int | None
    docstring: str | None
    enum_members: list[EnumMemberDocumentation] = field(default_factory=list)
    matcher_names: set[str] = field(default_factory=set)
    used_by_steps: list[StepReference] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class DocumentationResult:
    output_dir: Path
    step_count: int
    type_count: int


def generate_step_docs(
    features_dir: str | Path,
    output_dir: str | Path,
    *,
    site_title: str = "Behave step documentation",
    max_examples_per_step: int = 3,
) -> DocumentationResult:
    """Generate Sphinx-ready documentation sources for a Behave project."""

    resolved_features_dir = Path(features_dir).expanduser().resolve()
    resolved_output_dir = Path(output_dir).expanduser().resolve()

    if max_examples_per_step < 1:
        raise DocumentationError("'max_examples_per_step' must be at least 1.")

    catalog = _collect_catalog(
        resolved_features_dir,
        max_examples_per_step=max_examples_per_step,
    )
    _render_catalog(catalog, resolved_output_dir, site_title)

    return DocumentationResult(
        output_dir=resolved_output_dir,
        step_count=len(catalog.steps),
        type_count=len(catalog.types),
    )


@dataclass(slots=True)
class _Catalog:
    project_root: Path
    features_dir: Path
    steps: list[StepDocumentation]
    types: dict[str, TypeDocumentation]


@contextmanager
def _preserve_behave_state() -> Iterator[None]:
    factory = get_step_matcher_factory()
    saved_steps = {
        step_type: list(step_definitions)
        for step_type, step_definitions in registry.steps.items()
    }
    saved_bad_steps = list(getattr(registry.error_handler, "bad_step_definitions", []))
    saved_raise_errors = registry.RAISE_ERROR_ON_BAD_STEP_DEFINITION
    saved_default_matcher = factory.default_matcher
    saved_default_matcher_name = factory.default_matcher_name
    saved_initial_matcher_name = factory.initial_matcher_name
    saved_current_matcher = factory.current_matcher

    saved_type_registries: list[tuple[Any, dict[str, Any]]] = []
    seen_registry_ids: set[int] = set()
    for matcher_class in factory.step_matcher_class_mapping.values():
        type_registry = getattr(matcher_class, "TYPE_REGISTRY", None)
        if not isinstance(type_registry, dict):
            continue

        registry_id = id(type_registry)
        if registry_id in seen_registry_ids:
            continue
        seen_registry_ids.add(registry_id)
        saved_type_registries.append((type_registry, dict(type_registry)))

    try:
        registry.clear()
        registry.RAISE_ERROR_ON_BAD_STEP_DEFINITION = True
        factory.clear_registered_types()
        factory.use_default_step_matcher(saved_initial_matcher_name)
        yield
    finally:
        registry.clear()
        registry.steps = {
            step_type: list(step_definitions)
            for step_type, step_definitions in saved_steps.items()
        }
        registry.error_handler.bad_step_definitions = list(saved_bad_steps)
        registry.RAISE_ERROR_ON_BAD_STEP_DEFINITION = saved_raise_errors

        factory.clear_registered_types()
        for type_registry, values in saved_type_registries:
            type_registry.update(values)

        factory.default_matcher = saved_default_matcher
        factory.default_matcher_name = saved_default_matcher_name
        factory.initial_matcher_name = saved_initial_matcher_name
        factory._current_matcher = saved_current_matcher  # pylint: disable=protected-access


def _collect_catalog(features_dir: Path, *, max_examples_per_step: int) -> _Catalog:
    if not features_dir.is_dir():
        raise DocumentationError(
            f"Behave features directory '{features_dir}' does not exist."
        )

    steps_dir = features_dir / "steps"
    if not steps_dir.is_dir():
        raise DocumentationError(
            f"Behave steps directory '{steps_dir}' does not exist."
        )

    project_root = features_dir.parent
    with _preserve_behave_state():
        _load_behave_project(project_root, features_dir, steps_dir)
        type_docs = _build_type_docs(project_root)
        step_docs = _build_step_docs(project_root, type_docs)
        if not step_docs:
            raise DocumentationError(
                f"No step definitions were loaded from '{steps_dir}'."
            )
        _attach_examples(step_docs, features_dir, project_root, max_examples_per_step)
        _link_types_to_steps(step_docs, type_docs)

    return _Catalog(
        project_root=project_root,
        features_dir=features_dir,
        steps=step_docs,
        types=type_docs,
    )


def _load_behave_project(project_root: Path, features_dir: Path, steps_dir: Path) -> None:
    step_directories = _discover_step_directories(steps_dir)
    import_paths = _unique_paths([project_root, features_dir, *step_directories])
    environment_path = features_dir / "environment.py"

    with PathManager([str(path) for path in import_paths]):
        if environment_path.is_file():
            try:
                exec_file(str(environment_path), {})
            except Exception as exc:  # pragma: no cover - exercised in tests via wrapper
                raise DocumentationError(
                    f"Could not load Behave environment '{environment_path}': {exc}"
                ) from exc

        use_current_step_matcher_as_default()
        for step_directory in step_directories:
            for step_file in sorted(step_directory.glob("*.py")):
                _load_step_file(step_file)


def _discover_step_directories(steps_dir: Path) -> list[Path]:
    directories = {steps_dir}
    for step_file in steps_dir.rglob("*.py"):
        if "__pycache__" in step_file.parts:
            continue
        directories.add(step_file.parent)
    return sorted(directories)


def _unique_paths(paths: list[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
    return unique


def _load_step_file(step_file: Path) -> None:
    step_globals = {
        "register_type": register_type,
        "step_matcher": use_step_matcher,
        "use_default_step_matcher": use_default_step_matcher,
        "use_step_matcher": use_step_matcher,
    }
    setup_step_decorators(step_globals)

    try:
        exec_file(str(step_file), step_globals)
    except Exception as exc:
        raise DocumentationError(
            f"Could not load Behave step file '{step_file}': {exc}"
        ) from exc
    finally:
        use_default_step_matcher()


def _build_type_docs(project_root: Path) -> dict[str, TypeDocumentation]:
    type_docs: dict[str, TypeDocumentation] = {}
    for name, converter in sorted(_registered_types().items()):
        source_path, source_line = _callable_location(converter, project_root)
        type_docs[name] = TypeDocumentation(
            name=name,
            slug=_slugify(name),
            converter_name=_callable_name(converter),
            signature=_callable_signature(converter),
            pattern=_converter_pattern(converter),
            python_type=_callable_return_type(converter),
            source_path=source_path,
            source_line=source_line,
            docstring=inspect.getdoc(converter),
            enum_members=_enum_members(converter),
        )
    return type_docs


def _registered_types() -> dict[str, Any]:
    factory = get_step_matcher_factory()
    registered_types: dict[str, Any] = {}
    for matcher_class in factory.step_matcher_class_mapping.values():
        type_registry = getattr(matcher_class, "TYPE_REGISTRY", None)
        if not isinstance(type_registry, dict):
            continue
        for name, converter in type_registry.items():
            registered_types[name] = converter
    return registered_types


def _build_step_docs(
    project_root: Path,
    type_docs: dict[str, TypeDocumentation],
) -> list[StepDocumentation]:
    steps: list[StepDocumentation] = []
    for matcher in _iter_registered_steps():
        title = _step_title(matcher.step_type, matcher.pattern)
        source_path = _display_path(matcher.location.filename, project_root)
        parameters = _extract_parameters(matcher, type_docs)
        steps.append(
            StepDocumentation(
                slug=_step_slug(matcher, source_path),
                title=title,
                step_type=matcher.step_type,
                pattern=matcher.pattern,
                matcher=_matcher_name(matcher),
                regex_pattern=matcher.regex_pattern,
                source_path=source_path,
                source_line=matcher.location.line,
                function_name=_callable_name(matcher.func),
                signature=_callable_signature(matcher.func),
                docstring=inspect.getdoc(matcher.func),
                parameters=parameters,
            )
        )

    steps.sort(key=lambda step: (step.source_path, step.source_line, step.step_type, step.pattern))
    return steps


def _iter_registered_steps() -> Iterator[Matcher]:
    for step_type in STEP_TYPES:
        yield from registry.steps.get(step_type, [])


def _extract_parameters(
    matcher: Matcher,
    type_docs: dict[str, TypeDocumentation],
) -> list[StepParameterDocumentation]:
    if isinstance(matcher, (ParseMatcher, CFParseMatcher)):
        return _extract_parse_parameters(matcher, type_docs)
    if isinstance(matcher, RegexMatcher):
        return _extract_regex_parameters(matcher)
    return _extract_signature_parameters(matcher.func)


def _extract_parse_parameters(
    matcher: ParseMatcher,
    type_docs: dict[str, TypeDocumentation],
) -> list[StepParameterDocumentation]:
    signature = _callable_parameters(matcher.func)
    signature_types = dict(signature)
    signature_names = [name for name, _ in signature]

    parameters: list[StepParameterDocumentation] = []
    seen_names: set[str] = set()
    unnamed_index = 0

    for field_name, type_expression in _parse_pattern_fields(matcher.pattern):
        parameter_name = field_name
        if parameter_name is None:
            if unnamed_index < len(signature_names):
                parameter_name = signature_names[unnamed_index]
                unnamed_index += 1
            else:
                parameter_name = f"arg_{len(parameters) + 1}"

        base_type_name, cardinality = _split_type_expression(type_expression)
        type_page = None
        if base_type_name in type_docs:
            type_page = f"../types/{type_docs[base_type_name].slug}.md"

        parameters.append(
            StepParameterDocumentation(
                name=parameter_name,
                pattern_syntax=_parse_pattern_syntax(parameter_name, type_expression),
                type_expression=type_expression,
                base_type_name=base_type_name,
                cardinality=cardinality,
                python_type=signature_types.get(parameter_name),
                runtime_type=_resolve_runtime_type(
                    signature_types.get(parameter_name),
                    base_type_name,
                    type_expression,
                    type_docs,
                ),
                type_page=type_page,
            )
        )
        seen_names.add(parameter_name)

    for parameter_name, annotation in signature:
        if parameter_name in seen_names:
            continue
        parameters.append(
            StepParameterDocumentation(
                name=parameter_name,
                pattern_syntax=None,
                type_expression=None,
                base_type_name=None,
                cardinality=None,
                python_type=annotation,
                runtime_type=annotation,
                type_page=None,
            )
        )
    return parameters


def _extract_regex_parameters(matcher: RegexMatcher) -> list[StepParameterDocumentation]:
    signature = _callable_parameters(matcher.func)
    signature_names = [name for name, _ in signature]
    signature_types = dict(signature)

    parameters: list[StepParameterDocumentation] = []
    seen_names: set[str] = set()
    named_groups = {index: name for name, index in matcher.regex.groupindex.items()}

    for group_index in range(1, matcher.regex.groups + 1):
        parameter_name = named_groups.get(group_index)
        if parameter_name is None and group_index - 1 < len(signature_names):
            parameter_name = signature_names[group_index - 1]
        if parameter_name is None:
            parameter_name = f"group_{group_index}"

        parameters.append(
            StepParameterDocumentation(
                name=parameter_name,
                pattern_syntax=_regex_pattern_syntax(parameter_name, group_index, named_groups),
                type_expression=None,
                base_type_name=None,
                cardinality=None,
                python_type=signature_types.get(parameter_name),
                runtime_type=signature_types.get(parameter_name),
                type_page=None,
            )
        )
        seen_names.add(parameter_name)

    for parameter_name, annotation in signature:
        if parameter_name in seen_names:
            continue
        parameters.append(
            StepParameterDocumentation(
                name=parameter_name,
                pattern_syntax=None,
                type_expression=None,
                base_type_name=None,
                cardinality=None,
                python_type=annotation,
                runtime_type=annotation,
                type_page=None,
            )
        )
    return parameters


def _extract_signature_parameters(step_function: Any) -> list[StepParameterDocumentation]:
    parameters: list[StepParameterDocumentation] = []
    for parameter_name, annotation in _callable_parameters(step_function):
        parameters.append(
            StepParameterDocumentation(
                name=parameter_name,
                pattern_syntax=None,
                type_expression=None,
                base_type_name=None,
                cardinality=None,
                python_type=annotation,
                runtime_type=annotation,
                type_page=None,
            )
        )
    return parameters


def _callable_parameters(callable_obj: Any) -> list[tuple[str, str | None]]:
    try:
        signature = inspect.signature(callable_obj)
    except (TypeError, ValueError):
        return []

    parameters = list(signature.parameters.values())
    if parameters:
        parameters = parameters[1:]

    result: list[tuple[str, str | None]] = []
    for parameter in parameters:
        result.append(
            (
                parameter.name,
                _format_annotation(
                    parameter.annotation,
                    getattr(callable_obj, "__globals__", None),
                ),
            )
        )
    return result


def _parse_pattern_fields(pattern: str) -> list[tuple[str | None, str | None]]:
    fields: list[tuple[str | None, str | None]] = []
    for match in FIELD_PATTERN.finditer(pattern):
        body = match.group(1).strip()
        if not body:
            fields.append((None, None))
            continue

        if ":" in body:
            name_text, type_text = body.split(":", 1)
            name = name_text.strip() or None
            type_expression = type_text.strip() or None
            fields.append((name, type_expression))
            continue

        fields.append((body, None))
    return fields


def _split_type_expression(type_expression: str | None) -> tuple[str | None, str | None]:
    if not type_expression:
        return None, None

    cardinality = None
    base_type_name = type_expression
    suffix = type_expression[-1]
    if suffix in CARDINALITY_LABELS:
        base_type_name = type_expression[:-1]
        cardinality = CARDINALITY_LABELS[suffix]

    return base_type_name or None, cardinality


def _parse_pattern_syntax(parameter_name: str, type_expression: str | None) -> str:
    if type_expression:
        return f"{{{parameter_name}:{type_expression}}}"
    return f"{{{parameter_name}}}"


def _regex_pattern_syntax(
    parameter_name: str,
    group_index: int,
    named_groups: dict[int, str],
) -> str:
    if group_index in named_groups:
        return f"(?P<{parameter_name}>...)"
    return f"group {group_index}"


def _resolve_runtime_type(
    python_type: str | None,
    base_type_name: str | None,
    type_expression: str | None,
    type_docs: dict[str, TypeDocumentation],
) -> str | None:
    if python_type:
        return python_type

    if base_type_name is not None:
        type_doc = type_docs.get(base_type_name)
        if type_doc is not None and type_doc.python_type:
            return type_doc.python_type
        if base_type_name in PARSE_RUNTIME_TYPE_HINTS:
            return PARSE_RUNTIME_TYPE_HINTS[base_type_name]

    if type_expression and type_expression in PARSE_RUNTIME_TYPE_HINTS:
        return PARSE_RUNTIME_TYPE_HINTS[type_expression]

    return None


def _attach_examples(
    step_docs: list[StepDocumentation],
    features_dir: Path,
    project_root: Path,
    max_examples_per_step: int,
) -> None:
    docs_by_matcher = {
        (
            step_doc.step_type,
            step_doc.pattern,
            step_doc.source_path,
            step_doc.source_line,
        ): step_doc
        for step_doc in step_docs
    }

    for feature_file in sorted(features_dir.rglob("*.feature")):
        try:
            feature = parse_file(str(feature_file))
        except Exception as exc:
            raise DocumentationError(
                f"Could not parse feature file '{feature_file}': {exc}"
            ) from exc

        for scenario in feature.walk_scenarios():
            for step in scenario.all_steps:
                matcher = registry.find_step_definition(step)
                if matcher is None:
                    continue

                step_doc = docs_by_matcher.get(
                    (
                        matcher.step_type,
                        matcher.pattern,
                        _display_path(matcher.location.filename, project_root),
                        matcher.location.line,
                    )
                )
                if step_doc is None or len(step_doc.examples) >= max_examples_per_step:
                    continue

                example = StepExample(
                    keyword=step.keyword.strip(),
                    text=f"{step.keyword.strip()} {step.name}",
                    location=_step_location(step, project_root),
                )
                if example in step_doc.examples:
                    continue
                step_doc.examples.append(example)


def _step_location(step: Any, project_root: Path) -> str:
    filename = getattr(step, "filename", None)
    line = getattr(step, "line", None)
    if filename is None:
        return "<unknown>"

    display = _display_path(filename, project_root)
    if line is None:
        return display
    return f"{display}:{line}"


def _link_types_to_steps(
    step_docs: list[StepDocumentation],
    type_docs: dict[str, TypeDocumentation],
) -> None:
    for step_doc in step_docs:
        seen_type_names: set[str] = set()
        for parameter in step_doc.parameters:
            if parameter.base_type_name is None:
                continue

            type_doc = type_docs.get(parameter.base_type_name)
            if type_doc is None:
                continue

            type_doc.matcher_names.add(step_doc.matcher)
            if type_doc.name in seen_type_names:
                continue
            seen_type_names.add(type_doc.name)

            reference = StepReference(
                title=step_doc.title,
                page_path=f"../steps/{step_doc.slug}.md",
            )
            if reference not in type_doc.used_by_steps:
                type_doc.used_by_steps.append(reference)


def _callable_location(
    callable_obj: Any,
    project_root: Path,
) -> tuple[str | None, int | None]:
    try:
        source_file = inspect.getsourcefile(callable_obj) or inspect.getfile(callable_obj)
    except (OSError, TypeError):
        return None, None

    try:
        _, line_number = inspect.getsourcelines(callable_obj)
    except (OSError, TypeError):
        line_number = None

    return _display_path(source_file, project_root), line_number


def _callable_return_type(callable_obj: Any) -> str | None:
    try:
        signature = inspect.signature(callable_obj)
    except (TypeError, ValueError):
        return None

    globals_namespace = getattr(callable_obj, "__globals__", None)
    return _format_annotation(signature.return_annotation, globals_namespace)


def _enum_members(callable_obj: Any) -> list[EnumMemberDocumentation]:
    enum_type = None
    if inspect.isclass(callable_obj) and issubclass(callable_obj, Enum):
        enum_type = callable_obj
    else:
        try:
            signature = inspect.signature(callable_obj)
        except (TypeError, ValueError):
            signature = None

        if signature is not None:
            annotation = signature.return_annotation
            resolved = _resolve_annotation(annotation, getattr(callable_obj, "__globals__", None))
            if inspect.isclass(resolved) and issubclass(resolved, Enum):
                enum_type = resolved

    if enum_type is None:
        return []

    return [
        EnumMemberDocumentation(name=member.name, value=repr(member.value))
        for member in enum_type
    ]


def _resolve_annotation(annotation: Any, namespace: dict[str, Any] | None) -> Any:
    if annotation is inspect.Signature.empty:
        return None
    if isinstance(annotation, str):
        if namespace is None:
            return None
        return namespace.get(annotation)
    return annotation


def _format_annotation(
    annotation: Any,
    namespace: dict[str, Any] | None,
) -> str | None:
    if annotation is inspect.Signature.empty:
        return None
    if isinstance(annotation, str):
        return annotation

    resolved = _resolve_annotation(annotation, namespace)
    if inspect.isclass(resolved):
        if resolved.__module__ == "builtins":
            return resolved.__qualname__
        return resolved.__qualname__

    formatted = inspect.formatannotation(annotation)
    return formatted.replace("typing.", "")


def _callable_signature(callable_obj: Any) -> str | None:
    try:
        signature = inspect.signature(callable_obj)
    except (TypeError, ValueError):
        return None

    globals_namespace = getattr(callable_obj, "__globals__", None)
    rendered_parameters: list[str] = []
    seen_keyword_only = False
    for parameter in signature.parameters.values():
        prefix = ""
        if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
            prefix = "*"
        elif parameter.kind is inspect.Parameter.VAR_KEYWORD:
            prefix = "**"
        elif (
            parameter.kind is inspect.Parameter.KEYWORD_ONLY
            and not seen_keyword_only
        ):
            rendered_parameters.append("*")
            seen_keyword_only = True

        rendered = f"{prefix}{parameter.name}"
        annotation = _format_annotation(parameter.annotation, globals_namespace)
        if annotation:
            rendered += f": {annotation}"
        if parameter.default is not inspect.Signature.empty:
            rendered += f" = {parameter.default!r}"
        rendered_parameters.append(rendered)

    return_annotation = _format_annotation(
        signature.return_annotation,
        globals_namespace,
    )
    rendered_signature = f"{_callable_name(callable_obj)}({', '.join(rendered_parameters)})"
    if return_annotation:
        rendered_signature += f" -> {return_annotation}"
    return rendered_signature


def _converter_pattern(callable_obj: Any) -> str | None:
    pattern = getattr(callable_obj, "pattern", None)
    if pattern is None:
        return None
    return str(pattern)


def _callable_name(callable_obj: Any) -> str:
    return getattr(
        callable_obj,
        "__qualname__",
        getattr(callable_obj, "__name__", type(callable_obj).__name__),
    )


def _matcher_name(matcher: Matcher) -> str:
    name = getattr(matcher, "NAME", None)
    if name:
        return str(name)
    return type(matcher).__name__


def _step_title(step_type: str, pattern: str) -> str:
    prefix = "Generic" if step_type == "step" else step_type.capitalize()
    return f"{prefix} {pattern}"


def _step_slug(matcher: Matcher, source_path: str) -> str:
    return _slugify(f"{matcher.step_type}-{source_path}-{matcher.location.line}-{matcher.pattern}")


def _slugify(text: str) -> str:
    slug = SLUG_PATTERN.sub("-", text.lower()).strip("-")
    if slug:
        return slug
    return "item"


def _display_path(path_value: str | Path, project_root: Path) -> str:
    path_text = str(path_value)
    if path_text.startswith("<") and path_text.endswith(">"):
        return path_text

    path = Path(path_text)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    else:
        path = path.resolve()

    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return path.as_posix()


def _render_catalog(catalog: _Catalog, output_dir: Path, site_title: str) -> None:
    _prepare_output_dir(output_dir)
    steps_dir = output_dir / "steps"
    types_dir = output_dir / "types"
    static_dir = output_dir / "_static"
    steps_dir.mkdir(parents=True, exist_ok=True)
    types_dir.mkdir(parents=True, exist_ok=True)
    static_dir.mkdir(parents=True, exist_ok=True)

    grouped_steps = _group_steps_by_type(catalog.steps)
    _write_text(output_dir / "conf.py", _render_sphinx_conf(site_title))
    _write_text(static_dir / "behave-toolkit.css", _render_sphinx_css())
    _write_text(output_dir / "index.md", _render_root_index(catalog, site_title))
    _write_text(steps_dir / "index.md", _render_steps_index(catalog.steps))
    for step_type in STEP_TYPES:
        step_group = grouped_steps[step_type]
        if not step_group:
            continue
        _write_text(
            steps_dir / f"{_step_type_file_name(step_type)}.md",
            _render_step_keyword_page(step_type, step_group),
        )
    _write_text(types_dir / "index.md", _render_types_index(catalog.types))

    for step_doc in catalog.steps:
        _write_text(steps_dir / f"{step_doc.slug}.md", _render_step_page(step_doc))
    for type_doc in catalog.types.values():
        _write_text(types_dir / f"{type_doc.slug}.md", _render_type_page(type_doc))


def _prepare_output_dir(output_dir: Path) -> None:
    if output_dir.exists():
        for child_name in ("_static", "conf.py", "index.md", "steps", "types"):
            child_path = output_dir / child_name
            if child_path.is_file():
                child_path.unlink()
            elif child_path.is_dir():
                shutil.rmtree(child_path)
    output_dir.mkdir(parents=True, exist_ok=True)


def _render_sphinx_conf(site_title: str) -> str:
    title = repr(site_title)
    return "\n".join(
        [
            f"project = {title}",
            f"html_title = {title}",
            "extensions = ['myst_parser']",
            "source_suffix = {'.md': 'markdown'}",
            "root_doc = 'index'",
            "exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']",
            "templates_path = []",
            "html_static_path = ['_static']",
            "html_css_files = ['behave-toolkit.css']",
            "html_theme = 'furo'",
            "myst_heading_anchors = 3",
            "myst_enable_extensions = ['colon_fence', 'deflist']",
            "",
        ]
    )


def _render_sphinx_css() -> str:
    return "\n".join(
        [
            ":root {",
            "  --bt-radius: 0.75rem;",
            "}",
            "",
            ".bd-content table td code,",
            ".bd-content table th code {",
            "  white-space: nowrap;",
            "}",
            "",
            ".bd-content h3 {",
            "  margin-top: 2rem;",
            "  padding-top: 0.5rem;",
            "  border-top: 1px solid var(--color-background-border);",
            "}",
            "",
            ".bd-content blockquote {",
            "  font-size: 1rem;",
            "}",
            "",
            ".bd-content pre {",
            "  border-radius: var(--bt-radius);",
            "}",
            "",
        ]
    ) + "\n"


def _render_root_index(catalog: _Catalog, site_title: str) -> str:
    counts_by_type = {step_type: 0 for step_type in STEP_TYPES}
    for step_doc in catalog.steps:
        counts_by_type[step_doc.step_type] += 1

    lines = [
        f"# {site_title}",
        "",
        _myst_toctree(["steps/index", "types/index"], maxdepth=2, hidden=True),
        "",
        "This technical reference is generated by `behave-toolkit` for a",
        "Sphinx-based HTML site.",
        "",
        "## Navigation",
        "",
        f"- [Step reference](steps/index.md) ({len(catalog.steps)} step pages)",
        f"- [Type reference](types/index.md) ({len(catalog.types)} type pages)",
        "",
        "## Coverage",
        "",
        "| Step keyword | Count |",
        "| --- | ---: |",
    ]
    for step_type in STEP_TYPES:
        label = "Generic" if step_type == "step" else step_type.capitalize()
        lines.append(f"| {label} | {counts_by_type[step_type]} |")

    if catalog.types:
        lines.extend(
            [
                "",
                "## Highlights",
                "",
                "Step parameters link directly to custom parser/type pages.",
                "When a converter exposes an enum return type annotation, the",
                "generated type page lists the enum members too.",
            ]
        )
    return "\n".join(lines) + "\n"


def _render_steps_index(step_docs: list[StepDocumentation]) -> str:
    grouped_steps = _group_steps_by_type(step_docs)
    step_type_entries = [
        _step_type_file_name(step_type)
        for step_type in STEP_TYPES
        if grouped_steps[step_type]
    ]
    lines = [
        "# Step reference",
        "",
        _myst_toctree(step_type_entries, maxdepth=1, hidden=True),
        "",
        "Browse steps by keyword. Each keyword page contains the full catalog",
        "entries plus direct links to the individual implementation pages.",
        "",
        "| Keyword | Count | Link |",
        "| --- | ---: | --- |",
    ]

    for step_type in STEP_TYPES:
        if grouped_steps[step_type]:
            lines.append(
                "| "
                f"{_step_type_label(step_type)} | "
                f"{len(grouped_steps[step_type])} | "
                f"[Open {_step_type_label(step_type).lower()} reference]"
                f"({_step_type_file_name(step_type)}.md) |"
            )

    return "\n".join(lines) + "\n"


def _render_step_keyword_page(
    step_type: str,
    step_group: list[StepDocumentation],
) -> str:
    label = _step_type_label(step_type)
    lines = [
        f"# {label} steps",
        "",
        "[<- Back to step reference](index.md)",
        "",
        _myst_toctree([step_doc.slug for step_doc in step_group], maxdepth=1, hidden=True),
        "",
        f"This page groups all `{label}` step implementations.",
        "",
    ]

    for step_doc in step_group:
        lines.extend(_render_step_catalog_entry(step_doc))
        lines.append("")

    return "\n".join(lines) + "\n"


def _group_steps_by_type(
    step_docs: list[StepDocumentation],
) -> dict[str, list[StepDocumentation]]:
    grouped_steps: dict[str, list[StepDocumentation]] = {
        step_type: [] for step_type in STEP_TYPES
    }
    for step_doc in step_docs:
        grouped_steps[step_doc.step_type].append(step_doc)
    return grouped_steps


def _render_step_catalog_entry(step_doc: StepDocumentation) -> list[str]:
    lines = [
        f"### [{step_doc.title}]({step_doc.slug}.md)",
        "",
    ]

    summary = _docstring_summary(step_doc.docstring)
    if summary:
        lines.extend([summary, ""])

    lines.extend(
        [
            f"- Matcher: `{step_doc.matcher}`",
            f"- Function: `{step_doc.function_name}()`",
            f"- Signature: `{step_doc.signature or step_doc.function_name}`",
            f"- Source: `{step_doc.source_path}:{step_doc.source_line}`",
        ]
    )

    if step_doc.parameters:
        lines.extend(["", "**Parameters**", ""])
        lines.extend(_render_parameter_table(step_doc.parameters))
    else:
        lines.extend(
            [
                "",
                "**Parameters**",
                "",
                "This step does not accept documented parameters.",
            ]
        )

    lines.extend(["", "**Examples**", ""])
    if step_doc.examples:
        for example in step_doc.examples:
            lines.append(f"- `{example.text}` (`{example.location}`)")
    else:
        lines.append("No matching step examples were found in the parsed feature files.")

    return lines


def _step_type_label(step_type: str) -> str:
    if step_type == "step":
        return "Generic"
    return step_type.capitalize()


def _step_type_file_name(step_type: str) -> str:
    if step_type == "step":
        return "generic"
    return step_type


def _docstring_summary(docstring: str | None) -> str | None:
    if not docstring:
        return None

    first_paragraph = docstring.strip().split("\n\n", maxsplit=1)[0]
    cleaned = " ".join(line.strip() for line in first_paragraph.splitlines() if line.strip())
    return cleaned or None


def _render_parameter_table(parameters: list[StepParameterDocumentation]) -> list[str]:
    lines = [
        "| Parameter | Pattern field | Behave type | Runtime value | Step annotation | Notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for parameter in parameters:
        lines.append(
            "| "
            f"`{parameter.name}` | "
            f"{_parameter_pattern_text(parameter)} | "
            f"{_parameter_behave_type_text(parameter)} | "
            f"{_parameter_runtime_text(parameter)} | "
            f"{_parameter_annotation_text(parameter)} | "
            f"{_escape_table(_parameter_notes_text(parameter))} |"
        )
    return lines


def _parameter_pattern_text(parameter: StepParameterDocumentation) -> str:
    if parameter.pattern_syntax is None:
        return "-"
    return f"`{parameter.pattern_syntax}`"


def _parameter_behave_type_text(parameter: StepParameterDocumentation) -> str:
    if parameter.base_type_name and parameter.type_page:
        return f"[`{parameter.base_type_name}`]({parameter.type_page})"
    if parameter.type_expression:
        return f"`{parameter.type_expression}`"
    return "-"


def _parameter_runtime_text(parameter: StepParameterDocumentation) -> str:
    if parameter.runtime_type:
        return f"`{parameter.runtime_type}`"
    return "-"


def _parameter_annotation_text(parameter: StepParameterDocumentation) -> str:
    if parameter.python_type:
        return f"`{parameter.python_type}`"
    return "-"


def _parameter_notes_text(parameter: StepParameterDocumentation) -> str:
    notes: list[str] = []
    if parameter.cardinality:
        notes.append(parameter.cardinality)
    if parameter.pattern_syntax and parameter.pattern_syntax.startswith("(?P<"):
        notes.append("regex named capture")
    elif parameter.pattern_syntax and parameter.pattern_syntax.startswith("group "):
        notes.append("regex capture")
    if parameter.type_expression and parameter.type_page is None and parameter.base_type_name:
        if parameter.base_type_name not in PARSE_RUNTIME_TYPE_HINTS:
            notes.append("no generated type page")
    if not notes:
        return "-"
    return ", ".join(notes)


def _render_types_index(type_docs: dict[str, TypeDocumentation]) -> str:
    type_entries = [
        type_doc.slug
        for type_doc in sorted(type_docs.values(), key=lambda value: value.name.lower())
    ]
    lines = [
        "# Type reference",
        "",
    ]
    if not type_docs:
        lines.extend(
            [
                "No custom parse types were registered while loading the Behave project.",
                "",
            ]
        )
        return "\n".join(lines)

    lines.extend(
        [
            _myst_toctree(type_entries, maxdepth=1, hidden=True),
            "",
            "Each custom type page explains the converter signature, runtime",
            "type, enum values, and the steps that reference it.",
            "",
        ]
    )
    lines.extend(
        [
            "| Type | Pattern | Python type | Used by | Source |",
            "| --- | --- | --- | ---: | --- |",
        ]
    )
    for type_doc in sorted(type_docs.values(), key=lambda value: value.name.lower()):
        pattern = f"`{type_doc.pattern}`" if type_doc.pattern else "-"
        python_type = f"`{type_doc.python_type}`" if type_doc.python_type else "-"
        source = "-"
        if type_doc.source_path and type_doc.source_line is not None:
            source = f"`{type_doc.source_path}:{type_doc.source_line}`"
        lines.append(
            "| "
            f"[`{type_doc.name}`]({type_doc.slug}.md) | "
            f"{pattern} | "
            f"{python_type} | "
            f"{len(type_doc.used_by_steps)} | "
            f"{source} |"
        )
    return "\n".join(lines) + "\n"


def _myst_toctree(
    entries: list[str],
    *,
    maxdepth: int,
    hidden: bool,
) -> str:
    if not entries:
        return ""

    lines = ["```{toctree}"]
    if hidden:
        lines.append(":hidden:")
    lines.append(f":maxdepth: {maxdepth}")
    lines.append("")
    lines.extend(entries)
    lines.append("```")
    return "\n".join(lines)


def _render_step_page(step_doc: StepDocumentation) -> str:
    lines = [
        f"# {step_doc.title}",
        "",
        f"[<- Back to {_step_type_label(step_doc.step_type).lower()} steps]"
        f"({_step_type_file_name(step_doc.step_type)}.md)",
        "",
    ]

    summary = _docstring_summary(step_doc.docstring)
    if summary:
        lines.extend([f"> {summary}", ""])

    lines.extend(
        [
            "## Quick reference",
            "",
            "| Field | Value |",
            "| --- | --- |",
            f"| Keyword | `{_step_type_label(step_doc.step_type)}` |",
            f"| Matcher | `{step_doc.matcher}` |",
            f"| Function | `{step_doc.function_name}()` |",
            f"| Source | `{step_doc.source_path}:{step_doc.source_line}` |",
            f"| Step pattern | `{step_doc.pattern}` |",
            f"| Regex pattern | `{step_doc.regex_pattern}` |",
            "",
        ]
    )

    if step_doc.signature:
        lines.extend(
            [
                "## Signature",
                "",
                "```python",
                step_doc.signature,
                "```",
                "",
            ]
        )

    if step_doc.docstring:
        lines.extend(["## Full docstring", "", step_doc.docstring, ""])

    lines.extend(
        [
            "## Parameters",
            "",
        ]
    )
    if step_doc.parameters:
        lines.extend(_render_parameter_table(step_doc.parameters))
    else:
        lines.extend(["This step does not expose any documented parameters.", ""])

    lines.extend(
        [
            "",
            "## Examples",
            "",
        ]
    )
    if step_doc.examples:
        for example in step_doc.examples:
            lines.append(f"- `{example.text}` (`{example.location}`)")
    else:
        lines.append("No matching step examples were found in the parsed feature files.")

    lines.append("")
    return "\n".join(lines)


def _render_type_page(type_doc: TypeDocumentation) -> str:
    lines = [
        f"# Type `{type_doc.name}`",
        "",
        "[<- Back to type reference](index.md)",
        "",
        f"- Converter: `{type_doc.converter_name}()`",
    ]
    if type_doc.signature:
        lines.extend(
            [
                "",
                "## Signature",
                "",
                "```python",
                type_doc.signature,
                "```",
            ]
        )
    if type_doc.pattern:
        lines.append(f"- Parse pattern: `{type_doc.pattern}`")
    if type_doc.python_type:
        lines.append(f"- Python type: `{type_doc.python_type}`")
    if type_doc.matcher_names:
        supported_matchers = ", ".join(f"`{name}`" for name in sorted(type_doc.matcher_names))
        lines.append(f"- Used with matcher(s): {supported_matchers}")
    if type_doc.source_path and type_doc.source_line is not None:
        lines.append(f"- Source: `{type_doc.source_path}:{type_doc.source_line}`")
    lines.append("")

    if type_doc.docstring:
        lines.extend(["## Summary", "", type_doc.docstring, ""])

    if type_doc.enum_members:
        lines.extend(
            [
                "## Enum values",
                "",
                "| Name | Value |",
                "| --- | --- |",
            ]
        )
        for member in type_doc.enum_members:
            lines.append(f"| `{member.name}` | `{member.value}` |")
        lines.append("")

    lines.extend(["## Used by steps", ""])
    if type_doc.used_by_steps:
        for reference in sorted(type_doc.used_by_steps, key=lambda item: item.title.lower()):
            lines.append(f"- [{reference.title}]({reference.page_path})")
    else:
        lines.append("No loaded step currently references this type.")

    lines.append("")
    return "\n".join(lines)


def _escape_table(text: str) -> str:
    return text.replace("|", "\\|")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for step documentation generation."""

    parser = argparse.ArgumentParser(
        prog="behave-toolkit-docs",
        description="Generate Sphinx-friendly Behave step documentation.",
    )
    parser.add_argument(
        "--features-dir",
        default="features",
        help="Path to the Behave features directory.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path("docs") / "behave-toolkit"),
        help="Directory where the generated Markdown pages should be written.",
    )
    parser.add_argument(
        "--site-title",
        default="Behave step documentation",
        help="Title used in the generated root index page.",
    )
    parser.add_argument(
        "--max-examples",
        type=int,
        default=3,
        help="Maximum number of example step usages to record per step definition.",
    )

    args = parser.parse_args(argv)
    try:
        result = generate_step_docs(
            args.features_dir,
            args.output_dir,
            site_title=args.site_title,
            max_examples_per_step=args.max_examples,
        )
    except DocumentationError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(
        "Generated "
        f"{result.step_count} step page(s) and {result.type_count} type page(s) "
        f"in '{result.output_dir}'."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
