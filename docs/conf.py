# -*- coding: utf-8 -*-
"""
:author: Tim Häberlein
:version: 1.0
:date: 01.11.2025
:organisation: TU Dresden, FZM
"""

import os
import sys
from datetime import datetime

# Pfad zum Paket (../src) hinzufügen
sys.path.append(os.path.abspath("../src"))

# -- Projektinformationen -----------------------------------------------------
project = "read_transactions"
author = "Tim Häberlein"
current_year = str(datetime.now().year)
copyright = f"{current_year}, {author}"

# -- Allgemeine Konfiguration -------------------------------------------------
extensions = [
    "myst_parser",          # Markdown-Unterstützung
    "sphinx.ext.autodoc",  # Autodoc (wird von autoapi ergänzt)
    "sphinx.ext.napoleon", # Google/NumPy-Docstrings
    "autoapi.extension",   # Automatische API-Seiten für komplettes Paket
    "sphinxarg.ext",       # CLI-Doku aus argparse
    "sphinx.ext.githubpages", # GitHub Pages Unterstützung
]

# MyST (Markdown) Optionen
myst_enable_extensions = [
    "deflist",
    "fieldlist",
    "attrs_block",
    "attrs_inline",
]

# AutoAPI – erzeugt API-Referenz vollständig aus Codebaum
autoapi_type = "python"
autoapi_dirs = ["../src/read_transactions"]
autoapi_add_toctree_entry = True
# Bei Bedarf: Dateien behalten, um Output einzusehen
# autoapi_keep_files = True

# Templates, Patterns
templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- HTML-Ausgabe -------------------------------------------------------------
html_theme = "sphinx_rtd_theme"
# html_static_path = ["_static"]
html_title = project
html_logo = None  # Optional: Pfad zu Logo-Datei setzen
html_theme_options = {
    "collapse_navigation": True,
    "navigation_depth": 3,
}

# – Sprache
language = "de"

# ausführung nur bei direktem Script-Aufruf
if __name__ == '__main__':
    print('run')
    pass
