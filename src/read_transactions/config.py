# -*- coding: utf-8 -*-
"""
:author: Tim Häberlein
:version: 1.2
:date: 21.10.2025
:organisation: TU Dresden, FZM

ConfigManager
-------------
Lädt die zentrale Konfigurationsdatei (config.yaml) für das Projekt.
Suchreihenfolge:
  1. ./config.yaml (aktuelles Arbeitsverzeichnis)
  2. ../config.yaml (eine Ebene höher)
  3. ./config/config.yaml
  4. ../config/config.yaml
  5. ~/.config/read_transactions/config.yaml
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict


class ConfigManager:
    """Zentrale Verwaltung der Projektkonfiguration."""

    _config_cache: Dict[str, Any] | None = None

    @classmethod
    def load(cls) -> Dict[str, Any]:
        """Lädt und cached die YAML-Konfiguration."""
        if cls._config_cache is not None:
            return cls._config_cache

        config_path = cls._find_config_file()
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        if not isinstance(config, dict):
            raise ValueError(f"Ungültiges Format in {config_path}")

        cls._config_cache = config
        return config

    # ------------------------------------------------------------------
    # Hilfsfunktionen
    # ------------------------------------------------------------------
    @classmethod
    def _find_config_file(cls) -> Path:
        """Sucht config.yaml in mehreren typischen Pfaden."""
        search_paths = [
            Path.home() / ".config" / "read_transactions" / "config.yaml",  # Benutzerverzeichnis
            Path.cwd() / "config.yaml",                         # im aktuellen Verzeichnis
            Path.cwd().parent / "config.yaml",                  # eine Ebene höher
            Path.cwd().parent.parent / "config.yaml",           # zwei Ebenen höher
            Path.cwd().parent.parent.parent / "config.yaml",    # drei Ebenen höher
            Path.cwd() / "config" / "config.yaml",              # ./config/
            Path.cwd().parent / "config" / "config.yaml",       # ../config/
        ]

        for path in search_paths:
            if path.exists():
                return path

        # keine Datei gefunden → Fehlermeldung
        raise FileNotFoundError(
            "Keine Konfigurationsdatei gefunden.\n"
            "Bitte anlegen unter einem der folgenden Pfade:\n" +
            "\n".join(f" - {p}" for p in search_paths)
        )

    # ------------------------------------------------------------------
    # Zugriffsfunktionen
    # ------------------------------------------------------------------
    @classmethod
    def get_credentials(cls, crawler_name: str) -> Dict[str, str]:
        """Gibt die Credentials für einen Crawler zurück."""
        config = cls.load()
        creds = config.get("credentials", {}).get(crawler_name.lower())
        if not creds:
            raise KeyError(f"Keine Credentials für '{crawler_name}' in config.yaml gefunden.")
        return creds

    @classmethod
    def get_urls(cls, crawler_name: str) -> Dict[str, str]:
        """Gibt URL-Mappings für einen Crawler zurück."""
        config = cls.load()
        urls = config.get("urls", {}).get(crawler_name.lower())
        if not urls:
            raise KeyError(f"Keine URLs für '{crawler_name}' in config.yaml gefunden.")
        return urls
