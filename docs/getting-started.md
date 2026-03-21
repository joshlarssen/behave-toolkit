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

The config format is intentionally small: a root `variables` section and a root
`objects` section.

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

## Wire the toolkit from `environment.py`

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

## What happens at runtime

1. `configure_parsers()` runs at import time. If the config defines a
   `parsers:` section, it sets the step matcher and registers custom types
   before Behave imports step modules.
2. `expand_scenario_cycles()` runs from `before_all()`. It looks for
   `@cycling(N)` on plain scenarios, expands them into repeated runs, and is a
   no-op when the suite does not use that tag.
3. `install()` loads and validates the YAML file, attaches the manager under
   `context.toolkit`, and activates global objects by default.
4. `activate_feature_scope()` creates feature-scoped objects and registers
   cleanup with Behave.
5. `activate_scenario_scope()` creates scenario-scoped objects and registers
   cleanup with Behave.
6. Instances are injected onto the Behave context using either `inject_as` or
   the object name itself.

## Good first follow-ups

- Read [Configuration model](configuration.md) to understand the object schema.
- Read [Parser helpers](parser-helpers.md) if you want to configure custom
  Behave types from YAML.
- Read [Scenario cycling](scenario-cycling.md) if you want to replay a tagged
  plain scenario multiple times.
- Read [Lifecycle hooks](lifecycle.md) to understand hook order and cleanup.
- Read [Step documentation](step-documentation.md) if you want a reference site
  for your own step library.
