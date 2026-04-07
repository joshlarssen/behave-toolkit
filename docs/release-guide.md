# Maintainer release guide

[<- Back to home](index.md)

This page is for maintainers of the `behave-toolkit` repository itself. It documents the release flow that creates the changelog update PR, the GitHub release, and the PyPI publication.

## Release architecture at a glance

The release flow is driven by:

- `.github/workflows/release.yml`
- `release-please-config.json`
- `.release-please-manifest.json`
- `CHANGELOG.md`

The manifest file is part of the workflow state. Keep `.release-please-manifest.json` committed.

## One-time repository setup

Before the release flow can work end to end, make sure the repository is configured like this:

1. Enable `Settings > Actions > General > Allow GitHub Actions to create and approve pull requests`.
2. Set the repository variable `ENABLE_RELEASE_PLEASE=true` when you are ready for the workflow to create release PRs.
3. Optionally set `ENABLE_RELEASE_AUTOMERGE=true` if later release PRs should auto-merge after checks pass.
4. Enable repository auto-merge if you want that workflow option to be effective.
5. Configure a PyPI Trusted Publisher for the `Release` workflow before the first publish.
6. Optionally add a `RELEASE_PLEASE_TOKEN` secret if you want CI workflows to run on Release Please PRs as well.

## How a release is prepared

The workflow supports two entry paths:

- push a branch named `release/X.Y.Z`
- run the `Release` workflow manually with `release_version=X.Y.Z`

In either case, the workflow enters "prepare release PR" mode and asks Release Please to open or update a release PR targeting `main`.

## What to review on the release PR

Before merging the generated release PR, review these points deliberately:

- the version number is the one you intended to release
- `CHANGELOG.md` reads well for external users
- the package metadata and manifest updates look coherent
- normal CI is green on the PR

For the first public release especially, edit or review the generated changelog carefully so it reads like a curated initial release, not like raw bootstrap history.

## What happens after merge

Once the release PR lands on `main`, the same workflow enters "finalize release" mode.

It then:

1. runs Release Please in release mode to create the tag and GitHub release
2. checks out the created tag in the `verify-release` job
3. validates the release tag with:
   - `python -m mypy src tests test_support.py`
   - `python -m pylint src tests test_support.py`
   - `python -m compileall src tests test_support.py`
   - `python -m unittest discover -s tests -v`
   - `python -m sphinx -W --keep-going -b html docs docs/_build/html`
4. builds distributions with `python -m build`
5. validates them with `python -m twine check dist/*`
6. uploads the artifacts to the GitHub release
7. publishes the package to PyPI through Trusted Publishing
8. rebuilds and publishes the versioned GitHub Pages site from released docs tags

The published docs site keeps one directory per released documentation version,
plus a `latest/` alias that points to the newest release.

## First release vs later releases

The workflow intentionally keeps `0.1.0` manual even if auto-merge is enabled. Later releases can use the optional auto-merge path once you trust the automation and the repository settings are in place.

## Post-release checks

After the workflow succeeds, verify all of the following:

- the GitHub tag exists
- the GitHub release exists and contains the built artifacts
- the new package version is visible on PyPI
- the docs site shows the new version and `latest/` points to it
- the changelog on `main` reflects the published release

If the release included user-facing behavior changes, also make sure the docs site and README still reflect the new reality.

## Troubleshooting release problems

### No release PR was created

Check:

- `ENABLE_RELEASE_PLEASE=true` is set
- the event really matches `release/X.Y.Z` or workflow-dispatch input
- GitHub Actions is allowed to create and approve pull requests

### The release PR exists but other workflows did not run on it

If you need CI workflows to run on Release Please PRs, provide `RELEASE_PLEASE_TOKEN` instead of relying only on the default `github.token`.

### GitHub release was created but PyPI publish failed

Check the PyPI Trusted Publisher configuration first. The publish job uses `pypa/gh-action-pypi-publish` with OIDC, so the repository, workflow, and environment must match what PyPI expects.

### The built artifacts look wrong

Reproduce locally with:

```bash
python -m build
python -m twine check dist/*
```

That mirrors the final packaging validation step from the workflow.

## Suggested maintainer habit

Keep the release mechanics boring:

- merge only green release PRs
- read the generated changelog every time
- treat `.release-please-manifest.json` as workflow state, not as disposable noise
- keep this guide updated whenever the workflow changes
