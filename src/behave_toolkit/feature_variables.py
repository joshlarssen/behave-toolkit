"""Helpers for opt-in variable substitution inside parsed Behave feature models."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
import re
from typing import Any

from .errors import IntegrationError

FEATURE_VARIABLE_PATTERN = re.compile(r"\{\{\s*var\s*:\s*([^{}]+?)\s*\}\}")
RUNNER_VARIABLES_ATTRIBUTE = "_behave_toolkit_feature_variables_substituted"


@dataclass(slots=True)
class _VariableResolutionState:
    variable_stack: list[str] = field(default_factory=list)


class _FeatureVariableSubstituter:
    def __init__(self, variables: Mapping[str, Any]) -> None:
        self._variables = variables
        self._seen_nodes: set[int] = set()

    def apply(self, features: Iterable[Any]) -> int:
        total = 0
        for feature in features:
            total += self._substitute_node(feature)
        return total

    def _substitute_node(self, node: Any) -> int:
        if node is None:
            return 0

        node_id = id(node)
        if node_id in self._seen_nodes:
            return 0
        self._seen_nodes.add(node_id)

        total = 0
        total += self._substitute_name(node)
        total += self._substitute_description(node)

        background = getattr(node, "background", None)
        if background is not None:
            total += self._substitute_node(background)

        table = getattr(node, "table", None)
        if table is not None:
            total += self._substitute_table(table, owner=node)

        for step in list(getattr(node, "steps", []) or []):
            total += self._substitute_step(step)

        for child in list(getattr(node, "run_items", []) or []):
            total += self._substitute_node(child)

        for child in list(getattr(node, "scenarios", []) or []):
            total += self._substitute_node(child)

        for child in list(getattr(node, "examples", []) or []):
            total += self._substitute_node(child)

        return total

    def _substitute_name(self, node: Any) -> int:
        name = getattr(node, "name", None)
        if not isinstance(name, str):
            return 0

        updated, replacements = self._replace_text(
            name,
            location=self._location(node, "name"),
        )
        if replacements:
            node.name = updated
        return replacements

    def _substitute_description(self, node: Any) -> int:
        description = getattr(node, "description", None)
        if not isinstance(description, list):
            return 0

        total = 0
        changed = False
        for index, line in enumerate(description, start=1):
            if not isinstance(line, str):
                continue

            updated, replacements = self._replace_text(
                line,
                location=self._location(node, f"description line {index}"),
            )
            if replacements:
                description[index - 1] = updated
                changed = True
                total += replacements

        if changed:
            node.description = description
        return total

    def _substitute_step(self, step: Any) -> int:
        step_id = id(step)
        if step_id in self._seen_nodes:
            return 0
        self._seen_nodes.add(step_id)

        total = 0
        if isinstance(getattr(step, "name", None), str):
            updated, replacements = self._replace_text(
                step.name,
                location=self._location(step, "step text"),
            )
            if replacements:
                step.name = updated
                total += replacements

        if isinstance(getattr(step, "text", None), str):
            updated, replacements = self._replace_text(
                step.text,
                location=self._location(step, "docstring"),
            )
            if replacements:
                step.text = updated
                total += replacements

        table = getattr(step, "table", None)
        if table is not None:
            total += self._substitute_table(table, owner=step)

        return total

    def _substitute_table(self, table: Any, *, owner: Any) -> int:
        table_id = id(table)
        if table_id in self._seen_nodes:
            return 0
        self._seen_nodes.add(table_id)

        total = 0
        headings = getattr(table, "headings", None)
        if isinstance(headings, list):
            for column_index, heading in enumerate(headings, start=1):
                if not isinstance(heading, str):
                    continue

                updated, replacements = self._replace_text(
                    heading,
                    location=self._location(owner, f"table heading {column_index}"),
                )
                if replacements:
                    headings[column_index - 1] = updated
                    total += replacements

        rows = getattr(table, "rows", None)
        if rows is None:
            return total

        for row_index, row in enumerate(rows, start=1):
            cells = getattr(row, "cells", None)
            if not isinstance(cells, list):
                continue

            for column_index, cell in enumerate(cells, start=1):
                if not isinstance(cell, str):
                    continue

                updated, replacements = self._replace_text(
                    cell,
                    location=self._location(
                        owner,
                        f"table row {row_index} cell {column_index}",
                    ),
                )
                if replacements:
                    cells[column_index - 1] = updated
                    total += replacements

        return total

    def _replace_text(self, text: str, *, location: str) -> tuple[str, int]:
        replacements = 0

        def replace(match: re.Match[str]) -> str:
            nonlocal replacements
            variable_name = match.group(1).strip()
            if not variable_name:
                raise IntegrationError(
                    "Could not substitute behave-toolkit feature variable at "
                    f"{location}: empty variable name. Use '{{{{var:name}}}}'."
                )

            replacements += 1
            return self._resolve_variable(
                variable_name,
                location=location,
                state=_VariableResolutionState(),
            )

        return FEATURE_VARIABLE_PATTERN.sub(replace, text), replacements

    def _resolve_variable(
        self,
        variable_name: str,
        *,
        location: str,
        state: _VariableResolutionState,
    ) -> str:
        if variable_name in state.variable_stack:
            cycle = " -> ".join([*state.variable_stack, variable_name])
            raise IntegrationError(
                "Could not substitute behave-toolkit feature variable at "
                f"{location}: circular variable reference detected: {cycle}."
            )

        try:
            raw_value = self._variables[variable_name]
        except KeyError as exc:
            known = ", ".join(sorted(self._variables)) or "<none>"
            raise IntegrationError(
                "Could not substitute behave-toolkit feature variable at "
                f"{location}: unknown variable '{variable_name}'. Known variables: "
                f"{known}."
            ) from exc

        state.variable_stack.append(variable_name)
        try:
            value = self._resolve_variable_value(
                raw_value,
                location=location,
                state=state,
            )
        finally:
            state.variable_stack.pop()

        return self._render_scalar_value(variable_name, value, location=location)

    def _resolve_variable_value(
        self,
        value: Any,
        *,
        location: str,
        state: _VariableResolutionState,
    ) -> Any:
        if not isinstance(value, Mapping):
            return value

        if "$var" not in value:
            return value

        extra_keys = set(value) - {"$var"}
        if extra_keys:
            extras = ", ".join(sorted(extra_keys))
            raise IntegrationError(
                "Could not substitute behave-toolkit feature variable at "
                f"{location}: unsupported keys for nested $var marker: {extras}."
            )

        nested_name = value.get("$var")
        if not isinstance(nested_name, str) or not nested_name.strip():
            raise IntegrationError(
                "Could not substitute behave-toolkit feature variable at "
                f"{location}: nested $var marker requires a non-empty string."
            )

        return self._resolve_variable(
            nested_name.strip(),
            location=location,
            state=state,
        )

    def _render_scalar_value(self, variable_name: str, value: Any, *, location: str) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"

        if isinstance(value, (str, int, float)):
            return str(value)

        raise IntegrationError(
            "Could not substitute behave-toolkit feature variable at "
            f"{location}: variable '{variable_name}' resolved to unsupported value "
            f"type '{type(value).__name__}'. Use a scalar string, number, or "
            "boolean."
        )

    def _location(self, node: Any, label: str) -> str:
        filename = getattr(node, "filename", None)
        line = getattr(node, "line", None)
        owner = type(node).__name__
        label = f"{owner} {label}"

        if isinstance(filename, str) and filename:
            if isinstance(line, int):
                return f"{filename}:{line} ({label})"
            return f"{filename} ({label})"

        if isinstance(line, int):
            return f"line {line} ({label})"

        return label


def substitute_feature_model_variables(
    features: Iterable[Any],
    variables: Mapping[str, Any],
) -> int:
    """Replace `{{var:name}}` placeholders inside parsed Behave feature models."""

    return _FeatureVariableSubstituter(variables).apply(features)


def substitute_feature_variables(
    context: object,
    *,
    namespace: str = "toolkit",
) -> int:
    """Replace `{{var:name}}` placeholders in already-parsed feature models."""

    manager = getattr(context, namespace, None)
    config = getattr(manager, "config", None)
    variables = getattr(config, "variables", None)
    if not isinstance(variables, Mapping):
        raise IntegrationError(
            f"Context does not contain a behave-toolkit manager at '{namespace}'. "
            "Call install(context, ...) from before_all before calling "
            "substitute_feature_variables(context)."
        )

    runner = getattr(context, "_runner", None)
    features = getattr(runner, "features", None)
    if runner is None or features is None:
        raise IntegrationError(
            "behave-toolkit feature-variable substitution requires the real Behave "
            "context with _runner.features. Call substitute_feature_variables(context) "
            "from before_all()."
        )

    if getattr(runner, RUNNER_VARIABLES_ATTRIBUTE, False):
        return 0

    replacements = substitute_feature_model_variables(features, variables)
    setattr(runner, RUNNER_VARIABLES_ATTRIBUTE, True)
    return replacements
