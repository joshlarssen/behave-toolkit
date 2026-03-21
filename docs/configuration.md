# Configuration model

[<- Back to home](index.md)

## Root structure

| Key | Type | Purpose |
| --- | --- | --- |
| `version` | `int` | Config format version. Defaults to `1`. |
| `variables` | mapping | Reusable literal values referenced with `$var`. |
| `objects` | mapping | Named object definitions managed by the toolkit. |
| `parsers` | mapping | Optional Behave parser/type helpers configured at import time. |

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
  event_log: events.log
  report_name: report.json

objects:
  session_state:
    factory: my_project.runtime.SessionState
    scope: global
    kwargs:
      log_path:
        $var: event_log
    cleanup: close

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
