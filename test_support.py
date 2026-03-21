from __future__ import annotations

from pathlib import Path

from behave.configuration import Configuration
from behave.runner import Context, Runner

EVENTS: list[tuple[str, str]] = []


class TrackingResource:
    def __init__(self, label: str) -> None:
        self.label = label
        self.closed = False
        EVENTS.append(("create", label))

    def close(self) -> None:
        self.closed = True
        EVENTS.append(("cleanup", self.label))


def build_tracking_resource(label: str) -> TrackingResource:
    return TrackingResource(label)


class DependentResource:
    def __init__(self, dependency: TrackingResource, label: str) -> None:
        self.dependency = dependency
        self.label = label
        self.closed = False
        EVENTS.append(("create", label))

    def close(self) -> None:
        self.closed = True
        EVENTS.append(("cleanup", self.label))


def build_dependent_resource(
    dependency: TrackingResource,
    label: str,
) -> DependentResource:
    return DependentResource(dependency, label)


def make_context() -> Context:
    config = Configuration(load_config=False)
    return Context(runner=Runner(config))


def reset_events() -> None:
    EVENTS.clear()


def write_step_docs_fixture(project_root: Path) -> Path:
    features_dir = project_root / "features"
    steps_dir = features_dir / "steps"
    steps_dir.mkdir(parents=True)

    (features_dir / "environment.py").write_text(
        """
from enum import Enum

import parse

from behave import register_type, use_step_matcher

use_step_matcher("cfparse")


class Status(Enum):
    ACTIVE = "active"
    PENDING = "pending"


@parse.with_pattern(r"active|pending")
def parse_status(text: str) -> Status:
    \"\"\"Parse a textual account status.

    Args:
        text: Raw status token from the feature file.

    Returns:
        Status: Matching enum value.

    Raises:
        ValueError: If the feature token does not match a known status.
    \"\"\"
    return Status(text)


register_type(Status=parse_status)
        """.strip(),
        encoding="utf-8",
    )

    (steps_dir / "account_steps.py").write_text(
        """
from behave import given, then, when


@given("I have a {status:Status} account")
def step_have_status_account(context, status):
    \"\"\"Use a custom status parser.

    This summary should stay visible in the catalog page.

    Args:
        context: The Behave context for the current scenario.
        status (Status): Parsed status enum from the custom converter.

    Returns:
        None: The step does not return a value.

    Raises:
        AssertionError: If the parsed status cannot be accepted.
    \"\"\"
    del context, status


@when("I open {count:d} tabs")
def step_open_tabs(context, count):
    \"\"\"Open a dashboard tab count.\"\"\"
    del context, count


@then("the dashboard is ready")
def step_dashboard_ready(context):
    \"\"\"The dashboard should be fully loaded.\"\"\"
    del context
        """.strip(),
        encoding="utf-8",
    )

    (features_dir / "demo.feature").write_text(
        """
Feature: Demo step catalog

  Scenario: Account overview
    Given I have a active account
    When I open 2 tabs
    Then the dashboard is ready
        """.strip(),
        encoding="utf-8",
    )
    return features_dir
