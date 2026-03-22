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
    expand_scenario_cycles,
    install,
)

CONFIG_PATH = Path(__file__).with_name("behave-toolkit.yaml")


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

`expand_scenario_cycles(context)` returns the number of extra scenario runs that
were added. That can be useful if you want a short bootstrap log in
`before_all()`.

## Logging cycle progress

If you want readable progress like `1/1000`, use the cycle metadata helpers in
your hooks. If your config exposes a path object such as `test_log_path`, the
simplest setup is one persistent test log:

```python
from behave_toolkit import (
    activate_scenario_scope,
    configure_test_logging,
    expand_scenario_cycles,
    get_cycle_progress,
    install,
)


def before_all(context):
    added = expand_scenario_cycles(context)
    install(context, CONFIG_PATH)
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

`configure_test_logging(...)` is deliberately small and explicit:

- it writes to a dedicated file path that you choose
- it can mirror the same messages to console
- it resets existing handlers for the chosen logger name, which makes repeated
  local runs predictable

You can build persistent artifact paths with normal toolkit objects, for
example global `pathlib.Path` instances like `test_log_path` or
`latest_report_path`.

`format_cycle_progress(subject)` is the shorter logging helper. Use
`get_cycle_progress(subject)` when you want the raw tuple for assertions,
metrics, or your own message formatting.

If you later need several named log files, the optional YAML `logging:` section
plus `configure_loggers(context)` is also available. Keep that as an upgrade
path rather than the default.

## Scope and limits

`@cycling(N)` is intentionally limited to plain `Scenario` items.

- Use it when you want to replay the same scenario body several times.
- Do **not** use it on `Scenario Outline`.
- If you need data-driven combinations, keep using `Scenario Outline` with
  `Examples`.

Invalid tags such as `@cycling(foo)` fail fast with an `IntegrationError`
pointing at the offending scenario location.
