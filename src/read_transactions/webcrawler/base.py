# -*- coding: utf-8 -*-
"""
:author: Tim Häberlein
:version: 2.2
:date: 21.10.2025
:organisation: TU Dresden, FZM

WebCrawler
-----------
Zentrale Basisklasse für alle Crawler im Projekt `read_transactions_fm`.
- Einheitliches Logging über MainLogger
- Nutzung einer externen WebDriverFactory
- Robuste Typprüfung & flexible Datumsübergabe
- Standardmethoden für Login, Download, Verarbeitung und Speicherung
"""

# -------- start import block ---------

from __future__ import annotations

import os       # for file system operations
import sys      # for system-specific parameters and functions
import selenium.types   # for type hints
from selenium.webdriver.remote.webelement import WebElement     # for type hints
import shutil   # for file operations
import time     # for sleep and timeouts
import datetime # for date handling
import tempfile # for temporary directories
import pandas as pd     # for data manipulation
import re       # for regular expressions - filtern und verarbeiten von strings
import logging  # for logging
from typing import Any, Dict, Optional, Union   # for type hints
import warnings # for handling warnings

import inspect      # for better error logging
import linecache    # for better error logging

# own modules
from ..logger import MainLogger
from .webdriver import WebDriverFactory
from ..config import ConfigManager

# -------- /import block ---------

class WebCrawler:
    """
    Abstrakte Basisklasse für alle Crawler im Paket `read_transactions`.

    Diese Klasse kapselt den gesamten gemeinsamen Funktionsumfang:
    - zentrale Logging-Initialisierung über `MainLogger`
    - automatisches Laden von Konfiguration und Zugangsdaten aus `config.yaml`
    - standardisierte Selenium-WebDriver-Erzeugung über `WebDriverFactory`
    - konsistente Handhabung von Downloads, Datenverarbeitung und Speicherung

    Subklassen (z. B. `ArivaCrawler`, `AmazonCrawler`) müssen mindestens
    die Methoden `login()` und `download_data()` überschreiben.

    Typischer Ablauf:
        ```python
        with MyCrawler(start_date="01.01.2024", end_date="31.03.2024") as crawler:
            crawler.login()
            crawler.download_data()
            crawler.process_data()
            crawler.save_data()
        ```

    Parameter
    ----------
    name : str, optional
        Logisch eindeutiger Name der Crawler-Instanz (z. B. ``"ariva"``).
    output_path : str, optional
        Verzeichnis, in dem Ausgabedateien gespeichert werden (Standard: ``out``).
    start_date : str | pandas.Timestamp | datetime.date, optional
        Startdatum für den Datenabruf.
    end_date : str | pandas.Timestamp | datetime.date, optional
        Enddatum für den Datenabruf.
    details : bool, optional
        Ob zusätzliche Details extrahiert werden sollen?
        Uum beispiel bei trade_republic zusätzliche Order-Details oder bei amazon_visa vgl. mit amazon käufen.
        (Standard: ``True``).
    logging_level : str, optional
        Log-Level der Instanz (z. B. "DEBUG", "INFO", "WARNING").
        Standard: ``INFO``.
    global_log_level : str, optional
        Globales Log-Level für das gesamte Paket (Standard: ``INFO``).
    logfile : str, optional
        Pfad zu einer zentralen Logdatei (Standard: ``logs/read_transactions.log``).
    browser : str, optional
        Verwendeter Browser-Treiber (``edge``, ``chrome`` oder ``firefox``).
        Standard: ``edge``.
    headless : bool, optional
        Aktiviert Headless-Modus (sofern vom Browser unterstützt).
        Standard: ``False``.
    user_agent : str, optional
        Optionaler benutzerdefinierter User-Agent.

    Attribute
    ----------
    driver : selenium.webdriver.Remote
        Aktiver Selenium-WebDriver.
    data : pandas.DataFrame | dict[str, pandas.DataFrame]
        Heruntergeladene bzw. verarbeitete Daten.
    _credentials : dict
        Login-Daten des Crawlers (aus `config.yaml`).
    _urls : dict
        URL-Mappings des Crawlers (aus `config.yaml`).
    _logger : logging.Logger
        Instanzspezifischer Logger.
    _download_directory : str
        Temporäres Verzeichnis für heruntergeladene Dateien.
    """

    # ------------------------------------------------------------------
    # Konstruktor
    # ------------------------------------------------------------------
    def __init__(
            self,
            name: str = "WebCrawler",
            output_path: str = "out",
            start_date: Union[str, pd.Timestamp, datetime.date, None] = None,
            end_date: Union[str, pd.Timestamp, datetime.date, None] = None,
            details: bool = True,
            logging_level: str = "INFO",
            logfile: Optional[str | None] = None,
            *,
            browser: str = "edge",
            headless: bool = False,
            user_agent: Optional[str] = None,
    ) -> None:
        """Initialisiert den Crawler mit Standardparametern."""
        self.__name = name
        self.__output_path = output_path

        # Logging einrichten
        self._logging_lvl = logging_level
        if logfile:
            MainLogger.attach_file_for(self.__name, logfile, logging_level)
        self.__logger = MainLogger.get_logger(self.__name)
        MainLogger.set_stream_level(logging_level)

        # Zeitparameter setzen
        self.start_date = start_date
        self.end_date = end_date
        # sicherstellen, dass start_date nach end_date liegt (start_data >= end_date), sonst vertauschen
        if self.start_date < self.end_date:
            self._logger.warning(
                f"Startdatum {self.start_date.strftime('%d.%m.%Y')} liegt vor Enddatum "
                f"{self.end_date.strftime('%d.%m.%Y')}. Vertausche die Werte."
            )
            self.start_date, self.end_date = self.end_date, self.start_date

        # Details-Flag
        self.with_details = details

        # State & interne Felder
        self._state = "initialized"
        self._download_directory = tempfile.mkdtemp()
        self._logger.debug(f"Temporary download directory created: {self._download_directory}")
        self._initial_file_count = 0
        self.__credentials: Dict[str, str] = {}
        self.__urls: Dict[str, str] = {}
        self.__data: pd.DataFrame | Dict[str, pd.DataFrame] = pd.DataFrame()
        self.__account_balance = 0.0

        # WebDriver aus externer Factory
        self.driver = WebDriverFactory.create(
            browser=browser,
            headless=headless,
            download_dir=self._download_directory,
            user_agent=user_agent,
        )
        self.driver.minimize_window()

        self.__logger.info(f"WebCrawler {self.__name} initialized")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def name(self) -> str:
        """Name der Crawler-Instanz."""
        return self.__name

    @property
    def start_date(self) -> pd.Timestamp:
        """Startdatum (immer als pandas.Timestamp gespeichert)."""
        return self.__start_date

    @start_date.setter
    def start_date(self, value: Union[str, pd.Timestamp, datetime.date, None]):
        """
        Setzt das Startdatum. Unterstützte Typen: str (Format "DD.MM.YYYY"),
        pandas.Timestamp, datetime.date.

        Bei None wird das heutige Datum verwendet.

        :param value: Startdatum als str, pd.Timestamp, datetime.date oder None
        :return: -
        """
        if value is None:
            # genau heute (std, min, sec genau wie jetzt)
            value = pd.to_datetime("today") #- pd.DateOffset(days=1)
        if isinstance(value, str):
            value = pd.to_datetime(value, format="%d.%m.%Y", errors="raise")
        elif isinstance(value, datetime.date):
            value = pd.Timestamp(value)
        elif not isinstance(value, pd.Timestamp):
            raise TypeError("start_date must be str, datetime.date, or pd.Timestamp")
        self.__start_date = value

    @property
    def end_date(self) -> pd.Timestamp:
        """Enddatum (immer als pandas.Timestamp gespeichert)."""
        return self.__end_date

    @end_date.setter
    def end_date(self, value: Union[str, pd.Timestamp, datetime.date, None]):
        """
        Setzt das Enddatum. Unterstützte Typen: str (Format "DD.MM.YYYY"),
        pandas.Timestamp, datetime.date.

        Bei None wird das Datum von vor 6 Monaten verwendet.

        :param value: Enddatum als str, pd.Timestamp, datetime.date oder None
        :return: -
        """
        if value is None:
            # nur auf den tag genau - 6 monate
            value = pd.to_datetime("today") - pd.DateOffset(months=6)
            value = pd.Timestamp(year=value.year, month=value.month, day=value.day)
        if isinstance(value, str):
            value = pd.to_datetime(value, format="%d.%m.%Y", errors="raise")
        elif isinstance(value, datetime.date):
            value = pd.Timestamp(value)
        elif not isinstance(value, pd.Timestamp):
            raise TypeError("end_date must be str, datetime.date, or pd.Timestamp")
        self.__end_date = value

    @property
    def data(self) -> Union[pd.DataFrame, Dict[str, pd.DataFrame]]:
        """Heruntergeladene und ggf. verarbeitete Daten."""
        return self.__data

    @data.setter
    def data(self, value: Union[pd.DataFrame, Dict[str, pd.DataFrame]]):
        """
        Setzt die heruntergeladenen/verarbeiteten Daten.

        :param value: Daten als DataFrame oder dict[str, DataFrame]
        :type value: pd.DataFrame | dict[str, pd.DataFrame]
        :return: -
        """
        if not (isinstance(value, pd.DataFrame) or (isinstance(value, dict) and all(isinstance(v, pd.DataFrame) for v in value.values()))):
            raise TypeError("data must be a pandas DataFrame or dict[str, DataFrame]")
        self.__data = value

    @property
    def _credentials(self) -> Dict[str, str]:
        """
        Login-Daten für den Crawler. Beinhaltet z. B. Benutzername und Passwort.
        - user: str, Benutzername
        - password: str, Passwort
        """
        return self.__credentials

    @property
    def _urls(self) -> Dict[str, str]:
        """
        URLs für den Crawler. Beinhaltet z. B. Login- und Download-Links.
        - login: str, Login-URL
        - transactions: str, Transaktions-URL
        - kurse: Dict[str, str]: Kurs-URLs
        """
        return self.__urls

    @property
    def _logger(self) -> logging.Logger:
        """Interner Logger (für Subklassen)."""
        return self.__logger
    @property
    def account_balance(self) -> str:
        """Gibt den aktuellen Kontostand zurück."""
        return str(round(self.__account_balance, 2)) + " €"
    @account_balance.setter
    def account_balance(self, value: Any) -> None:
        """
        Setzt den aktuellen Kontostand.
        Args:
            value (str | float | int): Neuer Kontostand-Wert.
        """
        value = self._normalize_amount(value)
        try:
            value = float(value)
        except (ValueError, TypeError):
            self._logger.error(f"Ungültiger Kontostand-Wert: {value}")
            value = 0.0
        self.__account_balance = value

    @property
    def with_details(self) -> bool:
        """
        Gibt zurück, ob zusätzliche Details extrahiert werden:

        - Bei Trade Republic z. B. zusätzliche Order-Details
        - Bei Amazon Visa z. B. Verknüpfung mit Amazon-Käufen

        """
        return self.__with_details
    @with_details.setter
    def with_details(self, value: bool) -> None:
        """Setzt, ob zusätzliche Details extrahiert werden."""
        if isinstance(value, str):
            value = value.lower() in ['true', '1', 'yes', 'y']
        if not isinstance(value, bool):
            self._logger.warning(f"with_details muss ein bool sein, nicht {type(value)}. Setze auf True.")
            value = True
        self.__with_details = value

    # ------------------------------------------------------------------
    # Lifecycle-Methoden
    # ------------------------------------------------------------------
    def login(self) -> None:
        """Wird von Subklassen überschrieben – führt Login auf der Webseite aus."""
        self._state = "login"
        self.__logger.info(f"Starting login process für {self.__name}")
        self.driver.get(self._urls.get("login", "about:blank"))

    def download_data(self) -> None:
        """Wird von Subklassen überschrieben – startet Download-Vorgang."""
        self._state = "download_data"
        self.__logger.info(
            f"Downloading der Daten vom {self.start_date.strftime('%d.%m.%Y')} "
            f"bis zum {self.end_date.strftime('%d.%m.%Y')} gestartet.")

    def process_data(self, read_temp_files: bool = True, sep: str = ';') -> None:
        """Optional von Subklassen überschreiben – verarbeitet geladene Daten.
        Standardmäßig werden alle Dateien im temporären Download-Verzeichnis eingelesen
        und in ein einziges DataFrame zusammengeführt.
        Dabei wird die Funktion `preprocess_data()` für jedes DataFrame aufgerufen.

        Im Anschluss wird `self.data` normalisiert.

        Args:
            read_temp_files (bool, optional): Ob Dateien im temporären Download-Verzeichnis eingelesen werden sollen.
            sep (str, optional): Trennzeichen für CSV-Dateien. Standard ist ';'.
        Returns:
            None
        """
        self._state = "process_data"
        if read_temp_files:
            if not self._read_temp_files(sep=sep):
                self._logger.debug('Keine Dateien im Temp-Verzeichnis')

        if len(self.data) == 0:
            self._logger.warning("Keine Transaktionen zum Verarbeiten gefunden.")
            return

        merged_df = pd.DataFrame()

        try:
            if isinstance(self.data, dict):
                for key, df in self.data.items():
                    merged_df = pd.merge(
                        left=merged_df,
                        right=self.preprocess_data(key, df), how='outer'
                    ) if not merged_df.empty else self.preprocess_data(key, df)
                self.data = merged_df
            else:
                self.data = self.preprocess_data("", self.data)

        except Exception:
            self._logger.error("Fehler bei der Datenverarbeitung", exc_info=True)


    def preprocess_data(self, key: str, df: pd.DataFrame) -> pd.DataFrame:
        """
        Bereinigt ein einzelnes DataFrame.
        Für weitere Verarbeitung muss funktion in Unterklasse überschrieben werden.

        Args:
            key (str): Schlüssel des DataFrames (bei dict-Daten).
            df (pd.DataFrame): Eingabedaten.
        Returns:
            pd.DataFrame: Bereinigte Daten.
        """
        # header entfernen
        df = self._delete_header(df, header_key='Datum')
        return df

    def save_data(self) -> None:
        """Speichert geladene Daten als CSV."""
        def _save_df_to_csv(df: pd.DataFrame, name: str) -> None:
            # name und pfad erstellen
            filename = f"{name}.csv"
            file_path = os.path.join(self.__output_path, filename)

            # df formatiert speicher
            df.to_csv(file_path, sep=";", index=False, date_format="%d.%m.%Y")
            self._logger.info(f"Data saved to: {os.path.abspath(file_path)}")

        try:
            os.makedirs(self.__output_path, exist_ok=True)
            if isinstance(self.__data, pd.DataFrame):
                _save_df_to_csv(self.__data, self.__name)
                # file_path = os.path.join(self.__output_path, f"{self.__name}.csv")
                # self.__data.to_csv(file_path, sep=";", index=False)
                # self._logger.info(f"Data saved to: {os.path.abspath(file_path)}")
            elif isinstance(self.__data, dict):
                for fname, df in self.__data.items():
                    _save_df_to_csv(df, fname)
                    # file_path = os.path.join(self.__output_path, f"{fname}.csv")
                    # df.to_csv(file_path, sep=";", index=False)
                    # self.__logger.info(f"Data saved to: {os.path.abspath(file_path)}")
        except Exception:
            self.__logger.error("Error saving data", exc_info=True)

    def close(self) -> None:
        """Schließt WebDriver und löscht temporäre Ordner."""
        try:
            if hasattr(self, "driver"):
                self.driver.quit()
        except Exception:
            self.__logger.warning("Driver quit failed", exc_info=True)
        try:
            shutil.rmtree(self._download_directory)
            self.__logger.debug(f"Temporary directory removed: {self._download_directory}")
        except Exception:
            self.__logger.warning("Could not remove temporary directory", exc_info=True)
        self.__logger.info(f"WebCrawler {self.__name} closed")

    # ------------------------------------------------------------------
    # Config & Credentials
    # ------------------------------------------------------------------
    def _load_config(self) -> None:
        """
        Lädt Crawler-spezifische Konfiguration aus der zentralen config.yaml.

        Diese Methode liest:
          - Zugangsdaten (user, password, token, ...)
          - URLs (für den jeweiligen Crawler)

        Raises:
            FileNotFoundError: Wenn keine gültige config.yaml gefunden wurde.
            KeyError: Wenn keine passenden Einträge für diesen Crawler vorhanden sind.
        """
        try:
            self.__credentials = ConfigManager.get_credentials(self.__name)
            self.__urls = ConfigManager.get_urls(self.__name)
            self._logger.info(f"Konfiguration für {self.__name} geladen.")
        except FileNotFoundError as e:
            self._logger.error(f"Config-Datei nicht gefunden: {e}")
            self.close()
            raise
        except KeyError as e:
            self._logger.warning(f"Eintrag fehlt in config.yaml: {e}")
            self.close()
            raise
        except Exception as e:
            self._logger.error(f"Fehler beim Laden der Konfiguration: {e}", exc_info=True)
            self.close()
            raise

    # ------------------------------------------------------------------
    # Context Manager
    # ------------------------------------------------------------------
    def __enter__(self) -> "WebCrawler":
        """
        Context-Manager-Einstiegspunkt.

        Wird automatisch aufgerufen, wenn der Crawler in einem
        `with`-Block verwendet wird. Gibt die aktuelle Instanz zurück,
        sodass alle Methoden wie gewohnt verfügbar sind.

        Beispiel:
            >>> with WebCrawler(browser="edge", headless=True) as crawler:
            ...     crawler.login()
            ...     crawler.download_data()
            ...     crawler.process_data()
            ...     crawler.save_data()
            # Nach Ende des Blocks wird automatisch close() ausgeführt.
        """
        self._logger.debug("Entering context manager")
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        """
        Context-Manager-Ausstiegspunkt.

        Wird automatisch aufgerufen, wenn der `with`-Block endet,
        unabhängig davon, ob ein Fehler aufgetreten ist.
        Führt `close()` aus, um den WebDriver zu schließen und temporäre
        Dateien zu löschen.

        Args:
            exc_type: Typ der Exception (falls eine aufgetreten ist)
            exc_value: Exception-Instanz
            traceback: Traceback-Objekt der Exception

        Returns:
            bool: False, damit Exceptions im `with`-Block *nicht*
            unterdrückt werden. (Python wirft sie weiter.)
        """
        if exc_type is not None:
            self._logger.error(f"Exception occurred in context type {str(exc_type)}, value {str(exc_value)}")
        self.close()
        self._logger.debug(f"Exiting context manager for {self.__name}")
        # False sorgt dafür, dass Exceptions weitergereicht werden
        return False

    # -----------------------------------------------------------------------------------------------------------------
    # Download & Selenium Helpers
    # -----------------------------------------------------------------------------------------------------------------
    def wait_for_element(self, by: str, selector: str, timeout: int = 15) -> WebElement:
        """
        Wartet auf das Vorhandensein eines Elements und gibt es zurück.

        Args:
            by (str | selenium.webdriver.common.by.By):
                Suchstrategie für Selenium. Akzeptiert entweder:
                - einen case‑insensitiven String-Key (siehe *Accepted string keys*)
                - oder direkt eine Selenium-By‑Konstante (z. B. `By.CSS_SELECTOR`).
                Bei Übergabe eines bereits aufgelösten By/Tuple wird dieses direkt verwendet.
            selector (str):
                Selektor-String passend zur gewählten Strategie (z. B. CSS-Selector oder XPath).
            timeout (int, optional):
                Maximale Wartezeit in Sekunden. Standard ist 15.

        Returns:
            WebElement: Das gefundene Webelement.

        Raises:
            selenium.common.exceptions.TimeoutException:
                Wenn das Element innerhalb der `timeout`-Zeit nicht gefunden wird.

        Accepted string keys (case-insensitive) and mapping:
            - "id"                 -> By.ID
            - "name"               -> By.NAME
            - "css", "css selector"-> By.CSS_SELECTOR
            - "xpath"              -> By.XPATH
            - "link text"          -> By.LINK_TEXT
            - "partial link text"  -> By.PARTIAL_LINK_TEXT
            - "tag"                -> By.TAG_NAME
            - "class"              -> By.CLASS_NAME

        Default behavior:
            Wenn ein unbekannter String-Key übergeben wird, wird `By.CSS_SELECTOR` als Fallback verwendet.
            Wenn bereits eine By-Konstante oder ein Tuple `(By.SOMETHING, selector)` übergeben wird,
            wird dieser Wert unverändert verwendet.

        Examples:
            >>> # mit String-Key (case-insensitive)
            >>> elem = self.wait_for_element("css", "div.my-class")
            >>> # mit vollständigem Key
            >>> elem = self.wait_for_element("css selector", "div.my-class")
            >>> # mit Selenium By-Konstante
            >>> from selenium.webdriver.common.by import By
            >>> elem = self.wait_for_element(By.ID, "username")
            >>> # direktes Tuple (By, selector) möglich, falls intern verwendet
            >>> elem = self.wait_for_element((By.XPATH, "//button[text()=\\"OK\\"]"), None)

        """
        from selenium.webdriver.common.by import By as _By
        from selenium.webdriver.support.ui import WebDriverWait as _WebDriverWait
        from selenium.webdriver.support import expected_conditions as _EC

        by_map = {
            "id": _By.ID,
            "name": _By.NAME,
            "css": _By.CSS_SELECTOR,
            "css selector": _By.CSS_SELECTOR,
            "xpath": _By.XPATH,
            "link text": _By.LINK_TEXT,
            "partial link text": _By.PARTIAL_LINK_TEXT,
            "tag": _By.TAG_NAME,
            "class": _By.CLASS_NAME,
        }
        _by = by_map.get(str(by).lower(), _By.CSS_SELECTOR)
        return _WebDriverWait(self.driver, timeout).until(
            _EC.presence_of_element_located((_by, selector))
        )

    def wait_clickable_and_click(self, by: str, selector: str, timeout: int = 15) -> None:
        """Wartet auf ein Element und klickt es dann an.

        Args:
            by (str | By): Suchstrategie oder `By`-Konstante.
            selector (str): Selektor-String.
            timeout (int, optional): Timeout in Sekunden. Standard 15.

        See also:
            wait_for_element: Wartet auf das Element und gibt es zurück (verwendet von dieser Methode).

        Sphinx cross-reference (für generierte Docs / IDE‑Plugins):
            :meth:`wait_for_element`
            or fully qualified:
            :meth:`~read_transactions.webcrawler.base.WebCrawler.wait_for_element`
        """
        elem = self.wait_for_element(by, selector, timeout)
        elem.click()

    def find_first_matching_element(
            self, selectors: list[tuple[str, str]], timeout_each: int = 10, debug_msg: bool = False) -> WebElement:
        """
        Versucht mehrere Selektoren nacheinander und gibt das erste gefundene Element zurück.
        Args:
            selectors: Liste von (by, selector)-Tupeln.
            timeout_each: Timeout pro Selektor in Sekunden.
        Returns:
            WebElement: Erstes gefundenes Element.
        Raises:
            selenium.common.exceptions.TimeoutException:
                Wenn kein Element für die gegebenen Selektoren gefunden wird.

        Example:
            >>> selectors = (("css", "div.class1"), ("xpath", "//div[@id='main']"))
            >>> elem = self.find_first_matching_element(selectors, timeout_each=5)

        See also:
        wait_for_element: Wartet auf das Element und gibt es zurück (verwendet von dieser Methode).

        Sphinx cross-reference (für generierte Docs / IDE‑Plugins):
            :meth:`wait_for_element`
            or fully qualified:
            :meth:`~read_transactions.webcrawler.base.WebCrawler.wait_for_element`

        """
        from selenium.common.exceptions import TimeoutException
        for sel_tuple in selectors:
            by, selector = sel_tuple
            try:
                elem = self.wait_for_element(by, selector, timeout=timeout_each)
                if debug_msg:
                    self._logger.debug(f"Element gefunden mit selector {selector}")
                return elem
            except TimeoutException:
                continue
        raise TimeoutException("Kein Element für die gegebenen Selektoren gefunden.")

    def click_first_matching_element(self, selectors: list[tuple[str, str]], timeout_each: int = 10) -> None:
        """
        Versucht mehrere Selektoren nacheinander und klickt das erste gefundene Element an.
        Args:
            selectors: Liste von (by, selector)-Tupeln.
            timeout_each: Timeout pro Selektor in Sekunden.
        Raises:
            selenium.common.exceptions.TimeoutException:
                Wenn kein Element für die gegebenen Selektoren gefunden wird.

        Example:
            >>> selectors = (("css", "button.accept"), ("xpath", "//button[text()='Accept']"))
            >>> self.click_first_matching_element(selectors, timeout_each=5)
        """
        elem = self.find_first_matching_element(selectors, timeout_each)
        elem.click()

    def find_all_in(
            self, elem: WebElement, selectors: list[tuple[str, str]], debug_msg: bool = False) -> list[WebElement]:
        """Findet alle passenden Unterelemente innerhalb eines Elements."""
        from selenium.webdriver.common.by import By as _By
        from selenium.common.exceptions import TimeoutException

        by_map = {
            "id": _By.ID,
            "name": _By.NAME,
            "css": _By.CSS_SELECTOR,
            "css selector": _By.CSS_SELECTOR,
            "xpath": _By.XPATH,
            "link text": _By.LINK_TEXT,
            "partial link text": _By.PARTIAL_LINK_TEXT,
            "tag": _By.TAG_NAME,
            "class": _By.CLASS_NAME,
        }
        for by, selector in selectors:
            list_elems = []
            _by = by_map.get(str(by).lower(), _By.CSS_SELECTOR)
            try:
                list_elems = elem.find_elements(_by, selector)
                if len(list_elems) > 0:
                    if debug_msg:
                        self._logger.debug(f"Elemente gefunden mit selector {selector}, count: {len(list_elems)}")
                    return list_elems
            except Exception:
                continue
        raise TimeoutException

    def find_first_in(self, elem: WebElement, selectors: list[tuple[str, str]], debug_msg: bool = False) -> WebElement:
        """Findet das erste passende Unterelement innerhalb eines Elements."""
        from selenium.webdriver.common.by import By as _By
        from selenium.common.exceptions import TimeoutException

        by_map = {
            "id": _By.ID,
            "name": _By.NAME,
            "css": _By.CSS_SELECTOR,
            "css selector": _By.CSS_SELECTOR,
            "xpath": _By.XPATH,
            "link text": _By.LINK_TEXT,
            "partial link text": _By.PARTIAL_LINK_TEXT,
            "tag": _By.TAG_NAME,
            "class": _By.CLASS_NAME,
        }
        for by, selector in selectors:
            _by = by_map.get(str(by).lower(), _By.CSS_SELECTOR)
            try:
                found_elem = elem.find_element(_by, selector)
                if debug_msg:
                    self._logger.debug(f"Element gefunden mit selector {selector}")
                return found_elem
            except Exception:
                continue
        raise TimeoutException


    def scroll_into_view(self, element) -> None:
        """Scrollt ein Element ins Viewport."""
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)

    def click_js(self, element) -> None:
        """Klickt ein Element via JavaScript (Fallback bei Overlay o.Ä.)."""
        self.driver.execute_script("arguments[0].click();", element)

    def accept_cookies_if_present(self, selectors: tuple[str, ...] = ("button#onetrust-accept-btn-handler",
                                                                      "button[aria-label='Akzeptieren']",
                                                                      "button.cookie-accept"),
                                  timeout_each: int = 3) -> bool:
        """Versucht gängige Cookie-Banner wegzuklicken.

        Args:
            selectors: Liste möglicher CSS-Selektoren für Zustimmungs-Buttons.
            timeout_each: Zeitfenster pro Selektor.

        Returns:
            bool: True, wenn ein Banner geschlossen wurde.
        """
        from selenium.common.exceptions import TimeoutException as _Timeout
        for css in selectors:
            try:
                self.wait_clickable_and_click("css", css, timeout=timeout_each)
                self._logger.debug(f"Cookie-Banner bestätigt selector {css}")
                return True
            except _Timeout:
                continue
            except Exception:
                # Banner evtl. schon weg – kein harter Fehler
                continue
        return False

    def _wait_for_new_file(self, timeout: float = 30, check_interval: float = 0.5, include_temp: bool = True) -> Optional[str]:
        """Wartet auf eine neue Datei im Download-Ordner und gibt deren Dateinamen zurück.

        Args:
            timeout: Maximale Wartezeit in Sekunden.
            check_interval: Prüfintervall in Sekunden.
            include_temp: Ob temporäre Dateien (.crdownload/.tmp) berücksichtigt werden.

        Returns:
            Der Dateiname der neu erkannten Datei oder None bei Timeout.
        """
        start_time = time.time()
        last_log_time = start_time

        def list_files() -> list[str]:
            try:
                files = os.listdir(self._download_directory)
                if not include_temp:
                    files = [f for f in files if not f.endswith((".crdownload", ".tmp"))]
                return files
            except Exception:
                self._logger.error("Fehler beim Auflisten der Dateien", exc_info=True)
                return []

        if not hasattr(self, "_initial_file_count"):
            try:
                self._initial_file_count = len(list_files())
                self._logger.debug(f"Initialer Dateicount gesetzt count: {self._initial_file_count}")
            except Exception:
                self._logger.error("Fehler beim Setzen des initialen Dateicounts", exc_info=True)
                return None

        while time.time() - start_time < timeout:
            try:
                current_files = list_files()
                current_count = len(current_files)
                if current_count > self._initial_file_count:
                    newest_file = max(
                        (os.path.join(self._download_directory, f) for f in current_files),
                        key=os.path.getmtime
                    )
                    filename = os.path.basename(newest_file)
                    self._logger.debug(f"Neue Datei erkannt: {filename}")
                    self._initial_file_count = current_count
                    return filename
                if (time.time() - last_log_time) >= 2.0:
                    last_log_time = time.time()
                    self._logger.info(f'Warte auf neue Datei... time remaining: {round(timeout - (time.time() - start_time), 1)}s')
                time.sleep(check_interval)
            except Exception:
                self._logger.error("Fehler in der Überwachungsschleife", exc_info=True)
                return None

        self._logger.warning(f"Timeout – keine neue Datei erkannt timeout: {timeout}")
        return None

    def _read_temp_files(
            self,
            sep: str = ';',
            max_retries: int = 10,
            retry_wait: float = 1.0,
            check_interval: float = 0.1,
            download_timeout: float = 10.0,
    ) -> bool:
        """Liest Dateien aus dem Download-Ordner in `self.data`.

        Unterstützt CSV, XLS, XLSX. Wartet optional, bis temporäre
        Download-Dateien (.crdownload/.tmp) verschwunden sind.

        Returns:
            True bei Erfolg, sonst False.
        """
        retries = 0
        while retries < max_retries:
            try:
                files_in_dir = os.listdir(self._download_directory)
                self._logger.debug(f"Dateien im temporären Verzeichnis {files_in_dir}")

                if not files_in_dir:
                    self._logger.debug("Keine Datei im temporären Verzeichnis gefunden.")
                    retries += 1
                    time.sleep(retry_wait)
                    continue

                start_time = time.time()
                while time.time() - start_time < download_timeout:
                    pending = [f for f in os.listdir(self._download_directory) if f.endswith((".tmp", ".crdownload"))]
                    if not pending:
                        break
                    self._logger.info(
                        f"Warte auf unvollständige Downloads pending:{pending}, "
                        f"remaining: {round(download_timeout - (time.time() - start_time), 1)}"
                    )
                    time.sleep(check_interval)

                pending = [f for f in os.listdir(self._download_directory) if f.endswith((".tmp", ".crdownload"))]
                if pending:
                    self._logger.warning(f"Timeout: Dateien unvollständig: {pending}")
                    return False

                file_content: Dict[str, pd.DataFrame] = {}
                for f in os.listdir(self._download_directory):
                    downloaded_file = os.path.join(self._download_directory, f)
                    try:
                        if f.lower().endswith(".csv"):
                            df = pd.read_csv(downloaded_file, sep=sep)
                        elif f.lower().endswith(".xls"):
                            df = pd.read_excel(downloaded_file, engine='xlrd')
                        elif f.lower().endswith(".xlsx"):
                            with warnings.catch_warnings():
                                warnings.filterwarnings(
                                    "ignore",
                                    message="Workbook contains no default style, apply openpyxl's default",
                                    category=UserWarning,
                                )
                                df = pd.read_excel(downloaded_file, engine='openpyxl')
                        else:
                            continue
                        file_content[f] = df
                        self._logger.debug(f"Datei mit name {f} eingelesen, rows: {len(df)}")
                    except Exception:
                        self._logger.error("Fehler beim Einlesen einer Datei", exc_info=True)

                if not file_content:
                    # self._logger.warning("Keine unterstützten Dateien gefunden")
                    return False

                # Bei 1 Datei → direkt DF speichern, sonst dict
                self.data = file_content if len(file_content) > 1 else next(iter(file_content.values()))
                self._logger.info(f"{len(file_content)} Datei(en) erfolgreich eingelesen")
                return True

            except Exception:
                self._logger.error("Fehler beim Einlesen der heruntergeladenen Dateien", exc_info=True)
                return False

        self._logger.debug("Maximale Wiederholungen erreicht – ggf. unvollständige Downloads")
        return False

    def _retry_func(self, func, max_retries: int = 3, wait_seconds: float = 1.0,
                    args: Optional[tuple] = None, kwargs:Optional[dict] = None) -> bool:
        """Versucht die Funktion mehrfach bei Fehlschlag.

        Args:
            func: Funktion, die ausgeführt werden soll.
            max_retries: Maximale Anzahl an Versuchen.
            wait_seconds: Wartezeit zwischen den Versuchen.
        Returns:
            bool: True bei erfolgreicher Ausfürhung, sonst False.
        """
        from selenium.common.exceptions import TimeoutException

        if args is None:
            args = ()
        if kwargs is None:
            kwargs = {}
        for attempt in range(1, max_retries + 1):
            try:
                func(*args, **kwargs)
                self._logger.debug(f"Funktion {func} erfolgreich nach {attempt} Versuch(en)")
                return True
            except TimeoutException:
                self._logger.debug(f"Funktion {func} bei Versuch {attempt} fehlgeschlagen: Timeout")
                if attempt < max_retries:
                    time.sleep(wait_seconds)
            except Exception as e:
                self._logger.debug(f"Funktion {func} bei Versuch {attempt}", exc_info=True)
                if attempt < max_retries:
                    time.sleep(wait_seconds)
        self._logger.error(f"Maximale Versuche erreicht – Funktion {func} fehlgeschlagen")
        return False

    def _wait_for_manual_exit(self, msg: str = None):
        """
        Wartet auf manuelles Schließen des Browsers durch den Nutzer.

        :param msg: Nachricht, die angezeigt werden soll. (Optional)
        :return: -
        """

        msg = f"Drücke ENTER, um fortzufahren \n {msg}"
        self._logger.info(msg)
        input("\n")

    def _wait_for_condition(self, condition_func, timeout: float = 30.0, check_interval: float = 0.5) -> bool:
        """Wartet, bis eine Bedingungsfunktion True zurückgibt.

        Args:
            condition_func: Funktion, die eine boolesche Bedingung prüft.
            timeout: Maximale Wartezeit in Sekunden.
            check_interval: Prüfintervall in Sekunden.
        Returns:
            bool: True, wenn die Bedingung erfüllt wurde, sonst False.
        """
        start_time = time.time()
        last_time_log = start_time
        while time.time() - start_time < timeout:
            try:
                if (time.time() - last_time_log) >= 5.0:
                    last_time_log = time.time()
                    self._logger.info(f'Warte auf Bedingung... verbleibende Zeit: {round(timeout - (time.time() - start_time), 1)}s')
                if condition_func():
                    self._logger.debug("Bedingung erfüllt")
                    return True
                time.sleep(check_interval)
            except Exception:
                self._logger.error("Fehler beim Ausführen der Bedingungsfunktion", exc_info=True)
                return False
        self._logger.debug("Timeout – Bedingung nicht erfüllt")
        return False
    # -----------------------------------------------------------------------------------------------------------------

    # -----------------------------------------------------------------------------------------------------------------
    # DataFrame Helpers
    # -----------------------------------------------------------------------------------------------------------------

    # ---------- Header Removal ------------
    def _delete_header(self, df: pd.DataFrame, header_key: str = 'datum') -> pd.DataFrame:
        """
        Löscht die Header-Zeile bis zum header_key aus einem DataFrame und setzt die Spaltennamen.

        :param df: Eingabe-DataFrame.
        :param header_key: Key der Spalte, die im Header enthalten sein muss. (Standard: 'datum')
        :return: DataFrame ohne Header-Zeile.
        """
        # Falls Datei leer oder None
        if df is None or df.empty:
            self._logger.debug("⚠️ DataFrame ist None oder leer")
            return pd.DataFrame()
        # Finde die Header-Zeile
        header_row_idx = None
        for i, row in df.iterrows():
            first_val = str(row.iloc[0]).strip().lower()
            if first_val == header_key.lower():
                header_row_idx = i
                break
        if header_row_idx is not None and header_row_idx > 0:
            self._logger.debug(f"✅ Header gefunden in Zeile {header_row_idx}")
            df = df.iloc[header_row_idx:].reset_index(drop=True)
            # erste Zeile als Header setzen
            df.columns = df.iloc[0].to_list()
            return df.drop(0, axis=0).reset_index(drop=True)
        else:
            self._logger.debug(f"⚠️ Kein Header gefunden in DataFrame")
            return df  # Header nicht gefunden, Original zurückgeben


    # ---------- Data Normalization ------------
    def _normalize_dataframe(self, df: pd.DataFrame, remove_nan: bool = False, date_as_str: bool = False) -> pd.DataFrame:
        """
        Normalisiert die Transaktionsdaten eines DataFrames.
        - Datumsspalten in einheitliches Format bringen
        - Betragsspalten bereinigen
        - Spaltennamen vereinheitlichen

        :param df: Eingabe-DataFrame.
        :param remove_nan: Ob Zeilen mit NaN-Werten entfernt werden sollen. (Standard: False)
        :return: DataFrame mit normalisierten Daten.
        """
        # -------------------------------------------------------------------------------------------------------------
        # Spaltennamen erkennen und umbenennen
        # -------------------------------------------------------------------------------------------------------------
        # Datumsspalte
        date_cols = [col for col in df.columns if 'datum' in str(col).lower()]
        if len(date_cols) > 1:
            self._logger.debug(f"Mehrere Datumsspalten erkannt: {date_cols}, verwende die erste.")
        date_cols = date_cols[0] if date_cols else None
        # Betragsspalte
        amount_cols = [col for col in df.columns if any(x in str(col).lower() for x in ['betrag', 'summe', 'amount'])]
        if len(amount_cols) > 1:
            self._logger.debug(f"Mehrere Betragsspalten erkannt: {amount_cols}, verwende die erste.")
        amount_cols = amount_cols[0] if amount_cols else None
        # Verwendungszweck-Spalte
        purpose_cols = [col for col in df.columns if any(x in str(col).lower() for x in ['verwendungszweck', 'zweck', 'purpose', 'beschreibung'])]
        if len(purpose_cols) > 1:
            self._logger.debug(f"Mehrere Verwendungszweck-Spalten erkannt: {purpose_cols}, verwende die erste.")
        purpose_cols = purpose_cols[0] if purpose_cols else None
        # Empfänger/Absender-Spalte
        party_cols = [col for col in df.columns if any(x in str(col).lower() for x in ['empfänger', 'absender', 'receiver', 'sender', 'name'])]
        if len(party_cols) > 1:
            self._logger.debug(f"Mehrere Empfänger-Spalten erkannt: {party_cols}, verwende die erste.")
        party_cols = party_cols[0] if party_cols else None
        # Spalten umbenennen
        rename_map = {}
        if date_cols:
            rename_map[date_cols] = 'Datum'
        if amount_cols:
            rename_map[amount_cols] = 'Betrag'
        if purpose_cols:
            rename_map[purpose_cols] = 'Verwendungszweck'
        if party_cols:
            rename_map[party_cols] = 'Empfänger'
        df = df.rename(columns=rename_map)
        self._logger.debug(f"Spalten umbenannt: {rename_map}")
        # -------------------------------------------------------------------------------------------------------------

        # -------------------------------------------------------------------------------------------------------------
        # Normalisierungen durchführen
        # -------------------------------------------------------------------------------------------------------------
        # Datumsspalte normalisieren
        if date_cols:
            date_cols = rename_map[date_cols]  # aktualisierter Spaltenname
            df = self._normalize_date_in_dataframe(df, date_cols, date_as_str=date_as_str)
        # Betragsspalte normalisieren
        if amount_cols:
            amount_cols = rename_map[amount_cols]  # aktualisierter Spaltenname
            df = self._normalize_amount_in_dataframe(df, amount_cols, remove_nan=remove_nan)
        self._logger.debug("DataFrame normalisiert")

        # alle unerkannten Spaltennamen als key: value in spalte verwendungszweck 2 speichern
        # known_columns = [date_cols, amount_cols, purpose_cols, party_cols]  # da umbenannt, nicht mehr fkt.fähig
        known_columns = list(rename_map.values())
        unknown_cols = [col for col in df.columns if col not in known_columns]
        if unknown_cols:
            if len(unknown_cols) == 1:
                col = unknown_cols[0]
                df["Verwendungszweck 2"] = (
                    df[col]
                    .astype(str)
                    .apply(lambda v: " ".join(str(v).split()).strip() if pd.notna(v) and str(v).lower() != "nan" and str(v).strip() != "" else "")
                )
            else:

                df["Verwendungszweck 2"] = (
                    df[unknown_cols]
                    .astype(str)
                    .agg(lambda x: " | ".join(f"{col}: {' '.join(str(val).split()).strip()}" for col, val in x.items() if val and val != "nan"), axis=1)
                )
            # unbekannte Spalten entfernen
            df = df.drop(columns=unknown_cols)
            self._logger.debug(f"Unbekannte Spalten in 'Verwendungszweck 2' zusammengefasst: {unknown_cols}")
        # -------------------------------------------------------------------------------------------------------------
        return df

    def _normalize_date_in_dataframe(self, df: pd.DataFrame, date_column: str, *,
                                     date_as_str: bool = False, dayfirst: bool = True
                                     ) -> pd.DataFrame:
        """
        Normalisiert die Datumswerte in der angegebenen Spalte eines DataFrames.

        Args:
            df: Eingabe-DataFrame.
            date_column: Name der Spalte mit den Datumswerten.
            date_as_str: Ob das Datum als String zurückgegeben werden soll. (Standard: False)
            dayfirst: Ob der Tag vor dem Monat steht. (Standard: True)
        Returns:
            DataFrame mit normalisierten Datumswerten.
        """
        if date_column not in df.columns:
            self._log_error_with_debug_msg(f"Datumsspalte '{date_column}' nicht im DataFrame gefunden.")
            return df

        try:
            df[date_column] = pd.to_datetime(df[date_column], errors='coerce', dayfirst=dayfirst)
            # NaT (Not a Time) behandeln
            before_drop = len(df)
            df = df.dropna(subset=[date_column])  # Zeilen mit ungültigen Daten entfernen
            dropped = before_drop - len(df)
            if dropped > 0:
                self._logger.info(f"{dropped} Zeilen mit ungültigen Datumseinträgen entfernt.")
            # Start und Enddatum filtern
            before_drop = len(df)
            df = df[(df[date_column] <= self.start_date) & (df[date_column] >= self.end_date)]
            dropped = before_drop - len(df)
            if dropped > 0:
                self._logger.info(f"{dropped} Zeilen außerhalb des Datumsbereichs entfernt.")
            # formatieren
            # -> als datetime belassen und beim speichern formatieren
            if date_as_str:
                df[date_column] = df[date_column].dt.strftime('%d.%m.%Y')
        except Exception:
            self._logger.error("Fehler bei der Normalisierung der Datumsspalte", exc_info=True)

        return df

    def _normalize_amount_in_dataframe(self, df: pd.DataFrame, amount_column: str,* ,
                                       remove_nan: bool = False,
                                       ) -> pd.DataFrame:
        """
        Normalisiert die Beträge in der angegebenen Spalte eines DataFrames.

        Args:
            df: Eingabe-DataFrame.
            amount_column: Name der Spalte mit den Beträgen.
            remove_nan: Ob Zeilen mit NaN-Werten entfernt werden sollen. (Standard: False)
        Returns:
            DataFrame mit normalisierten Beträgen.

        """
        if amount_column not in df.columns:
            self._log_error_with_debug_msg(f"Betragsspalte '{amount_column}' nicht im DataFrame gefunden.")
            return df

        try:
            df[amount_column] = df[amount_column].pipe(self._normalize_amount)
            # NaN-Werte behandeln - entweder entfernen oder auf 0 setzen
            if remove_nan:  # Zeilen mit NaN entfernen
                before_drop = len(df)
                df = df.dropna(subset=[amount_column])  # Zeilen mit ungültigen Beträgen entfernen
                dropped = before_drop - len(df)
                if dropped > 0:
                    self._logger.debug(f"{dropped} Zeilen mit ungültigen Betragseinträgen entfernt.")
            else:  # NaN-Werte auf 0 setzen
                df[amount_column] = df[amount_column].fillna(0.0)
        except Exception:
            self._logger.error("Fehler bei der Normalisierug der Betragsspalte", exc_info=True)

        return df


    # -------- Betrag normalisieren --------------------
    def _normalize_amount(self, value: Any) -> float:
        """
        Bereinigt Währungs-Strings und konvertiert sie in float.
        Unterstützt pandas Series, DataFrames und einzelne Strings.

        :param value: Eingabewert (Series, DataFrame oder String).
        :return: Bereinigter Wert als float, Series oder DataFrame.

        """
        try:
            if isinstance(value, pd.DataFrame):
                for col in value.columns:
                    value[col] = self._normalize_amount(value[col])
                return value
            if isinstance(value, str):
                value = pd.Series([value])
                value = self._normalize_amount(value)
                return value.iloc[0]
            if not isinstance(value, pd.Series):
                return value
            # Entferne Währungszeichen etc.
            # regex: ^ - negiert: \d - Digit(0-9), Komma, Punkt oder Minus
            value = value.astype(str).str.replace(r"[^\d,.\-]", "", regex=True)

            # Erkenne und behandle deutsche 1000er-Trennung (z. B. 1.234,56)
            # Fall 1: sowohl Punkt als auch Komma → Punkt = Tausender, Komma = Dezimal
            # regex: \.\d{3,},\d{1,2}$ → Punkt gefolgt von mind. 3 Ziffern, Komma, 1-2 Ziffern am Ende
            mask = value.str.contains(r"\.\d{3,},\d{1,2}$")
            value.loc[mask] = value.loc[mask].str.replace(".", "", regex=False)

            # Fall 2: englisch (1,234.56) → Komma = Tausender, Punkt = Dezimal
            # regex: ,\d{3,}\.\d{1,2}$ → Komma gefolgt von mind. 3 Ziffern, Punkt, 1-2 Ziffern am Ende
            mask = value.str.contains(r",\d{3,}\.\d{1,2}$")
            value.loc[mask] = value.loc[mask].str.replace(",", "", regex=False)

            # Alle verbleibenden Kommas als Dezimalpunkte
            value = value.str.replace(",", ".", regex=False)

            # Zu float konvertieren
            value = pd.to_numeric(value, errors="coerce")
            # self._logger.debug("Betragsspalte vollständig normalisiert")
        except Exception:
            pass
        return value

    # -------- Dataframe filtern --------------------
    def _filter_out_rows_by_needles(self, df: pd.DataFrame, column: str, needles: list[str], *,
                                    case_sensitive: bool = False, allow_regex: bool = False, whole_word: bool = False,
                                    keep_na: bool = True,
                                    ) -> pd.DataFrame:
        """
        Entfernt Zeilen, wenn `column` einen Begriff der `needles` enthält.

        Args:
            df: Eingabe-DataFrame.
            column: Zu durchsuchende Spalte.
            needles: Liste Suchbegriffe (oder Regex, wenn allow_regex=True).
            case_sensitive: Groß-/Kleinschreibung beachten?
            allow_regex: `needles` als echte Regex behandeln?
            whole_word: Nur ganze Wörter matchen (setzt allow_regex=True intern).
            keep_na: NaN in `column` behalten (True) oder als "kein Treffer" behandeln (False).

        Returns:
            Gefiltertes DataFrame (Treffer werden entfernt).
        """

        if column not in df.columns:
            self._log_error_with_debug_msg(f"Spalte '{column}' nicht im DataFrame gefunden.")
            return df

        # Nichts zu filtern
        if not needles:
            return df

        # Muster bauen
        if whole_word:
            allow_regex = True  # Wortgrenzen brauchen Regex
            # Unicode-Wortgrenzen: (?u)\b  — escapen, damit Sonderzeichen in needles nicht "ausbrechen"
            parts = [rf"(?u)\b{re.escape(n)}\b" for n in needles]
            pattern = "|".join(parts)
        elif allow_regex:
            # Nutzer liefert Regex – mit Alternation verbinden (ohne Escaping)
            pattern = "|".join(f"(?:{n})" for n in needles)
        else:
            # Plain-Text-Suche: alles escapen und mit Alternation verbinden
            pattern = "|".join(re.escape(n) for n in needles)

        # Vektorisierte Suche
        ser = df[column].astype("string")
        # na=False → NaNs zählen als "kein Treffer"; wenn keep_na=True, bleiben sie sowieso drin
        mask_hit = ser.str.contains(
            pattern,
            case=case_sensitive,
            regex=True,
            na=False
        )

        # Treffer entfernen, optional NaN separat behandeln
        if keep_na:
            # Behalte NaN-Zeilen unabhängig vom Treffer (sie sind in mask_hit ohnehin False)
            out = df.loc[~mask_hit].copy()
        else:
            out = df.loc[~mask_hit | ser.isna()].copy()

        removed = len(df) - len(out)
        self._logger.debug(
            f"Filtered {removed} rows from '{column}' via needles={needles} "
            f"(case_sensitive={case_sensitive}, allow_regex={allow_regex}, whole_word={whole_word})."
        )
        return out.reset_index(drop=True)

    def _filter_in_rows_by_needles(self, df: pd.DataFrame, column: str, needles: list[str], *,
                                   case_sensitive: bool = False, allow_regex: bool = False, whole_word: bool = False,
                                   keep_na: bool = True,
                                   ) -> pd.DataFrame:
        """
        Behalte nur Zeilen, wenn `column` einen Begriff der `needles` enthält.
        Args:
            df: Eingabe-DataFrame.
            column: Zu durchsuchende Spalte.
            needles: Liste Suchbegriffe (oder Regex, wenn allow_regex=True).
            case_sensitive: Groß-/Kleinschreibung beachten?
            allow_regex: `needles` als echte Regex behandeln?
            whole_word: Nur ganze Wörter matchen (setzt allow_regex=True intern).
            keep_na: NaN in `column` behalten (True) oder als "kein Treffer" behandeln (False).
        Returns:
            Gefiltertes DataFrame (nur Treffer werden behalten).
        """
        if column not in df.columns:
            self._log_error_with_debug_msg(f"Spalte '{column}' nicht im DataFrame gefunden.")
            return df
        # Nichts zu filtern
        if not needles:
            return df
        # Muster bauen
        if whole_word:
            allow_regex = True  # Wortgrenzen brauchen Regex
            # Unicode-Wortgrenzen: (?u)\b  — escapen, damit Sonderzeichen in needles nicht "ausbrechen"
            parts = [rf"(?u)\b{re.escape(n)}\b" for n in needles]
            pattern = "|".join(parts)
        elif allow_regex:
            # Nutzer liefert Regex – mit Alternation verbinden (ohne Escaping)
            pattern = "|".join(f"(?:{n})" for n in needles)
        else:
            # Plain-Text-Suche: alles escapen und mit Alternation verbinden
            pattern = "|".join(re.escape(n) for n in needles)
        # Vektorisierte Suche
        ser = df[column].astype("string")
        # na=False → NaNs zählen als "kein Treffer"; wenn keep_na=True, bleiben sie sowieso drin
        mask_hit = ser.str.contains(
            pattern,
            case=case_sensitive,
            regex=True,
            na=False
        )
        # Nur Treffer behalten, optional NaN separat behandeln
        if keep_na:
            # Behalte NaN-Zeilen unabhängig vom Treffer (sie sind in mask_hit ohnehin False)
            out = df.loc[mask_hit | ser.isna()].copy()
        else:
            out = df.loc[mask_hit].copy()
        kept = len(out)
        self._logger.debug(
            f"Kept {kept} rows from '{column}' via needles={needles} "
            f"(case_sensitive={case_sensitive}, allow_regex={allow_regex}, whole_word={whole_word})."
        )
        return out.reset_index(drop=True)

    def _filter_columns_by_names(self, df: pd.DataFrame, column_names: list[str], *,
                                 add_missing: bool = False, fill_value=pd.NA, case_insensitive: bool = False,
                                 ) -> pd.DataFrame:
        """
        Behält nur die Spalten in `column_names` (in derselben Reihenfolge).
        Optional:
          - add_missing: fehlende Spalten erzeugen (mit fill_value)
          - case_insensitive: Spaltennamen case-insensitiv auflösen
        """
        if not case_insensitive:
            present = [c for c in column_names if c in df.columns]
            missing = [c for c in column_names if c not in df.columns]
            out = df[present].copy()
        else:
            lower_map = {c.lower(): c for c in df.columns}
            present_real = []
            missing = []
            for wanted in column_names:
                key = wanted.lower()
                if key in lower_map:
                    present_real.append(lower_map[key])
                else:
                    missing.append(wanted)
            out = df[present_real].copy()
            # gewünschte Reihenfolge gemäß column_names herstellen
            reorder = []
            seen = set()
            for wanted in column_names:
                real = lower_map.get(wanted.lower())
                if real and real not in seen:
                    reorder.append(real)
                    seen.add(real)
            out = out[reorder]

        if add_missing and missing:
            for m in missing:
                out[m] = fill_value
            # Reihenfolge erneut gemäß column_names
            out = out[column_names]

        self._logger.debug(
            f"_filter_columns_by_names: kept={list(out.columns)}, missing={missing}"
            + (", added_missing" if add_missing and missing else "")
        )
        return out

    def _rename_columns_by_map(self, df: pd.DataFrame, rename_map: dict[str, str], *,
                               case_insensitive: bool = False):
        """
        Benennt Spalten gemäß rename_map um.
        Args:
            df: Eingabe-DataFrame.
            rename_map: Dict mit {alter_spaltenname: neuer_spaltenname}.
            case_insensitive (bool, optional): Ob Spaltennamen case-insensitiv gesucht werden sollen.

        Optional: case_insensitive: Sucht Spaltennamen case-insensitiv.

        Returns:
            DataFrame mit umbenannten Spalten.

        """
        if case_insensitive:
            lower = {c.lower(): c for c in df.columns}
            applied = {lower[k.lower()]: v for k, v in rename_map.items() if k.lower() in lower}
            missing = [k for k in rename_map if k.lower() not in lower]
        else:
            applied = {k: v for k, v in rename_map.items() if k in df.columns}
            missing = [k for k in rename_map if k not in df.columns]

        if missing:
            self._logger.warning(f"_rename_columns_by_map: missing columns: {missing}")

        self._logger.debug(f"_rename_columns_by_map: renaming columns: {applied}")

        return df.rename(columns=applied)

    # -----------------------------------------------------------------------------------------------------------------

    # -----------------------------------------------------------------------------------------------------------------
    # Allgemeine Hilfsfunktionen
    # -----------------------------------------------------------------------------------------------------------------

    def _abort_windows_passkey(self, tries: int = 10, timeout: int = 10) -> bool:
        """
        Versucht, einen nativen Windows-Passkey/Hello/WebAuthn-Dialog zu schließen.
        Priorität: pywinauto -> ctypes SendInput -> pyautogui/keyboard -> ESC an Browser.
        Gibt True zurück, wenn mind. ein Abbruchversuch gesendet wurde.
        """
        def _press_esc_via_ctypes() -> bool:
            if sys.platform != "win32":
                return False
            try:
                import ctypes
                from ctypes import wintypes
                PUL = ctypes.POINTER(ctypes.c_ulong)
                class KEYBDINPUT(ctypes.Structure):
                    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                                ("dwExtraInfo", PUL)]
                class INPUT(ctypes.Structure):
                    _fields_ = [("type", wintypes.DWORD), ("ki", KEYBDINPUT), ("padding", wintypes.BYTE * 8)]
                SendInput = ctypes.windll.user32.SendInput
                INPUT_KEYBOARD = 1; KEYEVENTF_KEYUP = 0x0002; VK_ESCAPE = 0x1B
                def _key(vk, flags=0):
                    return INPUT(type=INPUT_KEYBOARD,
                                 ki=KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags, time=0, dwExtraInfo=None))
                arr = (INPUT * 2)(_key(VK_ESCAPE, 0), _key(VK_ESCAPE, KEYEVENTF_KEYUP))
                return SendInput(2, ctypes.byref(arr), ctypes.sizeof(INPUT)) == 2
            except Exception as e:
                return False

        def _get_active_window_info() -> tuple[int|None, str, str]:
            """
            Returns (hwnd, title, class_name) of the foreground window.
            On non-Windows returns (None, "", "").
            """
            if sys.platform != "win32":
                return None, "", ""
            import ctypes
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return None, "", ""
            # title
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            # class
            cls_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls_buf, 256)
            return hwnd, buf.value or "", cls_buf.value or ""

        def _is_windows_security_active() -> bool:
            """
            Heuristic: detects Windows Security / Hello / Security Key dialogs
            by foreground window title.
            """
            _, title, cls = _get_active_window_info()
            needles = (
                "Windows-Sicherheit", "Windows Sicherheit", "Windows Security",
                "Windows Hello", "Sicherheitsschlüssel", "Security Key"
            )
            title_l = title.lower()
            if any(n.lower() in title_l for n in needles):
                return True
            return False

        # ------- Hauptlogik -------
        time.sleep(1)  # kurz warten, bis Dialog da ist
        window_was_active = False
        sleep = timeout / max(tries, 1)
        if sys.platform == "win32":
            for attempt in range(tries):
                # prüfe ob Dialog ("Windows-Sicherheit" o.ä.) im Vordergrund ist
                if _is_windows_security_active():
                    window_was_active = True
                    self._logger.debug(f"Passkey-Abbruchversuch {attempt + 1}/{tries} (Windows)...")

                    # Variante A: ctypes SendInput
                    if _press_esc_via_ctypes():
                        self._logger.debug("Passkey-Abbruch via ctypes SendInput gesendet.")
                        time.sleep(1)
                elif window_was_active:
                    break
                time.sleep(sleep)
            else:
                self._logger.debug("Passkey-Abbruchversuche (Windows) erschöpft.")
                return False
            return True if window_was_active else False
        if sys.platform in ("linux", "darwin"):
            self._logger.warning("Passkey-Abbruch unter Linux/macOS nicht implementiert.")
            return True
        return False

    def _log_error_with_debug_msg(self, msg: str | None = None) -> None:
        """
        Loggt eine Debug-Nachricht mit Funktionsname, Dateiname und Zeilennummer
        der aufrufenden Stelle (nicht der Logger-Funktion selbst).

        Args:
            msg: Zusätzliche Nachricht, die geloggt werden soll. (Optional)

        Returns:
            None
        """
        frame = None
        caller = None
        if msg is None:
            msg = "Fehler"
        try:
            frame = inspect.currentframe()
            caller = frame.f_back if frame is not None else None
            if caller is not None:
                func_name = getattr(caller.f_code, "co_name", "<unknown>")
                file = getattr(caller.f_code, "co_filename", "<unknown>")
                lineno = getattr(caller, "f_lineno", 0)
                # line = linecache.getline(file, lineno).strip() if file and lineno else ""
            else:
                func_name, file, lineno, line = "<unknown>", "<unknown>", 0, ""
            self._logger.debug(f"{msg} - in {func_name} at {file}:{lineno})")
        except Exception:
            try:
                self._logger.debug(f"{msg} - beim Ermitteln der Debug-Info)")
            except Exception:
                pass
        finally:
            # Vermeide Reference-Cycles
            try:
                del frame
                del caller
            except Exception:
                pass


if __name__ == "__main__":
    # Beispielhafte Nutzung des WebCrawlers
    with WebCrawler(
        name="ExampleCrawler",
        output_path="output",
        start_date="01.01.2023",
        end_date="30.06.2023",
        autosave=True,
        logging_level="DEBUG",
        logfile=None,
    ) as crawler:
        crawler.login()

    # crawler = WebCrawler(logging_level="DEBUG")
    # crawler.login()
    # crawler.close()