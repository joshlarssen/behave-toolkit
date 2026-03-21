from __future__ import annotations

import re
from typing import Any, Protocol, cast

from behave.model import Rule, Scenario, ScenarioContainer, ScenarioOutline, copy_and_reset_steps

from .errors import IntegrationError

_CYCLING_TAG_PATTERN = re.compile(r"cycling\((\d+)\)\Z")
_EXPANDED_RUNNER_ATTRIBUTE = "_behave_toolkit_cycles_expanded"


class _SupportsFeatures(Protocol):
    features: list[Any]


def expand_scenario_cycles(context: object) -> int:
    """Expand `@cycling(N)` scenario tags into repeated scenario runs."""

    runner = _require_runner(context)
    if getattr(runner, _EXPANDED_RUNNER_ATTRIBUTE, False):
        return 0

    added = 0
    for feature in runner.features:
        if isinstance(feature, ScenarioContainer):
            added += _expand_container(feature)

    setattr(runner, _EXPANDED_RUNNER_ATTRIBUTE, True)
    return added


def _require_runner(context: object) -> _SupportsFeatures:
    runner = getattr(context, "_runner", None)
    features = getattr(runner, "features", None)
    if runner is None or features is None:
        raise IntegrationError(
            "behave-toolkit scenario cycling requires the real Behave context "
            "with _runner.features. Call expand_scenario_cycles(context) once "
            "from before_all()."
        )
    return cast(_SupportsFeatures, runner)


def _expand_container(container: ScenarioContainer) -> int:
    added = 0
    expanded_run_items: list[Any] = []
    for run_item in container.run_items:
        if isinstance(run_item, Rule):
            added += _expand_container(run_item)
            expanded_run_items.append(run_item)
            continue

        if isinstance(run_item, ScenarioOutline):
            _reject_cycle_tag_on_outline(run_item)
            expanded_run_items.append(run_item)
            continue

        if not isinstance(run_item, Scenario):
            expanded_run_items.append(run_item)
            continue

        expanded_run_items.append(run_item)
        cycle_count = _cycle_count(run_item)
        if cycle_count is None or cycle_count == 1:
            continue

        for cycle_index in range(2, cycle_count + 1):
            expanded_run_items.append(
                _clone_scenario(
                    run_item,
                    cycle_index=cycle_index,
                    cycle_count=cycle_count,
                )
            )
            added += 1

    container.run_items = expanded_run_items
    container.scenarios = [item for item in expanded_run_items if not isinstance(item, Rule)]
    return added


def _reject_cycle_tag_on_outline(outline: ScenarioOutline) -> None:
    cycle_count = _cycle_count(outline)
    if cycle_count is None:
        return

    raise _scenario_error(
        outline,
        "Scenario Outline items do not support @cycling(...). Use Examples for "
        "data-driven repetition, or move @cycling(...) onto a plain Scenario.",
    )


def _cycle_count(scenario: Scenario) -> int | None:
    matches = [
        count
        for tag in scenario.tags
        if (count := _parse_cycling_tag(str(tag), scenario)) is not None
    ]
    if not matches:
        return None

    if len(matches) > 1:
        raise _scenario_error(
            scenario,
            "Define at most one @cycling(...) tag per scenario.",
        )
    return matches[0]


def _parse_cycling_tag(tag: str, scenario: Scenario) -> int | None:
    if tag != "cycling" and not tag.startswith("cycling("):
        return None

    match = _CYCLING_TAG_PATTERN.fullmatch(tag)
    if match is None:
        raise _scenario_error(
            scenario,
            "Invalid cycle tag syntax. Use @cycling(3) with a positive integer.",
        )

    count = int(match.group(1))
    if count < 1:
        raise _scenario_error(
            scenario,
            "Cycle count must be at least 1.",
        )
    return count


def _clone_scenario(
    scenario: Scenario,
    *,
    cycle_index: int,
    cycle_count: int,
) -> Scenario:
    clone = Scenario(
        filename=scenario.filename,
        line=scenario.line,
        keyword=scenario.keyword,
        name=f"{scenario.name} [cycle {cycle_index}/{cycle_count}]",
        tags=list(scenario.tags),
        steps=copy_and_reset_steps(scenario.steps),
        description=list(scenario.description),
        parent=scenario.parent,
        background=scenario.background,
        background_steps=None,
    )
    clone.feature = scenario.feature
    return clone


def _scenario_error(scenario: Scenario, message: str) -> IntegrationError:
    return IntegrationError(
        f"Invalid scenario cycling configuration for '{scenario.name}' in "
        f"'{scenario.filename}:{scenario.line}': {message}"
    )
