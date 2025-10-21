# -*- coding: utf-8 -*-
"""
:author: Tim Häberlein
:version: 1.0
:date: 24.11.2024
:organisation: TU Dresden, FZM
"""
import time

import pandas as pd

# -------- start import block ---------
from WebCrawler.Base import *
import re

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
        time.sleep(0.5)
        self.__scroll_to_bottom()
        self.driver.minimize_window()

        # Warten bis Timeline sichtbar ist
        wait = WebDriverWait(self.driver, 15)
        try:
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'timeline')))
        except TimeoutException:
            self.logger.error("Timeline konnte nicht geladen werden.")
            return

        # Transaktionsdaten auslesen & elemente sammeln (alter Parser)
        # try:
        #     li_elements = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, 'timeline__entry')))
        # except TimeoutException:
        #     self.logger.error("Keine Timeline-Einträge gefunden.")
        #     return
        # self.data = self.__parse_transaction_elements(li_elements)
        # self.logger.info(f"{len(self.data)} Transaktionsdaten erfolgreich ausgelesen.")

        # Transaktionsdaten auslesen & elemente sammeln (neuer JS-basierter Parser)
        try:
            raw_entries = self.__get_raw_entries()
            if self.logger.level == logging.DEBUG:
                self.raw_entries = raw_entries
        except Exception:
            self.logger.error("Fehler beim Auslesen der Rohdaten-Einträge.", exc_info=True)
            return
        self.logger.info(f"Verarbeite {len(raw_entries)} Rohdaten-Einträge...")
        self.data = self.__process_js_transactions(raw_entries)
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

    def __scroll_to_bottom(self, wait_time: int = 10, pause_time:float = 0.1, stable_rounds: int = 3):
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

    def __get_raw_entries(self):
        """
        Liest alle Rohdaten-Einträge mittels Java-Scriot aus der Timeline.
        """
        js = """
            return Array.from(document.querySelectorAll('.timeline__entry')).map(li => {
                const cls = li.className || '';
                const title = li.querySelector('.timelineV2Event__title')?.innerText || '';
                const subtitle = li.querySelector('.timelineV2Event__subtitle')?.innerText || '';
                const price = li.querySelector('.timelineV2Event__price')?.innerText || '';
                const text = li.innerText || '';
                return {class: cls, title: title, subtitle: subtitle, price: price, text: text};
            });
        """
        try:
            raw_entries = self.driver.execute_script(js)
            self.logger.info(f"{len(raw_entries)} Rohdaten-Einträge erfolgreich ausgelesen.")
            return raw_entries
        except Exception as e:
            self.logger.error("Fehler beim Auslesen der Rohdaten-Einträge.", exc_info=True)
            return []
    def __process_js_transactions(self, raw_entries):
        """Verarbeitet die JavaScript-Rohdaten in DataFrame-kompatible Form."""

        # ---- Hilfsfunktionen ----
        def extract_date_and_purpose(subtitle, title, year):
            """Zerlegt das Datumsfeld und bildet den Verwendungszweck."""
            try:
                if not subtitle or not isinstance(subtitle, str):
                    raise ValueError("Kein gültiger subtitle-Text")

                match = re.match(r"^(\d{2}\.\d{2}\.)(?:\s*-\s*(.*))?$", subtitle.strip())
                if match:
                    datum_str = f"{match.group(1)}{year}"
                    verwendungszweck = f"{title} {match.group(2)}" if match.group(2) else title
                else:
                    datum_str = f"{subtitle.strip()}{year}"
                    verwendungszweck = title

                datum = pd.to_datetime(datum_str, format='%d.%m.%Y', errors='coerce')
                return datum, verwendungszweck

            except Exception as e:
                # Fehlerprotokoll für Debug
                self.logger.debug(f"Fehler beim Parsen von subtitle='{subtitle}': {e}")
                # Fallback
                return pd.NaT, title

        def normalize_price(price_str):
            """Bereinigt und formatiert Preisangaben."""
            if not price_str:
                return 'N/A'
            preis = price_str.replace('€', '').replace('.', '').replace(',', '.').strip()
            if not preis:
                return 'N/A'
            if preis.startswith('+'):
                preis = preis.replace('+', '')
            else:
                preis = f"-{preis}"
            return preis

        def update_month_context_from_text(text, month, year):
            """Aktualisiert Monat/Jahr basierend auf Monatsüberschrift."""
            text = text.strip()

            if text == "Dieser Monat":
                month = pd.to_datetime('today').strftime('%B')
                self.logger.debug(f"Wechsel zu Monat: {month} {year}")
                return month, year

            # 🧠 Regex:
            # ^([A-Za-zäöüÄÖÜß]+)         → fängt den Monatsnamen ein (auch mit Umlauten)
            # (?:\s+(\d{4}))?$            → optional: Leerzeichen + vierstellige Jahreszahl
            match = re.match(r"^([A-Za-zäöüÄÖÜß]+)(?:\s+(\d{4}))?$", text)

            if match:
                month = match.group(1)
                if match.group(2):
                    year = int(match.group(2))
                self.logger.debug(f"Wechsel zu Monat: {month} {year}")
            else:
                self.logger.debug(f"Unbekannte Monatszeile: '{text}'")

            return month, year
        # ----------------------------------------------------------------
        # ---- Hauptverarbeitungslogik ----
        daten = []
        month = pd.to_datetime('today').strftime('%B')
        year = pd.to_datetime('today').year
        stop_parsing = False

        for idx, e in enumerate(raw_entries):
            if stop_parsing:
                break

            classes = e.get('class', '')
            if '-isMonthDivider' in classes or '-isNewSection' in classes:
                month, year = update_month_context_from_text(e.get('text', ''), month, year)
                continue

            empfaenger = e.get('title', '').strip() or 'N/A'
            preis = normalize_price(e.get('price', '').strip())
            subtitle = e.get('subtitle', '').strip()
            datum, verwendungszweck = extract_date_and_purpose(subtitle, empfaenger, year)

            # 🔥 Enddatum-Abbruch
            if datum and datum < self.end_date:
                self.logger.info(f"Enddatum erreicht bei {datum.strftime('%d.%m.%Y')} – Parsing beendet.")
                stop_parsing = True
                break

            entry_dict ={
                'Datum': datum.strftime('%d.%m.%Y') if pd.notna(datum) else 'N/A',
                'Empfänger': empfaenger,
                'Verwendungszweck': verwendungszweck,
                'Betrag [€]': preis,
            }

            # self.driver.maximize_window()
            order_detail_keys = ['Kauforder', 'Verkaufsorder', 'Sparplan ausgeführt', 'Saveback']
            if any(key in verwendungszweck for key in order_detail_keys):
                details = self.__get_order_details_from_entry(idx)
                entry_dict['details'] = str(details)

            daten.append(entry_dict)



        return pd.DataFrame(daten)

    def __get_order_details_from_entry(self, index: int) -> dict:
        """
        Klickt auf einen timeline__entry, öffnet die Detailansicht,
        liest Label–Wert-Paare (Transaktion, Summe, Gebühr, …) aus
        und schließt das Overlay zuverlässig wieder.
        Gibt ein Dictionary der gefundenen Details zurück.
        """
        wait = WebDriverWait(self.driver, 12)
        details = {}

        # --- Subfunktion: Detailtabelle parsen ---
        def parse_detail_table():
            data = {}
            try:
                table = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.detailTable"))
                )
                rows = table.find_elements(By.CSS_SELECTOR, "div.detailTable__row")
                for row in rows:
                    try:
                        label = row.find_element(By.CSS_SELECTOR, "dt.detailTable__label").text.strip()
                        value = row.find_element(By.CSS_SELECTOR, "dd.detailTable__value").text.strip()
                        if label:
                            data[label] = value
                            self.logger.debug(f"Detail: {label} = {value}")
                    except Exception:
                        continue

                # Transaktion: „50 × 4,14 €“
                trans = data.get("Transaktion", "")
                m = re.match(r"(\d+(?:[.,]\d+)?)\s*[×x*]\s*([\d.,]+)\s*€", trans)
                if m:
                    data["Stückzahl"]  = float(m.group(1).replace(',', '.'))
                    data["Stückpreis"] = float(m.group(2).replace(',', '.'))

                # Numerische Felder konvertieren
                for key in ("Summe", "Gebühr"):
                    val = data.get(key)
                    if val and "€" in val:
                        data[key] = float(val.replace('€', '').replace('.', '').replace(',', '.').strip())
            except Exception as e:
                self.logger.warning(f"Detailtabelle konnte nicht gelesen werden: {e}", exc_info=True)
            return data

        # --- Subfunktion: Overlay schließen ---
        def close_overlay():
            for attempt, action in enumerate(("Button", "ESC", "Backdrop"), start=1):
                try:
                    if action == "Button":
                        btn = self.driver.find_element(By.CSS_SELECTOR, "button.closeButton.sideModal__close")
                        btn.click()
                    elif action == "ESC":
                        self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                    elif action == "Backdrop":
                        self.driver.find_element(By.CSS_SELECTOR, ".overlay.-raised").click()

                    WebDriverWait(self.driver, 5).until(
                        EC.invisibility_of_element_located((By.CSS_SELECTOR, ".timelineDetailModal"))
                    )
                    return True
                except Exception:
                    continue
            self.logger.debug("Detail-Overlay konnte nicht sicher geschlossen werden.")
            return False

        # --- Hauptablauf ---
        try:
            entries = self.driver.find_elements(By.CSS_SELECTOR, ".timeline__entry")
            if index < 0 or index >= len(entries):
                self.logger.debug(f"Index {index} außerhalb der Eintragsliste ({len(entries)}).")
                return {}

            entry = entries[index]

            # Nur echte klickbare Orders
            try:
                entry.find_element(By.CSS_SELECTOR, ".clickable.timelineEventAction")
            except NoSuchElementException:
                self.logger.debug(f"Entry {index} hat kein klickbares Event – überspringe.")
                return {}

            # Scroll-Offset (Header nicht verdecken)
            self.driver.execute_script("""
                const header = document.querySelector('header') || document.querySelector('.topBar');
                const h = header ? header.offsetHeight : 100;
                const y = arguments[0].getBoundingClientRect().top + window.scrollY - h - 20;
                window.scrollTo({top: y});
            """, entry)
            time.sleep(0.3)

            # Klick auf Entry
            entry.click()

            # Warte bis Overlay sichtbar und Tabelle da ist
            wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".timelineDetailModal")))
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.detailTable")))

            # Tabelle parsen
            details = parse_detail_table()

        except TimeoutException:
            self.logger.warning(f"Timeout beim Öffnen/Lesen der Order-Details (Index {index})")
        except Exception as e:
            self.logger.warning(f"Fehler beim Lesen der Order-Details (Index {index}): {e}", exc_info=True)
        finally:
            close_overlay()

        return details



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
    tr.set_logging_level('debug')
    # tr.end_date = tr.start_date - pd.DateOffset(months=12)
    tr.end_date = pd.to_datetime('15.10.2025', format='%d.%m.%Y')

    tr._read_credentials()
    tr.login()
    tr.download_data()
    # tr.close()
    # tr.process_data()
    # tr.save_data()

    # wait = WebDriverWait(tr.driver, 10)
    # entries = tr.driver.find_elements(By.CSS_SELECTOR, ".timeline__entry")
    # entry = entries[1]
    # container = modal.find_element(By.CSS_SELECTOR,
    #                                "div.timelineDetailModal__timelineDetail div:nth-child(2) > div"
    #                                )
    # rows = container.find_elements(By.CSS_SELECTOR, "div")
    # timer_element = wait.until(EC.presence_of_element_located((By.XPATH, "//button[@class='trLink smsCode__resendCode']//span[@role='timer']")))
    # button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@class='trLink smsCode__resendCode']//span[text()='Code als SMS senden']")))

    pass