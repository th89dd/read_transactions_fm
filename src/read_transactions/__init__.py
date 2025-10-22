# -*- coding: utf-8 -*-
"""
:author: Tim Häberlein
:version: 1.0
:date: 06.10.2024
:organisation: TU Dresden, FZM
"""

"""
read_transactions
-----------------
Zentrales Paket für alle Crawler und CLI-Funktionen.
"""

__version__ = "2.0.0"
__author__ = "Tim Häberlein"
__license__ = "MIT"

# Optionale vereinfachte Exporte (z. B. direkt aufrufbare CLI)
from .cli import main
from .webcrawler import AVAILABLE_CRAWLERS

__all__ = ["main", "AVAILABLE_CRAWLERS"]


if __name__ == '__main__':
    main()
