# -*- coding: utf-8 -*-
"""
:author: Tim Häberlein
:version: 1.0
:date: 24.11.2024
:organisation: TU Dresden, FZM
"""

# -------- start import block ---------


import os
import sys
import pandas as pd
import time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from WebCrawler.Base import *


# -------- end import block ---------

# Set the logging level to DEBUG for the root logger
# logging.getLogger().setLevel(logging.DEBUG)

class AmazonVisa(WebCrawler):

    def __init__(self, perform_download=True, *args, **kwargs):
        super().__init__(name='AmazonTransactions',*args, **kwargs)
        self.__verified = False
        self.credentials_file = 'credentials_amazon.txt'
        self.urls = {
            'login': 'https://customer.amazon.zinia.de/login',
            'transactions': 'https://customer.amazon.zinia.de/transactions',
        }
        if perform_download:
            self.perform_download()

    def login(self):
        wait = WebDriverWait(self.driver, 20)
        # Jetzt das Fenster minimieren
        self.driver.minimize_window()

        login_url = self.urls['login']
        self.driver.get(login_url)
        self.logger.info("Navigiere zur Login-Seite.")

        time.sleep(1)
        self.handle_cookie_banner()

        # Login ausführen
        try:
            # Wait until the password element is present
            username_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[data-testid='login-email-email']")))
            username_field.send_keys(self.credentials['user'])
            self.logger.debug("Username wurde eingegeben.")
            button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='login-email-links']")))
            button.click()

        except Exception as e:
            self.logger.error("Fehler beim Ausfüllen des Benutzernamens", exc_info=True)

        try:
            # Wait until the password field is present
            password_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[data-testid='password-module-inputs-gap-0']")))
            for i in range(4):
                input_field = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, f"input[data-testid='password-module-inputs-gap-{i}']")))
                input_field.send_keys(self.credentials['password'][i])
            self.logger.debug("PIN wurde eingegeben.")
            button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='login-gaps-button']")))
            button.click()
        except Exception as e:
            self.logger.error("Fehler beim Ausfüllen des Passworts", exc_info=True)

        # Verifizierungscode (email, sms ...)
        try:
            # self.driver.minimize_window()
            # self.__verify_identity()
            pass
        except Exception:
            self.logger.error("Fehler bei der Authentifizierung", exc_info=True)

        try:
            # wait until the transactions page is loaded
            amount = wait.until(EC.visibility_of_element_located((By.XPATH, '//*[@id="root"]/div/div/div/div/div/div/main/section/section/main/section/div[1]/header/div[1]/div/article/section/div[3]/h5')))
            # '//*[@id="root"]/div/div/div/div/div/div/main/section/section/main/section/div[1]/header/div[1]/div/article/section/div[3]/h5'
            # wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "h5[data-testid='credit-chart-label-value']")))
            self.account_balance = amount.text
            self.logger.info("Erfolgreich eingeloggt. Aktueller Kontostand: {}".format(self.account_balance))
        except Exception:
            self.logger.error("Fehler beim Einloggen", exc_info=True)

    def download_data(self):
        wait_sec = 20
        wait = WebDriverWait(self.driver, wait_sec)
        self.logger.info("Navigiere zur Transaktions-Seite.")
        self.driver.get(self.urls['transactions'])
        # time.sleep(2)  # Warten, bis die Seite geladen ist
        # self.driver.maximize_window()

        try:
            # filter öffnen
            filter_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="root"]/div/div/div/div/div/div/main/section/section/div/section/div/div/section/header/div/aside/a[1]/span[1]/span')))
            # '//*[@id="root"]/div/div/div/div/div/div/main/section/section/div/section/div/div/section/header/div/aside/a[1]/span[1]/span'
            # filter_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[@class='sc-kHhbVh hqiEPQ' and text()='Filter']")))
            filter_button.click()

            self.driver.maximize_window()
            # datum auswählen
            radio_button = wait.until(EC.visibility_of_element_located((By.XPATH, '//*[@id="root"]/div/div/div/div/div/div/main/section/section/div/section/div/div/div[2]/div/div/div/div[1]/section/div[6]/div/div[1]/span/input')))

            radio_button.click()

            # start-datum eingeben
            start_date_picker = wait.until(EC.visibility_of_element_located((By.XPATH, '//*[@id="root"]/div/div/div/div/div/div/main/section/section/div/section/div/div/div[2]/div/div/div/div[2]/div/div/div[1]/div/div[1]/div/div[1]/p')))
            start_date_picker.click()
            day_input = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[@data-orderid='3']")))
            month_input = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[@data-orderid='2']")))
            year_input = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[@data-orderid='1']")))
            day_input.send_keys(self.end_date.strftime('%d'))
            month_input.send_keys(self.end_date.strftime('%m'))
            year_input.send_keys(self.end_date.strftime('%Y'))
            # self.logger.debug(f"Date picker paragraph: {start_date_picker.text}")

            # end-datum eingeben
            end_date_picker = wait.until(EC.visibility_of_element_located((By.XPATH, '//*[@id="root"]/div/div/div/div/div/div/main/section/section/div/section/div/div/div[2]/div/div/div/div[2]/div/div/div[2]/div/div[1]/div/div[1]/p')))
            end_date_picker.click()
            day_input = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[@data-orderid='3']")))
            month_input = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[@data-orderid='2']")))
            year_input = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[@data-orderid='1']")))
            day_input.send_keys(self.start_date.strftime('%d'))
            month_input.send_keys(self.start_date.strftime('%m'))
            year_input.send_keys(self.start_date.strftime('%Y'))

            apply_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='filter-modal-apply-button']")))
            apply_button.click()

            self.driver.minimize_window()

            # umsätze älter als 90 tage anzeigen
            try:
                show_transactions = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="root"]/div/div/div/div/div/div/main/section/section/div/section/div/div/section/section/section/section/div/div/div[2]/button/span/span')))
                show_transactions.click()
                confirm_btn = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="root"]/div/div/div/div/div/div/main/section/section/div/section/div/div/section/section/section/section[2]/div[2]/div/footer/section/aside/button/span')))
                confirm_btn.click()
                self.__verify_identity()
            except TimeoutException:
                self.logger.info("Keine Umsätze älter als 90 Tage vorhanden.")



            # download-button klicken
            download_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a[data-testid='transactions-all-download']")))
            download_button.click()
            self.driver.minimize_window()

            time.sleep(1)

            # excel downloaden
            xls_download_button = wait.until(EC.visibility_of_element_located((By.XPATH, '//*[@id="root"]/div/div/div/div/div/div/main/section/section/div/section/div/div/section/header/div[1]/aside/div/div/footer/section/aside/button[1]/span')))
            xls_download_button.click()

            # # umsätze älter als 90 tage
            # try:
            #     show_transactions = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="root"]/div/div/div/div/div/div/div/div/div/main/section/section/div/section/div/div/section/section/section/section[2]/div/div/footer/section/aside/button/span')))
            #     show_transactions.click()
            #     self.__verify_identity()
            #
            # except TimeoutException:
            #     self.logger.info("Keine Umsätze älter als 90 Tage vorhanden.")
            #     return

        except Exception:
            self.logger.error("Fehler beim Download der aktuellen Umsätze", exc_info=True)

        # time.sleep(3)  # wait for the download to start
        self._read_temp_files(sep=',')
        # start_time = time.time()
        # downloaded = False
        # while not downloaded:  # read all files in the download directory sorted in a dict
        #     time.sleep(0.5)
        #     if time.time() - start_time > 15:
        #         self.logger.error("Timeout beim Lesen der Dateien.")
        #         break
        #     downloaded = self._read_temp_files(sep=',')


    def process_data(self):
        merged_df = pd.DataFrame()
        try:
            for key, value in self.data.items():
                df = value.copy()
                merged_df = pd.concat([merged_df, df], ignore_index=True)

            self.data = merged_df.iloc[10:].rename(columns=merged_df.iloc[9]).dropna(subset=['Datum'])
        except Exception:
            self.logger.error("Fehler beim Zusammenführen der Daten", exc_info=True)

        self.__postprocess_data()

    def handle_cookie_banner(self):
        """
        Handles the cookie banner.
        """
        wait_sec = 5
        try:
            # Wait until the button is present and clickable
            decline_button = (WebDriverWait(self.driver, wait_sec).until
                              (EC.element_to_be_clickable(
                (By.XPATH, "//button[@onclick='handleDecline()']"))))
            decline_button.click()
            self.logger.debug("'Ablehnen' button clicked.")
        except Exception:
            self.logger.error("Fehler beim Klicken des 'Ablehnen'-Buttons im Cookie-Banner", exc_info=True)

    # ----------------------------------------------------------------
    # --------------------- private methods -------------------------
    def __verify_identity(self):
        self.__verified = False
        wait = WebDriverWait(self.driver, 10)

        try:
            mycode = self.__check_sms_code_input()

            input_field = wait.until(EC.visibility_of_element_located((By.XPATH, '//*[@id="root"]/div/div/div/div/div/div/main/section/section/div/section/div/div/section/section/section/section[2]/div[2]/div/div/div/div/div/section/div/div/section/section/div/div[1]/section/input')))
            input_field.send_keys(mycode)

            submit_btn = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="root"]/div/div/div/div/div/div/main/section/section/div/section/div/div/section/section/section/section[2]/div[2]/div/div/div/div/div/section/div/div/section/button/span')))
            submit_btn.click()

            time.sleep(0.5)

            submit_btn2 = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="root"]/div/div/div/div/div/div/main/section/section/div/section/div/div/section/section/section/section[2]/div[2]/div/footer/section/aside/button/span')))
            submit_btn2.click()

            # falls fehler, dann nochmal
            try:
                restart_btn = WebDriverWait(self.driver, 1).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="root"]/div/div/div/div/div/div/main/section/section/div/section/div/div/section/section/section/section[2]/div[2]/div/div/div/div/div[2]/div/div/div[2]/button')))
                restart_btn.click()
                self.logger.warning("Falscher SMS-Code eingegeben. Identifizierung wird wiederholt.")
                self.__verify_identity()
            except TimeoutException:
                pass
            
        except Exception:
            self.logger.error("Fehler bei der Authentifizierung", exc_info=True)
            self.close()

    def __check_sms_code_input(self):
        sms_code = input("Bitte geben Sie den 4-stelligen SMS-Code oder retry für erneute Anforderung ein:")
        self.sms_code  = sms_code
        if sms_code == "retry":
            self.__get_another_sms_code()

        else:
            self.__verified = True
            return sms_code

    def __get_another_sms_code(self):
        """
        Request another SMS code.
        """
        wait = WebDriverWait(self.driver, 5)
        resend_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="root"]/div/div/div/div/div/div/main/section/section/div/section/div/div/section/section/section/section[2]/div[2]/div/div/div/div/div/section/div/div/section/section/section/a/span')))
        resend_button.click()
        self.logger.info("Neuer SMS-Code angefordert.")



    def __postprocess_data(self):
        """
        Postprocess the data by converting date formats and numerical values.
        """
        try:
            self.data = self.data[['Datum', 'Betrag', 'Beschreibung', 'Punkte', 'Karte']]
        except Exception:
            self.logger.error("Fehler beim Postprocessing der Daten", exc_info=True)


if __name__ == '__main__':
    # aufruf für cli
    # AmazonVisa.cli_entry()

    # Testing
    amazon = AmazonVisa(perform_download=False, output_path='../out')
    amazon.credentials_file = '../credentials_amazon.txt'
    amazon._read_credentials()
    amazon.login()
    amazon.download_data()
    amazon.close()
    amazon.process_data()
    # amazon.save_data()


    # wait = WebDriverWait(amazon.driver, 10)
    # files_in_dir = os.listdir(amazon._download_directory)
    # downloaded_file = os.path.join(amazon._download_directory, files_in_dir[0])
    # df = pd.read_excel(downloaded_file, engine='openpyxl')
    # df = pd.read_excel(downloaded_file, engine="xlrd")
    pass

