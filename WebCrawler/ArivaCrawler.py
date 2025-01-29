# -*- coding: utf-8 -*-
"""
:author: Tim Häberlein
:version: 1.0
:date: 24.11.2024
:organisation: TU Dresden, FZM
"""

# -------- start import block ---------
from WebCrawler.Base import *

# -------- end import block ---------


class ArivaKurse(WebCrawler):
    def __init__(self, perform_download=True, *args, **kwargs):
        super().__init__(name='ArivaKurse', *args, **kwargs)
        self.credentials_file = 'credentials_ariva.txt'

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
                start_date_field.send_keys(self.end_date.strftime('%d.%m.%Y'))

                end_date_field = self.driver.find_element(By.ID, "maxTime")
                end_date_field.clear()
                end_date_field.send_keys(self.start_date.strftime('%d.%m.%Y'))

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

    def _read_credentials(self):
        super()._read_credentials()
        user = self.credentials.pop('user')
        password = self.credentials.pop('password')
        self.urls = self.credentials.copy()
        self.credentials = {'user': user, 'password': password}


if __name__ == '__main__':
    # from WebCrawler.ArivaCrawler import ArivaKurse
    # ariva = ArivaKurse(start_date='1.11.2024', perform_download=False, output_path='../out')  # if perform_download is True, the following steps will done automatically
    # ariva.end_date = '13.10.2024'  # you can also set the date by property, not only by constructor
    # ariva.credentials_file = '../credentials_ariva.txt'  # if you want to use another credentials file or path
    # ariva._read_credentials()
    # ariva.login()
    # ariva.download_data()
    # ariva.close()
    # ariva.process_data()
    # ariva.save_data()
     pass
