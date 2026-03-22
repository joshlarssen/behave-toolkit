# behave-toolkit

`behave-toolkit` is a small toolkit for teams that like Behave's explicit
execution model but want less repetitive wiring as suites grow.

The project is deliberately pragmatic:

- keep `features/environment.py` readable
- make object lifetimes explicit with `global`, `feature`, and `scenario`
  scopes
- move repetitive setup into explicit YAML instead of hidden framework magic
- add a few focused helpers only where Behave gets noisy in larger suites

## What it gives you today

- YAML-configured objects with deterministic file or directory loading
- fail-fast validation with dedicated `ConfigError` and `IntegrationError`
  exceptions
- explicit `$ref` and `$var` markers for dependencies and reusable values
- opt-in `{{var:name}}` substitution for feature files
- lifecycle activation helpers for `environment.py`
- config-driven parser helpers for Behave custom types
- tag-driven scenario cycling with `@cycling(N)`
- generated step reference documentation for consumer Behave suites
- one small persistent test logger helper, plus optional YAML-defined named
  loggers if you later need more than one output

Project documentation for `behave-toolkit` itself lives in `docs/` and is meant
to be published on GitHub Pages.

## Quick start

Install the package:

```bash
pip install behave-toolkit
```

That single install now gives you both main usage modes:

- the Python integration API used from `features/environment.py`
- the `behave-toolkit-docs` CLI plus the Sphinx toolchain needed to build HTML

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

For many suites, that is enough. `install()` creates `global` objects during
`before_all()`, `activate_feature_scope()` creates feature objects,
`activate_scenario_scope()` creates scenario objects, and instances are exposed
on the Behave context using either `inject_as` or the object name.

That means the default `global` lifecycle is:

- created from `before_all()` when you call `install(context, CONFIG_PATH)`
- kept alive for the whole Behave run
- cleaned automatically when Behave tears down the test-run layer at the very end

`factory` can point to:

- your own project code
- an installed package from the active environment
- the Python standard library

Markers are explicit on purpose:

- `$ref`: inject another configured object
- `$ref` + `attr`: inject one attribute path from another object
- `$var`: inject a named value from the root `variables` section

If you want to reuse those same root variables directly in `.feature` files,
call `substitute_feature_variables(context)` from `before_all()` after
`install()`. Feature placeholders use the explicit `{{var:name}}` syntax.

`install()` validates the whole configuration up front. Invalid scopes, bad
imports, unknown `$ref` / `$var` entries, and object-reference cycles fail fast
with messages that include the config path and the relevant object field.

When the config grows, `CONFIG_PATH` can point to a dedicated config directory
instead of one file. `behave-toolkit` loads all `.yaml` / `.yml` files from that
directory recursively in deterministic order and merges them. Duplicated names
across files fail fast so ownership stays explicit.

Example layout:

```text
features/
  behave-toolkit/
    00-variables.yaml
    10-parsers.yaml
    20-objects.yaml
    30-logging.yaml
```

## Add optional helpers only when you need them

### Parser helpers

If your suite uses custom Behave types, `configure_parsers(CONFIG_PATH)` can
move matcher selection and type registration into the same YAML config. This is
import-time setup, so keep it at module level in `environment.py`.

### Feature-file variables

If you want to reuse root config values directly in Gherkin, call
`substitute_feature_variables(context)` after `install(context, CONFIG_PATH)`:

```python
from behave_toolkit import substitute_feature_variables


def before_all(context):
    install(context, CONFIG_PATH)
    substitute_feature_variables(context)
```

This replaces `{{var:name}}` placeholders in feature names, descriptions, step
text, docstrings, and tables. Tags are intentionally left unchanged.

### Scenario cycling

If you want to replay one plain scenario several times, call
`expand_scenario_cycles(context)` from `before_all()` and tag the scenario with
`@cycling(N)`. Each replay keeps its own scenario hooks, context layer, and
report entry.

### Logging

If your config exposes a path object such as `test_log_path`, the recommended
default is one persistent test log:

```python
from behave_toolkit import configure_test_logging


def before_all(context):
    install(context, CONFIG_PATH)
    context.test_logger = configure_test_logging(context.test_log_path)
```

If that one file is enough, stop there. If you later need several named outputs,
the optional `logging:` section plus `configure_loggers(context)` can
materialize them from YAML.

### Step documentation

To generate a technical reference site from a consumer Behave project:

```bash
behave-toolkit-docs --features-dir features --output-dir docs/behave-toolkit
python -m sphinx -b html docs/behave-toolkit docs/_build/behave-toolkit
```

The generated pages include grouped step catalogs, one page per step
definition, one page per custom parse type, and links from typed parameters
back to their type pages.

If your feature files use `{{var:name}}`, pass the same toolkit config to the
docs generator so example matching sees the substituted text:

```bash
behave-toolkit-docs \
  --features-dir features \
  --output-dir docs/behave-toolkit \
  --config-path features/behave-toolkit.yaml
```

## Project documentation

Build the main project documentation locally with:

```bash
pip install -e .
python -m sphinx -W --keep-going -b html docs docs/_build/html
```

A dedicated GitHub Actions workflow builds this site on pull requests and
deploys it to GitHub Pages from `main`.

The workflow always validates the docs build. Deployment starts automatically
after a one-time GitHub setup in `Settings > Pages`: set
`Build and deployment > Source` to `GitHub Actions`.

## Releasing

Releases are automated with `.github/workflows/release.yml`.

- release preparation starts from a short-lived branch named `release/X.Y.Z`
- pushing that branch prepares or updates a release PR that targets `main`
- the release PR updates `CHANGELOG.md` and the package version metadata
- after the PR lands on `main`, the workflow finalizes the tag, GitHub release,
  package artifacts, and PyPI publication
- the workflow stays dormant until you set the repository variable
  `ENABLE_RELEASE_PLEASE=true`

For the first public release, create `release/0.1.0`, let the workflow open the
release PR, then review that generated `CHANGELOG.md` entry manually before
merging so the first public notes read like a curated initial release rather
than raw bootstrap history.

If you also set `ENABLE_RELEASE_AUTOMERGE=true`, the workflow will enable
auto-merge for release PRs after `0.1.0`. Keep the first release manual.

Repository setup for the release workflow:

- set the repository variable `ENABLE_RELEASE_PLEASE=true` only after the
  release workflow is actually configured
- optionally set `ENABLE_RELEASE_AUTOMERGE=true` after enabling repository
  auto-merge and deciding that non-initial releases may merge automatically
- enable `Settings > Actions > General > Allow GitHub Actions to create and approve pull requests`
- enable repository auto-merge if you want later release PRs to merge by
  themselves once checks pass
- configure a PyPI Trusted Publisher for the `Release` workflow before the first publish
- optionally add a `RELEASE_PLEASE_TOKEN` secret if you also want CI workflows to run on Release Please PRs

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
