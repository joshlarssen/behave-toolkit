# behave-toolkit

`behave-toolkit` helps growing `behave` suites stay explicit, predictable, and easier to maintain.

It keeps `features/environment.py` readable, moves repetitive object wiring into YAML, and adds a small set of opt-in helpers only where large Behave suites usually start to hurt: shared object setup, parser registration, reusable variables, cycle-heavy scenarios, logging, and step-library discovery.

```{toctree}
:hidden:
:maxdepth: 2

getting-started
integration-examples
configuration
lifecycle
parser-helpers
logging
scenario-cycling
step-documentation
compatibility
troubleshooting
api-reference
release-guide
```

::::{grid} 1 1 2 2
:gutter: 2

:::{grid-item-card} Quick start
:link: getting-started
:link-type: doc

Build the smallest working integration in a few minutes.
:::

:::{grid-item-card} Integration examples
:link: integration-examples
:link-type: doc

Copy full files and hook templates for real Behave projects.
:::

:::{grid-item-card} Configuration model
:link: configuration
:link-type: doc

Understand `variables`, `objects`, `$ref`, `$var`, context injection, and config directories.
:::

:::{grid-item-card} Lifecycle hooks
:link: lifecycle
:link-type: doc

See exactly which helper belongs in import time, `before_all`, `before_feature`, and `before_scenario`.
:::

:::{grid-item-card} Logging and diagnostics
:link: logging
:link-type: doc

Start with one persistent test log, then scale to named loggers only if you need them.
:::

:::{grid-item-card} Parser helpers
:link: parser-helpers
:link-type: doc

Move Behave custom type registration into YAML without hiding what is happening.
:::

:::{grid-item-card} Scenario cycling
:link: scenario-cycling
:link-type: doc

Replay one plain scenario with `@cycling(N)` while keeping hooks and reports explicit.
:::

:::{grid-item-card} Step documentation
:link: step-documentation
:link-type: doc

Generate a Sphinx-ready reference site from your downstream Behave step library.
:::

:::{grid-item-card} Compatibility and support
:link: compatibility
:link-type: doc

Check supported Python versions, Behave expectations, and what CI validates today.
:::

:::{grid-item-card} Troubleshooting
:link: troubleshooting
:link-type: doc

Diagnose the most common `ConfigError`, `IntegrationError`, parser, and docs-generation problems.
:::

:::{grid-item-card} API reference
:link: api-reference
:link-type: doc

Quick-reference the public functions, manager surface, and error types exposed by the package.
:::

:::{grid-item-card} Maintainer release guide
:link: release-guide
:link-type: doc

Run the Release Please, GitHub release, and PyPI publishing flow with confidence.
:::
::::

## Choose your path

- If you want the smallest working setup, start with [Quick start](getting-started.md).
- If you want full files you can adapt directly, go to [Integration examples](integration-examples.md).
- If you want the exact config schema and scope rules, read [Configuration model](configuration.md) and [Lifecycle hooks](lifecycle.md).
- If you need version or support details before adopting the package, read [Compatibility and support](compatibility.md).
- If something failed and you want a fix fast, jump to [Troubleshooting](troubleshooting.md).
- If you maintain this repository, keep [Maintainer release guide](release-guide.md) bookmarked.

## What the toolkit gives you today

- file- or directory-based config loading with deterministic YAML merging
- `global`, `feature`, and `scenario` scoped object activation
- YAML-defined factories resolved from your own code, installed packages, or the standard library
- explicit object references with `$ref` and reusable config values with `$var`
- opt-in `{{var:name}}` substitution inside parsed feature files
- config-driven parser helpers with matcher selection and enum shortcuts
- tag-driven scenario cycling with `@cycling(N)`
- a small persistent test logger with `configure_test_logging()`, plus optional YAML-configured named loggers
- Sphinx-ready step documentation with feature examples, typed parameters, and Google-style docstring rendering
- fail-fast `ConfigError`, `IntegrationError`, and `DocumentationError` messages

## Recommended reading order

1. Read [Quick start](getting-started.md) to get one clean integration working.
2. Read [Integration examples](integration-examples.md) if you want copy-paste templates for real suites.
3. Read [Configuration model](configuration.md) and [Lifecycle hooks](lifecycle.md) to understand the core mental model.
4. Add optional layers only when they solve a real problem: [Logging and diagnostics](logging.md), [Parser helpers](parser-helpers.md), [Scenario cycling](scenario-cycling.md), and [Step documentation](step-documentation.md).
5. Use [Compatibility and support](compatibility.md), [Troubleshooting](troubleshooting.md), and [API reference](api-reference.md) as reference pages.

## Project docs vs generated step docs

This site documents the `behave-toolkit` package itself.

The package also generates documentation for downstream Behave suites via `behave-toolkit-docs`. That generated output is a separate concern and is documented in [Step documentation](step-documentation.md).

The published GitHub Pages site is versioned by release, with `latest` pointing
at the newest released documentation set.

```{note}
The currently supported runtime scopes are `global`, `feature`, and `scenario`.
Scenario cycling is orthogonal: it multiplies scenario executions, not object scopes.
```
