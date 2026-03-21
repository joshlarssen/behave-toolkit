# Scenario cycling

[<- Back to home](index.md)

`behave-toolkit` can replay a tagged plain scenario multiple times with a
single helper call in `before_all()`.

## Basic usage

Add `@cycling(N)` to a plain scenario:

```gherkin
Feature: Operational flows

  @cycling(3)
  Scenario: Billing burst
    Given the toolkit global session is ready
    When I submit 3 requests to billing
    Then the request summary is stored
```

Wire the helper from `features/environment.py`:

```python
from pathlib import Path

from behave_toolkit import (
    activate_feature_scope,
    activate_scenario_scope,
    configure_parsers,
    expand_scenario_cycles,
    install,
)

CONFIG_PATH = Path(__file__).with_name("behave-toolkit.yaml")
configure_parsers(CONFIG_PATH)


def before_all(context):
    expand_scenario_cycles(context)
    install(context, CONFIG_PATH)


def before_feature(context, feature):
    del feature
    activate_feature_scope(context)


def before_scenario(context, scenario):
    del scenario
    activate_scenario_scope(context)
```

`expand_scenario_cycles(context)` is safe to leave wired in even if no scenario
uses `@cycling(...)`. In that case it is a no-op.

## What it does

Before Behave starts running features, the helper expands a tagged scenario into
multiple scenario executions:

- the original scenario still runs once
- additional runs are appended with names like `[cycle 2/3]`
- each cycle gets its own `before_scenario` / `after_scenario` hook flow
- scenario-scoped objects are created and cleaned up for each replay

This keeps lifecycle behavior explicit instead of hiding retries or loops inside
step code.

## Reporting behavior

Cycle replays appear as separate scenarios in Behave output and formatter
reports. That is intentional: if cycle 2 fails and cycle 1 passes, you can see
which replay failed.

## Scope and limits

`@cycling(N)` is intentionally limited to plain `Scenario` items.

- Use it when you want to replay the same scenario body several times.
- Do **not** use it on `Scenario Outline`.
- If you need data-driven combinations, keep using `Scenario Outline` with
  `Examples`.

Invalid tags such as `@cycling(foo)` fail fast with an `IntegrationError`
pointing at the offending scenario location.
