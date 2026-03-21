# Step documentation

[<- Back to home](index.md)

`behave-toolkit` can generate a Sphinx-ready technical reference from a Behave
project. This is aimed at the *consumer* suite you are testing, not at the
toolkit repository itself.

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
pip install -e ".[docs]"
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
