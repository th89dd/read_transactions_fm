# -*- coding: utf-8 -*-
"""
:author: Tim Häberlein
:version: 1.0
:date: 24.11.2024
:organisation: TU Dresden, FZM
"""
import time

# -------- start import block ---------
from WebCrawler.Base import *

# -------- end import block ---------


class TradeRepublic(WebCrawler):
    """
    TradeRepublic is a class to download tansaction data from the online banking platform Traderepublic
    """
    def __init__(self, perform_download=True, *args, **kwargs):
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

        super().__init__(name='TradeRepublicTransactions', *args, **kwargs)
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

        # user
        self.__user_input()
        # passwort
        self.__pwd_input()

        # 2 faktor authentifizierung
        self.__identify()

    def download_data(self):
        # Basis-Methode aufrufen
        super().download_data()
        try:
            self.logger.info("Navigiere zur Transaktions-Seite.")
            self.driver.get(self.urls['transactions'])
        except Exception as e:
            self.logger.error("Fehler beim Navigieren zur Transaktions-Seite", exc_info=True)

        # Bis nach unten scrollen, um alle Transaktionen zu laden
        self.driver.maximize_window()
        self.__scroll_to_bottom()
        self.driver.minimize_window()

        # Warten bis Timeline sichtbar ist
        wait = WebDriverWait(self.driver, 15)
        try:
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'timeline')))
        except TimeoutException:
            self.logger.error("Timeline konnte nicht geladen werden.")
            return

        # Elemente sammeln
        try:
            li_elements = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, 'timeline__entry')))
        except TimeoutException:
            self.logger.error("Keine Timeline-Einträge gefunden.")
            return

        # Transaktionsdaten auslesen
        self.data = self.__parse_transaction_elements(li_elements)
        self.logger.info(f"{len(self.data)} Transaktionsdaten erfolgreich ausgelesen.")

    def process_data(self):
        """
        Performs post-processing on the transaction data.
        """
        super().process_data()
        # convert lebensmittel
        # lebensmittel_list = ['edeka', 'penny', 'lidl', 'aldi', 'rewe', 'netto', 'konsum', 'kaufland', 'real', 'marktkauf']
        # self.data['Empfänger'] = self.data['Verwendungszweck'].apply(lambda x: x if any(l in x.lower() for l in lebensmittel_list) else None)

        # Umbuchungen finden und Verwendungszweck sowie Empfänger anpassen
        # self.data['Verwendungszweck'] = self.data['Verwendungszweck'].apply(TradeRepublic.find_umbuchungen)
        # self.data.loc[self.data['Verwendungszweck'] == '[DKB_Tim]', 'Empfänger'] = None

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

    # ----------------------------------------------------------------
    # --------------------- private methods -------------------------
    def __user_input(self):
        wait_sec = 10
        try:
            username_field = WebDriverWait(self.driver, wait_sec).until(EC.presence_of_element_located((By.ID, "loginPhoneNumber__input")))
            username_field.send_keys(self.credentials['user'])
            username_field.send_keys(Keys.RETURN)
            self.logger.debug("Usename wurde eingegeben und Formular abgeschickt.")
        except Exception as e:
            self.logger.error("Fehler beim Ausfüllen des Benutzernamens", exc_info=True)

    def __pwd_input(self):
        wait_sec = 10
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

    def __identify(self):
        wait_sec = 10
        wait = WebDriverWait(self.driver, wait_sec)
        try:
            # Wait until the fieldset is present
            fieldset = wait.until(
                EC.presence_of_element_located((By.ID, "smsCode__input"))
            )
            # Find all input fields within the fieldset
            pin_inputs = fieldset.find_elements(By.CLASS_NAME, "codeInput__character")

            # Prompt the user to enter the four digits
            pin = self.__get_sms_code()

            # Enter each digit into the corresponding input field
            for i, digit in enumerate(pin):
                pin_inputs[i].send_keys(digit)

        except Exception as e:
            self.logger.error("Fehler bei der Eingabe des SMS-Codes", exc_info=True)
            self.error_close()

    def __get_sms_code(self):
        # Prompt the user to enter the four digits

        pin = input("Bitte geben Sie den 4-stellige Verifizierungs-Code ein, der über die APP angezeigt wird oder SMS, falls du die via SMS-Code verifizieren möchtest:")
        if pin == 'SMS':
            return self.__verify_by_sms()
        else:
            return pin

    def __verify_by_sms(self):
        sms_ready = False
        self.driver.maximize_window()
        time.sleep(0.5)
        self.driver.minimize_window()
        while not sms_ready:
                timer_value_s = self.__read_timer()
                if timer_value_s == '0':
                    self.__send_sms_code()
                    sms_ready = True
                else:
                    self.logger.info("SMS-Code wird in systembedingt erst in {} Sekunden gesendet.".format(timer_value_s))
                    time.sleep(2)
        pin = input("Bitte geben Sie den 4-stellige SMS-Code ein oder erneut SMS, falls sie das Verfahren neu starten möchten:")
        if pin == 'SMS':
            self.__verify_by_sms()
        else:
            return pin

    def __read_timer(self):
        try:
            # Wait until the timer element is present
            wait = WebDriverWait(self.driver, 2)
            timer_element = wait.until(EC.presence_of_element_located((By.XPATH, "//button[@class='trLink smsCode__resendCode']//span[@role='timer']")))

            # Read the timer value
            timer_value = timer_element.text
            return timer_value

        except TimeoutException:
            return '0'

        except Exception as e:
            self.logger.error("Error identifying or reading the timer.", exc_info=True)
            self.error_close()

    def __send_sms_code(self):
        try:
            # Wait until the button is present and clickable
            wait = WebDriverWait(self.driver, 10)
            button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@class='trLink smsCode__resendCode']//span[text()='Code als SMS senden']")))
            button.click()
        except Exception as e:
            self.logger.error("Error sending the SMS code.", exc_info=True)
            self.error_close()

    def __scroll_to_bottom(self, wait_time: int = 10, pause_time:float = 0.01, stable_rounds: int = 3):
        """
        Scrollt die Seite bis zum Ende und wartet jeweils, bis neue Elemente geladen sind.
        """

        self.logger.info("Scrolle, bis alle Transaktionen geladen sind...")
        wait = WebDriverWait(self.driver, wait_time)
        last_count = 0
        same_count = 0

        while same_count < stable_rounds:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(pause_time)
            li_elements = self.driver.find_elements(By.CLASS_NAME, 'timeline__entry')
            current_count = len(li_elements)

            if current_count == last_count:
                same_count += 1
            else:
                same_count = 0
            last_count = current_count

        self.logger.info(f"Scrollen abgeschlossen. Insgesamt {last_count} Einträge geladen.")

    def __parse_transaction_elements(self, li_elements):
        """
        Parsed alle Timeline-Einträge in eine DataFrame-kompatible Struktur.
        """
        daten = []
        month = pd.to_datetime('today').strftime('%B')
        year = pd.to_datetime('today').year

        for li in li_elements:
            try:
                classes = li.get_attribute('class')

                # Monatsabschnitte erkennen
                if '-isNewSection' in classes or '-isMonthDivider' in classes:
                    self.__update_month_context(li, month, year)
                    continue

                eintrag = self.__parse_single_transaction(li, month, year)
                if eintrag is None:
                    break  # Datumsgrenze erreicht
                daten.append(eintrag)

            except Exception as inner_e:
                self.logger.debug(f"Fehler beim Verarbeiten eines Eintrags: {li.text[:60]}...", exc_info=True)

        return pd.DataFrame(daten)

    def __update_month_context(self, li, month, year):
        """
        Aktualisiert den aktuellen Monat und das Jahr basierend auf der Monatsüberschrift.
        """
        text = li.text.strip()
        if text == "Dieser Monat":
            month = pd.to_datetime('today').strftime('%B')
            self.logger.debug(f"Wechsel zu Monat: {month} {year}")
        else:
            try:
                month_text, year_text = text.split(' ')
                month = month_text
                year = int(year_text)
                self.logger.debug(f"Wechsel zu Monat: {month} {year}")
            except ValueError:
                self.logger.debug(f"Unbekannte Monatszeile: '{text}'")
        return month, year

    def __parse_single_transaction(self, li, month, year):
        """
        Liest eine einzelne Transaktion aus einem Timeline-Element aus.
        Gibt ein Dictionary mit Datum, Empfänger, Verwendungszweck und Betrag zurück.
        Bricht zurück, wenn die end_date erreicht wurde.
        """
        # Empfänger
        try:
            empfaenger = li.find_element(By.CLASS_NAME, 'timelineV2Event__title').text.strip()
        except NoSuchElementException:
            empfaenger = 'N/A'

        # Betrag
        try:
            preis_element = li.find_element(By.CLASS_NAME, 'timelineV2Event__price')
            if preis_element:
                preis = preis_element.text.replace(' €', '').replace('.', '').strip()
                preis = preis.replace(',', '.')
                preis = preis.replace('+', '') if preis.startswith('+') else f"-{preis}"
            else:
                preis = 'N/A'
        except NoSuchElementException:
            preis = 'N/A'

        # Datum + Verwendungszweck
        try:
            datum_element = li.find_element(By.CLASS_NAME, 'timelineV2Event__subtitle')
            if datum_element:
                raw_datum = datum_element.text.strip()
                try:
                    datum, extra = raw_datum.split('-')
                    datum = f"{datum.strip()}{year}"
                    verwendungszweck = f"{empfaenger} {extra.strip()}"
                except ValueError:
                    datum = f"{raw_datum}{year}"
                    verwendungszweck = empfaenger

                # Datumsgrenze prüfen
                if pd.to_datetime(datum, format='%d.%m.%Y') < self.end_date:
                    self.logger.debug(f"Datumsgrenze erreicht bei {datum}.")
                    return None
            else:
                datum = 'N/A'
                verwendungszweck = empfaenger
        except NoSuchElementException:
            datum = 'N/A'
            verwendungszweck = empfaenger

        return {
            'Datum': datum,
            'Empfänger': empfaenger,
            'Verwendungszweck': verwendungszweck,
            'Betrag [€]': preis,
        }

    # ----------------------------------------------------------------
    # --------------------- static methods ---------------------------
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


if __name__ == '__main__':
    tr = TradeRepublic(perform_download=False, output_path='../out')
    tr.credentials_file = '../credentials_traderepublic.txt'  # if you want to use another credentials file or path
    # tr.set_logging_level('debug')
    tr._read_credentials()
    tr.end_date = tr.start_date - pd.DateOffset(months=12)
    tr.login()
    tr.download_data()
    tr.close()
    tr.process_data()
    tr.save_data()

    # wait = WebDriverWait(tr.driver, 10)
    # timer_element = wait.until(EC.presence_of_element_located((By.XPATH, "//button[@class='trLink smsCode__resendCode']//span[@role='timer']")))
    # button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@class='trLink smsCode__resendCode']//span[text()='Code als SMS senden']")))

    pass