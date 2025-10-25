# -*- coding: utf-8 -*-
"""
:author: Tim Häberlein
:version: 1.2
:date: 24.10.2025
:organisation: TU Dresden, FZM
"""

import logging
from logging.handlers import RotatingFileHandler
import os
from typing import Optional
import json
import traceback


class MainLogger:
    """Globale, rekonfigurierbare Logging-Klasse für das gesamte Paket."""

    __default_level = logging.DEBUG
    __logfile_path: Optional[str] = None
    _root_logger: Optional[logging.Logger] = None

    # ----------------------------------------------------------------------
    # Hauptkonfiguration (reconfigurable)
    # ----------------------------------------------------------------------
    @classmethod
    def configure(cls, level: str = "DEBUG", logfile: Optional[str] = None, fmt: Optional[str] = None) -> None:
        """
        (Re)Initialisiert das globale Logging-System.
        Kann beliebig oft aufgerufen werden, alte Handler werden ersetzt.

        Args:
            level: Basis-Log-Level für den Logger (Default: DEBUG)
            logfile: Pfad zur Logdatei (optional)
            fmt: Optional benutzerdefiniertes Logformat
        """
        # Logger holen oder neu erstellen
        # if cls._root_logger is None:
        cls._root_logger = logging.getLogger("read_transactions")

        # 🔥 Alle alten Handler entfernen (damit kein doppeltes Logging)
        for h in list(cls._root_logger.handlers):
            cls._root_logger.debug(f"🗑️ Entferne alten Handler: {type(h).__name__}")
            cls._root_logger.removeHandler(h)

        # Basis-Level (Logger-Level → akzeptiert alles)
        cls.__default_level = getattr(logging, level.upper(), logging.DEBUG)
        cls._root_logger.setLevel(cls.__default_level)

        log_format = fmt or "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"
        datefmt = "%Y-%m-%d %H:%M:%S"

        # --- Konsole ---
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(log_format, datefmt))
        console_handler.setLevel(logging.INFO)  # nur INFO+ auf Konsole
        cls._root_logger.addHandler(console_handler)
        cls._root_logger.debug("🖥️ Logging auf Konsole aktiviert.")

        # --- Datei ---
        if logfile:
            try:
                logfile = os.path.abspath(os.path.expanduser(logfile))
                os.makedirs(os.path.dirname(logfile), exist_ok=True)
                file_handler = RotatingFileHandler(
                    logfile, maxBytes=5 * 1024 * 1024, backupCount=1, encoding="utf-8"
                )
                file_handler.setFormatter(logging.Formatter(log_format, datefmt))
                file_handler.setLevel(logging.DEBUG)
                cls._root_logger.addHandler(file_handler)
                cls._root_logger.debug(f"📁 Logging in Datei: {logfile}")
                cls.__logfile_path = logfile
            except Exception as e:
                cls._root_logger.warning(
                    f"Konnte Logdatei '{logfile}' nicht anlegen: {e}. "
                    "Falle auf Konsolen-Logging zurück."
                )
        else:
            cls._root_logger.debug("Kein Logfile angegeben – Logging nur auf Konsole aktiv.")

        cls._root_logger.debug(f"✅ MainLogger (re)konfiguriert: {MainLogger.debug_overview()}")

    # ----------------------------------------------------------------------
    # Logger holen
    # ----------------------------------------------------------------------
    @classmethod
    def get_logger(cls, name: Optional[str] = None) -> logging.Logger:
        """Gibt einen Unterlogger zurück, der an den MainLogger angehängt ist."""
        if cls._root_logger is None:
            cls.configure()
        full_name = f"read_transactions.{name}" if name else "read_transactions"
        return logging.getLogger(full_name)

    # ----------------------------------------------------------------------
    # Laufzeitänderungen
    # ----------------------------------------------------------------------
    @classmethod
    def set_level(cls, level: str) -> None:
        """Ändert den globalen Logger-Level (wirkt auf alle Handler)."""
        if cls._root_logger is None:
            cls.configure()
        lvl = getattr(logging, level.upper(), logging.INFO)
        cls._root_logger.setLevel(lvl)
        cls._root_logger.debug(f"🌍 Globaler Log-Level gesetzt auf {level}")

    @classmethod
    def set_stream_level(cls, level: str) -> None:
        """Ändert nur den Level des StreamHandlers (Konsole)."""
        if cls._root_logger is None:
            print("⚠️ MainLogger ist noch nicht konfiguriert. Konfiguriere mit Standardwerten.")
            cls.configure()
        lvl = getattr(logging, level.upper(), logging.INFO)
        for handler in cls._root_logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                handler.setLevel(lvl)
                cls._root_logger.debug(f"🎛️ Stream-Log-Level geändert auf {level}")

    @classmethod
    def set_file_level(cls, level: str) -> None:
        """Ändert nur den Level des FileHandlers."""
        if cls._root_logger is None:
            cls.configure()
        lvl = getattr(logging, level.upper(), logging.INFO)
        for handler in cls._root_logger.handlers:
            if isinstance(handler, logging.FileHandler):
                handler.setLevel(lvl)
                cls._root_logger.debug(f"📄 File-Log-Level geändert auf {level}")

    # ----------------------------------------------------------------------
    # Debug / Übersicht
    # ----------------------------------------------------------------------
    @classmethod
    def debug_overview(cls) -> str:
        """
        Gibt eine Übersicht der aktuellen Logging-Konfiguration als string zurück:
        - Logger-Level
        - Handler-Levels (Stream/File)
        - Pfad zur Logdatei
        """
        debug_overview = str()
        if cls._root_logger is None:
            debug_overview+= "⚠️ MainLogger ist noch nicht konfiguriert."
            return debug_overview

        debug_overview+=("🧭 Aktuelle Logging-Konfiguration:")
        debug_overview+=(f" Logger-Name: {cls._root_logger.name}")
        debug_overview+=(f" Logger-Level: {logging.getLevelName(cls._root_logger.level)}")

        for handler in cls._root_logger.handlers:
            htype = type(handler).__name__
            hlevel = logging.getLevelName(handler.level)
            desc = ""
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                desc = " (Konsole)"
            elif isinstance(handler, logging.FileHandler):
                path = getattr(handler, 'baseFilename', '?')
                desc = f" (Datei: {path})"
            debug_overview+=(f"- {htype:<22} → Level: {hlevel:<8}{desc}")

        return debug_overview


    # ----------------------------------------------------------------------
    # Optional: JSON-Formatter (z. B. für API-Logs)
    # ----------------------------------------------------------------------
class JsonFormatter(logging.Formatter):
    """Formatter, der Logeinträge als JSON ausgibt."""

    def format(self, record):
        log_record = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }
        if record.exc_info:
            log_record["exception"] = "".join(traceback.format_exception(*record.exc_info))
        return json.dumps(log_record, ensure_ascii=False)



# ----------------------------------------------------------------------
# Test (nur bei direkter Ausführung)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    logfile = os.path.expanduser("~/.config/read_transactions/readtx.log")
    MainLogger.configure(logfile=logfile)
    log = MainLogger.get_logger("test")

    log.debug("DEBUG-Test (nur Datei)")
    log.info("INFO-Test (Konsole + Datei)")
    log.warning("WARN-Test (Konsole + Datei)")
    log.error("ERROR-Test (Konsole + Datei)")
