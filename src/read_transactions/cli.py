# -*- coding: utf-8 -*-
"""
:author: Tim Häberlein
:version: 1.1
:date: 01.11.2025
:organisation: TU Dresden, FZM
"""

# -------- start import block ---------
import argparse
import sys
# import os
import ast  # Für sichere Auswertung von Literal-Ausdrücken
# import pandas as pd
# from concurrent.futures import ProcessPoolExecutor, as_completed

# try:
from read_transactions.logger import MainLogger
from read_transactions.webcrawler import AVAILABLE_CRAWLERS
from read_transactions.config import ConfigManager
# except ImportError:
    # from src.read_transactions.logger import MainLogger
    # from src.read_transactions.webcrawler import AVAILABLE_CRAWLERS
    # from src.read_transactions.config import ConfigManager

# -------- /import block ---------
"""
read_transactions CLI
---------------------
Startet Crawler direkt über die Kommandozeile.

Beispiele:
    python -m read_transactions list
    python -m read_transactions run ariva --start 01.01.2024 --end 31.01.2024
"""

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
    """Startet den angegebenen Crawler."""
    if name not in AVAILABLE_CRAWLERS:
        print(f"❌ Unbekannter Crawler: {name}")
        print("Verfügbare Optionen:")
        for key in AVAILABLE_CRAWLERS:
            print(f"  - {key}")
        sys.exit(1)

    crawler_cls = AVAILABLE_CRAWLERS[name]

    print(f"🚀 Starte {name}-Crawler ...")
    MainLogger.attach_file_for(name=name, level="DEBUG")  # extra Log-Datei für diesen Crawler
    with crawler_cls(start_date=start, end_date=end,
                     logging_level=log_level,
                     **(options or {})) as crawler:
        try:
            crawler.login()
            crawler.download_data()
            crawler.process_data()
            crawler.save_data()
        except Exception as e:
            print(f"❌ Fehler während der Ausführung: {e}")
            sys.exit(1)

    print(f"✅ {name}-Crawler abgeschlossen.\n")

def run_all_crawlers(start: str | None, end: str | None, log_level: str, options: dict | None = None,
                     include: list[str] | None = None, exclude: list[str] | None = None, dry_run: bool = False,
                     parallel: int = 0) -> None:
    """
    Startet mehrere Crawler gem. config.yaml: run_all.<crawler>: true/false.
    Per --include/--exclude kann die Auswahl überschrieben werden.
    """
    cfg_flags = ConfigManager.get_run_all()  # dict[str,bool]
    available = set(AVAILABLE_CRAWLERS.keys())
    # Auswahl aus Config
    selected = {name for name, enabled in (cfg_flags or {}).items() if enabled} & available
    # Fallback: Wenn in der Config nichts gesetzt ist, nimm alle bekannten:
    if not selected:
        selected = set(available)

    # Include/Exclude anwenden
    if include:
        selected &= {n.lower() for n in include}
    if exclude:
        selected -= {n.lower() for n in exclude}

    if not selected:
        print("⚠️  Keine Crawler ausgewählt (nach Filtern).")
        return

    print("📋 Ausführungsliste:", ", ".join(sorted(selected)))
    print("parallele Prozesse:", parallel)
    if dry_run:
        print("Dry-Run aktiv – keine Crawler werden gestartet.")
        return

    if parallel and parallel > 1:
        run_all_crawlers_parallel(sorted(selected), start, end, log_level, options, parallel)
    else:
        # Ausführen – sequenziell
        for name in sorted(selected):
            try:
                run_crawler(name, start, end, log_level, options=options)
            except SystemExit:
                # run_crawler beendet mit sys.exit(1) bei Fehler → weiter zum nächsten
                continue
            except Exception as e:
                print(f"❌ Fehler bei {name}: {e}")
                continue

def _worker_run(name: str, start: str|None, end: str|None, log_level: str, options: dict|None):
    # Tatsächlicher Run
    try:
        run_crawler(name, start, end, log_level, options=options)
        return (name, True, None)
    except Exception as e:
        return (name, False, str(e))

def run_all_crawlers_parallel(selected: list[str], start, end, log_level, options, max_workers: int):
    # not implemented yet - fallback auf sequenziell
    print("⚠️  Parallele Ausführung noch nicht implementiert – Fallback auf sequenziell.")
    for name in selected:
        try:
            run_crawler(name, start, end, log_level, options=options)
        except SystemExit:
            continue
    return

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
# Parser-Erstellung (für Sphinx & CLI)
# -------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    """
    Baut den ArgumentParser für das CLI und gibt ihn zurück.
    Wichtig: Keine Seiteneffekte (kein Logging, keine IO) – damit Sphinx
    via sphinx-argparse diese Funktion gefahrlos importieren und rendern kann.
    """
    parser = argparse.ArgumentParser(
        prog="readtx",
        description="CLI für das read_transactions-Projekt – verwaltet und startet Crawler.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Verfügbare Befehle")

    # --- list command -----------------------------------------------------------------------------------------------
    subparsers.add_parser("list", help="Listet alle verfügbaren Crawler auf")

    # --- run command ------------------------------------------------------------------------------------------------
    parser_run = subparsers.add_parser("run", help="Startet einen bestimmten Crawler oder all")
    parser_run.add_argument("crawler", nargs='?',
                            help="Name des Crawlers, z. B. amazon_visa, amex (weglassen bei --all).")
    parser_run.add_argument("--start", metavar='Startdatum', type=str,
                            help="Startdatum im Format (dd.mm.yyyy) (default: heute - 1 Tag)")
    parser_run.add_argument("--end", metavar='Enddatum', type=str,
                            help="Enddatum im Format (dd.mm.yyyy) (default: heute - 6 Monate)")
    parser_run.add_argument("-l", "--log-level", dest='log_level',
                            type=lambda s: s.upper(),
                            help="Logging-Level für den Konsolenhandler",
                            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                            default="INFO")
    parser_run.add_argument('-o', '--options', metavar='key=value', dest='options', type=str, nargs='*',
                            help="Zusatzparameter, siehe Klassen-Dokumentation des jeweiligen Crawlers")
    parser_run.add_argument("-a", "--all", action="store_true",
                            help="Startet alle in run_all konfigurierten Crawler")
    parser_run.add_argument("--include", nargs="*", help="Nur diese Crawler (mit -a/--all)")
    parser_run.add_argument("--exclude", nargs="*", help="Diese Crawler ausschließen (mit -a/--all)")
    parser_run.add_argument("--dry-run", action="store_true", help="Nur anzeigen, was laufen würde")
    parser_run.add_argument("-p", "--parallel", type=int, default=0,
                            help="Anzahl paralleler Prozesse (0/1 = sequentiell) - *experimentell*")

    # --- config command  --------------------------------------------------------------------------------------------
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
                             help="Pfad zur Konfigurationsdatei (default: %USERPROFILE%/.config/read_transactions/config.yaml)",
                             default=None)

    # set credentials
    parser_set = config_subparsers.add_parser("set", help="Setzt Benutzername und/oder Passwort für einen Crawler")
    parser_set.add_argument("crawler", help="Crawler-Name (z. B. amex, amazon_visa)")
    parser_set.add_argument("--user", help="Benutzername")
    parser_set.add_argument("--pwd", help="Passwort (wird verschlüsselt gespeichert)")

    # run-all
    parser_cfg_ra = config_subparsers.add_parser(
        "run-all", help="Konfiguriert, welche Crawler bei 'run -a/--all' berücksichtigt werden"
    )
    ra_sub = parser_cfg_ra.add_subparsers(dest="ra_action", help="Aktionen")

    # show
    ra_show = ra_sub.add_parser("show", help="Zeigt die run_all-Einstellungen")
    ra_show.add_argument("-e", "--effective", action="store_true",
                         help="Zeigt zusätzlich die tatsächlich aktivierten & verfügbaren Crawler")

    # enable
    ra_enable = ra_sub.add_parser("enable", help="Aktiviert einen/mehrere Crawler für --all")
    ra_enable.add_argument("crawler", nargs="+", help="z. B. amex ariva trade_republic")

    # disable
    ra_disable = ra_sub.add_parser("disable", help="Deaktiviert einen/mehrere Crawler für --all")
    ra_disable.add_argument("crawler", nargs="+", help="z. B. amex ariva trade_republic")

    # set <crawler> on|off
    ra_set = ra_sub.add_parser("set", help="Setzt einen Crawler explizit auf on/off")
    ra_set.add_argument("crawler", help="Crawler-Name")
    ra_set.add_argument("--off", help="auf aus setzen, sonst an", action="store_true")

    return parser

# -------------------------------------------------------------------
# Hauptfunktion (nur hier: Logging & Ausführung)
# -------------------------------------------------------------------
def _configure_logging() -> None:
    """Konfiguriert das Logging – nur im CLI-Lauf, niemals beim Import (Sphinx!)."""
    logfile = "~/.config/read_transactions/readtx.log"
    MainLogger.configure(logfile=logfile)
    # Beispiel: zentrale Level setzen, wenn gewünscht:
    # MainLogger.set_stream_level("DEBUG")
    # MainLogger.set_file_level("INFO")
    MainLogger._root_logger.debug('-------------------- Neue CLI-Session --------------------')
    MainLogger.debug_overview()

def main(argv: list[str] | None = None) -> None:
    # Nur beim echten CLI-Run Logging aktivieren:
    _configure_logging()

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "list":
        list_crawlers()

    elif args.command == "run":
        options = parse_kv_list(args.options)
        if args.all:
            if args.crawler:
                # Zugriff auf das konkrete Subparser-Objekt, um schöne Fehlermeldung zu zeigen
                for action in parser._subparsers._actions:
                    if isinstance(action, argparse._SubParsersAction):
                        parser_run = action.choices.get("run")
                        break
                else:
                    parser_run = None
                if parser_run:
                    parser_run.error("Mit --all bitte keinen einzelnen Crawler angeben.")
                else:
                    print("Mit --all bitte keinen einzelnen Crawler angeben."); sys.exit(2)

            run_all_crawlers(
                start=args.start, end=args.end, log_level=args.log_level, options=options,
                include=args.include, exclude=args.exclude, dry_run=args.dry_run,
                parallel=args.parallel
            )
        else:
            if not args.crawler:
                for action in parser._subparsers._actions:
                    if isinstance(action, argparse._SubParsersAction):
                        parser_run = action.choices.get("run")
                        break
                else:
                    parser_run = None
                if parser_run:
                    parser_run.error("Bitte einen Crawler-Namen angeben oder --all nutzen.")
                else:
                    print("Bitte einen Crawler-Namen angeben oder --all nutzen."); sys.exit(2)

            run_crawler(args.crawler, args.start, args.end, args.log_level, options=options)

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

        elif args.action == "run-all":
            flags = ConfigManager.get_run_all()
            if args.ra_action == "show":
                print(f"🔧 run_all ({ConfigManager.config_path}):")
                if not flags:
                    print("  (kein Abschnitt 'run_all' gefunden – Standard: alle bekannten Crawler)")
                else:
                    for k, v in sorted(flags.items()):
                        print(f"  - {k}: {'on' if v else 'off'}")

                if getattr(args, "effective", False):
                    enabled = {k for k, v in (flags or {}).items() if v}
                    available = set(AVAILABLE_CRAWLERS.keys())
                    effective = sorted(enabled & available) if enabled else sorted(available)
                    print("\n✅ Effektiv berücksichtigt bei 'run --all':", ", ".join(effective) or "—")
                    print("📦 Verfügbar:", ", ".join(sorted(AVAILABLE_CRAWLERS.keys())))

            elif args.ra_action in ("enable", "disable"):
                val = (args.ra_action == "enable")
                for c in args.crawler:
                    ConfigManager.set_run_all(c, val)

            elif args.ra_action == "set":
                ConfigManager.set_run_all(args.crawler, False if args.off else True)

            else:
                # Hilfe des run-all-Subparsers zeigen
                for action in parser._subparsers._actions:
                    if isinstance(action, argparse._SubParsersAction):
                        parser_cfg_ra = action.choices.get("config")
                        break
                # Fallback:
                print("Ungültige 'run-all'-Aktion."); sys.exit(2)
        else:
            # Hilfe für 'config' zeigen
            for action in parser._subparsers._actions:
                if isinstance(action, argparse._SubParsersAction):
                    parser_config = action.choices.get("config")
                    break
            print("Ungültiger config-Befehl."); sys.exit(2)

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
