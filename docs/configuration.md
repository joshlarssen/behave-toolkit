# Configuration model

[<- Back to home](index.md)

The config format is intentionally small: start with `variables` and `objects`, then add `parsers` or `logging` only if your suite really needs those extras.

## Root structure

| Key | Type | Purpose |
| --- | --- | --- |
| `version` | `int` | Config format version. Defaults to `1`. |
| `variables` | mapping | Reusable values referenced with `$var` in YAML or `{{var:name}}` in feature files. |
| `objects` | mapping | Named object definitions managed by the toolkit. |
| `parsers` | mapping | Optional Behave parser/type helpers configured at import time. |
| `logging` | mapping | Optional named logger definitions configured from `before_all()`. |

## When to use each root section

| Section | Use it when... | Typical status |
| --- | --- | --- |
| `variables` | you want reusable literal values such as URLs, file names, or environment labels | common |
| `objects` | you want the toolkit to create, inject, and clean up instances for you | core feature |
| `parsers` | you already have custom Behave types and want to move matcher/type registration into YAML | optional |
| `logging` | you need several named loggers defined from config | optional |

If you only want one persistent `test-run.log`, skip `logging:` and call `configure_test_logging(...)` yourself. That is the recommended starting point for most suites.

## File or directory input

`install(...)` and `configure_parsers(...)` accept either:

- one YAML file
- or a dedicated config directory

When you pass a directory, `behave-toolkit` loads every `.yaml` and `.yml` file recursively in deterministic path order and merges the known root sections.

```text
features/
  behave-toolkit/
    00-variables.yaml
    10-parsers.yaml
    20-objects.yaml
    30-logging.yaml
```

Duplicate names across files fail fast. Defining the same object, parser type, or logger twice is treated as a config error instead of silently letting the last file win.

## Recommended config-directory organization

A simple convention that works well in larger suites is:

- `00-variables.yaml` for root literals and environment labels
- `10-parsers.yaml` for Behave type registration
- `20-objects.yaml` for managed objects and paths
- `30-logging.yaml` only if you really need YAML-defined named loggers

The numbering is not required by the package, but it makes ownership and review easier because the deterministic merge order becomes obvious at a glance.

## Object fields

Each entry in `objects` supports the following fields:

| Field | Required | Purpose |
| --- | --- | --- |
| `factory` | yes | Import path for the callable used to create the object. |
| `scope` | no | One of `global`, `feature`, or `scenario`. Defaults to `scenario`. |
| `args` | no | Positional constructor arguments. |
| `kwargs` | no | Keyword constructor arguments. |
| `cleanup` | no | Method or attribute name called during cleanup. |
| `inject_as` | no | Context attribute name used instead of the object name. |

`factory` can point to:

- code from your own project
- an installed dependency from the active environment
- the Python standard library

## Scope dependency rules

Objects can depend on wider or same-scope objects, but not on narrower scopes.

| Object scope | It may depend on... |
| --- | --- |
| `global` | other `global` objects and root variables |
| `feature` | `global` or `feature` objects, plus root variables |
| `scenario` | `global`, `feature`, or `scenario` objects, plus root variables |

That means:

- a `scenario` object can safely reuse a `feature` or `global` object
- a `feature` object cannot depend on a `scenario` object
- a `global` object cannot depend on `feature` or `scenario` objects

## Context injection and naming

By default, each created object is exposed on the Behave context using its object name.

Example:

```yaml
objects:
  report_path:
    factory: pathlib.Path
    args:
      - reports
      - latest.json
```

becomes `context.report_path`.

If you want a different name, use `inject_as`:

```yaml
objects:
  report_path:
    factory: pathlib.Path
    inject_as: output_file
    args:
      - reports
      - latest.json
```

becomes `context.output_file`.

`context.toolkit` is reserved for the toolkit manager unless you install it under another namespace.

## Markers

The config stays explicit by using dedicated markers instead of hidden magic.

| Marker | Purpose |
| --- | --- |
| `$ref` | Reuse another configured object. |
| `$ref` + `attr` | Reuse one attribute path from another object. |
| `$var` | Reuse a root-level variable from the config. |

## Variables in YAML vs variables in feature files

`behave-toolkit` supports two different but related variable mechanisms:

| Use case | Syntax | Where it is used | Extra helper required? |
| --- | --- | --- | --- |
| reuse a config value inside YAML object or logger fields | `$var` | YAML config | no |
| reuse a config value directly inside Gherkin text | `{{var:name}}` | parsed feature files | yes, call `substitute_feature_variables(context)` |

Feature-file substitution is intentionally stricter than YAML substitution: `{{var:name}}` placeholders must resolve to scalar strings, numbers, or booleans.

## Example with references and variables

```yaml
version: 1
variables:
  report_name: report.json

objects:
  artifacts_path:
    factory: pathlib.Path
    scope: global
    args:
      - artifacts

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

  latest_report_path:
    factory: pathlib.Path
    scope: global
    args:
      - $ref: artifacts_path
      - $var: report_name
```

## Feature-file placeholders

If you want to reuse root variables directly in Gherkin, call `substitute_feature_variables(context)` from `before_all()` after `install()`.

```gherkin
Scenario: Login against {{var:environment_name}}
  Given I open {{var:base_url}}
```

The helper currently rewrites:

- feature, rule, background, and scenario names
- description lines
- step text
- docstrings
- table headings and cells, including `Scenario Outline` example tables

Tags are intentionally not rewritten.

## Parser configuration

The optional `parsers` section configures Behave custom types and the default step matcher.

| Field | Purpose |
| --- | --- |
| `step_matcher` | Default Behave matcher to use while step modules are imported. |
| `types` | Mapping of custom type names to parser helper specs. |

Each custom type can either reference an existing converter or generate one from an enum:

| Field | Purpose |
| --- | --- |
| `converter` | Import path to an existing converter callable. |
| `enum` | Import path to an `Enum` class. The toolkit builds the converter for you. |
| `pattern` | Regex pattern attached to the converter if it does not already define one. |
| `regex_group_count` | Optional regex group metadata for advanced parse patterns. Most users can omit it. |
| `matcher` | Per-type matcher override for registration (`parse` or `cfparse`). |
| `case_sensitive` | Enum helper option controlling case-sensitive lookup. |
| `lookup` | Enum helper mode: `value` or `name`. |

See [Parser helpers](parser-helpers.md) for end-to-end examples.

## Logging configuration

If you only want one persistent `test-run.log`, you can skip `logging:` entirely and call `configure_test_logging(...)` from `before_all()`.

Use the optional `logging` section when you want multiple named loggers to be materialized by `configure_loggers(context)`.

```yaml
logging:
  test_run:
    path:
      $ref: test_log_path
    logger_name: suite-tests
    inject_as: test_logger

  diagnostics:
    path:
      $ref: diagnostics_log_path
    logger_name: suite-diagnostics
    inject_as: diagnostics_logger
    console: false
```

Each logger supports:

| Field | Purpose |
| --- | --- |
| `path` | File path or marker-based value used for the log file. |
| `logger_name` | Optional underlying Python logger name. Defaults to the logger key. |
| `inject_as` | Optional Behave context attribute name for the logger object. |
| `level` | Logging level passed to Python logging. Defaults to `INFO`. |
| `console` | Mirror output to console in addition to the file. Defaults to `true`. |
| `mode` | File open mode, for example `w` or `a`. Defaults to `w`. |

Logger paths support the same marker style as object arguments.

Logger creation is intentionally global in this first version, so call `configure_loggers(context)` only after global objects are active. With the default `install(context, CONFIG_PATH)` flow that means immediately after `install()` is fine.

For the full logging story, see [Logging and diagnostics](logging.md).

## Validation behavior

`install()` validates the whole config before any object is left attached to the Behave context. That catches problems early, including:

- invalid scope values
- non-importable factories
- unknown `$ref` targets
- unknown `$var` names
- cycles between object references
- invalid wider-to-narrower scope dependencies
- conflicting context names for objects or loggers

`substitute_feature_variables()` then validates feature placeholders when you opt into that helper. Unknown names, circular variable references, and non-scalar resolved values fail fast with `IntegrationError`.

```{tip}
If a config change fails, read [Troubleshooting](troubleshooting.md) next. It explains how to diagnose the most common validation and hook-order problems.
```
