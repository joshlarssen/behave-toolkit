# Parser helpers

[<- Back to home](index.md)

`behave-toolkit` can configure Behave custom types from the same YAML file that
already defines your scoped objects. This reduces the usual `environment.py`
boilerplate around:

- `use_step_matcher(...)`
- `register_type(...)`
- `@parse.with_pattern(...)`

## When this runs

Parser helpers must run **at import time**, before Behave imports your step
modules. The recommended pattern is to call `configure_parsers(CONFIG_PATH)` at
module level in `features/environment.py`.

```python
from pathlib import Path

from behave_toolkit import configure_parsers

CONFIG_PATH = Path(__file__).with_name("behave-toolkit.yaml")
configure_parsers(CONFIG_PATH)
```

If the config has no `parsers:` section, the helper is a no-op.

## Example: enum-based type with almost no boilerplate

```yaml
version: 1
parsers:
  step_matcher: cfparse
  types:
    Status:
      enum: support_types.Status
      case_sensitive: false
```

```python
from enum import Enum


class Status(Enum):
    ACTIVE = "active"
    PENDING = "pending"
```

With that config in place, you can use:

```python
@given("I have a {status:Status} account")
def step_have_status_account(context, status: Status) -> None:
    ...
```

The toolkit automatically:

- registers the custom type under the name `Status`
- builds a converter that returns the enum member
- derives the parse pattern from enum values
- keeps the generated step docs in sync with the configured type

## Example: reuse an existing converter function

```yaml
parsers:
  step_matcher: cfparse
  types:
    Priority:
      converter: support_types.parse_priority
      pattern: low|high
```

```python
from enum import Enum


class Priority(Enum):
    LOW = "low"
    HIGH = "high"


def parse_priority(text: str) -> Priority:
    return Priority(text)
```

This lets the config provide the parse pattern, so your Python converter does
not need a `@parse.with_pattern(...)` decorator anymore.

## Advanced fields

| Field | Purpose |
| --- | --- |
| `step_matcher` | Default matcher used while step modules are imported. |
| `converter` | Import path to an existing converter callable. |
| `enum` | Import path to an `Enum` class for auto-generated converters. |
| `pattern` | Explicit regex pattern for the converter. |
| `regex_group_count` | Extra regex metadata for advanced parse patterns. |
| `matcher` | Per-type registration matcher override (`parse` or `cfparse`). |
| `case_sensitive` | Enum-helper option controlling token lookup. |
| `lookup` | Enum-helper mode: `value` or `name`. |

## Documentation integration

Because `configure_parsers(CONFIG_PATH)` runs when `environment.py` is imported,
`behave-toolkit-docs` sees the same configured custom types as your real Behave
suite.

That means the generated type pages still include:

- runtime type information
- enum values
- links from step parameters back to type pages
- generated or handwritten docstrings for the converters
