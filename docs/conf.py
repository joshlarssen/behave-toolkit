from importlib.util import find_spec
from pathlib import Path
import re

project = "behave-toolkit"
DOCS_ROOT = Path(__file__).resolve().parent


def _project_version() -> str:
    current_ref = globals().get("smv_current_version")
    if isinstance(current_ref, str):
        match = re.fullmatch(r"behave-toolkit-v(?P<version>\d+\.\d+\.\d+)", current_ref)
        if match is not None:
            return match.group("version")

    pyproject_text = (DOCS_ROOT.parent / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(
        r'(?ms)^\[project\].*?^version\s*=\s*"(?P<version>[^"]+)"',
        pyproject_text,
    )
    if match is None:
        raise RuntimeError("Could not determine the project version from pyproject.toml.")
    return match.group("version")


def _version_sort_key(name: str) -> tuple[int, int, int]:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)$", name)
    if match is None:
        return (-1, -1, -1)
    return tuple(int(part) for part in match.groups())


def _version_label(name: str) -> str:
    if name.startswith("behave-toolkit-"):
        return name[len("behave-toolkit-") :]
    return name


def _sort_versions(items: list[object]) -> list[object]:
    return sorted(
        items,
        key=lambda item: _version_sort_key(getattr(item, "name", str(item))),
        reverse=True,
    )


release = _project_version()
version = release
html_title = "behave-toolkit"
extensions = ["myst_parser", "sphinx_design"]
if find_spec("sphinx_multiversion") is not None:
    extensions.insert(0, "sphinx_multiversion")

source_suffix = {".md": "markdown"}
root_doc = "index"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
templates_path = ["_templates"]
html_static_path = ["_static"]
html_css_files = ["behave-toolkit-docs.css"]
html_theme = "furo"
myst_heading_anchors = 3
myst_enable_extensions = ["colon_fence", "deflist"]

html_baseurl = "https://joshlarssen.github.io/behave-toolkit/"
html_sidebars = {
    "**": [
        "sidebar/brand.html",
        "sidebar/search.html",
        "sidebar/scroll-start.html",
        "versioning.html",
        "sidebar/navigation.html",
        "sidebar/ethical-ads.html",
        "sidebar/scroll-end.html",
        "sidebar/variant-selector.html",
    ]
}

# Publish released docs only. Release tags are named `behave-toolkit-vX.Y.Z`.
smv_tag_whitelist = r"^behave-toolkit-v\d+\.\d+\.\d+$"
smv_branch_whitelist = r"^$"
smv_remote_whitelist = None
smv_released_pattern = r"^refs/tags/behave-toolkit-v\d+\.\d+\.\d+$"
smv_outputdir_format = "{config.release}"


def _register_template_filters(app: object) -> None:
    templates = app.builder.templates.environment.filters
    templates["version_label"] = _version_label
    templates["version_sort"] = _sort_versions


def setup(app: object) -> None:
    app.connect("builder-inited", _register_template_filters)
