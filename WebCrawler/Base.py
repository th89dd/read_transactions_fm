# -*- coding: utf-8 -*-
"""
:author: Tim Häberlein
:version: 1.0
:date: 06.10.2024
:organisation: TU Dresden, FZM
"""

# -------- start import block ---------
# standard libraries
import os
import shutil
import time
import threading
import logging
import json

# data handling
import tempfile
import pandas as pd

# web scraping
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
# import undetected_chromedriver as uc  # pip install undetected-chromedriver
from selenium.webdriver.support.ui import Select
# from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException

# time format
import locale
locale.setlocale(locale.LC_TIME, 'de_DE.UTF-8')
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
# -------- end import block ---------


class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }
        if record.exc_info:  # Fehler/Exception hinzufügen
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

def configure_logger(name: str, log_file: str = "../logs/webcrawlers.json", level=logging.INFO):
    """
    Configures the logger for the WebCrawler
    Parameters:
        - name (str): Name of the logger
        - log_file (str): Path to the log file
        - level (int): Logging level
    Returns:
        - logger (logging.Logger): Logger object
    """

    # log_file pfad erzeugen
    log_file_path = os.path.abspath(log_file)
    if not os.path.exists(os.path.dirname(log_file_path)):
        os.makedirs(os.path.dirname(log_file_path))

    logger = logging.getLogger(name)
    logger.setLevel(level)

    formatter = JsonFormatter()

    # FileHandler (JSON-Datei)
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Optional: Konsolen-Handler für Standardausgabe (Lesbarkeit)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)

    return logger


class WebCrawler(object):
    """
    WebCrawler is a main class to download bank data
    """
    def __init__(self, name='WebCrawler', output_path='out',
                 start_date=pd.to_datetime('today'),
                 end_date=(pd.to_datetime('today') - pd.DateOffset(months=6)),
                 autosave=True,
                 logging_level=logging.INFO,
                 ):
        """
        Initializes the WebCrawler with the specified output path

        Args:
            output_path (str): The directory where the output files will be saved. Default is 'out'.
            start_date (str): The start date for the data download in the format 'dd.mm.yyyy'. Default is today's date.
            end_date (str): The end date for the data download in the format 'dd.mm.yyyy'. Default is 6 months ago from today's date.
            perform_download (bool): Whether to download the data or not. Default is True.
            autosave (bool): Whether to save downloaded data to the output directory. Default is True.
        """

        # initialize variables
        self.__name = name  # name of the WebCrawler
        self.__output_path = output_path  # output path
        self.__autosave = autosave  # weather to save the data or not
        self.start_date = start_date
        self.end_date = end_date
        self.account_balance = None

        self.__credentials_file = 'credentials.txt'
        self.__credentials = dict()  # dictionary to store credentials
        self.__urls = dict()  # dictionary to store urls
        self.__data = pd.DataFrame()  # data frame to store the downloaded data

        self._state = None  # state of the WebCrawler

        # set up logging
        self.logger = configure_logger(self.__name, level=logging_level)
        self.logger.info('initialized')

        # create output directory if it does not exist
        if not os.path.exists(self.__output_path):
            os.makedirs(self.__output_path)
            # clear output directory
            self.logger.info(f'Output directory created: {self.__output_path}')
        # delete all files in the output directory
        # [os.remove(os.path.join(self.__output_path, f)) for f in os.listdir(self.__output_path) if os.path.isfile(os.path.join(self.__output_path, f))]

        # create temporary directory
        self._download_directory = tempfile.mkdtemp()
        self.logger.info(f'Temporary directory created: {self._download_directory}')

        # initialize webdriver
        # options = uc.ChromeOptions()
        options = webdriver.EdgeOptions()
        # options.add_argument('--disable-gpu')
        # options.add_argument("--disable-software-rasterizer")  # Software-Rendering deaktivieren
        options.add_argument("--log-level=3")  # Weniger Logs, nur kritische Fehler
        # options.add_argument("--disable-renderer-backgrounding")
        # options.add_argument("--renderer-process-limit=1")  # Weniger Prozesse
        # options.add_argument("--disable-accelerated-2d-canvas")  # Kein Hardware-Canvas
        # options.add_argument("--disable-accelerated-video-decode")
        # options.add_argument("--enable-software-compositing")
        # options.add_argument('--headless')  # ohne browserfenster -> funktioniert zB bei TR nicht (scrollen erforderlich, Banner wird nicht gefunden)
        # options.add_argument('--start-minimized')
        # Setze einige Optionen, um die Automatisierung weniger erkennbar zu machen
        options.add_argument("--disable-blink-features=AutomationControlled")
        # options.add_argument("--allow-running-insecure-content")  # unsichere Protokolle aktivieren
        # options.add_argument("--ignore-certificate-errors")  # SSL-Zertifikatsfehler ignorieren
        # options.add_argument("--allow-insecure-localhost")   # Für lokale unsichere Zertifikate

        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_experimental_option("prefs", {
            "download.default_directory": self._download_directory,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": False,
        })
        # self.driver = uc.Chrome(options=options)
        self.driver = webdriver.Edge(options=options)

        self._state = 'initialized'

    # ----------------------------------------------------------------
    # ----------------------- public methods ------------------------
    def login(self):
        """
        Logs in to the online banking platform.
        Note that you need to import the credentials from a file bevor calling this method.
        """
        self._state = 'login'
        pass

    def download_data(self):
        """
        Downloads the data from the online banking platform
        """
        self._state = 'download_data'
        pass

    def process_data(self):
        """
        Processes the downloaded data
        """
        self._state = 'process_data'
        pass

    def save_data(self):
        """
        Saves the downloaded data to a file
        """
        try:
            self.__data.to_csv(os.path.join(self.__output_path, '{}.csv'.format(self.__name)), sep=";", index=False)
            # self.logger.info('Data saved to {}'.format(os.path.join(self.__output_path, '{}.csv'.format(self.__name))))
            # self.logger.info('Data saved to {}'.format(os.path.abspath(os.path.join(self.__output_path, '{}.csv'.format(self.__name)))))
            self.logger.info('Data saved to {}'.format(os.path.abspath('{}.csv'.format(self.__name))))
        except Exception as e:
            self.logger.error('Error saving data', exc_info=True)

        self._state = 'save_data'

    def close(self):
        """
        Closes the webdriver and the temporary directory
        Note that this method should be called after the download process is finished and the data is stored in the internal variable self.data
        """
        self.driver.quit()
        del self.driver
        shutil.rmtree(self._download_directory)
        self.logger.info('Temporary directory removed: {}'.format(self._download_directory))
        self.logger.info('{} closed'.format(self.__name))
        self._state = 'closed'

    def error_close(self):
        self.close()
        os._exit(1)
        self.logger.error('WebCrawler closed due to error')

    def perform_download(self):
        """
        Performs the download process automatically.
        - read credentials
        - login
        - download data
        - close webdriver
        - process data
        - save data (if autosave is True)
        """
        # zugangsdaten einlesen
        self._read_credentials()
        self.login()
        self.download_data()
        self.close()
        self.process_data()
        if self.__autosave:
            self.save_data()

    def set_logging_level(self, level):
        """
        Ändert das Logging-Level zur Laufzeit.

        Args:
            level (str): Das neue Logging-Level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL').
        """
        numeric_level = getattr(logging, level.upper(), None)
        if not isinstance(numeric_level, int):
            self.logger.error(f"Ungültiges Logging-Level: {level}")
            return

        self.logger.setLevel(numeric_level)
        for handler in self.logger.handlers:
            handler.setLevel(numeric_level)

        self.logger.info(f"Logging-Level geändert auf: {level}")

    # ----------------------------------------------------------------
    # ----------------------- private methods -----------------------
    def _read_temp_files(self, sep=';'):
        """
        Reads the temporary files in the download directory and stores them in the data dictionary
        :return:
        """
        # read all files in the download directory sorted in a dict
        try:
            files_in_dir = os.listdir(self._download_directory)
            self.logger.debug(f"Dateien im temporären Verzeichnis: {files_in_dir}")
            self.logger.info('{len_files} Dateien im temporären Verzeichnis gefunden.'.format(len_files=len(files_in_dir)))
            file_content = dict()
            if files_in_dir:
                for f in files_in_dir:
                    if f.endswith(".csv"):
                        logging.debug(f"CSV-Datei gefunden: {f}")
                        downloaded_file = os.path.join(self._download_directory, f)
                        df = pd.read_csv(downloaded_file, sep=sep)
                        file_content[f] = df
                        logging.debug(df.head())
                        logging.debug(f"Heruntergeladene Datei: {downloaded_file} erfolgreich eingelesen")
                    elif f.endswith(".xls"):
                        logging.debug(f"Excel-Datei gefunden: {f}")
                        downloaded_file = os.path.join(self._download_directory, f)
                        df = pd.read_excel(downloaded_file, engine='xlrd')
                        file_content[f] = df
                        logging.debug(df.head())
                        logging.debug(f"Heruntergeladene Datei: {downloaded_file} erfolgreich eingelesen")
                self.__data = file_content
                return True
            else:
                logging.info("Keine Datei im temporären Verzeichnis gefunden.")
                return False
        except Exception as e:
            self.logger.error("Fehler beim Einlesen der heruntergeladenen Dateien", exc_info=True)

    def _read_credentials(self):
        """
        Reads the credentials from a file and returns them as a dictionary
        """
        try:
            with open(self.__credentials_file, 'r', encoding='utf-8') as file:
                lines = file.readlines()
            credentials = {}
            for line in lines:
                try:
                    if len(line) > 1:
                        key, value = line.strip().split(':', 1)
                        credentials[key] = value.strip()
                    else:
                        continue
                except ValueError:
                    self.logger.error('Error reading credentials line: {}'.format(line), exc_info=True)
                    continue
        except Exception as e:
            self.logger.error('Error reading credentials file', exc_info=True)

        self.credentials = credentials

    # ----------------------------------------------------------------
    # ----------------------- static methods -------------------------
    @staticmethod
    def config_logger(logger, log_level=logging.INFO):
        """
        Configures the logger for the WebCrawler
        :param logger: logger object
        :param log_level: log level
        """
        logger.setLevel(log_level)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        ch = logging.StreamHandler()
        ch.setLevel(log_level)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    # ----------------------------------------------------------------
    # ----------------------- properties ----------------------------
    @property
    def name(self) -> str:
        """
        Getter for the name property.
        :return: Name of the WebCrawler
        """
        return self.__name

    @name.setter
    def name(self, value):
        """
        Setter for the name property.
        :param value: new name value
        :type value: str
        """
        assert isinstance(value, str), 'Name must be a string'
        self.__name = value

    @property
    def output_path(self):
        return self.__output_path

    @property
    def start_date(self):
        return self.__start_date

    @start_date.setter
    def start_date(self, value):
        try:
            date = pd.to_datetime(value, format='%d.%m.%Y')
        except ValueError:
            raise ValueError('Start date must be in the format dd.mm.yyyy')
        self.__start_date = date

    @property
    def end_date(self):
        return self.__end_date

    @end_date.setter
    def end_date(self, value):
        try:
            date = pd.to_datetime(value, format='%d.%m.%Y')
        except ValueError:
            raise ValueError('End date must be in the format dd.mm.yyyy')
        self.__end_date = date

    @property
    def urls(self) -> dict:
        """
        Getter for the urls property.
        :return: url as dictionary
        """
        return self.__urls

    @urls.setter
    def urls(self, value):
        """
        Setter for the urls property.
        :param value: new url value
        :type value: dict
        """
        assert isinstance(value, dict), 'URLs must be a dictionary'
        self.__urls = value

    @property
    def data(self) -> pd.DataFrame:
        """
        Getter for the data property.
        Return the downloaded data as a pandas DataFrame.

        :return: data as Dataframe
        """
        return self.__data

    @data.setter
    def data(self, value):
        """
        Setter for the data property.
        :param value: new data value
        :type value: pd.DataFrame
        """
        assert isinstance(value, pd.DataFrame), 'Data must be a pandas DataFrame'
        self.__data = value

    @property
    def credentials_file(self):
        return self.__credentials_file

    @credentials_file.setter
    def credentials_file(self, value):
        self.__credentials_file = value

    @property
    def credentials(self) -> dict:
        return self.__credentials

    @credentials.setter
    def credentials(self, value):
        assert isinstance(value, dict), 'Credentials must be a dictionary with user and password'
        self.__credentials = value


if __name__ == '__main__':
    crawler = WebCrawler()
    # crawler.close()
    pass





