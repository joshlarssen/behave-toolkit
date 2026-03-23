# Getting started

[<- Back to home](index.md)

This page shows the smallest useful integration first. If you want full recipes that combine several optional helpers, continue with [Integration examples](integration-examples.md).

## Before you start

- You already have a Behave project with a `features/` directory.
- You want to keep `environment.py` explicit instead of hiding setup behind a large plugin layer.
- You are running on a supported Python version. See [Compatibility and support](compatibility.md).

## 1. Install the package

```bash
pip install behave-toolkit
```

That single install gives you:

- the runtime helpers used from `features/environment.py`
- the `behave-toolkit-docs` CLI
- the Sphinx dependencies needed to build generated HTML step documentation

## 2. Create a minimal project layout

```text
features/
  behave-toolkit.yaml
  environment.py
  steps/
    reporting_steps.py
  smoke.feature
```

## 3. Create a toolkit config

Start with one variable, one feature-scoped resource, and one scenario-scoped path built from it:

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

`factory` can point to:

- your own project code
- an installed dependency
- the Python standard library

`args` and `kwargs` can also use direct YAML values. You only need `$ref` and
`$var` when you want to reuse another managed object or a root config variable.

```yaml
objects:
  api_client:
    factory: demo.clients.ApiClient
    kwargs:
      base_url: https://example.test
      timeout: 30
      verify_ssl: true
```

## 4. Wire `features/environment.py`

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

This is the core runtime path:

- `install()` loads and validates the config, attaches the manager under `context.toolkit`, and activates `global` objects by default
- `activate_feature_scope()` creates feature-scoped objects inside `before_feature`
- `activate_scenario_scope()` creates scenario-scoped objects inside `before_scenario`
- cleanup is registered with Behave so each scope tears down at the right time automatically

## 5. Use the injected objects from a step

If you do not set `inject_as`, the object name becomes the context attribute name.

```python
from behave import then


@then("the report path is available")
def step_report_path_available(context):
    context.report_path.write_text("ready\n", encoding="utf-8")
    assert context.report_path.exists()
```

And a matching feature file can stay completely ordinary:

```gherkin
Feature: Toolkit smoke

  Scenario: Use toolkit-managed objects
    Then the report path is available
```

## 6. Run Behave

```bash
behave
```

At runtime the flow is:

1. `before_all()` installs the toolkit and creates `global` objects.
2. `before_feature()` creates feature-scoped objects.
3. `before_scenario()` creates scenario-scoped objects.
4. Steps use the injected instances through `context`.
5. Behave cleanup tears objects down in reverse creation order at the matching scope boundary.

## 7. Add optional helpers only when you need them

| If you need... | Helper | When it runs | Where it belongs |
| --- | --- | --- | --- |
| Behave custom type registration from YAML | `configure_parsers(CONFIG_PATH)` | import time | top-level in `environment.py`, before step modules load |
| root config variables directly in `.feature` files | `substitute_feature_variables(context)` | `before_all` | after `install()` |
| repeated runs of one plain scenario | `expand_scenario_cycles(context)` | `before_all` | after `install()`, and after feature-variable substitution if you use both |
| one persistent suite log | `configure_test_logging(...)` | usually `before_all` | after `install()` so your path objects already exist |
| several named logs from YAML | `configure_loggers(context)` | usually `before_all` | after `install()` so global objects already exist |

## 8. Full hook template with optional helpers

Use this as the starting point when your suite grows beyond the minimal path:

```python
from pathlib import Path

from behave_toolkit import (
    activate_feature_scope,
    activate_scenario_scope,
    configure_parsers,
    configure_test_logging,
    expand_scenario_cycles,
    install,
    substitute_feature_variables,
)

CONFIG_PATH = Path(__file__).with_name("behave-toolkit")

# Optional: only useful when your config defines a `parsers:` section.
configure_parsers(CONFIG_PATH)


def before_all(context):
    install(context, CONFIG_PATH)

    # Optional: enable `{{var:name}}` placeholders in parsed feature files.
    substitute_feature_variables(context)

    # Optional: expand `@cycling(N)` tags on plain scenarios.
    expand_scenario_cycles(context)

    # Optional: keep one persistent suite log.
    # Remove this line if your config does not define `test_log_path`.
    context.test_logger = configure_test_logging(context.test_log_path)


def before_feature(context, feature):
    del feature
    activate_feature_scope(context)


def before_scenario(context, scenario):
    del scenario
    activate_scenario_scope(context)
```

If `CONFIG_PATH` points to a directory instead of a single file, use `Path(__file__).with_name("behave-toolkit")` or any other directory path that suits your project layout.

## Next steps

- Read [Integration examples](integration-examples.md) for copy-paste multi-feature setups.
- Read [Configuration model](configuration.md) for the full schema and scope rules.
- Read [Lifecycle hooks](lifecycle.md) for exact hook timing and cleanup behavior.
- Read [Troubleshooting](troubleshooting.md) if `install()` or one of the optional helpers fails.
