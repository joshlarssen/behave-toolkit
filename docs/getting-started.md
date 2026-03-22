# Getting started

[<- Back to home](index.md)

## Install the package

```bash
pip install behave-toolkit
```

This single install gives you:

- the runtime helpers used from `features/environment.py`
- the `behave-toolkit-docs` CLI
- the Sphinx dependencies needed to build generated HTML documentation

## Create a toolkit config

The config format is intentionally small. Start with root `variables` and
`objects`, then add `parsers` or `logging` only if your suite really needs
those extras.

```yaml
version: 1
variables:
  report_name: report.json

objects:
  workspace:
    factory: tempfile.TemporaryDirectory
    scope: feature
    cleanup: cleanup

  workspace_path:
    factory: pathlib.Path
    scope: feature
    args:
      - $ref: workspace
        attr: name

  report_path:
    factory: pathlib.Path
    scope: scenario
    args:
      - $ref: workspace_path
      - $var: report_name
```

For larger suites, you can split that config into a dedicated
`behave-toolkit/` directory and point `CONFIG_PATH` at the directory instead of
one file.

## Wire the toolkit from `environment.py`

```python
from pathlib import Path

from behave_toolkit import (
    activate_feature_scope,
    activate_scenario_scope,
    install,
)

CONFIG_PATH = Path(__file__).with_name("behave-toolkit.yaml")


def before_all(context):
    install(context, CONFIG_PATH)


def before_feature(context, feature):
    del feature
    activate_feature_scope(context)


def before_scenario(context, scenario):
    del scenario
    activate_scenario_scope(context)
```

That minimal flow is the recommended starting point.

## Add optional helpers only when needed

If you use custom Behave types, register them at import time:

```python
from pathlib import Path

from behave_toolkit import configure_parsers

CONFIG_PATH = Path(__file__).with_name("behave-toolkit.yaml")
configure_parsers(CONFIG_PATH)
```

If you want to replay a plain scenario several times, expand cycle tags from
`before_all()`:

```python
from behave_toolkit import expand_scenario_cycles


def before_all(context):
    expand_scenario_cycles(context)
    install(context, CONFIG_PATH)
```

If you want to reuse root config variables directly in `.feature` files, call
`substitute_feature_variables(context)` from `before_all()` after `install()`:

```python
from behave_toolkit import substitute_feature_variables


def before_all(context):
    install(context, CONFIG_PATH)
    substitute_feature_variables(context)
```

Feature placeholders use `{{var:name}}`. They apply to feature/scenario names,
description lines, step text, docstrings, and tables. Tags are intentionally
left unchanged.

## What happens at runtime

1. `install()` loads and validates the YAML file or config directory, attaches
   the manager under `context.toolkit`, and activates global objects by
   default. In the normal flow that means global objects are created from
   `before_all()` and cleaned automatically at the very end of the Behave run.
2. `activate_feature_scope()` creates feature-scoped objects and registers
   cleanup with Behave.
3. `activate_scenario_scope()` creates scenario-scoped objects and registers
   cleanup with Behave.
4. Instances are injected onto the Behave context using either `inject_as` or
   the object name itself.
5. `configure_parsers()` is optional import-time setup for custom types.
6. `substitute_feature_variables()` is an optional `before_all()` helper for
   `{{var:name}}` placeholders in parsed feature files.
7. `expand_scenario_cycles()` is an optional `before_all()` helper for
   `@cycling(N)`.

## Optional: keep one persistent test log

If your config exposes a path object such as `test_log_path`, you can keep test
logging explicit in `environment.py` with the small manual helper:

```python
from behave_toolkit import configure_test_logging


def before_all(context):
    install(context, CONFIG_PATH)
    context.test_logger = configure_test_logging(context.test_log_path)
```

This is the recommended logging setup for most suites: one predictable
`test-run.log` file, plus optional console output.

Combine it with `format_cycle_progress(scenario)` if you want messages like
`Cycle 3/10 -> Billing burst [cycle 3/10]`.

If you later need several named outputs defined in YAML, add a `logging:`
section and call `configure_loggers(context)`. That is intentionally optional,
not the default recommendation.

If you want to make the global lifetime more explicit, use
`install(..., activate_global=False)` and call `activate_global_scope(context)`
from `before_all()` yourself. The lifetime stays the same: created once for the
whole run, cleaned once at the end.

## Good first follow-ups

- Read [Configuration model](configuration.md) to understand the object schema.
- Read [Parser helpers](parser-helpers.md) if you want to configure custom
  Behave types from YAML.
- Read [Scenario cycling](scenario-cycling.md) if you want to replay a tagged
  plain scenario multiple times.
- Read [Lifecycle hooks](lifecycle.md) to understand hook order and cleanup.
- Read [Step documentation](step-documentation.md) if you want a reference site
  for your own step library.
