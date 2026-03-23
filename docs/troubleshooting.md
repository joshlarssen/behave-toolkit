# Troubleshooting

[<- Back to home](index.md)

This page collects the most common adoption and integration problems. Most failures fall into one of three buckets:

- config validation (`ConfigError`)
- hook ordering or context usage (`IntegrationError`)
- docs-generation or parser-registration alignment issues

## First question: is each helper in the right place?

| Helper | Where it belongs |
| --- | --- |
| `configure_parsers(CONFIG_PATH)` | module import time in `environment.py` |
| `install(context, CONFIG_PATH)` | `before_all()` |
| `substitute_feature_variables(context)` | `before_all()`, after `install()` |
| `expand_scenario_cycles(context)` | `before_all()`, after `install()` |
| `configure_test_logging(...)` | usually `before_all()`, after `install()` |
| `configure_loggers(context)` | usually `before_all()`, after `install()` |
| `activate_feature_scope(context)` | `before_feature()` |
| `activate_scenario_scope(context)` | `before_scenario()` |

If a helper is in the wrong place, fix that first before chasing anything more subtle.

## `ConfigError`: the config failed before runtime started

Typical causes:

- the `factory` import path is wrong
- a `$ref` points at an unknown object
- a `$var` points at an unknown variable
- an object depends on a narrower scope
- duplicate names exist across config files

### Factory import problems

Symptom: `install()` fails because a factory or converter is not importable.

Checks:

- confirm the import path matches a real Python symbol
- confirm the module is importable from the environment where Behave runs
- if it is your own project code, confirm that the project layout makes that module visible to Python

### Unknown `$ref` or `$var`

Symptom: config loading says that a referenced object or variable does not exist.

Checks:

- spelling matters; object and variable names are exact
- when you use a config directory, confirm the relevant file is inside the configured directory
- remember that duplicate names fail fast instead of silently overriding one another

### Wider-to-narrower scope dependency

Symptom: validation says an object cannot depend on an object from a narrower scope.

Mental model:

- `global` can only depend on `global`
- `feature` can depend on `global` or `feature`
- `scenario` can depend on `global`, `feature`, or `scenario`

If the dependency direction points the other way, move the dependent object to a narrower scope or extract the shared value into a root variable.

## `IntegrationError`: the config was valid, but the Behave wiring is wrong

Typical causes:

- `activate_feature_scope()` or `activate_scenario_scope()` was called before `install()`
- a helper was called from the wrong hook
- a reserved or duplicate context name collided with something else
- a helper that should only run once was called twice

### Forgot `install()` or called it too late

Symptom: activation helpers complain that the toolkit is not installed.

Fix: call `install(context, CONFIG_PATH)` from `before_all()` before any scope-activation or optional runtime helper.

### Scope already active

Symptom: activation says the scope is already active.

Fix: call `activate_feature_scope(context)` once from `before_feature()` and `activate_scenario_scope(context)` once from `before_scenario()`.

### Context-name collisions

Symptom: validation or logger configuration says a context name is already used.

Fix: rename `inject_as` (or the default object name) so it does not collide with:

- another object in the same scope
- a configured logger
- the manager namespace such as `toolkit`

## Feature-variable issues

### `{{var:name}}` placeholders are still visible at runtime

Symptom: step text or scenario names still contain `{{var:...}}`.

Fix: call `substitute_feature_variables(context)` from `before_all()` after `install()`.

### Unknown feature variable

Symptom: substitution says a variable name is unknown.

Fix: define it in the root `variables:` section of the toolkit config. Feature placeholders do not read environment variables directly.

### Unsupported feature-variable value type

Symptom: substitution says the resolved value type is unsupported.

Fix: `{{var:name}}` placeholders must resolve to a scalar string, number, or boolean. Move structured values back into YAML object fields instead.

## Parser helpers are not taking effect

Symptom: a custom type works in one environment but not when Behave imports steps, or docs generation misses the type.

Fixes:

- call `configure_parsers(CONFIG_PATH)` at module import time, not inside `before_all()`
- if you use a converter-based type, provide `pattern` unless the converter already exposes the necessary parse metadata
- confirm the same config path is used for both runtime and docs generation

## Scenario cycling problems

### `@cycling(...)` on `Scenario Outline`

Symptom: scenario cycling rejects the scenario.

Fix: `@cycling(N)` only works on plain `Scenario`. Use `Examples` for `Scenario Outline`.

### Invalid cycle tag syntax

Symptom: `@cycling(foo)` or similar fails.

Fix: use `@cycling(3)` with a positive integer.

## Generated step docs are missing examples or types

### No examples attached to steps

Checks:

- confirm `--features-dir` points at the correct Behave project
- if your feature files use `{{var:name}}`, pass `--config-path`
- confirm your suite actually contains matching feature-step usages

### Custom types missing from generated docs

Checks:

- confirm `configure_parsers(CONFIG_PATH)` runs at import time in `environment.py`
- confirm the parser config is in the file or directory you pass to `configure_parsers(...)`

## Use the manager to inspect the current state

The manager attached at `context.toolkit` is often the fastest way to see what the toolkit thinks is configured.

```python
def before_scenario(context, scenario):
    activate_scenario_scope(context)
    print("Configured objects:", context.toolkit.list_objects())
    print("Configured loggers:", context.toolkit.list_loggers())
    print("Scenario objects:", context.toolkit.active_objects("scenario"))
    print("report_path spec:", context.toolkit.spec("report_path"))
```

Useful methods to remember:

- `list_objects()`
- `list_loggers()`
- `spec(name)`
- `instance(name)`
- `logger(name)`
- `objects_for_scope(scope)`
- `active_objects(scope)`

## Local validation commands

When in doubt, run the same validation commands the repository uses:

```bash
python -m unittest discover -s tests -v
python -m mypy src tests test_support.py
python -m pylint src tests test_support.py
python -m compileall src tests test_support.py
python -m sphinx -W --keep-going -b html docs docs/_build/html
```

If the problem persists after that, capture the exact config snippet, the hook wiring, and the full error message. Those three pieces usually make the root cause obvious.
