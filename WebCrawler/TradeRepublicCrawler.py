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
            # li_elements = li_elements[:40]
            # self.li_elements = li_elements
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
                            month, year = li.text.split(' ')
                            year = int(year)
                            # new_month = li.text
                            # if month == 'Dezember' and new_month == 'Januar':
                            #     year = year - 1
                            # if new_month in ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember']:
                            #     month = new_month
                            #     self.logger.debug("Neuer Monat gefunden: {} {}".format(month, year))
                                # current_date = pd.to_datetime(f"{month} {year}", format='%B %Y') + pd.DateOffset(months=1)
                                # if current_date < pd.to_datetime(self.end_date, format='%d.%m.%Y'):
                                #     break
                        continue

                    # Name extrahieren
                    name_element = li.find_element(By.CLASS_NAME, 'timelineV2Event__title')
                    name = name_element.text.strip() if name_element else 'N/A'

                    # Preis extrahieren
                    preis_element = li.find_element(By.CLASS_NAME, 'timelineV2Event__price')
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
                        if pd.to_datetime(datum, format='%d.%m.%Y') < self.end_date:
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
                    self.logger.debug("interner Fehler beim Auslesen der einzelnen Zeilen, li-text: {}".format(li.text), exc_info=True)
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
    # tr = TradeRepublic(perform_download=False)
    # tr.credentials_file = '../credentials_traderepublic.txt'  # if you want to use another credentials file or path
    # tr.set_logging_level('debug')
    # tr._read_credentials()
    # tr.login()
    # tr.download_data()
    # tr.close()

    # wait = WebDriverWait(tr.driver, 10)
    # timer_element = wait.until(EC.presence_of_element_located((By.XPATH, "//button[@class='trLink smsCode__resendCode']//span[@role='timer']")))
    # button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@class='trLink smsCode__resendCode']//span[text()='Code als SMS senden']")))

    pass