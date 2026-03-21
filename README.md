# behave-toolkit

`behave-toolkit` is an opinionated toolkit for making large `behave` suites
 easier to configure, understand, and evolve.

The first bootstrap version focuses on a clean project foundation:

- declarative YAML configuration for named objects
- explicit lifecycle scopes (`step`, `scenario`, `feature`, `global`)
- a small installation API for `features/environment.py`
- a package layout that leaves room for future documentation, variables, and parser helpers

## Status

This repository is intentionally starting small. The current code provides:

- configuration loading and validation
- fail-fast diagnostics with dedicated `ConfigError` and `IntegrationError` exceptions
- scope normalization
- lifecycle activation helpers for `environment.py`
- object creation and cleanup for `global`, `feature`, and `scenario` scopes
- explicit `$ref` and `$var` markers for object dependencies and reusable values
- Sphinx-oriented step documentation generation with custom type pages
- a manager attached to the Behave context for inspection and future extensions

The next milestones are expected to add:

- optional parser/type helper integrations
- experimental step-scoped objects

Project documentation for `behave-toolkit` itself lives in `docs/` and is meant
to be published on GitHub Pages.

## Quick start

Install the package:

```bash
pip install behave-toolkit
```

Create a configuration file:

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

Wire it from `features/environment.py`:

```python
from pathlib import Path

from behave_toolkit import activate_feature_scope, activate_scenario_scope, install

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

Global objects are created during `install()`. Feature and scenario objects are
created by the matching hook helpers. Instances are exposed on the Behave
context using either `inject_as` or the object name.

`factory` can point to:

- your own project code
- an installed package from the active environment
- the Python standard library

Markers are explicit on purpose:

- `$ref`: inject another configured object
- `$ref` + `attr`: inject one attribute path from another object
- `$var`: inject a named value from the root `variables` section

`install()` now validates the whole configuration up front. Invalid scopes, bad
imports, unknown `$ref` / `$var` entries, and object-reference cycles fail fast
with messages that include the config path and the relevant object field.

## Step documentation for Sphinx

Generate a Sphinx-ready technical reference from a Behave project:

```bash
behave-toolkit-docs --features-dir features --output-dir docs/behave-toolkit
```

The generated pages include:

- a Sphinx/MyST project scaffold with `conf.py`, sidebar navigation,
  and grouped step reference pages
- a browsable step catalog grouped by keyword, with integrated
  docstring summaries and parameter details
- one page per step definition with signature, full implementation
  docstring, structured Google-style `Args` / `Returns` / `Raises`
  sections, parameter breakdown, and examples
- one page per custom parse type with links back from steps to the type
- enum values when a converter exposes an enum return annotation

To build the final HTML site, install the docs extras and run Sphinx:

```bash
pip install -e ".[docs]"
python -m sphinx -b html docs/behave-toolkit docs/_build/behave-toolkit
```

The generated Sphinx project is configured for the `Furo` theme,
`sphinx-design` cards, and `MyST` Markdown parsing.

## Project documentation

Build the main project documentation locally with:

```bash
pip install -e ".[docs]"
python -m sphinx -W --keep-going -b html docs docs/_build/html
```

A dedicated GitHub Actions workflow builds this site on pull requests and
deploys it to GitHub Pages from `main`.

The first time you enable publishing on GitHub, go to `Settings > Pages` and
set `Build and deployment > Source` to `GitHub Actions`.

## Development

Install the package in editable mode with development tools:

```bash
pip install -e ".[dev]"
```

Run the test suite:

```bash
python -m unittest discover -s tests -v
```

Run a quick syntax validation:

```bash
python -m compileall src tests test_support.py
```

Run static analysis:

```bash
python -m mypy src tests test_support.py
python -m pylint src tests test_support.py
```

The GitHub Actions CI workflow runs static analysis once on Ubuntu with Python
3.11, then runs the unit tests in a smaller Ubuntu and Windows matrix for
Python 3.11 and 3.12.
