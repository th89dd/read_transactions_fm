# -*- coding: utf-8 -*-
"""
:author: Tim Häberlein
:version: 1.0
:date: 24.11.2024
:organisation: TU Dresden, FZM
"""

# -------- start import block ---------
import time
from WebCrawler.Base import *


# -------- end import block ---------


class Amex(WebCrawler):
    def __init__(self, perform_download=True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__verified = False
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
        # Verifizierungscode (email, sms ...)
        try:
            self.driver.minimize_window()

            self.__verify_identity()

            wait = WebDriverWait(self.driver, 20)  # Warte bis zu 20 Sekunden
            submit_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[text()='Weiter' and @type='submit']")))
            submit_button.click()
            # warten, bis seite aufgebaut wurde
            balance_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Primary' and text()='Details zum Kontostand']")))

        except Exception:
            self.logger.error("Fehler bei der Authentifizierung", exc_info=True)

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
            date_input.send_keys(self.end_date.strftime("%d/%m/%Y"))

            date_input = wait.until(EC.element_to_be_clickable((By.ID, "endDate")))
            # date_input.clear()
            date_input.send_keys(Keys.CONTROL + "a")  # Wählt den gesamten Text aus
            # date_input.send_keys(Keys.BACKSPACE)  # Löscht den ausgewählten Text
            date_input.send_keys(self.start_date.strftime("%d/%m/%Y"))

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
        merged_df = pd.DataFrame()

        try:
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
    def __verify_identity(self):
        self.__verified = False
        verify_method = None
        wait = WebDriverWait(self.driver, 5)
        mycode = None

        try:
            # search for sms choose button
            self.logger.info('test')
            sms_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//h3[text()='Einmaliger Verifizierungscode (SMS)']/ancestor::button")))
            sms_button.click()
            self.logger.info("SMS Authentifizierung-Button geklickt.")
            verify_method = "sms"
        except TimeoutException:
            self.logger.info("Timeout beim Suchen des SMS Authentifizierung-Buttons", exc_info=True)
            # verify with mail
            try:
                # search for mail field
                email_field = wait.until(EC.presence_of_element_located((By.XPATH, "//p[@data-testid='verification-note']")))
                email_text = email_field.text
                if '@' in email_text:
                    self.logger.info("Email field contains '@'.")
                    verify_method = "email"
                else:
                    self.logger.info("Email field does not contain '@'.")
            except TimeoutException:
                self.logger.error("Timeout beim Suchen des Email-Feldes", exc_info=True)
                self.close()

        if verify_method == "sms":
            while not self.__verified:
                mycode = self.__check_sms_code_input()
        elif verify_method == "email":
            while not self.__verified:
                mycode = input("Bitte geben Sie den 6-stelligen Code aus der Email ein:")
        else:
            self.logger.error("Keine Authentifizierungsmethode gefunden.", exc_info=True)
            self.close()

        try:
            input_field = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "input[data-testid='question-value']")))
            input_field.send_keys(mycode)
            input_field.send_keys(Keys.RETURN)
        except Exception:
            self.logger.error("Fehler bei der Authentifizierung", exc_info=True)
            self.close()

    def __check_email_code_input(self):
        email_code = input("Bitte geben Sie den 6-stelligen Code aus der E-Mail ein:")
        self.__verified = True
        return email_code

    def __check_sms_code_input(self):
            sms_code = input("Bitte geben Sie den 6-stelligen SMS-Code oder retry für erneute Anforderung ein:")
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
        resend_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@data-testid='resend-button']")))
        resend_button.click()
        self.logger.info("Neuer SMS-Code angefordert.")

    def __check_sms_code_input_cyclic(self):
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
    amex = Amex(perform_download=False, output_path='../out/amex')
    amex.credentials_file = '../credentials_amex.txt'
    amex._read_credentials()
    amex.login()
    amex.download_data()
    # amex.close()
    # amex.process_data()
    # amex.save_data()
