# Lifecycle hooks

[<- Back to home](index.md)

## Supported scopes

| Scope | Typical hook | Lifetime |
| --- | --- | --- |
| `global` | `before_all` | Entire test run |
| `feature` | `before_feature` | One feature file |
| `scenario` | `before_scenario` | One scenario |

The current release only supports these three runtime scopes.

## Public hook helpers

| Helper | Typical call site | Purpose |
| --- | --- | --- |
| `expand_scenario_cycles(context)` | `before_all` | Expand tagged plain scenarios that use `@cycling(N)` before any feature runs. |
| `install(context, config_path, ...)` | `before_all` | Load the config, validate it, attach the manager, and optionally activate global objects. |
| `activate_global_scope(context, ...)` | `before_all` | Explicitly activate global objects when you disable `activate_global`. |
| `activate_feature_scope(context, ...)` | `before_feature` | Create and expose feature-scoped objects. |
| `activate_scenario_scope(context, ...)` | `before_scenario` | Create and expose scenario-scoped objects. |
| `activate_scope(context, scope, ...)` | advanced usage | Generic scope activation wrapper. |

## Cleanup model

The toolkit relies on Behave's cleanup layers through `context.add_cleanup(...)`
so that cleanup runs with the same scope boundaries as object creation.

- objects are created lazily within the requested scope
- cleanup is registered immediately after creation
- teardown runs in reverse order of creation inside the Behave layer

## Manager inspection

By default the toolkit manager is attached to `context.toolkit`. Useful methods
include:

| Method | Purpose |
| --- | --- |
| `context.toolkit.list_objects()` | List configured object names. |
| `context.toolkit.spec(name)` | Inspect the normalized spec for one object. |
| `context.toolkit.instance(name)` | Fetch an already-active object instance. |
| `context.toolkit.objects_for_scope(scope)` | List the specs assigned to a scope. |
| `context.toolkit.active_objects(scope)` | Inspect currently active instances by scope. |

## Integration failures

Two public error types are especially relevant while wiring hooks:

- `ConfigError` for YAML loading, validation, references, and import problems
- `IntegrationError` for namespace collisions, missing installation, or calling
  activation helpers in the wrong hook order

```{note}
If you call `activate_feature_scope()` or `activate_scenario_scope()` before
`install()`, the error message explicitly tells you to wire `install(context,
...)` from `before_all`.
```
