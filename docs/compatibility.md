# Compatibility and support

[<- Back to home](index.md)

This page makes the current support story explicit for adopters and contributors.

## Support summary

| Area | Current status | Source of truth |
| --- | --- | --- |
| Python runtime | `3.10`, `3.11`, `3.12` supported | `pyproject.toml` and CI matrix |
| Behave dependency | `behave>=1.3.3` | `pyproject.toml` |
| Operating systems validated in CI | Ubuntu and Windows | `.github/workflows/ci.yml` |
| Static analysis baseline | Python `3.10` on Ubuntu | `.github/workflows/ci.yml` |
| Docs build baseline | Python `3.10` on Ubuntu | `.github/workflows/docs.yml` and release verification |

Python versions earlier than `3.10` are not supported by the current release line.

## What CI validates today

The repository currently validates:

- static analysis (`mypy`, `pylint`, `compileall`) on Ubuntu with Python `3.10`
- unit tests on Ubuntu and Windows with Python `3.10`, `3.11`, and `3.12`
- Sphinx documentation builds on Ubuntu with Python `3.10`
- release verification on the release tag with Python `3.10`

That means support is not just declared in packaging metadata; it is also exercised continuously in GitHub Actions.

## Behave version expectations

The package declares `behave>=1.3.3`.

In practice, CI installs the current resolver-selected Behave release that satisfies that requirement on each supported Python version. The project does not currently publish a separate exhaustive Behave-version matrix beyond that declared minimum.

If your own suite needs a tighter Behave pin, keep that pin in the downstream consumer project and validate it there.

## Documentation toolchain on Python 3.10+

The main docs and the generated step-doc flow are available from the same `pip install behave-toolkit` command.

On Python `3.10`, packaging resolves a Python-3.10-compatible documentation stack automatically. On Python `3.11+`, newer Sphinx releases are used.

The key point for users is simple: the docs workflow and generated-docs commands are part of the supported experience on the same Python range as the runtime helpers.

## How support changes should be communicated

Any future support change should update all of the following together:

- `project.requires-python` in `pyproject.toml`
- Python classifiers in `pyproject.toml`
- the CI matrix in `.github/workflows/ci.yml`
- the docs workflow and release verification workflow if needed
- this page and the release notes / changelog

Support should never change silently in metadata alone.

## Local verification commands

The repository uses these validation commands locally and in CI:

```bash
python -m unittest discover -s tests -v
python -m mypy src tests test_support.py
python -m pylint src tests test_support.py
python -m compileall src tests test_support.py
python -m sphinx -W --keep-going -b html docs docs/_build/html
```

If you are evaluating compatibility in a downstream project, run the relevant subset of those checks in the Python and Behave versions you care about.
