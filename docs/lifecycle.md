# Lifecycle hooks

[<- Back to home](index.md)

`behave-toolkit` keeps Behave's execution model explicit: helpers belong in the same hooks you would already use by hand.

## Timing overview

| When | Helper | Why |
| --- | --- | --- |
| module import time | `configure_parsers(CONFIG_PATH)` | Behave custom types must be registered before step modules are imported. |
| `before_all` | `install(context, CONFIG_PATH)` | Load config, validate it, attach the manager, and activate `global` objects by default. |
| `before_all` | `substitute_feature_variables(context)` | Replace `{{var:name}}` placeholders inside already-parsed feature models. Call this after `install()`. |
| `before_all` | `expand_scenario_cycles(context)` | Expand `@cycling(N)` tags on plain scenarios before any feature runs. Call this after `install()`, and after feature-variable substitution if you use both. |
| `before_all` | `configure_test_logging(...)` or `configure_loggers(context)` | Start logging once global path objects already exist. |
| `before_feature` | `activate_feature_scope(context)` | Create feature-scoped objects and register their cleanup. |
| `before_scenario` | `activate_scenario_scope(context)` | Create scenario-scoped objects and register their cleanup. |

## Recommended full hook template

```python
from pathlib import Path

from behave_toolkit import (
    activate_feature_scope,
    activate_global_scope,
    activate_scenario_scope,
    configure_loggers,
    configure_parsers,
    configure_test_logging,
    expand_scenario_cycles,
    install,
    substitute_feature_variables,
)

CONFIG_PATH = Path(__file__).with_name("behave-toolkit")

# Optional import-time setup.
configure_parsers(CONFIG_PATH)


def before_all(context):
    install(context, CONFIG_PATH)

    # Optional helpers. Keep only the lines your suite actually needs.
    substitute_feature_variables(context)
    expand_scenario_cycles(context)
    context.test_logger = configure_test_logging(context.test_log_path)
    # configure_loggers(context)


def before_feature(context, feature):
    del feature
    activate_feature_scope(context)


def before_scenario(context, scenario):
    del scenario
    activate_scenario_scope(context)
```

If you want to make the `global` lifetime more explicit, the advanced path is:

```python
def before_all(context):
    install(context, CONFIG_PATH, activate_global=False)
    activate_global_scope(context)
```

The lifetime stays the same either way: created once for the whole run, destroyed once at the very end.

## Supported scopes

| Scope | Typical hook | Lifetime |
| --- | --- | --- |
| `global` | `before_all` | Entire test run |
| `feature` | `before_feature` | One feature file |
| `scenario` | `before_scenario` | One scenario |

The current release only supports these three runtime scopes.

## Global scope behavior

`global` is the run-wide scope:

- with the default flow, `install(context, ...)` activates it from `before_all()`
- with the explicit flow, call `install(..., activate_global=False)` and then `activate_global_scope(context)` from `before_all()`
- cleanup runs automatically when Behave closes the test-run layer at the very end of the suite

That makes `global` a good fit for shared clients, suite-wide artifact directories, or other resources that should be created once and destroyed once.

## Cleanup model

The toolkit relies on Behave's cleanup layers through `context.add_cleanup(...)` so that teardown follows the same scope boundaries as object creation.

- objects are created lazily within the requested scope
- cleanup is registered immediately after creation
- teardown runs in reverse order of creation inside the Behave layer

## Manager inspection and debugging

By default the toolkit manager is attached to `context.toolkit`. Useful methods include:

| Method | Purpose |
| --- | --- |
| `context.toolkit.list_objects()` | List configured object names. |
| `context.toolkit.list_loggers()` | List configured logger names. |
| `context.toolkit.spec(name)` | Inspect the normalized spec for one object. |
| `context.toolkit.instance(name)` | Fetch an already-active object instance. |
| `context.toolkit.logger(name)` | Fetch an active configured logger. |
| `context.toolkit.objects_for_scope(scope)` | List specs assigned to one scope. |
| `context.toolkit.active_objects(scope)` | Inspect currently active instances for a scope. |

Example debugging snippet:

```python
def before_scenario(context, scenario):
    activate_scenario_scope(context)
    print("Configured objects:", context.toolkit.list_objects())
    print("Scenario objects:", context.toolkit.active_objects("scenario"))
    print("report_path spec:", context.toolkit.spec("report_path"))
```

That is especially helpful when you are tracking down unexpected names, missing path objects, or scope-ordering mistakes.

## Logging helpers and hook order

For logging, the recommended default is `configure_test_logging(log_path)` when you just want one persistent `test-run.log`-style file.

Reach for `configure_loggers(context)` only when you want several named outputs defined in YAML.

When you do use `configure_loggers(context)`, call it after global objects are active:

- with the default `install(context, config_path)` flow, that means immediately after `install()`
- with the explicit `activate_global=False` flow, call `activate_global_scope(context)` first and then `configure_loggers(context)`

## Integration failures the docs assume you will meet eventually

Two public error types matter most while wiring hooks:

- `ConfigError` for YAML loading, validation, references, and import problems
- `IntegrationError` for namespace collisions, missing installation, repeated activation, or calling helpers in the wrong hook order

```{note}
If you call `activate_feature_scope()` or `activate_scenario_scope()` before `install()`, the error message explicitly tells you to wire `install(context, ...)` from `before_all()`.
```

If you hit one of those failures, go straight to [Troubleshooting](troubleshooting.md).
