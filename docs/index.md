# behave-toolkit

`behave-toolkit` helps large `behave` suites stay explicit, easier to wire, and
easier to understand.

Start with the small core:

- configure shared objects in YAML
- call `install()` from `before_all()`
- activate `feature` and `scenario` scopes from the matching Behave hooks

Then add optional layers only when you need them: parser helpers, scenario
cycling, generated step docs, or YAML-defined named loggers.

```{toctree}
:hidden:
:maxdepth: 2

getting-started
configuration
parser-helpers
scenario-cycling
lifecycle
step-documentation
api-reference
```

::::{grid} 1 1 2 2
:gutter: 2

:::{grid-item-card} Getting started
:link: getting-started
:link-type: doc

Install the package, create a YAML config, and wire the toolkit into
`features/environment.py`.
:::

:::{grid-item-card} Configuration model
:link: configuration
:link-type: doc

Understand `variables`, `objects`, `$ref`, `$var`, cleanup hooks, and context
injection.
:::

:::{grid-item-card} Lifecycle hooks
:link: lifecycle
:link-type: doc

See how `install()` and the scope activation helpers map onto Behave's hook
order.
:::

:::{grid-item-card} Parser helpers
:link: parser-helpers
:link-type: doc

Move custom type registration, matcher selection, and enum-based parser helpers
into the same YAML config.
:::

:::{grid-item-card} Scenario cycling
:link: scenario-cycling
:link-type: doc

Replay a tagged plain scenario multiple times with `@cycling(N)` while keeping
Behave hooks and reports explicit.
:::

:::{grid-item-card} Step documentation
:link: step-documentation
:link-type: doc

Generate a technical reference site from your own Behave project, including
typed parameters and implementation docstrings.
:::

:::{grid-item-card} API reference
:link: api-reference
:link-type: doc

Quick-reference the public functions, manager surface, and error types exposed
by the package.
:::
::::

## Why this project exists

As a Behave suite grows, three things usually start to hurt:

- object setup logic gets duplicated across hooks and steps
- dependencies become implicit and harder to reason about
- step libraries grow faster than their documentation

`behave-toolkit` is meant to reduce that pressure without hiding Behave's
execution model behind a heavy framework.

## Recommended reading order

1. [Getting started](getting-started.md) for the smallest working integration.
2. [Configuration model](configuration.md) for `objects`, `variables`, `$ref`,
   and `$var`.
3. [Lifecycle hooks](lifecycle.md) for the exact Behave hook mapping.
4. Add [Parser helpers](parser-helpers.md), [Scenario cycling](scenario-cycling.md),
   or [Step documentation](step-documentation.md) only when those problems
   become real in your suite.

## What is stable today

- file- or directory-based config loading with deterministic YAML merging
- `global`, `feature`, and `scenario` scoped object activation
- YAML-defined factories resolved from your own code, installed packages, or
  the standard library
- config-driven parser helpers with matcher selection and enum shortcuts
- tag-driven scenario cycling with `@cycling(N)`
- explicit object references with `$ref` and reusable values with `$var`
- a small persistent test logger with `configure_test_logging()`, plus optional
  YAML-configured named loggers for larger suites
- fail-fast `ConfigError` and `IntegrationError` messages
- Sphinx-ready step documentation with custom type pages, enum values, feature
  examples, and structured Google-style docstrings

```{note}
The currently supported runtime scopes are `global`, `feature`, and `scenario`.
Scenario cycling is orthogonal: it multiplies scenario executions, not object
scopes.
```

## Documentation strategy

This site documents the main `behave-toolkit` package itself.

The package also generates documentation for *consumer* Behave suites via
`behave-toolkit-docs`. That generated output is a separate concern and is
documented in [Step documentation](step-documentation.md).
