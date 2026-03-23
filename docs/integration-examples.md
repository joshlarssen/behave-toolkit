# Integration examples

[<- Back to home](index.md)

This page focuses on copy-paste patterns for real Behave projects. Start with the smallest recipe that solves your problem, then add the optional layers only when they earn their place.

## Recipe 1: the smallest useful integration

Use this when you only want scoped object creation and cleanup.

```text
features/
  behave-toolkit.yaml
  environment.py
  steps/
    reporting_steps.py
  smoke.feature
```

`features/behave-toolkit.yaml`:

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

`features/environment.py`:

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

`features/steps/reporting_steps.py`:

```python
from behave import then


@then("the report file can be written")
def step_report_file_can_be_written(context):
    context.report_path.write_text("ok\n", encoding="utf-8")
    assert context.report_path.exists()
```

## Recipe 2: split config into a directory

Use this when one YAML file starts to feel crowded or when different people own different areas.

```text
features/
  behave-toolkit/
    00-variables.yaml
    10-parsers.yaml
    20-objects.yaml
  environment.py
  support_types.py
```

`features/behave-toolkit/00-variables.yaml`:

```yaml
version: 1
variables:
  environment_name: qa
  base_url: https://qa.example.test
  report_name: latest-report.json
```

`features/behave-toolkit/10-parsers.yaml`:

```yaml
parsers:
  step_matcher: cfparse
  types:
    Status:
      enum: support_types.Status
      case_sensitive: false
```

`features/behave-toolkit/20-objects.yaml`:

```yaml
objects:
  artifacts_path:
    factory: pathlib.Path
    scope: global
    args:
      - artifacts

  test_log_path:
    factory: pathlib.Path
    scope: global
    args:
      - $ref: artifacts_path
      - test-run.log

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

`features/support_types.py`:

```python
from enum import Enum


class Status(Enum):
    ACTIVE = "active"
    PENDING = "pending"
```

## Recipe 3: one `environment.py` that combines the common optional helpers

Use this when you want parser helpers, feature-file variables, scenario cycling, and one persistent log together.

```python
from pathlib import Path

from behave_toolkit import (
    activate_feature_scope,
    activate_scenario_scope,
    configure_parsers,
    configure_test_logging,
    expand_scenario_cycles,
    format_cycle_progress,
    install,
    substitute_feature_variables,
)

CONFIG_PATH = Path(__file__).with_name("behave-toolkit")

# Import-time setup for Behave custom types.
configure_parsers(CONFIG_PATH)


def before_all(context):
    install(context, CONFIG_PATH)
    substitute_feature_variables(context)
    added = expand_scenario_cycles(context)
    context.test_logger = configure_test_logging(context.test_log_path)
    if added:
        context.test_logger.info("Expanded %s extra cycle runs", added)


def before_feature(context, feature):
    del feature
    activate_feature_scope(context)


def before_scenario(context, scenario):
    activate_scenario_scope(context)
    progress = format_cycle_progress(scenario)
    if progress is None:
        context.test_logger.info("%s", scenario.name)
    else:
        context.test_logger.info("Cycle %s -> %s", progress, scenario.name)
```

The ordering above is the recommended one when you combine these helpers:

1. `configure_parsers(CONFIG_PATH)` at import time
2. `install(context, CONFIG_PATH)` in `before_all()`
3. `substitute_feature_variables(context)` if you use `{{var:name}}`
4. `expand_scenario_cycles(context)` if you use `@cycling(N)`
5. `configure_test_logging(...)` or `configure_loggers(context)` after global objects exist

## Recipe 4: reuse root variables directly in feature files

`features/login.feature`:

```gherkin
Feature: Login against {{var:environment_name}}

  Scenario: Open the configured home page
    Given I open {{var:base_url}}
```

`features/environment.py`:

```python
from pathlib import Path

from behave_toolkit import install, substitute_feature_variables

CONFIG_PATH = Path(__file__).with_name("behave-toolkit")


def before_all(context):
    install(context, CONFIG_PATH)
    substitute_feature_variables(context)
```

Feature placeholders use `{{var:name}}`. They are resolved from the root `variables:` section and apply to names, descriptions, step text, docstrings, and tables. Tags are intentionally left unchanged.

## Recipe 5: upgrade from one log file to named loggers in YAML

Use this when one persistent `test-run.log` is no longer enough.

Add paths in `objects:`:

```yaml
objects:
  artifacts_path:
    factory: pathlib.Path
    scope: global
    args:
      - artifacts

  test_log_path:
    factory: pathlib.Path
    scope: global
    args:
      - $ref: artifacts_path
      - test-run.log

  diagnostics_log_path:
    factory: pathlib.Path
    scope: global
    args:
      - $ref: artifacts_path
      - diagnostics.log
```

Add named logger definitions:

```yaml
logging:
  test_run:
    path:
      $ref: test_log_path
    logger_name: suite-tests
    inject_as: test_logger

  diagnostics:
    path:
      $ref: diagnostics_log_path
    logger_name: suite-diagnostics
    inject_as: diagnostics_logger
    console: false
```

Wire them from `before_all()`:

```python
from pathlib import Path

from behave_toolkit import configure_loggers, install

CONFIG_PATH = Path(__file__).with_name("behave-toolkit")


def before_all(context):
    install(context, CONFIG_PATH)
    configure_loggers(context)
```

Use YAML-defined loggers only when you really want multiple named outputs. For many suites, the smaller `configure_test_logging()` helper stays the better default.

## Recipe 6: generate a step reference site for a downstream suite

Once your step library grows, generate a searchable reference site directly from your Behave project:

```bash
behave-toolkit-docs --features-dir features --output-dir docs/behave-toolkit --config-path features/behave-toolkit
python -m sphinx -b html docs/behave-toolkit docs/_build/behave-toolkit
```

Pass `--config-path` when your feature files use `{{var:name}}`, so example matching sees the substituted text.

## Which recipe should you start with?

- Start with **Recipe 1** if you only need scoped objects and cleanup.
- Add **Recipe 2** when config ownership grows and one YAML file stops scaling.
- Use **Recipe 3** if your suite already needs several optional helpers together.
- Use **Recipe 4** only when feature-file placeholders make scenarios easier to read or easier to share across environments.
- Use **Recipe 5** only when one persistent suite log is no longer enough.
- Use **Recipe 6** once your step library has become large enough that discovery is a real problem.
