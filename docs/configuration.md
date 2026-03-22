# Configuration model

[<- Back to home](index.md)

## Root structure

| Key | Type | Purpose |
| --- | --- | --- |
| `version` | `int` | Config format version. Defaults to `1`. |
| `variables` | mapping | Reusable literal values referenced with `$var`. |
| `objects` | mapping | Named object definitions managed by the toolkit. |
| `parsers` | mapping | Optional Behave parser/type helpers configured at import time. |
| `logging` | mapping | Optional named logger definitions configured from `before_all()`. |

Most suites can start with just `version`, `variables`, and `objects`.
`parsers` and `logging` are optional layers for the cases where Behave setup has
started to become repetitive.

## File or directory input

`install(...)` and `configure_parsers(...)` accept either:

- one YAML file
- or a dedicated config directory

When you pass a directory, `behave-toolkit` loads every `.yaml` / `.yml` file
recursively in deterministic path order and merges the known root sections.

```text
features/
  behave-toolkit/
    00-variables.yaml
    10-parsers.yaml
    20-objects.yaml
    30-logging.yaml
```

Duplicate names across files fail fast. For example, defining the same object or
logger name twice is treated as a config error instead of “last file wins”.

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

## Markers

The config stays explicit by using dedicated markers instead of hidden magic.

| Marker | Purpose |
| --- | --- |
| `$ref` | Reuse another configured object. |
| `$ref` + `attr` | Reuse one attribute path from another object. |
| `$var` | Reuse a root-level variable from the config. |

## Example with references

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

## Validation behavior

`install()` validates the whole config before any object is left attached to the
Behave context. This catches problems early, including:

- invalid scope values
- non-importable factories
- unknown `$ref` targets
- unknown `$var` names
- cycles between object references
- invalid wider-to-narrower scope dependencies

```{tip}
If you want to inject an instance under a shorter or more domain-specific name,
use `inject_as`. Otherwise the toolkit exposes it with the object name.
```

## Parser configuration

The optional `parsers` section configures Behave custom types and the default
step matcher.

| Field | Purpose |
| --- | --- |
| `step_matcher` | Default Behave matcher to use while step modules are imported. |
| `types` | Mapping of custom type names to parser helper specs. |

Each custom type can either reference an existing converter or generate one from
an enum:

| Field | Purpose |
| --- | --- |
| `converter` | Import path to a callable that converts raw text. |
| `enum` | Import path to an `Enum` class. The toolkit builds the converter for you. |
| `pattern` | Regex pattern attached to the converter if it does not already define one. |
| `regex_group_count` | Optional regex group count metadata for advanced parse patterns. |
| `matcher` | Per-type matcher override for registration (`parse` or `cfparse`). |
| `case_sensitive` | Enum helper option controlling case-sensitive lookup. |
| `lookup` | Enum helper mode: `value` or `name`. |

See [Parser helpers](parser-helpers.md) for end-to-end examples.

## Logging configuration

If you only want one persistent `test-run.log`, you can skip `logging:`
entirely and call `configure_test_logging(...)` yourself from `before_all()`.

Use the optional `logging` section when you want multiple named loggers to be
materialized by `configure_loggers(context)` from `before_all()`.

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

`path` supports the same marker style as object arguments:

- `$ref` to a configured object, such as a `pathlib.Path`
- `$ref` + `attr` for one attribute path
- `$var` to reuse a root variable

Logger references are intentionally global in this first version, so configure
them after global objects are active.

- With the default `install(context, CONFIG_PATH)`, global objects are already
  active, so `configure_loggers(context)` can run immediately after `install()`.
- If you use `install(..., activate_global=False)`, call
  `activate_global_scope(context)` first and then `configure_loggers(context)`.
