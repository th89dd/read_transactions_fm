# -*- coding: utf-8 -*-
"""
:author: Tim Häberlein
:version: 1.0
:date: 21.10.2025
:organisation: TU Dresden, FZM
"""

# -------- start import block ---------
import argparse
import sys
import pandas as pd
from .webcrawler import AVAILABLE_CRAWLERS

# -------- /import block ---------
"""
read_transactions CLI
---------------------
Startet Crawler direkt über die Kommandozeile.

Beispiele:
    python -m read_transactions list
    python -m read_transactions run ariva --start 01.01.2024 --end 31.01.2024
"""


# AVAILABLE_CRAWLERS = {
#     "ariva": ArivaCrawler,
#     "amex": AmexCrawler, ...}

def list_crawlers() -> None:
    """Zeigt alle verfügbaren Crawler aus der Registry an."""
    if not AVAILABLE_CRAWLERS:
        print("⚠️  Keine Crawler registriert.")
        return

    print("Verfügbare Crawler:")
    for key in AVAILABLE_CRAWLERS:
        print(f"  - {key}")
    print()


def run_crawler(name: str, start: str, end: str, log_level:str) -> None:
    """Startet den angegebenen Crawler."""
    if name not in AVAILABLE_CRAWLERS:
        print(f"❌ Unbekannter Crawler: {name}")
        print("Verfügbare Optionen:")
        for key in AVAILABLE_CRAWLERS:
            print(f"  - {key}")
        sys.exit(1)

    crawler_cls = AVAILABLE_CRAWLERS[name]

    print(f"🚀 Starte {name}-Crawler ...")
    with crawler_cls(start_date=start, end_date=end, logging_level=log_level) as crawler:
        try:
            crawler.login()
            crawler.download_data()
            crawler.process_data()
            crawler.save_data()
        except Exception as e:
            print(f"❌ Fehler während der Ausführung: {e}")
            sys.exit(1)

    print(f"✅ {name}-Crawler abgeschlossen.\n")


# -------------------------------------------------------------------
# Hauptfunktion
# -------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="read_transactions",
        description="CLI für das read_transactions-Projekt – verwaltet und startet Crawler.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Verfügbare Befehle")

    # --- list command ---
    subparsers.add_parser("list", help="Listet alle verfügbaren Crawler auf")

    # --- run command ---
    parser_run = subparsers.add_parser("run", help="Startet einen bestimmten Crawler")
    parser_run.add_argument("name", help="Name des Crawlers (z. B. ariva)")
    parser_run.add_argument("--start", type=str, help="Startdatum (dd.mm.yyyy)",
                            default=pd.to_datetime("today").strftime('%d.%m.%Y')
                            )
    parser_run.add_argument("--end", type=str, help="Enddatum (dd.mm.yyyy)",
                            default=(pd.to_datetime("today")-pd.DateOffset(months=6)).strftime('%d.%m.%Y')
                            )
    parser_run.add_argument("--log_level", type=str, help="Log_Level (DEBUG, INFO, WARNING, ERROR)",
                            default="INFO")
    args = parser.parse_args()

    if args.command == "list":
        list_crawlers()
    elif args.command == "run":
        run_crawler(args.name, args.start, args.end, args.log_level)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

