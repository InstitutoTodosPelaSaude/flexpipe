# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import sys
from pathlib import Path

# Add parent directory to path to read pyproject.toml
sys.path.insert(0, str(Path(__file__).parent.parent))

# flexpipe uses dynamic versioning via hatch-vcs, so read from importlib.metadata
try:
    from importlib.metadata import version as _v
    release = _v("flexpipe")
except Exception:
    release = "0.0.0"

version = release

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "flexpipe"
copyright = "Instituto Todos pela Saúde"
author = "Instituto Todos pela Saúde"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "myst_parser",
    "sphinx_copybutton",
    "sphinxcontrib.mermaid",
]

# MyST Parser configuration for Markdown support
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
    "html_admonition",
    "html_image",
    "strikethrough",
    "substitution",
    "tasklist",
]

myst_heading_anchors = 3

# Source file suffixes
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# Language settings
language = "en"

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

# Theme options
html_theme_options = {
    "logo_only": False,
    "prev_next_buttons_location": "bottom",
    "style_external_links": True,
    "style_nav_header_background": "#2980B9",
    # Toc options
    "collapse_navigation": False,
    "sticky_navigation": True,
    "navigation_depth": 4,
    "includehidden": True,
    "titles_only": False,
}

# Custom CSS
html_css_files = [
    "custom.css",
]

# -- Options for internationalization ----------------------------------------
locale_dirs = ["locale/"]
gettext_compact = False
