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
# data handling
import tempfile
import pandas as pd
import logging
# web scraping
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
# import undetected_chromedriver as uc  # pip install undetected-chromedriver
from selenium.webdriver.support.ui import Select
# from selenium.webdriver.common.action_chains import ActionChains

# time format
import locale
locale.setlocale(locale.LC_TIME, 'de_DE.UTF-8')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# -------- end import block ---------


class WebCrawler(object):
    """
    WebCrawler is a main class to download bank data
    """
    def __init__(self, output_path='out',
                 start_date=pd.to_datetime('today').strftime('%d.%m.%Y'),
                 end_date=(pd.to_datetime('today') - pd.DateOffset(months=6)).strftime('%d.%m.%Y'),
                 autosave=True,
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
        self.__name = 'WebCrawler'
        self.__output_path = output_path  # output path
        self.__autosave = autosave  # weather to save the data or not
        self.__start_date = start_date
        self.__end_date = end_date

        self.__credentials_file = 'credentials.txt'
        self.__credentials = dict()  # dictionary to store credentials
        self.__urls = dict()  # dictionary to store urls
        self.__data = pd.DataFrame()  # data frame to store the downloaded data

        # set up logging
        self.logger = logging.getLogger(__name__)

        # create output directory if it does not exist
        if not os.path.exists(self.__output_path):
            os.makedirs(self.__output_path)
            # clear output directory
            self.logger.info(f'Output directory created: {self.__output_path}')
        # delete all files in the output directory
        [os.remove(os.path.join(self.__output_path, f)) for f in os.listdir(self.__output_path) if os.path.isfile(os.path.join(self.__output_path, f))]

        # create temporary directory
        self._download_directory = tempfile.mkdtemp()
        self.logger.info(f'Temporary directory created: {self._download_directory}')

        # initialize webdriver
        # options = uc.ChromeOptions()
        options = webdriver.EdgeOptions()
        # options.add_argument('--headless')
        # options.add_argument('--start-minimized')
        # Setze einige Optionen, um die Automatisierung weniger erkennbar zu machen
        options.add_argument("--disable-blink-features=AutomationControlled")
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

    # ----------------------------------------------------------------
    # ----------------------- public methods ------------------------
    def login(self):
        """
        Logs in to the online banking platform.
        Note that you need to import the credentials from a file bevor calling this method.
        """
        pass

    def download_data(self):
        """
        Downloads the data from the online banking platform
        """
        pass

    def process_data(self):
        """
        Processes the downloaded data
        """
        pass

    def save_data(self):
        """
        Saves the downloaded data to a file
        """
        try:
            self.__data.to_csv(os.path.join(self.__output_path, '{}.csv'.format(self.__name)), sep=";", index=False)
            self.logger.info('Data saved to {}'.format(os.path.join(self.__output_path, '{}.csv'.format(self.__name))))
        except Exception as e:
            self.logger.error('Error saving data', exc_info=True)

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
                self.__data = file_content
            else:
                logging.info("Keine Datei im temporären Verzeichnis gefunden.")
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

    @property
    def end_date(self):
        return self.__end_date

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


class ArivaKurse(WebCrawler):
    def __init__(self, output_path='out/kurse',
                 start_date=pd.to_datetime('today').strftime('%d.%m.%Y'),
                 end_date=(pd.to_datetime('today') - pd.DateOffset(months=6)).strftime('%d.%m.%Y'),
                 perform_download=True,
                 autosave=True,
                 ):
        super().__init__(output_path, start_date, end_date, autosave)
        self.name = 'ArivaKurse'
        self.credentials_file = 'credentials_ariva.txt'

        self._read_credentials()
        user = self.credentials.pop('user')
        password = self.credentials.pop('password')
        self.urls = self.credentials.copy()
        self.credentials = {'user': user, 'password': password}
        # self.urls = {
        #     'apple': 'https://www.ariva.de/aktien/apple-aktie/kurse/historische-kurse',
        #     'msci_world': 'https://www.ariva.de/etf/ishares-core-msci-world-ucits-etf-usd-acc/kurse/historische-kurse',
        #     'microsoft': 'https://www.ariva.de/aktien/microsoft-corp-aktie/kurse/historische-kurse',
        #     'xtr_artificial_intelligence': 'https://www.ariva.de/fonds/xtrackers-artificial-intelligence-and-big-data-ucits-etf-1c/kurse/historische-kurse',
        #     'xtr_msci_world_it': 'https://www.ariva.de/fonds/xtrackers-msci-world-information-technology-ucits-etf-1c/kurse/historische-kurse',
        #     'xtr_msci_world': 'https://www.ariva.de/fonds/xtrackers-msci-world-ucits-etf-1c/kurse/historische-kurse',
        # }

        if perform_download:
            self.perform_download()

    def login(self):
        wait_sec = 2
        login_url = 'https://www.ariva.de/user/login/?ref=L2FrdGllbi9hcHBsZS1ha3RpZS9rdXJzZS9oaXN0b3Jpc2NoZS1rdXJzZT9nbz0xJmJvZXJzZV9pZD00MCZtb250aD0mY3VycmVuY3k9RVVSJmNsZWFuX3NwbGl0PTEmY2xlYW5fYmV6dWc9MQ=='
        self.driver.get(login_url)
        self.logger.info("Navigiere zur Login-Seite.")
        time.sleep(0.5)

        try:
            username_field = self.driver.find_element(By.ID, "username")
            password_field = self.driver.find_element(By.ID, "password")

            username_field.send_keys(self.credentials['user'])
            password_field.send_keys(self.credentials['password'])
            password_field.send_keys(Keys.RETURN)
            logging.debug("Anmeldedaten wurden eingegeben und Formular abgeschickt.")

            self.handle_ad_banner()
        except Exception as e:
            self.logger.error('Fehler beim Login', exc_info=True)

    def handle_ad_banner(self):
        """
        Handles the advertisement banner that appears after logging in.
        """
        try:
            wait_sec = 5
            WebDriverWait(self.driver, wait_sec).until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            self.logger.debug(f"Anzahl der iFrames gefunden: {len(iframes)}")

            self.driver.switch_to.frame(iframes[2])
            accept_button = self.driver.find_element(By.XPATH, "//button[@title='Akzeptieren und weiter']")

            if accept_button.is_displayed():
                accept_button.click()
                self.logger.debug("Werbebanner geschlossen: 'Akzeptieren und weiter'-Button wurde geklickt.")
            else:
                logging.info("Button wurde gefunden, aber ist nicht sichtbar.")

            self.driver.switch_to.default_content()
        except Exception as e:
            self.logger.error("Fehler beim Suchen des Buttons im iFrame", exc_info=True)

    def download_data(self):
        wait_sec = 1
        time.sleep(1)
        self.driver.minimize_window()
        for key, url in self.urls.items():
            self.driver.get(url)
            self.logger.info(f"Navigiere zu {key}-Kursseite.")

            try:
                currency_dropdown = self.driver.find_element(By.CLASS_NAME, "waehrung")
                select_currency = Select(currency_dropdown)
                select_currency.select_by_value("EUR")
                logging.debug("Währung auf Euro gesetzt.")

                start_date_field = self.driver.find_element(By.ID, "minTime")
                start_date_field.clear()
                start_date_field.send_keys(self.end_date)

                end_date_field = self.driver.find_element(By.ID, "maxTime")
                end_date_field.clear()
                end_date_field.send_keys(self.start_date)

                delimiter_field = self.driver.find_element(By.ID, "trenner")
                delimiter_field.clear()
                delimiter_field.send_keys(";")

                download_button = self.driver.find_element(By.XPATH, "//input[@type='submit' and @value='Download']")
                download_button.click()
                logging.debug("Download-Button geklickt, CSV wird heruntergeladen.")
            except Exception as e:
                logging.debug(f"Fehler beim Ausfüllen des Formulars: {e}")
            time.sleep(wait_sec)

        # read all files in the download directory sorted in a dict
        self._read_temp_files()

    def process_data(self):
            # convert written data to a single dataframe
            merged_df = pd.DataFrame()
            for key, value in self.data.items():
                df = value.copy()
                df = self.preprocess_data(df)
                df['WKN'] = self.extract_wkn(key)
                merged_df = pd.concat([merged_df, df], ignore_index=True)
            self.data = merged_df

    @staticmethod
    def preprocess_data(df):
        """
        Preprocesses the data by converting date formats and numerical values.

        Args:
            df (pandas.DataFrame): The DataFrame containing the data to be preprocessed.

        Returns:
            pandas.DataFrame: The preprocessed DataFrame.
        """
        df['Datum'] = df['Datum'].apply(lambda x: pd.to_datetime(x).strftime('%d.%m.%Y'))
        for key in ['Hoch', 'Tief', 'Schlusskurs']:
            df[key] = df[key].apply(lambda x: float(x.replace(',', '.')) * 1)
        return df[['Datum', 'Schlusskurs', 'Hoch', 'Tief']]

    @staticmethod
    def extract_wkn(filename):
        """
        Extracts the WKN (Wertpapierkennnummer) from the filename.

        Args:
            filename (str): The name of the file from which to extract the WKN.

        Returns:
            str: The extracted WKN.
        """
        return filename.split('_')[1]


class TradeRepublic(WebCrawler):
    """
    TradeRepublic is a class to download tansaction data from the online banking platform Traderepublic
    """
    def __init__(self, output_path='out/traderepublic',
                 start_date=pd.to_datetime('today').strftime('%d.%m.%Y'),
                 end_date=(pd.to_datetime('today') - pd.DateOffset(months=6)).strftime('%d.%m.%Y'),
                 perform_download=True,
                 autosave=True,
                 ):
        """
        Initializes the TradeRepublic class with the specified output path
        and the specified start and end dates.

        Args:
            output_path (str): The directory where the output files will be saved. Default is 'out/traderepublic'.
            start_date (str): The start date for the data download in the format 'dd.mm.yyyy'. Default is today's date.
            end_date (str): The end date for the data download in the format 'dd.mm.yyyy'. Default is 6 months ago from today's date.
            perform_download (bool): Whether to download the data or not. Default is True.
            autosave (bool): Whether to save downloaded data to the output directory. Default is True.
        """

        super().__init__(output_path, start_date, end_date, autosave)
        self.name = 'TradeRepublicTransactions'
        self.credentials_file = 'credentials_traderepublic.txt'
        self.urls = {
            'login': 'https://app.traderepublic.com/login',
            'transactions': 'https://app.traderepublic.com/profile/transactions',
        }

        if perform_download:
            self.perform_download()

    def login(self):
        """
        Logs in to the online banking platform Traderepublic
        """
        wait_sec = 10
        login_url = self.urls['login']
        self.driver.get(login_url)
        self.logger.info("Navigiere zur Login-Seite.")

        time.sleep(1)
        self.handle_cookie_banner()
        # Jetzt das Fenster minimieren
        self.driver.minimize_window()
        # user name
        try:
            username_field = WebDriverWait(self.driver, wait_sec).until(EC.presence_of_element_located((By.ID, "loginPhoneNumber__input")))
            username_field.send_keys(self.credentials['user'])
            username_field.send_keys(Keys.RETURN)
            self.logger.debug("Usename wurde eingegeben und Formular abgeschickt.")
        except Exception as e:
            self.logger.error("Fehler beim Ausfüllen des Benutzernamens", exc_info=True)

        try:
            # Wait until the fieldset is present
            fieldset = WebDriverWait(self.driver, wait_sec).until(
                EC.presence_of_element_located((By.ID, "loginPin__input"))
            )
            # Find all input fields within the fieldset
            pin_inputs = fieldset.find_elements(By.CLASS_NAME, "codeInput__character")
            pin = self.credentials['password']  #[0:2]

            # Enter each digit into the corresponding input field
            for i, digit in enumerate(pin):
                pin_inputs[i].send_keys(digit)
        except Exception as e:
            self.logger.error("Fehler beim Login: Eingabe der PIN", exc_info=True)

        try:
            # Wait until the fieldset is present
            fieldset = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.ID, "smsCode__input"))
            )
            # Find all input fields within the fieldset
            pin_inputs = fieldset.find_elements(By.CLASS_NAME, "codeInput__character")

            # Prompt the user to enter the four digits
            pin = input("Bitte geben Sie den 4-stellige SMS-Code ein: ")

            # Enter each digit into the corresponding input field
            for i, digit in enumerate(pin):
                pin_inputs[i].send_keys(digit)

        except Exception as e:
            self.logger.error("Fehler bei der Eingabe des SMS-Codes", exc_info=True)

    def download_data(self):
        try:
            self.logger.info("Navigiere zur Transaktions-Seite.")
            self.driver.get(self.urls['transactions'])
        except Exception as e:
            self.logger.error("Fehler beim Navigieren zur Transaktions-Seite", exc_info=True)

        self.driver.maximize_window()
        time.sleep(1)

        wait = WebDriverWait(self.driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'timeline')))
        # Scroll down the page in a loop until the bottom is reached
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        while True:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.2)  # Wait for new elements to load
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        self.driver.minimize_window()

        daten = []
        month = pd.to_datetime('today').strftime('%B')
        year = pd.to_datetime('today').year
        self.logger.info("start downloading transactions")
        try:
            wait = WebDriverWait(self.driver, 10)
            li_elements = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, 'timeline__entry')))
            for li in li_elements:
                try:
                    # Klassen des <li> Elements abrufen
                    classes = li.get_attribute('class')
                    # Prüfen, ob das <li> Element die unerwünschten Klassen enthält
                    if '-isNewSection' in classes or '-isMonthDivider' in classes:
                        if li.text == "Dieser Monat":
                            month = pd.to_datetime('today').strftime('%B')
                            self.logger.debug("Neuer Monat gefunden: {} {}".format(month, year))
                        else:
                            new_month = li.text
                            if month == 'Dezember' and new_month == 'Januar':
                                year = year - 1
                            if new_month in ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember']:
                                month = new_month
                                self.logger.debug("Neuer Monat gefunden: {} {}".format(month, year))
                                # current_date = pd.to_datetime(f"{month} {year}", format='%B %Y') + pd.DateOffset(months=1)
                                # if current_date < pd.to_datetime(self.end_date, format='%d.%m.%Y'):
                                #     break
                        continue

                    # Name extrahieren
                    name_element = li.find_element(By.CLASS_NAME, 'timelineV2Event__title')
                    name = name_element.text.strip() if name_element else 'N/A'

                    # Preis extrahieren
                    preis_element = li.find_element(By.CSS_SELECTOR, '.timelineV2Event__price p')
                    if preis_element:
                        preis = preis_element.text.replace(' €', '').replace('.', '').strip()
                        preis = preis.replace(',', '.')
                        if not preis.startswith('+'):
                            preis = '-{betrag}'.format(betrag=preis)
                        else:
                            preis = '{betrag}'.format(betrag=preis.replace('+', ''))
                    else:
                        preis = 'N/A'

                    # Datum extrahieren
                    datum_element = li.find_element(By.CLASS_NAME, 'timelineV2Event__subtitle')
                    if datum_element:
                        try:
                            datum, extra = datum_element.text.strip().split('-')
                            datum = '{date}{year}'.format(date=datum.strip(), year=year)
                            name += ' ' + extra.strip()
                        except ValueError:
                            datum = datum_element.text.strip()
                            datum = '{date}{year}'.format(date=datum.strip(), year=year)

                        # Prüfen, ob das Datum in der gewünschten Zeitspanne liegt
                        if pd.to_datetime(datum, format='%d.%m.%Y') < pd.to_datetime(self.end_date, format='%d.%m.%Y'):
                            break
                    else:
                        datum = 'N/A'

                    daten.append({
                        'Datum': datum,
                        'Verwendungszweck': name,
                        'Betrag [€]': preis,
                    })
                except Exception as inner_e:
                    # interner fehler, eintrag lässt sich nicht auslesen
                    self.logger.debug("interner Fehler beim Auslesen der einzelnen Zeilen", exc_info=True)
        except Exception as e:
            self.logger.error("Fehler beim Auslesen der Transaktionsdaten", exc_info=True)

        self.logger.info("{} Transaktionsdaten wurden erfolgreich ausgelesen.".format(len(daten)))

        self.data = pd.DataFrame(daten)

    def process_data(self):
        """
        Performs post-processing on the transaction data.
        """
        # convert lebensmittel
        lebensmittel_list = ['edeka', 'penny', 'lidl', 'aldi', 'rewe', 'netto', 'konsum', 'kaufland', 'real', 'marktkauf']
        self.data['Empfänger'] = self.data['Verwendungszweck'].apply(lambda x: x if any(l in x.lower() for l in lebensmittel_list) else None)

        self.data['Verwendungszweck'] = self.data['Verwendungszweck'].apply(TradeRepublic.find_umbuchungen)

    # bestätige das Cookie-Banner
    def handle_cookie_banner(self):
        """
        Handles the cookie banner.
        """
        wait_sec = 10
        try:
            # Wait until the checkbox is present
            checkbox = WebDriverWait(self.driver, wait_sec).until(
                EC.presence_of_element_located((By.ID, "necessarySelection"))
            )
            # Check if the checkbox is not already selected
            if not checkbox.is_selected():
                checkbox.click()
                logging.debug("Checkbox 'necessarySelection' selected.")
            else:
                logging.debug("Checkbox 'necessarySelection' is already selected.")
            # Wait until the button is present and clickable
            save_button = WebDriverWait(self.driver, wait_sec).until(EC.element_to_be_clickable((By.XPATH, "//span[@class='buttonBase__title' and text()='Auswahl speichern']")))
            save_button.click()
            logging.debug("'Auswahl speichern' button clicked.")

        except Exception as e:
            logging.error(f"Fehler beim Suchen des Buttons im Cookie-Banner: {e}")

    @staticmethod
    def find_umbuchungen(text):
        """
        Find all transactions that are transfers between different accounts.
        Args:
            text (str): The transaction text.
        """
        if text.startswith('Einzahlung') or text.startswith('Tim Häberlein'):
            return "[DKB_Tim]"
        return text


class Amex(WebCrawler):
    def __init__(self, output_path='out/amex',
                 start_date=pd.to_datetime('today').strftime('%d.%m.%Y'),
                 end_date=(pd.to_datetime('today') - pd.DateOffset(months=6)).strftime('%d.%m.%Y'),
                 perform_download=True,
                 autosave=True,
                 ):
        super().__init__(output_path, start_date, end_date, autosave)
        self.__sms_code_set = False
        self.name = 'AmexTransaction'
        self.credentials_file = 'credentials_amex.txt'
        self.urls = {
            'login': 'https://www.americanexpress.com/de-de/account/login',
            'transactions_recent': 'https://global.americanexpress.com/activity/recent',
            'transactions': 'https://global.americanexpress.com/activity/search',
        }

        if perform_download:
            self.perform_download()

    def login(self):
        wait_sec = 5
        # Jetzt das Fenster minimieren
       # self.driver.minimize_window()

        login_url = self.urls['login']
        self.driver.get(login_url)
        self.logger.info("Navigiere zur Login-Seite.")

        time.sleep(1)
        self.handle_cookie_banner()

        # Login ausführen
        try:
            # Wait until the password element is present
            username_field = WebDriverWait(self.driver, wait_sec).until(EC.presence_of_element_located((By.ID, "eliloUserID")))
            username_field.send_keys(self.credentials['user'])
            # username_field.send_keys(Keys.RETURN)
            self.logger.debug("Username wurde eingegeben.")
        except Exception as e:
            self.logger.error("Fehler beim Ausfüllen des Benutzernamens", exc_info=True)

        try:
            # Wait until the password element is present
            password_field = WebDriverWait(self.driver, wait_sec).until(
                EC.presence_of_element_located((By.ID, "eliloPassword")))
            password_field.send_keys(self.credentials['password'])
            password_field.send_keys(Keys.RETURN)
            self.logger.debug("PIN wurde eingegeben und Formular abgeschickt.")
        except Exception:
            self.logger.error("Fehler beim Login: Eingabe der PIN", exc_info=True)

        # SMS Authentifizierung
        try:
            self.driver.minimize_window()
            # Wait until the SMS Authentifizierung-Button is present and clickable
            wait = WebDriverWait(self.driver, 5)
            sms_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//h3[text()='Einmaliger Verifizierungscode (SMS)']/ancestor::button")))
            # sms_button = WebDriverWait(self.driver, wait_sec).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='option-button']")))
            sms_button.click()
            self.logger.debug("SMS Authentifizierung-Button geklickt.")

            # SMS-Code eingeben
            sms_thread = threading.Thread(target=self.__check_sms_code_input)
            sms_thread.Daemon = True
            self.__sms_code_set = False
            sms_thread.start()
            sms_code = input("Bitte geben Sie den 6-stelligen SMS-Code ein: ")
            self.__sms_code_set = True
            self.logger.debug("SMS-Code eingegeben: {sms_code}".format(sms_code=sms_code))
            input_field = WebDriverWait(self.driver, wait_sec).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "input[data-testid='question-value']")))
            input_field.send_keys(sms_code)
            input_field.send_keys(Keys.RETURN)


            # sms_code = input("Bitte geben Sie den 6-stelligen SMS-Code ein: ")  # TODO: subprocess starten, der zählt ob code innerhalb gewisser zeit angefordert wurde, sonst sms erneut anfordern
            # self.logger.debug("SMS-Code eingegeben: {sms_code}".format(sms_code=sms_code))

            # time.sleep(1)
            # maximize window
            # self.driver.maximize_window()

            wait = WebDriverWait(self.driver, 20)  # Warte bis zu 20 Sekunden
            submit_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[text()='Weiter' and @type='submit']")))
            submit_button.click()
            # warten, bis seite aufgebaut wurde
            balance_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Primary' and text()='Details zum Kontostand']")))


        except Exception:
            self.logger.error("Fehler bei der SMS Authentifizierung", exc_info=True)

    def download_data(self):
        wait_sec = 10
        wait = WebDriverWait(self.driver, wait_sec)
        self.logger.info("Navigiere zur Transaktions-Seite.")
        self.driver.get(self.urls['transactions'])
        time.sleep(2)  # Warten, bis die Seite geladen ist
        self.driver.maximize_window()

        try:
            # wait until start_date is present
            date_input = wait.until(EC.element_to_be_clickable((By.ID, "startDate")))
            # date_input.clear()
            date_input.send_keys(Keys.CONTROL + "a")  # Wählt den gesamten Text aus
            # date_input.send_keys(Keys.BACKSPACE)  # Löscht den ausgewählten Text
            date_input.send_keys(pd.to_datetime(self.end_date, format="%d.%m.%Y").strftime("%d/%m/%Y"))

            date_input = wait.until(EC.element_to_be_clickable((By.ID, "endDate")))
            # date_input.clear()
            date_input.send_keys(Keys.CONTROL + "a")  # Wählt den gesamten Text aus
            # date_input.send_keys(Keys.BACKSPACE)  # Löscht den ausgewählten Text
            date_input.send_keys(pd.to_datetime(self.start_date, format="%d.%m.%Y").strftime("%d/%m/%Y"))

            # button suchen drücken
            search_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[text()='Suchen']")))
            search_button.click()

            # prüfe, ob alle daten geladen wurden
            self.__load_more()

            # alle transaktionen auswählen und runterladen
            # nach oben scrollen zum Suchen button reicht nicht -> bis top
            self.driver.execute_script("window.scrollTo(0, 0);")  # scroll to top
            # self.driver.execute_script("arguments[0].scrollIntoView(true);", search_button)  # scroll to element
            time.sleep(2)  # wait for scrolling
            wait = WebDriverWait(self.driver, wait_sec)
            checkbox_label = wait.until(EC.element_to_be_clickable((By.XPATH, "//label[@for='select-all-transactions']")))
            checkbox_label.click()
            download_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//p[text()='Herunterladen']/ancestor::button")))
            download_button.click()
            checkbox_csv = wait.until(EC.element_to_be_clickable((By.XPATH, "//label[@for='axp-activity-download-body-selection-options-type_csv']")))
            checkbox_csv.click()
            checkbox_all = wait.until(EC.element_to_be_clickable((By.XPATH, "//label[@for='axp-activity-download-body-checkbox-options-includeAll']")))
            checkbox_all.click()
            download_link = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Herunterladen")))
            download_link.click()
            self.logger.info("Downloading transactions into temporary file.")
            time.sleep(1)
        except Exception:
            self.logger.error("Fehler beim Download der aktuellen Umsätze", exc_info=True)

        self._read_temp_files(sep=',')  # read all files in the download directory sorted in a dict

    def process_data(self):
        try:
            merged_df = pd.DataFrame()
            for key, value in self.data.items():
                df = value.copy()
                merged_df = pd.concat([merged_df, df], ignore_index=True)
        except Exception:
            self.logger.error("Fehler beim Zusammenführen der Daten", exc_info=True)

        self.data = merged_df
        self.__postprocess_data()

    def handle_cookie_banner(self):
        """
        Handles the cookie banner.
        """
        wait_sec = 5
        try:
            # Wait until the button is present and clickable
            decline_button = WebDriverWait(self.driver, wait_sec).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='granular-banner-button-decline-all']")))
            decline_button.click()
            self.logger.debug("'Ablehnen' button clicked.")
        except Exception:
            self.logger.error("Fehler beim Klicken des 'Ablehnen'-Buttons im Cookie-Banner", exc_info=True)

    # ----------------------------------------------------------------
    # --------------------- private methods -------------------------
    def __check_sms_code_input(self):
        """
        Check if the SMS code input is set and rerun the function if not.
        """
        time.sleep(20)
        while not self.__sms_code_set:
            self.logger.info("Kein SMS-Code eingegeben, fordere neuen Code an.")
            wait = WebDriverWait(self.driver, 5)
            resend_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@data-testid='resend-button']")))
            resend_button.click()
            time.sleep(15)  # Warte bis neuer Code angefordert wird

    def __load_more(self):
        end_reached = False
        while not end_reached:
            try:
                wait = WebDriverWait(self.driver, 10)
                activity_count = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div[data-module-name='axp-activity-count']")))
                count_text = activity_count.text
                # Zahlen aus dem Text extrahieren
                current_count, total_count = map(int, count_text.split(" von "))
                # Prüfen, ob alle Transaktionen geladen wurden
                if current_count >= total_count:
                    end_reached = True
                else:
                    more_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[text()='Mehr anzeigen']")))
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", more_button)  # scroll to element
                    time.sleep(2)  # wait for scrolling
                    more_button.click()  # click on the button
            except Exception:
                self.logger.error("Kein 'Mehr anzeigen'-Button gefunden.", exc_info=True)
                end_reached = True

    def __postprocess_data(self):
        """
        Postprocess the data by converting date formats and numerical values.
        """
        try:
            # convert datum
            self.data['Datum'] = self.data['Datum'].apply(lambda x: x.replace('/', '.'))
            # convert betrag
            self.data['Betrag'] = self.data['Betrag'].apply(lambda x: x.replace(',', '.'))

            self.data = self.data[['Datum', 'Betrag', 'Beschreibung']]
        except Exception:
            self.logger.error("Fehler beim Postprocessing der Daten", exc_info=True)


if __name__ == '__main__':
    # crawler = WebCrawler()
    amex = Amex(perform_download=False, output_path='../out/amex')
    amex.credentials_file = '../credentials_amex.txt'
    amex._read_credentials()
    amex.login()
    amex.download_data()
    # amex.close()
    # amex.process_data()





