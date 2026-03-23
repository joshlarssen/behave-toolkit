# Logging and diagnostics

[<- Back to home](index.md)

`behave-toolkit` intentionally keeps logging small and explicit. Start with one persistent suite log. Move to YAML-defined named loggers only when one file is no longer enough.

## Choose the smallest thing that works

| Need | Recommended tool |
| --- | --- |
| one persistent `test-run.log` file | `configure_test_logging(...)` |
| several named loggers with config-owned paths | YAML `logging:` section plus `configure_loggers(context)` |
| readable cycle progress messages | `format_cycle_progress(...)` or `get_cycle_progress(...)` |

## Recommended default: one persistent suite log

Create a path object in your config:

```yaml
objects:
  artifacts_path:
    factory: pathlib.Path
    scope: global
    args:
      - artifacts

  test_log_path:
    factory: pathlib.Path
    scope: global
    args:
      - $ref: artifacts_path
      - test-run.log
```

Then wire the logger from `before_all()`:

```python
from pathlib import Path

from behave_toolkit import configure_test_logging, install

CONFIG_PATH = Path(__file__).with_name("behave-toolkit.yaml")


def before_all(context):
    install(context, CONFIG_PATH)
    context.test_logger = configure_test_logging(context.test_log_path)
```

`configure_test_logging(...)` deliberately does a few simple things well:

- resolves the chosen path and creates parent directories if needed
- writes file output in UTF-8
- optionally mirrors the same messages to console
- resets existing handlers for that logger name so repeated local runs stay predictable

## Upgrade path: named loggers from YAML

Use YAML-defined loggers when you want multiple named outputs, for example one suite log and one diagnostics log.

```yaml
objects:
  diagnostics_log_path:
    factory: pathlib.Path
    scope: global
    args:
      - $ref: artifacts_path
      - diagnostics.log

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

```python
from pathlib import Path

from behave_toolkit import configure_loggers, install

CONFIG_PATH = Path(__file__).with_name("behave-toolkit.yaml")


def before_all(context):
    install(context, CONFIG_PATH)
    configure_loggers(context)
```

`configure_loggers(context)` should run once from `before_all()`, after global objects are active.

## Logging cycle progress

Scenario cycling becomes easier to follow if you log the cycle label in `before_scenario()`.

```python
from behave_toolkit import activate_scenario_scope, format_cycle_progress


def before_scenario(context, scenario):
    activate_scenario_scope(context)
    progress = format_cycle_progress(scenario)
    if progress is None:
        context.test_logger.info("%s", scenario.name)
    else:
        context.test_logger.info("Cycle %s -> %s", progress, scenario.name)
```

Use `get_cycle_progress(...)` instead when you want the raw `(current_cycle, total_cycles)` tuple for assertions or your own formatting.

## Runtime inspection

The manager gives you a lightweight way to inspect configured logging state:

```python
def before_all(context):
    install(context, CONFIG_PATH)
    configure_loggers(context)
    print(context.toolkit.list_loggers())
    print(context.toolkit.logger("test_run"))
```

## Practical recommendations

- Start with `configure_test_logging(...)` unless you already know you need more than one log file.
- Keep logger paths as managed objects when you want them to be easy to reuse elsewhere in the suite.
- Treat YAML-defined named loggers as a scaling tool, not the default recommendation.
- Remember that logger config is global in this version of the toolkit.

If your logging setup fails because of duplicate names, missing paths, or hook ordering, see [Troubleshooting](troubleshooting.md).
