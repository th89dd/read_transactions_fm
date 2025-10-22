# -*- coding: utf-8 -*-
"""
:author: Tim Häberlein
:version: 1.0
:date: 21.10.2025
:organisation: TU Dresden, FZM
"""

"""
read_transactions.__main__
--------------------------
CLI-Einstiegspunkt.

Erlaubt das Starten über:
    python -m read_transactions <command>
Beispiele:
    python -m read_transactions list
    python -m read_transactions run ariva --headless
"""

from .cli import main

if __name__ == "__main__":
    main()


