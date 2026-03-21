# Step documentation

[<- Back to home](index.md)

`behave-toolkit` can generate a Sphinx-ready technical reference from a Behave
project. This is aimed at the *consumer* suite you are testing, not at the
toolkit repository itself.

After a plain `pip install behave-toolkit`, you can:

1. use the Python API in `features/environment.py` for lifecycle/config wiring
2. run `behave-toolkit-docs` to generate documentation sources
3. run `python -m sphinx ...` to build the final HTML site

## Generate the sources

```bash
behave-toolkit-docs --features-dir features --output-dir docs/behave-toolkit
```

The generated output includes:

- a Sphinx/MyST scaffold with `conf.py`
- grouped keyword pages (`Given`, `When`, `Then`, `Generic`)
- one page per step definition
- one page per custom parse type
- links from typed parameters back to their type pages
- feature-file examples attached to matching steps
- enum values when a converter exposes an enum return annotation
- structured Google-style `Args`, `Returns`, and `Raises` sections when present

## Build the final HTML site

```bash
python -m sphinx -b html docs/behave-toolkit docs/_build/behave-toolkit
```

Typical end-to-end flow in a consumer project:

```bash
pip install behave-toolkit
behave-toolkit-docs --features-dir features --output-dir docs/behave-toolkit
python -m sphinx -b html docs/behave-toolkit docs/_build/behave-toolkit
```

## Recommended type-registration pattern

Custom parse types should be registered at import time, before step loading.
The safest pattern is:

1. define converters in a dedicated support module
2. call `register_type(...)` from `features/environment.py`
3. import the resulting types in your step modules if you want annotations

This keeps both Behave itself and the generated documentation aligned.

## Documentation-friendly step design

The generator works best when steps are:

- annotated with meaningful parameter types
- documented with concise summaries in the first paragraph
- backed by real `.feature` examples in the suite
- using Google-style docstrings when you want richer parameter/return/raise
  sections in the output

```{tip}
Even if your step library grows large, generated reference pages stay readable
when the first paragraph of each docstring is a clean one-line summary.
```
