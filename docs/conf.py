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
sys.path.insert(0, os.path.abspath("../src"))

# -- Projektinformationen -----------------------------------------------------
project = "Read Transactions"
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
    "deflist",      # Definition Lists
    "fieldlist",    # Field Lists
    "attrs_block",  # Attribute-Blöcke
    "attrs_inline", # Attribute Inline
    "colon_fence",  #- Erweiterte Codeblöcke
]

# AutoAPI – erzeugt API-Referenz vollständig aus Codebaum
autoapi_type = "python"
autoapi_dirs = ["../src/read_transactions"]
autoapi_add_toctree_entry = True
# Bei Bedarf: Dateien behalten, um Output einzusehen
# autoapi_keep_files = True

# Kein Unterstrich-Verzeichnis für AutoAPI (umgeh Jekyll-Eigenheiten)
autoapi_root = "api"            # <— statt _autoapi

# Basis-URL setzen (hilft bei Kanonischen Links/Previews)
html_baseurl = "https://th89dd.github.io/read_transactions_fm/"

# Templates, Patterns
templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- HTML-Ausgabe -------------------------------------------------------------
# html_theme = "sphinx_rtd_theme"

html_theme = "furo"
# (Optional) hübschere Syntax-Highlighting-Styles:
pygments_style = "tango"          # für Light
pygments_dark_style = "native"    # für Dark
html_static_path = ["_static", "../assets"]
html_title = project
html_logo = '../assets/readtx.svg'    # Optional: Pfad zu Logo-Datei setzen
html_favicon =  '../assets/readtx.ico'  # Optional: Pfad zu Favicon-Datei setzen
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
