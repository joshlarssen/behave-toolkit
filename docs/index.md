# behave-toolkit

`behave-toolkit` helps large `behave` suites stay explicit, easier to wire,
and easier to understand. The project currently focuses on configuration-driven
object lifecycles, import-time parser helpers, explicit scope activation, strong
diagnostics, and generated step reference documentation.

```{toctree}
:hidden:
:maxdepth: 2

getting-started
configuration
parser-helpers
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

## What is stable today

- `global`, `feature`, and `scenario` scoped object activation
- YAML-defined factories resolved from your own code, installed packages, or
  the standard library
- config-driven parser helpers with matcher selection and enum shortcuts
- explicit object references with `$ref` and reusable values with `$var`
- fail-fast `ConfigError` and `IntegrationError` messages
- Sphinx-ready step documentation with custom type pages, enum values, feature
  examples, and structured Google-style docstrings

```{note}
`step` scope is intentionally reserved but not implemented yet. The current
production-ready scopes are `global`, `feature`, and `scenario`.
```

## Documentation strategy

This site documents the main `behave-toolkit` package itself.

The package also generates documentation for *consumer* Behave suites via
`behave-toolkit-docs`. That generated output is a separate concern and is
documented in [Step documentation](step-documentation.md).
