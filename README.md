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
- scope normalization
- a lightweight manager attached to the Behave context

The next milestones are expected to add:

- object instantiation and cleanup by scope
- reference resolution between configured objects
- step catalogue generation
- variable interpolation helpers
- optional parser/type helper integrations

## Quick start

Install the package:

```bash
pip install behave-toolkit
```

Create a configuration file:

```yaml
version: 1
objects:
  api_client:
    factory: my_project.clients.ApiClient
    scope: scenario
    kwargs:
      base_url: https://example.test
    cleanup: close
```

Wire it from `features/environment.py`:

```python
from behave_toolkit import install


def before_all(context):
    install(context, "features/behave-toolkit.yaml")
```

After installation, the loaded manager is available on `context.toolkit` by default.

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
python -m compileall src tests
```

Run static analysis:

```bash
python -m mypy src tests
python -m pylint src tests
```

The GitHub Actions CI workflow runs static analysis once on Ubuntu with Python
3.11, then runs the unit tests in a smaller Ubuntu and Windows matrix for
Python 3.11 and 3.12.

