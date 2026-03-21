from pathlib import Path

project = "behave-toolkit"
html_title = "behave-toolkit"
extensions = [
    "myst_parser",
    "sphinx_design",
]
source_suffix = {".md": "markdown"}
root_doc = "index"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
templates_path = []
html_static_path = ["_static"]
html_css_files = ["behave-toolkit-docs.css"]
html_theme = "furo"
myst_heading_anchors = 3
myst_enable_extensions = ["colon_fence", "deflist"]

# Keep the config file import-safe for Sphinx on every runner.
DOCS_ROOT = Path(__file__).resolve().parent
