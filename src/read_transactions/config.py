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

"""
TODOs:
- Passwörter verschlüsselt speichern
- default Config-Datei über cli generieren
- congig über cli anzeigen/löschen/bearbeiten
"""

import os
# import yaml
from ruamel.yaml import YAML
from io import StringIO
from pathlib import Path
from typing import Any, Dict
from cryptography.fernet import Fernet

from .logger import MainLogger
import logging

class ConfigManager:
    """Zentrale Verwaltung der Projektkonfiguration."""

    _config_cache: Dict[str, Any] | None = None
    _yaml = YAML()
    _yaml.preserve_quotes = True
    _logger = MainLogger.get_logger('config_manager')
    _key_path = Path.home() / ".config" / "read_transactions" / "secret.key"
    _fernet_cache: Fernet | None = None

    @classmethod
    def load(cls) -> Dict[str, Any]:
        """Lädt und cached die YAML-Konfiguration."""
        if cls._config_cache is not None:
            cls._logger.debug("Lade Konfiguration aus Cache")
            return cls._config_cache

        try:
            config_path = cls._find_config_file()
        except FileNotFoundError:
            cls._logger.debug("Keine Konfigurationsdatei gefunden. Lade default")
            config_path = cls.create_default()

        with open(config_path, "r", encoding="utf-8") as f:
            # config = yaml.safe_load(f) or {}
            cls._logger.debug(f"Lade Konfiguration aus {config_path}")
            config = cls._yaml.load(f) or {}
        if not isinstance(config, dict):
            raise ValueError(f"Ungültiges Format in {config_path}")

        cls._config_cache = config
        return config
    # ------------------------------------------------------------------
    # Verschlüsselungsfunktionen ()
    # ------------------------------------------------------------------
    @classmethod
    def _get_cipher(cls) -> Fernet:
        """Lädt oder erzeugt den Verschlüsselungsschlüssel."""
        if cls._fernet_cache is not None:
            return cls._fernet_cache

        cls._key_path.parent.mkdir(parents=True, exist_ok=True)
        if not cls._key_path.exists():
            key = Fernet.generate_key()
            cls._key_path.write_bytes(key)
            cls._logger.debug(f"🔑 Neuer Verschlüsselungsschlüssel erstellt: {cls._key_path}")
        else:
            key = cls._key_path.read_bytes()
        return Fernet(key)

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
        cls._logger.debug(f"Credentials für '{crawler_name}' geladen.")
        if not creds:
            raise KeyError(f"Keine Credentials für '{crawler_name}' in config.yaml gefunden.")

        # Optional: Entschlüsselung der Passwörter hier
        pwd = creds.get("password")
        if pwd and isinstance(pwd, str) and pwd.startswith("ENC("):  # Beispiel-Prüfung
            try:
                token = pwd[4:-1]  # Entferne ENC( und )
                cipher = cls._get_cipher()
                decrypted_pwd = cipher.decrypt(token.encode("utf-8")).decode("utf-8")  # entschlüsseln
                creds["password"] = decrypted_pwd
                cls._logger.debug(f"Passwort für '{crawler_name}' entschlüsselt.")
            except Exception as e:
                cls._logger.error(f"Fehler beim Entschlüsseln des Passworts für '{crawler_name}': {e}")
                raise ValueError(f"Fehler beim Entschlüsseln des Passworts für '{crawler_name}'") from e
        return creds

    @classmethod
    def get_urls(cls, crawler_name: str) -> Dict[str, str]:
        """Gibt URL-Mappings für einen Crawler zurück."""
        config = cls.load()
        urls = config.get("urls", {}).get(crawler_name.lower())
        cls._logger.debug(f"URLs für '{crawler_name}' geladen.")
        if not urls:
            raise KeyError(f"Keine URLs für '{crawler_name}' in config.yaml gefunden.")
        return urls

    # ------------------------------------------------------------------
    # Benutzerdaten setzen (verschlüsselt)
    # ------------------------------------------------------------------
    @classmethod
    def set_credentials(cls, crawler_name: str, user: str | None = None, pwd: str | None = None) -> None:
        """
        Setzt die Credentials für einen Crawler und speichert sie verschlüsselt.
        Args:
            crawler_name: Name des Crawlers (z. B. 'amex')
            user: Neuer Benutzername
            pwd: Neues Passwort
        """
        try:
            config = cls.load()
            # lesen oder leer erstellen:
            creds = config.setdefault("credentials", {}).setdefault(crawler_name.lower(), {})
            if user:
                creds["user"] = user
            if pwd:
                cipher = cls._get_cipher()
                encrypted_pwd = cipher.encrypt(pwd.encode("utf-8")).decode("utf-8")
                creds["password"] = f"ENC({encrypted_pwd})"  # Markierung für verschlüsselte Passwörter

            path = cls._find_config_file()
            with open(path, "w", encoding="utf-8") as f:
                cls._yaml.dump(config, f)
            cls._config_cache = config
            cls._logger.debug(f"Credentials für '{crawler_name}' aktualisiert und gespeichert.")
        except Exception as e:
            cls._logger.error(f"Fehler beim Setzen der Credentials für '{crawler_name}': {e}")
            raise

    # ------------------------------------------------------------------
    # CLI-Hilfsfunktionen (anzeigen, löschen, bearbeiten)
    # ------------------------------------------------------------------
    @classmethod
    def show(cls) -> None:
        """Zeigt den aktuell geladenen Config-Inhalt als YAML an."""
        try:
            cfg = cls.load()
            print("📄 Aktuelle Konfiguration:\n")

            stream = StringIO()
            cls._yaml.dump(cfg, stream)
            print(stream.getvalue())

        except FileNotFoundError as e:
            print(f"❌ {e}")
        except Exception as e:
            print(f"⚠️ Fehler beim Anzeigen der Config: {e}")

    @classmethod
    def clear(cls, delete_file: bool = False) -> None:
        """
        Löscht den internen Config-Cache oder optional die Config-Datei selbst.

        Args:
            delete_file (bool): Wenn True, wird die gefundene config.yaml gelöscht.
        """
        cls._config_cache = None
        if delete_file:
            try:
                path = cls._find_config_file()
                os.remove(path)
                print(f"🗑️ Config-Datei gelöscht: {path}")
                cls._logger.debug(f"Config-Datei {path} gelöscht.")
            except FileNotFoundError:
                print("❌ Keine config.yaml gefunden.")
            except Exception as e:
                print(f"⚠️ Fehler beim Löschen: {e}")
        else:
            print("🧹 Config-Cache geleert (Datei bleibt erhalten).")

    @classmethod
    def edit(cls, key_path: str, value: Any) -> None:
        """
        Ändert oder fügt einen Eintrag in der Config-Datei hinzu.

        Args:
            key_path (str): Punkt-getrennter Pfad, z. B. 'credentials.amex.user'
            value (Any): Neuer Wert (automatisch als String gespeichert)
        """
        try:
            cfg = cls.load()
            keys = key_path.split(".")
            d = cfg
            for k in keys[:-1]:
                d = d.setdefault(k, {})
            d[keys[-1]] = value

            path = cls._find_config_file()
            with open(path, "w", encoding="utf-8") as f:
                cls._yaml.dump(cfg, f)
            cls._config_cache = cfg
            print(f"✅ Wert aktualisiert: {key_path} = {value}")
            cls._logger.debug(f"Config-Eintrag '{key_path}' auf '{value}' in {path} gesetzt.")
        except FileNotFoundError:
            print("❌ Keine config.yaml gefunden.")
        except Exception as e:
            print(f"⚠️ Fehler beim Bearbeiten der Config: {e}")
            cls._logger.error(f"Fehler beim Bearbeiten der Config: {e}")
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Default-Config erstellen
    # ------------------------------------------------------------------

    @classmethod
    def create_default(cls, path: str | None = None, overwrite: bool = False) -> Path:
        """
        Erstellt eine Standard-config.yaml mit Beispielinhalten und Kommentaren.

        Args:
            path: Optionaler Pfad, an dem die Datei erstellt werden soll.
                  (Standard: ~/.config/read_transactions/config.yaml)
            overwrite: Wenn True, überschreibt eine bestehende Datei.

        Returns:
            Path: Pfad zur erstellten Konfigurationsdatei.
        """
        from pathlib import Path
        import textwrap

        default_content = textwrap.dedent("""\
            # Credentials for various services (amex, amazon_visa, ariva)
            credentials:
                # American Express login credentials - uncomment if needed
                amex:
                    user: max_mustermann
                    password: geheim123
              
                # Trade Republic credentials
                trade_republic:
                    user: max_mustermann
                    password: geheim123
              
                # Amazon Visa login credentials
                amazon_visa:
                    user: max_mustermann
                    password: geheim123
    
                # Ariva login credentials - for downloading historical stock prices
                ariva:
                    user: max_mustermann
                    password: geheim123              
    
            # URL endpoints for various services
            urls:
                # American Express URLs
                amex:
                    login: https://www.americanexpress.com/de-de/account/login
                    transactions: https://global.americanexpress.com/activity/search
                
                # Trade Republic URLs
                trade_republic:
                    login: https://app.traderepublic.com/login
                    transactions: https://app.traderepublic.com/profile/transactions  
              
                # Amazon Visa URLs
                amazon_visa:
                    login: https://customer.amazon.zinia.de/login
                    transactions: https://customer.amazon.zinia.de/transactions
    
                # Ariva URLs
                ariva:
                    login: https://login.ariva.de/realms/ariva/protocol/openid-connect/auth?client_id=ariva-web&redirect_uri=https%3A%2F%2Fwww.ariva.de%2F%3Fbase64_redirect%3DaHR0cHM6Ly93d3cuYXJpdmEuZGUv&response_type=code&scope=openid+profile+email&state=example
                    # Endpoints for historical stock price data - add various entries as needed
                    kurse:
                        apple: https://www.ariva.de/aktien/apple-aktie/kurse/historische-kurse
                        msci_world: https://www.ariva.de/etf/ishares-core-msci-world-ucits-etf-usd-acc/kurse/historische-kurse
                        microsoft: https://www.ariva.de/aktien/microsoft-corp-aktie/kurse/historische-kurse
                        ai_big_data: https://www.ariva.de/etf/xtrackers-artificial-intelligence-and-big-data-ucits-etf-1c/kurse/historische-kurse
                        msci_world_it: https://www.ariva.de/fonds/xtrackers-msci-world-information-technology-ucits-etf-1c/kurse/historische-kurse
                        msci_world2: https://www.ariva.de/fonds/xtrackers-msci-world-ucits-etf-1c/kurse/historische-kurse
                        byd_electric: https://www.ariva.de/aktien/byd-electronic-ltd-aktie/kurse/historische-kurse
                        byd_auto: https://www.ariva.de/aktien/byd-co-ltd-aktie/kurse/historische-kurse
                        phy_gold: https://www.ariva.de/ishares-physical-gold-etc-auf-gold-ishares-plc-etc/kurse/historische-kurse
                        novo_nordisk: https://www.ariva.de/aktien/novo-nordisk-as-aktie/kurse/historische-kurse
                        global_aerospace: https://www.ariva.de/etf/ishares-global-aerospace-defence-ucits-etf-usd-acc/kurse/historische-kurse
                        european_defence: https://www.ariva.de/etf/wisdomtree-europe-defence-ucits-etf-eur-acc/kurse/historische-kurse
                        msci_europe_healthcare: https://www.ariva.de/etf/ishares-msci-europe-health-care-sector-ucits-etf-eur-acc/kurse/historische-kurse
                        msci_europe_energy: https://www.ariva.de/etf/spdr-msci-europe-energy-ucits-etf/kurse/historische-kurse
                        msci_europe_em: https://www.ariva.de/etf/ishares-msci-em-ucits-etf-usd-dist/kurse/historische-kurse
                        ftse_all_world: https://www.ariva.de/etf/vanguard-ftse-all-world-ucits-etf-usd-acc/kurse/historische-kurse
                        vanguard_lifestrategy_80_equity: https://www.ariva.de/etf/vanguard-lifestrategy-80-equity-ucits-etf-eur-acc/kurse/historische-kurse
                        ftse_global_all_cap: https://www.ariva.de/etf/vanguard-esg-global-all-cap-ucits-etf-usd-acc/kurse/historische-kurse
                        # add more if needed
            """)

        if not path:
            path = Path.home() / ".config" / "read_transactions" / "config.yaml"

        path = Path(path)
        if path.exists() and not overwrite:
            cls._logger.debug(f"Config-Datei existiert bereits: {path}")
            print(f"⚠️ Datei existiert bereits: {path} (verwende --overwrite zum Überschreiben)")
            # cls._config_cache = None
            return path

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(default_content)
        cls._logger.debug(f"✅ Default-Konfiguration erstellt unter: {path}")
        print(f"✅ Default-Konfiguration erstellt unter: {path}")
        return path


if __name__ == "__main__":
    # Kurzer Testlauf
    logger = logging.getLogger("config_manager")
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    try:
        config = ConfigManager.load()
        print("Konfiguration erfolgreich geladen")
        # print(config)
    except Exception as e:
        print(f"Fehler: {e}")