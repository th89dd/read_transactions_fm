# -*- coding: utf-8 -*-
"""
:author: Tim Häberlein
:version: 1.0
:date: 21.10.2025
:organisation: TU Dresden, FZM
"""

# -------- start import block ---------
import logging
import os
from typing import Optional

import json
import traceback
# -------- /import block ---------

class MainLogger:
    """Zentrale Logging-Klasse für das gesamte Package.

    Diese Klasse verwaltet das globale Logging-Setup für alle Komponenten.
    Sie sorgt dafür, dass:
      * das Logging-System nur einmal konfiguriert wird (Singleton-Pattern),
      * alle Logger einheitliche Formatierung und Handler nutzen,
      * optionale Datei-Logs unterstützt werden,
      * und das Log-Level zentral steuerbar ist.

    Beispiel:
        >>> MainLogger.configure(level="DEBUG", logfile="log.txt")
        >>> logger = MainLogger.get_logger("excel_protection_remover.cleaner")
        >>> logger.info("Cleaner gestartet")
    """

    __is_configured = False
    __default_level = logging.INFO
    __logfile_path: Optional[str] = None

    @classmethod
    def configure(cls, level: str = "INFO", logfile: Optional[str] = None, fmt: Optional[str] = None,) -> None:
        """Initialisiert das globale Logging-System.

        Args:
            level: Log-Level-Name (z. B. "DEBUG", "INFO", "WARNING", "ERROR").
            logfile: Optionaler Pfad für Logdatei (wenn None → keine Datei).
            fmt: Optionales Format-Template für Logzeilen.
        """
        if cls.__is_configured:
            return

        cls.__default_level = getattr(logging, level.upper(), logging.INFO)
        cls.__logfile_path = logfile

        log_format = fmt or "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"
        datefmt = "%Y-%m-%d %H:%M:%S"

        root_logger = logging.getLogger()
        root_logger.setLevel(cls.__default_level)

        # Konsole
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(log_format, datefmt))
        root_logger.addHandler(console_handler)

        # Optionale Datei
        if logfile:
            try:
                logfile = os.path.abspath(logfile)
                os.makedirs(os.path.dirname(logfile), exist_ok=True)
                file_handler = logging.FileHandler(logfile, encoding="utf-8")
                file_handler.setFormatter(logging.Formatter(log_format, datefmt))
                root_logger.addHandler(file_handler)
                root_logger.info(f"Logging in Datei: {logfile}")
                cls.__logfile_path = logfile
            except Exception as e:
                root_logger.warning(
                    f"Konnte Logdatei '{logfile}' nicht anlegen: {e}. "
                    "Falle auf Konsolen-Logging zurück."
                )
                cls.__logfile_path = None
        else:
            root_logger.debug("Kein Logfile angegeben – Logging nur auf Konsole aktiv.")

        cls.__is_configured = True
        root_logger.debug("MainLogger konfiguriert.")

    @classmethod
    def get_logger(cls, name: Optional[str] = None) -> logging.Logger:
        """Gibt einen hierarchischen Logger zurück.

        Args:
            name: Optionaler Loggername (z. B. Modulname oder Klassenname).
                Wenn None, wird der Standardname "excel_protection_remover" verwendet.

        Returns:
            logging.Logger: Konfigurierter Logger.
        """
        if not cls.__is_configured:
            cls.configure()
        if not name:
            name = "read_transactions"
        return logging.getLogger(name)

    @classmethod
    def set_level(cls, level: str) -> None:
        """Ändert den globalen Log-Level zur Laufzeit.

        Args:
            level: Log-Level-Name ("DEBUG", "INFO", etc.).
        """
        lvl = getattr(logging, level.upper(), logging.INFO)
        logging.getLogger().setLevel(lvl)
        cls.__default_level = lvl

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "time": self.formatTime(record, self.datefmt) if self.datefmt else self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }

        # Falls eine Exception vorhanden ist, Stacktrace als String speichern
        if record.exc_info:
            log_record["exception"] = "".join(traceback.format_exception(*record.exc_info))

        return json.dumps(log_record, ensure_ascii=False)

# ausführung nur bei direktem Script-Aufruf
if __name__ == '__main__':
    print('run')
    pass