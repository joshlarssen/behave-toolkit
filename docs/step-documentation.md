# Step documentation

[<- Back to home](index.md)

`behave-toolkit` can generate a Sphinx-ready technical reference from a downstream Behave project. This is for your own Behave suite, not for the `behave-toolkit` repository itself.

## When to use this feature

Reach for generated step docs when:

- your step library is large enough that people struggle to discover existing steps
- you want one searchable place for step patterns, type information, and source links
- you want examples from real `.feature` files attached to step reference pages

Skip this feature if your suite is still small and grep is enough. It becomes most useful once step discovery has become a real cost for the team.

## What the generator produces

The generated output includes:

- a Sphinx/MyST scaffold with `conf.py`
- grouped keyword pages (`Given`, `When`, `Then`, `Generic`)
- one page per step definition
- one page per custom parse type
- links from typed parameters back to their type pages
- feature-file examples attached to matching steps
- enum values when a converter exposes an enum return annotation
- structured Google-style `Args`, `Returns`, and `Raises` sections when present

## End-to-end CLI flow

Generate the docs sources:

```bash
behave-toolkit-docs --features-dir features --output-dir docs/behave-toolkit
```

If your feature files use `{{var:name}}`, pass the same toolkit config so example matching sees the substituted text:

```bash
behave-toolkit-docs --features-dir features --output-dir docs/behave-toolkit --config-path features/behave-toolkit
```

Then build the final HTML site:

```bash
python -m sphinx -b html docs/behave-toolkit docs/_build/behave-toolkit
```

Typical end-to-end flow in a consumer project:

```bash
pip install behave-toolkit
behave-toolkit-docs --features-dir features --output-dir docs/behave-toolkit
python -m sphinx -b html docs/behave-toolkit docs/_build/behave-toolkit
```

## CLI options

| Option | Default | Purpose |
| --- | --- | --- |
| `--features-dir` | `features` | Behave features directory to inspect. |
| `--output-dir` | `docs/behave-toolkit` | Directory where generated Markdown pages should be written. |
| `--site-title` | `Behave step documentation` | Title shown on the generated root page. |
| `--max-examples` | `3` | Maximum number of example step usages recorded per step definition. |
| `--config-path` | unset | Optional toolkit config used to resolve `{{var:name}}` placeholders while matching feature examples. |

## Python API

If you prefer to drive the generator from Python, the public API is:

```python
from behave_toolkit import generate_step_docs

result = generate_step_docs(
    "features",
    "docs/behave-toolkit",
    site_title="QA Step Catalog",
    max_examples_per_step=3,
    config_path="features/behave-toolkit",
)
print(result.step_count, result.type_count)
```

`generate_step_docs(...)` returns a `DocumentationResult` with the output path and the number of generated step and type pages.

## Keep parser registration aligned

Custom parse types should still be configured at import time, before step loading.

Recommended pattern:

1. define converters or enums in a dedicated support module
2. declare them in your toolkit config under `parsers:`
3. call `configure_parsers(CONFIG_PATH)` from `features/environment.py`
4. run `behave-toolkit-docs` against the same project

This keeps both Behave itself and the generated documentation aligned.

## Writing doc-friendly steps

The generator works best when steps are:

- annotated with meaningful parameter types
- documented with a concise summary in the first paragraph
- backed by real `.feature` examples in the suite
- using Google-style docstrings when you want richer parameter, return, and raise sections in the output

```{tip}
Even for large suites, generated pages stay readable when the first paragraph of each docstring is a clean one-line summary.
```

## Feature variables and example matching

If your feature files use `{{var:name}}`, the generator needs the same toolkit config that your Behave run uses.

Otherwise the parsed example text will still contain placeholders and may not match the real step patterns.

That is why the CLI exposes `--config-path` and the Python API exposes `config_path=...`.

## Troubleshooting hints

- If no examples are attached to step pages, confirm that `--features-dir` points at the correct Behave project.
- If examples still do not match and your features use `{{var:name}}`, pass `--config-path`.
- If custom types are missing, confirm that `configure_parsers(CONFIG_PATH)` runs at import time in `environment.py`.

For broader debugging help, see [Troubleshooting](troubleshooting.md).
