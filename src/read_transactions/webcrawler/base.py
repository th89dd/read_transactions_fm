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

import os
import shutil
import time
import datetime
import tempfile
import pandas as pd
import logging
from typing import Any, Dict, Optional, Union
import warnings

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
            start_date: Union[str, pd.Timestamp, datetime.date, None] = pd.to_datetime("today"),
            end_date: Union[str, pd.Timestamp, datetime.date, None] = (pd.to_datetime("today") - pd.DateOffset(months=6)),
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
            MainLogger.configure(level=logging_level, logfile=logfile)
        self.__logger = MainLogger.get_logger(self.__name)
        MainLogger.set_stream_level(logging_level)

        # Zeitparameter setzen
        self.start_date = start_date
        self.end_date = end_date

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
            value = pd.to_datetime("today")- pd.DateOffset(days=1)
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
            value = pd.to_datetime("today") - pd.DateOffset(months=6)
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

    def process_data(self, sep: str = ';') -> None:
        """Optional von Subklassen überschreiben – verarbeitet geladene Daten."""
        self._state = "process_data"
        if not self._read_temp_files(sep=sep):
            self._logger.debug('Keine Dateien im Temp-Verzeichnis')

    def save_data(self) -> None:
        """Speichert geladene Daten als CSV."""
        try:
            os.makedirs(self.__output_path, exist_ok=True)
            if isinstance(self.__data, pd.DataFrame):
                file_path = os.path.join(self.__output_path, f"{self.__name}.csv")
                self.__data.to_csv(file_path, sep=";", index=False)
                self._logger.info(f"Data saved to: {os.path.abspath(file_path)}")
            elif isinstance(self.__data, dict):
                for fname, df in self.__data.items():
                    file_path = os.path.join(self.__output_path, f"{fname}.csv")
                    df.to_csv(file_path, sep=";", index=False)
                    self.__logger.info(f"Data saved to: {os.path.abspath(file_path)}")
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

    # ------------------------------------------------------------------
    # Download & Selenium Helpers
    # ------------------------------------------------------------------
    def wait_for_element(self, by: str, selector: str, timeout: int = 15):
        """Wartet auf das Vorhandensein eines Elements und gibt es zurück.

        Args:
            by: Selenium-By-Strategie, z. B. "css selector"/By.CSS_SELECTOR.
            selector: Selektor-String.
            timeout: Max. Wartezeit in Sekunden.

        by_map = {
            - "id": _By.ID,
            - "name": _By.NAME,
            - "css": _By.CSS_SELECTOR,
            - "css selector": _By.CSS_SELECTOR,
            - "xpath": _By.XPATH,
            - "link text": _By.LINK_TEXT,
            - "partial link text": _By.PARTIAL_LINK_TEXT,
            - "tag": _By.TAG_NAME,
            - "class": _By.CLASS_NAME,
        }

        Returns:
            WebElement: Gefundenes Element.

        Raises:
            TimeoutException: Wenn das Element nicht rechtzeitig erscheint.
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
        """Wartet, bis ein Element klickbar ist, und klickt es dann an.
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

        Args:
            by (str): by je nach by_map
            selector (str): selector
            timeout (int): Timeout in sekunden


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
        elem = _WebDriverWait(self.driver, timeout).until(
            _EC.element_to_be_clickable((_by, selector))
        )
        elem.click()

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
                    self._logger.warning("Keine unterstützten Dateien gefunden")
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

    def _retry_func(self, func, max_retries: int = 3, wait_seconds: float = 1.0) -> bool:
        """Versucht die Funktion mehrfach bei Fehlschlag.

        Args:
            func: Funktion, die ausgeführt werden soll.
            max_retries: Maximale Anzahl an Versuchen.
            wait_seconds: Wartezeit zwischen den Versuchen.
        Returns:
            bool: True bei erfolgreicher Ausfürhung, sonst False.
        """
        from selenium.common.exceptions import TimeoutException
        for attempt in range(1, max_retries + 1):
            try:
                func()
                self._logger.debug(f"Funktion {func} erfolgreich nach {attempt} Versuch(en)")
                return True
            except TimeoutException:
                self._logger.debug(f"Funktion {func} bei Versuch {attempt} fehlgeschlagen: Timeout")
                if attempt < max_retries:
                    time.sleep(wait_seconds)
            except Exception as e:
                self._logger.debug(f"Funktion {func} bei Versuch {attempt} fehlgeschlagen: {e}")
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

    def _normalize_dataframe(self, df: pd.DataFrame, remove_nan: bool = False) -> pd.DataFrame:
        """
        Normalisiert die Transaktionsdaten eines DataFrames.
        - Datumsspalten in einheitliches Format bringen
        - Betragsspalten bereinigen
        - Spaltennamen vereinheitlichen

        :param df: Eingabe-DataFrame.
        :param remove_nan: Ob Zeilen mit NaN-Werten entfernt werden sollen. (Standard: False)
        :return: DataFrame mit normalisierten Daten.
        """
        def _safe_replace(value: pd.Series, to_replace: str, replacement: str) -> pd.Series:
            try:
                return value.astype(str).str.replace(replacement, to_replace)
            except Exception:
                return value
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
            self._logger.debug(f"Mehrere Empfänger/Absender-Spalten erkannt: {party_cols}, verwende die erste.")
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
            rename_map[party_cols] = 'Empfänger/Absender'
        df = df.rename(columns=rename_map)
        self._logger.debug(f"Spalten umbenannt: {rename_map}")
        # -------------------------------------------------------------------------------------------------------------

        # -------------------------------------------------------------------------------------------------------------
        # Normalisierungen durchführen
        # -------------------------------------------------------------------------------------------------------------
        # Datumsspalte normalisieren
        if date_cols:
            date_cols = rename_map[date_cols]  # aktualisierter Spaltenname
            try:
                df[date_cols] = pd.to_datetime(df[date_cols], errors='coerce', dayfirst=True)
                # NaT (Not a Time) behandeln
                before_drop = len(df)
                df = df.dropna(subset=[date_cols])  # Zeilen mit ungültigen Daten entfernen
                dropped = before_drop - len(df)
                if dropped > 0:
                    self._logger.debug(f"{dropped} Zeilen mit ungültigen Datumseinträgen entfernt.")
                # formatieren
                df[date_cols] = df[date_cols].dt.strftime('%d.%m.%Y')
            except Exception:
                self._logger.error("Fehler bei der Normalisierung der Datumsspalte", exc_info=True)

        # Betragsspalte normalisieren
        if amount_cols:
            amount_cols = rename_map[amount_cols]  # aktualisierter Spaltenname
            try:
                df[amount_cols] = df[amount_cols].pipe(self._normalize_amount)
                # NaN-Werte behandeln - entweder entfernen oder auf 0 setzen
                if remove_nan:  # Zeilen mit NaN entfernen
                    before_drop = len(df)
                    df = df.dropna(subset=[amount_cols])  # Zeilen mit ungültigen Beträgen entfernen
                    dropped = before_drop - len(df)
                    if dropped > 0:
                        self._logger.debug(f"{dropped} Zeilen mit ungültigen Betragseinträgen entfernt.")
                else:  # NaN-Werte auf 0 setzen
                    df[amount_cols] = df[amount_cols].fillna(0.0)
            except Exception:
                self._logger.error("Fehler bei der Normalisierug der Betragsspalte", exc_info=True)
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


    def _normalize_amount(self, value: Any) -> Any:
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