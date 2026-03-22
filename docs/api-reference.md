# API reference

[<- Back to home](index.md)

## Main import surface

```python
from behave_toolkit import (
    ConfigError,
    DocumentationError,
    DocumentationResult,
    IntegrationError,
    LifecycleManager,
    LoggerSpec,
    LoggingConfig,
    ObjectSpec,
    ParserConfig,
    ParserTypeSpec,
    Scope,
    ToolkitConfig,
    ToolkitError,
    activate_feature_scope,
    activate_global_scope,
    activate_scenario_scope,
    activate_scope,
    configure_loggers,
    configure_test_logging,
    configure_parsers,
    expand_scenario_cycles,
    format_cycle_progress,
    generate_step_docs,
    get_cycle_progress,
    install,
    load_config,
    load_yaml_file,
    load_yaml_text,
)
```

## Configuration loading helpers

| API | Purpose |
| --- | --- |
| `load_yaml_file(path)` | Load toolkit config from one YAML file or a config directory. |
| `load_yaml_text(text)` | Load toolkit config from a YAML string. |
| `load_config(raw_mapping)` | Normalize already-loaded mapping data into `ToolkitConfig`. |

## Installation and activation helpers

| API | Purpose | Typical Behave hook |
| --- | --- | --- |
| `install(context, config_path, namespace="toolkit", activate_global=True)` | Load and validate config, attach the manager, and activate global objects. | `before_all` |
| `expand_scenario_cycles(context)` | Expand tagged plain scenarios that use `@cycling(N)` before feature execution starts. | `before_all` |
| `configure_parsers(config_path)` | Configure Behave step matcher defaults and register custom types from YAML. | module import time |
| `configure_test_logging(log_path, logger_name="behave-tests", level="INFO", console=True, console_stream=None, mode="w")` | Configure one dedicated logger for a persistent test-run file plus optional console output. Recommended when one log file is enough. | usually `before_all` |
| `configure_loggers(context, namespace="toolkit")` | Configure all named loggers from the YAML `logging:` section. No-op when no loggers are defined. Use this when you want several named outputs. | usually `before_all` |
| `activate_global_scope(context, namespace="toolkit")` | Explicitly activate global objects. | `before_all` |
| `activate_feature_scope(context, namespace="toolkit")` | Activate feature-scoped objects. | `before_feature` |
| `activate_scenario_scope(context, namespace="toolkit")` | Activate scenario-scoped objects. | `before_scenario` |
| `activate_scope(context, scope, namespace="toolkit")` | Generic wrapper for scope activation. | advanced usage |

```{tip}
The smallest recommended runtime path is `install()` plus the feature/scenario
activation helpers. Add `configure_test_logging()` if you want one persistent
suite log. Reach for `configure_loggers()` only when one file is no longer
enough.
```

## Documentation generation API

| API | Purpose |
| --- | --- |
| `generate_step_docs(features_dir, output_dir, *, site_title="Behave step documentation", max_examples_per_step=3)` | Generate Sphinx-ready step/type reference pages from Python. |
| `DocumentationResult` | Return type exposing `output_dir`, `step_count`, and `type_count`. |

## Cycle inspection helpers

| API | Purpose | Typical use |
| --- | --- | --- |
| `get_cycle_progress(subject)` | Return `(current_cycle, total_cycles)` for a scenario or Behave context. | hook logic or assertions |
| `format_cycle_progress(subject)` | Return a display-ready label like `2/5`. | logging and progress output |

## Manager methods you will usually care about

| Manager method | Purpose |
| --- | --- |
| `list_objects()` | Return configured object names. |
| `list_loggers()` | Return configured logger names from the `logging:` section. |
| `spec(name)` | Return the normalized `ObjectSpec` for one object. |
| `instance(name)` | Return an active instance by name. |
| `logger(name)` | Return one configured active logger by name. |
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
| `LoggerSpec` | One normalized configured logger definition. |
| `LoggingConfig` | Parsed logging-helper section with named logger specs. |
| `ParserTypeSpec` | One configured Behave custom type helper. |
| `ParserConfig` | Parsed parser-helper section with matcher and type specs. |
| `ToolkitConfig` | Parsed root configuration with `variables`, `objects`, `parsers`, and `logging`. |
| `Scope` | Scope enum used across config normalization and activation (`global`, `feature`, `scenario`). |

```{note}
The project intentionally keeps the public API surface small. The main contract
is the set of installation helpers plus the manager attached to the Behave
context.
```
