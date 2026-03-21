# API reference

[<- Back to home](index.md)

## Main import surface

```python
from behave_toolkit import (
    ConfigError,
    IntegrationError,
    LifecycleManager,
    activate_feature_scope,
    activate_global_scope,
    activate_scenario_scope,
    activate_scope,
    install,
)
```

## Installation and activation helpers

| API | Purpose | Typical Behave hook |
| --- | --- | --- |
| `install(context, config_path, namespace="toolkit", activate_global=True)` | Load and validate config, attach the manager, and activate global objects. | `before_all` |
| `activate_global_scope(context, namespace="toolkit")` | Explicitly activate global objects. | `before_all` |
| `activate_feature_scope(context, namespace="toolkit")` | Activate feature-scoped objects. | `before_feature` |
| `activate_scenario_scope(context, namespace="toolkit")` | Activate scenario-scoped objects. | `before_scenario` |
| `activate_scope(context, scope, namespace="toolkit")` | Generic wrapper for scope activation. | advanced usage |

## Manager methods you will usually care about

| Manager method | Purpose |
| --- | --- |
| `list_objects()` | Return configured object names. |
| `spec(name)` | Return the normalized `ObjectSpec` for one object. |
| `instance(name)` | Return an active instance by name. |
| `objects_for_scope(scope)` | List the object specs assigned to one scope. |
| `active_objects(scope)` | Inspect currently active instances for a scope. |

## Public errors

| Error | Meaning |
| --- | --- |
| `ToolkitError` | Common base class for toolkit-specific failures. |
| `ConfigError` | YAML loading or configuration validation failed. |
| `IntegrationError` | Hook wiring or Behave context integration failed. |
| `DocumentationError` | Step documentation generation failed. |

## Related config dataclasses

| Type | Purpose |
| --- | --- |
| `ObjectSpec` | One normalized configured object definition. |
| `ToolkitConfig` | Parsed root configuration with `variables` and `objects`. |
| `Scope` | Scope enum used across config normalization and activation. |

```{note}
The project intentionally keeps the public API surface small. The main contract
is the set of installation helpers plus the manager attached to the Behave
context.
```
