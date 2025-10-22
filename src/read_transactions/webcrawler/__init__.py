# -*- coding: utf-8 -*-
"""
:author: Tim Häberlein
:version: 1.0
:date: 06.10.2024
:organisation: TU Dresden, FZM
"""

"""
read_transactions.webcrawler
-----------------------------
Zentrales Modul für alle WebCrawler.

Funktionen:
- Automatisches Laden aller Crawler-Klassen im Paket
- Vereinfachte Importe (direkt aus webcrawler importierbar)
- Registry (AVAILABLE_CRAWLERS) für CLI und andere Module
"""

import importlib
import pkgutil
import inspect
import sys
from pathlib import Path
from .base import WebCrawler


__version__ = "2.0.0"
__author__ = "Tim Häberlein"
__license__ = "MIT"


AVAILABLE_CRAWLERS = {}
__all__ = []


pkg_path = Path(__file__).parent

for module_info in pkgutil.iter_modules([str(pkg_path)]):
    name = module_info.name
    if name in {"base", "webdriver", "__init__"}:
        continue

    # Erstelle beide möglichen Modulpfade
    candidates = [
        # f"src.read_transactions.webcrawler.{name}",
        f"read_transactions.webcrawler.{name}",
    ]

    for module_name in candidates:
        if module_name in sys.modules:
            module = sys.modules[module_name]
        else:
            try:
                module = importlib.import_module(module_name)
            except ModuleNotFoundError:
                continue

        # Klassen finden, die von WebCrawler erben
        for class_name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, WebCrawler) and obj is not WebCrawler:
                if name.lower() not in AVAILABLE_CRAWLERS:  # 🔥 doppelte Einträge vermeiden
                    AVAILABLE_CRAWLERS[name.lower()] = obj
                    globals()[class_name] = obj
                    __all__.append(class_name)
                    print(f"📦 Crawler geladen: {name} → {class_name}")



if __name__ == '__main__':
    pass
