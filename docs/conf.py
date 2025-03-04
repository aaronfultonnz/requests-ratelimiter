"""Config file for Sphinx documentation"""

# General information about the project.
exclude_patterns = ["_build"]
master_doc = "index"
needs_sphinx = "5.0"
project = "requests-ratelimiter"
source_suffix = [".rst", ".md"]
templates_path = ["_templates"]

# Sphinx extensions
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx_autodoc_typehints",
    "sphinx_copybutton",
    "myst_parser",
]
myst_enable_extensions = ["colon_fence"]

# Enable automatic links to other projects' Sphinx docs
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "requests": ("https://requests.readthedocs.io/en/latest/", None),
    "urllib3": ("https://urllib3.readthedocs.io/en/stable/", None),
    "pyrate_limiter": ("https://pyratelimiter.readthedocs.io/en/latest/", None),
}

# napoleon settings
napoleon_google_docstring = True
napoleon_include_init_with_doc = True
numpydoc_show_class_members = False

# copybutton settings: Strip prompt text when copying code blocks
copybutton_prompt_text = r">>> |\.\.\. |\$ "
copybutton_prompt_is_regexp = True

# Disable autodoc's built-in type hints, and use sphinx_autodoc_typehints extension instead
autodoc_typehints = "none"

# HTML general settings
html_show_sphinx = False
html_static_path = ["_static"]
pygments_style = "friendly"
pygments_dark_style = "material"

# HTML theme settings
html_theme = "furo"
html_theme_options = {
    "light_logo": "requests-ratelimiter.png",
    "dark_logo": "requests-ratelimiter-white.png",
    "sidebar_hide_name": True,
}
