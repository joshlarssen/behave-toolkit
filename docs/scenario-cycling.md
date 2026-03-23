# Scenario cycling

[<- Back to home](index.md)

`behave-toolkit` can replay a tagged plain scenario multiple times with one helper call in `before_all()`.

## When to use it

Use `@cycling(N)` when you want to rerun the exact same plain scenario body several times while keeping:

- separate `before_scenario` and `after_scenario` hook execution for each run
- separate scenario-scoped object creation and cleanup for each run
- separate report entries so failures stay attributable

If you need data-driven combinations, keep using `Scenario Outline` with `Examples`.

```{warning}
`@cycling(N)` is intentionally limited to plain `Scenario` items. It does not support `Scenario Outline`.
```

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
    expand_scenario_cycles,
    install,
)

CONFIG_PATH = Path(__file__).with_name("behave-toolkit.yaml")


def before_all(context):
    install(context, CONFIG_PATH)
    expand_scenario_cycles(context)


def before_feature(context, feature):
    del feature
    activate_feature_scope(context)


def before_scenario(context, scenario):
    del scenario
    activate_scenario_scope(context)
```

If you also use `substitute_feature_variables(context)`, call it before `expand_scenario_cycles(context)` so the cloned scenarios inherit already-substituted text.

`expand_scenario_cycles(context)` is safe to leave wired in even if no scenario uses `@cycling(...)`. In that case it is a no-op.

## What it does

Before Behave starts running features, the helper expands a tagged scenario into multiple scenario executions:

- the original scenario still runs once
- additional runs are appended with names like `[cycle 2/3]`
- each cycle gets its own `before_scenario` and `after_scenario` hook flow
- scenario-scoped objects are created and cleaned up for each replay

This keeps lifecycle behavior explicit instead of hiding retries or loops inside step code.

## Reporting behavior

Cycle replays appear as separate scenarios in Behave output and formatter reports. That is intentional: if cycle 2 fails and cycle 1 passes, you can see exactly which replay failed.

`expand_scenario_cycles(context)` returns the number of extra scenario runs that were added. That can be useful if you want a short bootstrap log in `before_all()`.

## Logging cycle progress

If you want readable progress like `2/10`, combine scenario cycling with the small logging helper.

```python
from pathlib import Path

from behave_toolkit import (
    activate_scenario_scope,
    configure_test_logging,
    expand_scenario_cycles,
    get_cycle_progress,
    install,
)

CONFIG_PATH = Path(__file__).with_name("behave-toolkit.yaml")


def before_all(context):
    install(context, CONFIG_PATH)
    added = expand_scenario_cycles(context)
    context.test_logger = configure_test_logging(context.test_log_path)
    context.test_logger.info("Expanded %s extra cycle runs", added)


def before_scenario(context, scenario):
    activate_scenario_scope(context)
    progress = get_cycle_progress(scenario)
    if progress is None:
        context.test_logger.info("%s", scenario.name)
    else:
        context.test_logger.info(
            "Cycle %s/%s -> %s",
            progress[0],
            progress[1],
            scenario.name,
        )
```

`format_cycle_progress(subject)` is the shorter helper when you only want a display-ready label such as `2/10`.

## Failure modes

Invalid tags such as `@cycling(foo)` fail fast with an `IntegrationError` pointing at the offending scenario location.

If you accidentally put `@cycling(...)` on a `Scenario Outline`, the error explicitly tells you to use `Examples` instead.
