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
import os
import ast  # Für sichere Auswertung von Literal-Ausdrücken
import pandas as pd

try:
    from read_transactions.logger import MainLogger
    from read_transactions.webcrawler import AVAILABLE_CRAWLERS
    from read_transactions.config import ConfigManager
except ImportError:
    from src.read_transactions.logger import MainLogger
    from src.read_transactions.webcrawler import AVAILABLE_CRAWLERS
    from src.read_transactions.config import ConfigManager

# -------- /import block ---------
"""
read_transactions CLI
---------------------
Startet Crawler direkt über die Kommandozeile.

Beispiele:
    python -m read_transactions list
    python -m read_transactions run ariva --start 01.01.2024 --end 31.01.2024
"""

"""
TODOs:
- [] mehrere crawler auf einmal starten
"""


# AVAILABLE_CRAWLERS = {
#     "ariva": ArivaCrawler,
#     "amex": AmexCrawler, ...}

# -------------------------------------------------------------------
# Funktionen zum Listen und Ausführen von Crawlern
# -------------------------------------------------------------------
def list_crawlers() -> None:
    """Zeigt alle verfügbaren Crawler aus der Registry an."""
    if not AVAILABLE_CRAWLERS:
        print("⚠️  Keine Crawler registriert.")
        return

    print("Verfügbare Crawler:")
    for key in AVAILABLE_CRAWLERS:
        print(f"  - {key}")
    print()

def run_crawler(name: str, start: str, end: str, log_level: str, options: dict | None = None) -> None:
    crawler_cls = AVAILABLE_CRAWLERS[name]
    with crawler_cls(start_date=start, end_date=end, logging_level=log_level, **(options or {})) as crawler:
        ...
def run_crawler(name: str, start: str, end: str, log_level:str, options: dict | None = None) -> None:
    """Startet den angegebenen Crawler."""
    if name not in AVAILABLE_CRAWLERS:
        print(f"❌ Unbekannter Crawler: {name}")
        print("Verfügbare Optionen:")
        for key in AVAILABLE_CRAWLERS:
            print(f"  - {key}")
        sys.exit(1)

    crawler_cls = AVAILABLE_CRAWLERS[name]

    print(f"🚀 Starte {name}-Crawler ...")
    with crawler_cls(start_date=start, end_date=end, logging_level=log_level, **(options or {})) as crawler:
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
# Hilfsfunktionen
# -------------------------------------------------------------------
def parse_kv_list(kv_list) -> dict:
    """Parst eine Liste von key=value Strings in ein Dictionary."""
    opts = {}
    if not kv_list:
        return opts
    for item in kv_list:
        if '=' not in item:
            continue
        k, v = item.split('=', 1)
        try:
            v = ast.literal_eval(v)
        except Exception:
            pass
        opts[k] = v
    return opts


# -------------------------------------------------------------------
# Hauptfunktion
# -------------------------------------------------------------------

def main() -> None:
    # ------------------------------------------------------------------------------------------
    # Logger konfigurieren
    # ------------------------------------------------------------------------------------------
    logfile = os.path.expanduser("~") + "/.config/read_transactions/readtx.log"
    MainLogger.configure(logfile=logfile)
      # Log-Datei immer auf DEBUG setzen
    # MainLogger.set_file_level("INFO")
    # MainLogger.set_stream_level("DEBUG")
    # MainLogger.set_file_level("INFO")
    # cli_logger = MainLogger.get_logger("cli")
    # cli_logger.debug("CLI Logger initialisiert.")
    MainLogger._root_logger.debug('-------------------- Neue CLI-Session --------------------')
    MainLogger.debug_overview()




    # ------------------------------------------------------------------------------------------
    # CLI-Parser einrichten
    # ------------------------------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        prog="readtx",
        description="CLI für das read_transactions-Projekt – verwaltet und startet Crawler.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Verfügbare Befehle")

    # --- list command ---
    subparsers.add_parser("list", help="Listet alle verfügbaren Crawler auf")

    # --- run command ---
    parser_run = subparsers.add_parser("run", help="Startet einen bestimmten Crawler")
    parser_run.add_argument("name", help="Name des Crawlers (z. B. ariva)")
    parser_run.add_argument("--start", metavar='Startdatum', type=str,
                            help="Startdatum im Format (dd.mm.yyyy) (default: heute - 1 Tag)",
                            default=None
                            )
    parser_run.add_argument("--end", metavar='Enddatum', type=str,
                            help="Enddatum im Format (dd.mm.yyyy) (default: heute - 6 Monate)",
                            default=None
                            )
    parser_run.add_argument("--l", metavar='log_level', dest='log_level', type=str,
                            help="log_level = logging Level für den Konsolenhandler (DEBUG, INFO, WARNING, ERROR)",
                            default="INFO")
    parser_run.add_argument('--o', metavar='options', dest='options', type=str, nargs='*',
                            help="zusätzliche Parameter für den Crawler im Format key=value key2=value2 ...",
                            default=None)


    # --- config command  ---
    parser_config = subparsers.add_parser("config", help="Verwaltet die Konfiguration")
    config_subparsers = parser_config.add_subparsers(dest="action", help="Verfügbare Aktionen")
    # show
    parser_show = config_subparsers.add_parser("show", help="Zeigt die aktuelle Konfiguration an")
    parser_show.add_argument("--credentials", action="store_true",
                             help="Zeigt nur verschlüsselte Zugangsdaten im Klartext an")
    parser_show.add_argument("--urls", action="store_true",
                             help="Zeigt nur die konfigurierten URLs an")
    # clear
    parser_clear = config_subparsers.add_parser("clear", help="Löscht Cache oder Datei")
    parser_clear.add_argument("--delete", action="store_true", help="Löscht zusätzlich die Datei")

    # edit
    parser_edit = config_subparsers.add_parser("edit", help="Ändert einen Config-Eintrag")
    parser_edit.add_argument("key", help="Pfad (z. B. credentials.amex.user)")
    parser_edit.add_argument("value", help="Neuer Wert")

    # init
    parser_init = config_subparsers.add_parser("init", help="Erstellt eine Default-Konfiguration")
    parser_init.add_argument("--overwrite", action="store_true", help="Überschreibt bestehende Datei")
    parser_init.add_argument("--path", type=str,
                             help="Pfad zur Konfigurationsdatei (default: %%USERPROFILE%%/.config/read_transactions/config.yaml)",
                             default=None)

    # set credentials
    parser_set = config_subparsers.add_parser("set", help="Setzt Benutzername und/oder Passwort für einen Crawler")
    parser_set.add_argument("crawler", help="Crawler-Name (z. B. amex, amazon_visa)")
    parser_set.add_argument("--user", help="Benutzername")
    parser_set.add_argument("--pwd", help="Passwort (wird verschlüsselt gespeichert)")


    args = parser.parse_args()

    if args.command == "list":
        list_crawlers()
    elif args.command == "run":
        options = parse_kv_list(args.options)
        run_crawler(args.name, args.start, args.end, args.log_level, options=options)
        # run_crawler(args.name, args.start, args.end, args.log_level)
    elif args.command == "config":
        config_mgr = ConfigManager
        if args.action == "show":
            if args.credentials:
                for crawler in AVAILABLE_CRAWLERS:
                    cred = config_mgr.get_credentials(crawler)
                    print(f"{crawler}: {cred}")
            if args.urls:
                for crawler in AVAILABLE_CRAWLERS:
                    url = config_mgr.get_urls(crawler)
                    print(f"{crawler}: {url}")
            if not args.credentials and not args.urls:
                config_mgr.show()
        elif args.action == "clear":
            config_mgr.clear(delete_file=args.delete)
        elif args.action == "edit":
            config_mgr.edit(args.key, args.value)
        elif args.action == "init":
            config_mgr.create_default(overwrite=args.overwrite, path=args.path)
        elif args.action == "set":
            config_mgr.set_credentials(args.crawler, user=args.user, pwd=args.pwd)
        else:
            parser_config.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

