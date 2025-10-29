# -*- coding: utf-8 -*-
"""
:author: Tim Häberlein
:version: 2.0
:date: 25.10.2025
:organisation: TU Dresden, FZM

TradeRepublicCrawler
-----------
Crawler für TradeRepublic – lädt Transaktionen im gewählten Zeitraum herunter
und führt sie in ein einheitliches Format über.

Der Crawler orientiert sich an der Architektur der `ArivaCrawler`- und `AmazonVisaCrawler`-Klassen.
Er nutzt Selenium zur Browsersteuerung, greift auf Anmeldedaten aus der zentralen `config.yaml` zu
und setzt auf die generische Basisklasse `WebCrawler`, die Standardfunktionen wie Logging,
Fehlerbehandlung, Warte- und Retry-Mechanismen, Datendownload und Dateiverarbeitung bereitstellt.
"""

"""
TODOs:
- Login-Prozess mit Ländervorwahl für Telefonnummer erweitern
"""

# -------- start import block ---------
import os
import re
import time
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from typing import Any

try:
    from .base import WebCrawler
except ImportError:
    from src.read_transactions.webcrawler.base import WebCrawler
# -------- /import block ---------

class TradeRepublicCrawler(WebCrawler):
    """
    TradeRepublicCrawler
    --------------------
    Crawler für Transaktionsdaten von **Trade Republic**.

    Der Crawler automatisiert den Login im Webinterface von
    [https://app.traderepublic.com](https://app.traderepublic.com),
    lädt alle Transaktionen im gewählten Zeitraum, verarbeitet
    die Daten zu einem strukturierten pandas-DataFrame und
    speichert sie optional als CSV.

    Ablauf:
        1. Login mit Telefonnummer und PIN.
        2. Zwei-Faktor-Authentifizierung (SMS- oder App-Code).
        3. Scrollen und Laden aller Transaktionen.
        4. Extraktion und Verarbeitung der Transaktionsdaten.
        5. Optionale Speicherung der Daten im Ausgabeverzeichnis.

    Voraussetzung:
        - Gültige Zugangsdaten in `config.yaml` unter:
            ```yaml
            credentials:
                trade_republic:
                    # ohne +49 Ländervorwahl
                    user: 1701234567
                    password: 1234

            urls:
                traderepublic:
                    login: https://app.traderepublic.com/login
                    transactions: https://app.traderepublic.com/profile/transactions
            ```
        - Installierter Selenium-WebDriver (Edge, Chrome oder Firefox)
        - Python ≥ 3.10

    Parameter
    ----------
    details : bool, optional
        Falls `True`, werden bei Kauf-/Verkaufsorders zusätzliche
        Details (Stückzahl, Stückpreis, Gebühren, etc.) extrahiert.
        Standard: `True`.

    output_path : str, optional
        Zielverzeichnis, in dem heruntergeladene oder verarbeitete
        Dateien gespeichert werden. Standard: ``out``.

    start_date : str | pandas.Timestamp | datetime.date, optional
        Startdatum für den Transaktionsabruf. Format: ``"dd.mm.yyyy"``.
        Standard: heutiges Datum.

    end_date : str | pandas.Timestamp | datetime.date, optional
        Enddatum für den Transaktionsabruf. Format: ``"dd.mm.yyyy"``.
        Standard: sechs Monate vor `start_date`.

    logging_level : str, optional
        Log-Level der Crawler-Instanz (z. B. ``"DEBUG"``, ``"INFO"``).
        Standard: ``"INFO"``.

    global_log_level : str, optional
        Globales Log-Level für das gesamte Paket.
        Standard: ``"INFO"``.

    logfile : str, optional
        Pfad zu einer Logdatei. Wenn `None`, wird nur in die Konsole geloggt.

    browser : str, optional
        Zu verwendender WebDriver (``"edge"``, ``"chrome"`` oder ``"firefox"``).
        Standard: ``"edge"``.

    headless : bool, optional
        Falls `True`, wird der Browser im Hintergrundmodus gestartet.
        Standard: ``False``.

    user_agent : str, optional
        Optionaler benutzerdefinierter User-Agent für den WebDriver.

    Attribute
    ----------
    data : pandas.DataFrame
        Enthält die verarbeiteten Transaktionsdaten nach `process_data()`.

    _credentials : dict
        Zugriff auf die aus der Konfiguration geladenen Zugangsdaten.

    _urls : dict
        Zugriff auf die aus der Konfiguration geladenen URLs.

    _logger : logging.Logger
        Instanzspezifischer Logger mit konsistenter Formatierung.

    Beispiel
    --------
    ```python
    from read_transactions.webcrawler import TradeRepublicCrawler

    with TradeRepublicCrawler(logging_level="DEBUG") as crawler:
        crawler.login()
        crawler.download_data()
        crawler.process_data()
        crawler.save_data()
    ```
    """
    def __init__(self, *args, **kwargs):
        super().__init__(name="trade_republic",*args, **kwargs)
        self._load_config()
        self.__portfolio_balance = 0.0

    @property
    def portfolio_balance(self) -> str:
        """Gibt den aktuellen Portfolio-Gesamtwert als formatierten String zurück."""
        return str(round(self.__portfolio_balance, 2)) + " €"
    @portfolio_balance.setter
    def portfolio_balance(self, value: Any) -> None:
        """Setzt den Portfolio-Gesamtwert."""
        value = self._normalize_amount(value)
        try:
            value = float(value)
        except (ValueError, TypeError):
            self._logger.warning(f"Konnte Portfolio-Gesamtwert nicht in float umwandeln: {value}")
            value = 0.0
        self.__portfolio_balance = value

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------
    def login(self) -> None:
        """Führt Login bei Trade Republic aus (User, PIN, 2FA)."""
        super().login()
        driver = self.driver
        urls = self._urls

        driver.get(urls["login"])
        self._handle_cookie_banner()

        # Ausführen mit Retry
        self._retry_func(self._enter_phone, max_retries=2, wait_seconds=1)
        self._retry_func(self._enter_pin, max_retries=2, wait_seconds=1)

        # Zwei-Faktor-Authentifizierung
        self._verify_identity()

        # Warten auf Login-Abschluss
        self._retry_func(self._wait_for_login_completed, max_retries=2, wait_seconds=2)

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------
    def download_data(self) -> None:
        """Lädt Transaktionsdaten von Trade Republic."""
        super().download_data()
        driver = self.driver
        urls = self._urls

        try:
            driver.get(urls["transactions"])
            self._wait_for_account_balance()
            self._scroll_to_bottom()

            raw_entries = self._get_raw_entries()
            df = self._process_raw_entries(raw_entries)
            self.data = df

            self._logger.info(f"{len(df)} Transaktionen erfolgreich eingelesen.")
        except Exception:
            self._logger.error("Fehler beim Download der Transaktionsdaten.", exc_info=True)

    # ------------------------------------------------------------------
    # Verarbeitung
    # ------------------------------------------------------------------
    def process_data(self) -> None:
        """Führt die Rohdaten in ein bereinigtes DataFrame-Format über."""
        # super().process_data() -> keine Daten einzulesen -> speziell implementieren
        self._state = "process_data"
        if not isinstance(self.data, pd.DataFrame) or self.data.empty:
            self._logger.warning("Keine Transaktionsdaten zum Verarbeiten gefunden.")
            return
        self.data = self._normalize_dataframe(self.data)
        self._logger.info(f"{len(self.data)} Trade Republic Transaktionen verarbeitet.")

    # ------------------------------------------------------------------
    # Cookie-Banner
    # ------------------------------------------------------------------
    def _handle_cookie_banner(self) -> None:
        """Schließt ggf. das Cookie-Banner über bekannte Buttons."""
        try:
            checkbox = self.wait_for_element("id", "necessarySelection", 15)
            if not checkbox.is_selected():
                checkbox.click()
            self.wait_clickable_and_click(
                "xpath",
                "//span[@class='buttonBase__title' and text()='Auswahl speichern']",
                15)
            # self.click_js(save_btn)
            self._logger.debug("Cookie-Banner erkannt und geschlossen.")
        except Exception:
            self._logger.debug("Kein Cookie-Banner erkannt oder bereits geschlossen.")

    # ------------------------------------------------------------------
    # Login-Helfer
    # ------------------------------------------------------------------
    # Telefonnummer eingeben
    def _enter_phone(self) -> None:
        """Gibt die Telefonnummer im Login-Formular ein."""
        field = self.wait_for_element("id", "loginPhoneNumber__input", 10)
        field.send_keys(self._credentials["user"])
        field.send_keys(Keys.RETURN)
        self._logger.debug("Telefonnummer eingegeben.")

    # PIN eingeben
    def _enter_pin(self) -> None:
        """Gibt die PIN im Login-Formular ein."""
        fieldset = self.wait_for_element("id", "loginPin__input", 10)
        pin_inputs = fieldset.find_elements(By.CLASS_NAME, "codeInput__character")
        pin = str(self._credentials["password"])
        for i, digit in enumerate(pin):
            pin_inputs[i].send_keys(digit)
        self._logger.debug("PIN eingegeben.")

    def _wait_for_login_completed(self) -> None:
        """Wartet, bis der Login-Prozess abgeschlossen ist."""
        self.portfolio_balance = self.wait_for_element(
            "xpath",
            "//span[contains(@class,'currencyStatus')]//span[@role='status']",
            10).text.strip()
        self._logger.info(f"Login erfolgreich – Portfolio-Gesamtwert: {self.portfolio_balance}")

    def _wait_for_account_balance(self) -> None:
        """Wartet, bis das Konto-Dashboard mit dem Kontostand geladen ist."""
        self.account_balance = self.wait_for_element(
            'xpath',
            "//span[contains(@class,'cashBalance__amount')]",
            15).text.strip()
        self._logger.info(f"Konto-Gesamtwert geladen: {self.account_balance}")

    # ------------------------------------------------------------------
    # Zwei-Faktor-Authentifizierung
    # ------------------------------------------------------------------
    def _verify_identity(self) -> None:
        """Führt Zwei-Faktor-Authentifizierung (SMS oder App) aus."""
        def _get_code() -> str:
            """Fordert den Benutzer zur Eingabe des Push-Codes auf oder startet SMS-Verifizierung."""
            self._logger.info("📲 Push-Verifizierung – Code wird per App gesendet.")
            code = input(
                "🔐 Bitte 4-stelligen Code aus der push-Benachrichtigung eingeben ('sms' - für sms-verifizierung): "
            ).strip()
            if code.lower() == "sms":
                code = _get_sms_code()
                while code.lower() == "sms":  # neustart der sms-verifizierung
                    code = _get_sms_code()
                return code
            else:
                return code

        def _get_sms_code() -> str:
            """Startet SMS-Verifizierung und fordert zur Code-Eingabe auf."""
            try:
                sms_rdy = False
                self.driver.maximize_window()
                time.sleep(0.1)
                self.driver.minimize_window()
                while not sms_rdy:  # auslesen des sms_rdy status
                    try:
                        timer_val = self.wait_for_element(
                            "xpath",
                            "//button[@class='trLink smsCode__resendCode']//span[@role='timer']",
                            10).text
                    except TimeoutException:
                        timer_val = 0
                    if timer_val == 0:
                        # timer value nicht mehr gefunden → sms_rdy = True + sms code anfordern
                        sms_rdy = True
                        self.wait_clickable_and_click(
                            "xpath",
                            "//button[contains(@class,'smsCode__resendCode') and .//span[normalize-space()='Code als SMS senden']]",
                            10)
                    else:  # warten bis timer 0 erreicht
                        self._logger.info(f"Warte auf SMS-Verifizierungsoption... ({timer_val} Sekunden verbleibend)")
                        time.sleep(5)
                # SMS-Code angefordert - eingabe auffordern
                self._logger.info("📩 SMS-Verifizierung – Code wird per SMS gesendet.")
                code = input("🔐 Bitte 4-stelligen Code aus SMS eingeben: ('sms' - für Neustart)").strip()
                return code
            except Exception:
                self._logger.warning("Konnte SMS-Verifizierungs-Button nicht finden.")
            return 'sms'  # fallback um neustart zu erzwingen

        def _enter_and_submit_code() -> bool:
            """Gibt den 4-stelligen Code in die Eingabefelder ein."""
            try:
                code = _get_code()
                if not code or len(code) != 4:
                    self._logger.warning("Ungültiger Code eingegeben.")
                    return False
                otp_field = self.wait_for_element("id", "smsCode__input", 5)
                inputs = otp_field.find_elements(By.CLASS_NAME, "codeInput__character")
                for i, digit in enumerate(code):
                    inputs[i].send_keys(digit)
                return True
            except Exception:
                self._logger.error("Fehler bei der Code-Eingabe.", exc_info=True)
                return False

        try:
            otp_field = self.wait_for_element("id", "smsCode__input", 15)
            if not otp_field:
                return
            for attempt in range(3):  # max 3 versuche zur verifizierung starten
                self._logger.info(f"Starte OTP-Verifikation (Versuch {attempt+1}/3)…")
                if _enter_and_submit_code():
                    self._logger.debug("OTP-Code eingegeben, warte auf Bestätigung…")
                    break
            else:
                self._logger.error("Maximale Anzahl an 2FA-Versuchen erreicht.")
        except Exception:
            self._logger.error("Fehler bei der Zwei-Faktor-Authentifizierung.", exc_info=True)

    # ------------------------------------------------------------------
    # Scrollen
    # ------------------------------------------------------------------
    def _scroll_to_bottom(self, pause: float = 0.25, stable_rounds: int = 3) -> None:
        """Scrollt die Seite vollständig, bis keine neuen Einträge mehr erscheinen."""
        self._logger.info("Scrolle bis zum Seitenende, um alle Transaktionen zu laden...")
        self.driver.maximize_window()
        last_count = 0
        same_count = 0
        while same_count < stable_rounds:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(pause)
            entries = self.driver.find_elements(By.CLASS_NAME, "timeline__entry")
            current_count = len(entries)
            if current_count == last_count:
                same_count += 1
            else:
                same_count = 0
            last_count = current_count
        self.driver.minimize_window()
        self.driver.execute_script("window.scrollTo(0, 0);")
        self._logger.debug(f"Scrollen abgeschlossen – {last_count} Einträge geladen.")

    # ------------------------------------------------------------------
    # Rohdaten auslesen
    # ------------------------------------------------------------------
    def _get_raw_entries(self) -> list[dict]:
        """Liest Timeline-Elemente direkt per JavaScript aus."""
        js = """
        return Array.from(document.querySelectorAll('.timeline__entry')).map(li => ({
            class: li.className,
            title: li.querySelector('.timelineV2Event__title')?.innerText || '',
            subtitle: li.querySelector('.timelineV2Event__subtitle')?.innerText || '',
            price: li.querySelector('.timelineV2Event__price')?.innerText || '',
            text: li.innerText || ''
        }));
        """
        try:
            raw = self.driver.execute_script(js)
            self._logger.debug(f"{len(raw)} Rohdateneinträge aus Timeline gelesen.")
            return raw
        except Exception:
            self._logger.error("Fehler beim Auslesen der Timeline-Rohdaten.", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # Rohdaten verarbeiten
    # ------------------------------------------------------------------
    def _process_raw_entries(self, raw_entries):
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
                self._logger.debug(f"Fehler beim Parsen von subtitle='{subtitle}': {e}")
                # Fallback
                return pd.NaT, title

        def normalize_price(price_str):
            """Bereinigt und formatiert Preisangaben."""
            if not price_str:
                return 'N/A'
            if price_str.startswith('+'):
                preis = price_str.replace('+', '')
            else:
                preis = f"-{price_str}"
            return preis

        def update_month_context_from_text(text, month, year):
            """Aktualisiert Monat/Jahr basierend auf Monatsüberschrift."""
            text = text.strip()

            if text == "Dieser Monat":
                month = pd.to_datetime('today').strftime('%B')
                self._logger.debug(f"Wechsel zu Monat: {month} {year}")
                return month, year

            # 🧠 Regex:
            # ^([A-Za-zäöüÄÖÜß]+)         → fängt den Monatsnamen ein (auch mit Umlauten)
            # (?:\s+(\d{4}))?$            → optional: Leerzeichen + vierstellige Jahreszahl
            match = re.match(r"^([A-Za-zäöüÄÖÜß]+)(?:\s+(\d{4}))?$", text)

            if match:
                month = match.group(1)
                if match.group(2):
                    year = int(match.group(2))
                self._logger.debug(f"Wechsel zu Monat: {month} {year}")
            else:
                self._logger.debug(f"Unbekannte Monatszeile: '{text}' in {year}/{month}")

            return month, year
        # ----------------------------------------------------------------
        # ---- Hauptverarbeitungslogik ----
        daten = []
        month = pd.to_datetime('today').strftime('%B')
        year = pd.to_datetime('today').year
        stop_parsing = False
        self._logger.info(f"Verarbeite Rohdaten der Transaktionen... (Detailmodus: {self.with_details})")

        start_time = time.time()
        last_log_time = start_time
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
                self._logger.info(f"Enddatum erreicht bei {datum.strftime('%d.%m.%Y')} – Parsing beendet.")
                stop_parsing = True
                break

            entry_dict ={
                'Datum': datum.strftime('%d.%m.%Y') if pd.notna(datum) else 'N/A',
                'Empfänger': empfaenger,
                'Verwendungszweck': verwendungszweck,
                'Betrag': preis,}

            # self.driver.maximize_window()
            # Zusätzliche Details bei Kauf-/Verkaufsorders
            if self.with_details:
                order_detail_keys = ['Kauforder', 'Verkaufsorder', 'Sparplan ausgeführt', 'Saveback']
                if any(key in verwendungszweck for key in order_detail_keys):
                    details = self._get_order_details_from_entry(idx)
                    if 'overlay_close_error' in details:
                        break
                    entry_dict['details'] = str(details)

            daten.append(entry_dict)

            if time.time() - last_log_time > 5:
                self._logger.info(f"Verarbeite Eintrag {idx+1}/{len(raw_entries)}...")
                self._logger.debug(f"{len(daten)} Einträge bisher verarbeitet.")
                last_log_time = time.time()

        return pd.DataFrame(daten)

    def _get_order_details_from_entry(self, index: int) -> dict:
        """
        Klickt auf einen timeline__entry, öffnet die Detailansicht,
        liest Label–Wert-Paare (Transaktion, Summe, Gebühr, …) aus
        und schließt das Overlay zuverlässig wieder.
        Gibt ein Dictionary der gefundenen Details zurück.
        """
        details = {}

        # --- Subfunktion: Detailtabelle parsen ---
        def parse_detail_table():
            data = {}
            try:
                table = self.wait_for_element(
                    "css selector","div.detailTable", 10)
                rows = table.find_elements(By.CSS_SELECTOR, "div.detailTable__row")
                for row in rows:
                    try:
                        label = row.find_element(By.CSS_SELECTOR, "dt.detailTable__label").text.strip()
                        value = row.find_element(By.CSS_SELECTOR, "dd.detailTable__value").text.strip()
                        if label:
                            data[label] = value
                            # self._logger.debug(f"Detail: {label} = {value}")
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
                    if val:
                        data[key] = self._normalize_amount(val)
            except Exception as e:
                self._logger.warning(f"Detailtabelle konnte nicht gelesen werden: {e}", exc_info=True)
            return data

        # --- Subfunktion: Overlay schließen ---
        def close_overlay(timeout: int = 12) -> bool:
            """Schließt das Overlay durch Tabben zum Schließen-Button und Betätigen."""
            modals = self.driver.find_elements(By.CSS_SELECTOR, ".timelineDetailModal")
            if len(modals) == 0:
                self._logger.debug("Kein Overlay zum Schließen gefunden.")
                return True  # bereits geschlossen
            closed = False
            start_time = time.time()
            body = self.driver.find_element(By.TAG_NAME, "body")
            while (time.time() - start_time) < timeout:
                body.send_keys(Keys.TAB)
                # time.sleep(0.5)
                ele = self.driver.switch_to.active_element
                if ele.text.lower() == 'schließen':
                    ele.send_keys(Keys.SPACE)
                    time.sleep(0.5)
                    # self._logger.debug("Overlay geschlossen.")
                    return True
                # check if closed
                # modals = self.driver.find_elements(By.CSS_SELECTOR, ".timelineDetailModal")
                # if len(modals) == 0:
                #     self._logger.debug("Overlay geschlossen.")
                #     return True
            return False

        # --- Hauptablauf ---
        try:
            self.wait_for_element("css selector", ".timeline__entry", 10)
            entries = self.driver.find_elements(By.CSS_SELECTOR, ".timeline__entry")
            if index < 0 or index >= len(entries):
                self._logger.debug(f"Index {index} außerhalb der Eintragsliste ({len(entries)}).")
                return {}

            entry = entries[index]

            # Nur echte klickbare Orders
            try:
                entry.find_element(By.CSS_SELECTOR, ".clickable.timelineEventAction")
            except NoSuchElementException:
                self._logger.debug(f"Entry {index} hat kein klickbares Event – überspringe.")
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
            self.wait_for_element('css selector', ".timelineDetailModal", 10)
            self.wait_for_element('css selector', "div.detailTable", 10)

            # Tabelle parsen
            details = parse_detail_table()

        except TimeoutException:
            self._logger.warning(f"Timeout beim Öffnen/Lesen der Order-Details (Index {index})")
        except Exception as e:
            self._logger.warning(f"Fehler beim Lesen der Order-Details (Index {index}): {e}", exc_info=True)
        finally:
            closed = close_overlay()
            if not closed:
                self._logger.error("Konnte Order-Detail-Overlay nicht schließen.")
                return {'overlay_close_error': True}

        return details


# ----------------------------------------------------------------------
# Direktstart (Debug)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # from src.read_transactions.logger import MainLogger
    # MainLogger.configure()
    # MainLogger.set_stream_level("DEBUG")
    end_date = pd.to_datetime("today") - pd.DateOffset(months=1)
    with TradeRepublicCrawler(logging_level="DEBUG", end_date=end_date) as crawler:
        crawler.login()
        crawler.download_data()
        crawler.process_data()
        crawler.save_data()

    # crawler = TradeRepublicCrawler(logging_level="DEBUG", end_date=end_date)
    # crawler.login()
    # crawler.download_data()
    # crawler.process_data()
    # crawler.close()
    # self = crawler

    tr1 = pd.read_csv("../../../out/trade_republic.csv", sep=";")
    tr2 = pd.read_csv("../../../out/trade_republic2.csv", sep=";")

    # only in tr1 not in tr2
    df_diff1 = tr1.merge(tr2, indicator=True, how='outer').query('_merge == "left_only"').drop('_merge', axis=1)



