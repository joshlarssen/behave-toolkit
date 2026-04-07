"""Prepare the Sphinx multiversion output for GitHub Pages."""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


def _version_key(path: Path) -> tuple[int, int, int]:
    return tuple(int(part) for part in path.name.split("."))


def _write_root_redirect(build_dir: Path) -> None:
    (build_dir / "index.html").write_text(
        """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta http-equiv="refresh" content="0; url=./latest/">
    <meta name="robots" content="noindex">
    <title>behave-toolkit documentation</title>
  </head>
  <body>
    <p>Redirecting to the latest documentation version...</p>
    <p><a href="./latest/">Open the latest documentation</a></p>
  </body>
</html>
""",
        encoding="utf-8",
    )


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit("Usage: prepare_versioned_docs.py <build-dir>")

    build_dir = Path(argv[1]).expanduser().resolve()
    if not build_dir.is_dir():
        raise SystemExit(f"Build directory '{build_dir}' does not exist.")

    release_dirs = sorted(
        [
            path
            for path in build_dir.iterdir()
            if path.is_dir() and VERSION_PATTERN.fullmatch(path.name)
        ],
        key=_version_key,
    )
    if not release_dirs:
        raise SystemExit(
            f"Build directory '{build_dir}' does not contain any release subdirectories."
        )

    latest_dir = build_dir / "latest"
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    shutil.copytree(release_dirs[-1], latest_dir)

    (build_dir / ".nojekyll").write_text("", encoding="utf-8")
    _write_root_redirect(build_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
