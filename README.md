# behave-toolkit

`behave-toolkit` is an opinionated toolkit for making large `behave` suites easier to configure, understand, and evolve.

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

Run the test suite:

```bash
python -m unittest discover -s tests -v
```

Run a quick syntax validation:

```bash
python -m compileall src tests
```

