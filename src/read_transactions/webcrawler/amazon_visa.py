# -*- coding: utf-8 -*-
"""
:author: Tim Häberlein
:version: 2.0
:date: 22.10.2025
:organisation: TU Dresden, FZM

AmazonCrawler
-------------
Crawler für Amazon Visa (Zinia) – lädt Transaktionen im XLS-Format herunter.

Verwendung:
    from read_transactions.webcrawler.amazon import AmazonCrawler

    with AmazonCrawler(logging_level="DEBUG") as crawler:
        crawler.login()
        crawler.download_data()
        crawler.process_data()
        crawler.save_data()
"""
# -------- start import block ---------
import time
import pandas as pd
from selenium.common.exceptions import TimeoutException

from typing import Any

# Import der eigenen Klassen über relativen Pfad
# oder absoluten Pfad für den direkten Test
try:
    from .base import WebCrawler
except ImportError:
    from src.read_transactions.webcrawler.base import WebCrawler
# -------- /import block ---------


class AmazonVisaCrawler(WebCrawler):
    """
    Crawler für Amazon Visa (Zinia).

    Der Crawler automatisiert den Login auf `customer.amazon.zinia.de`,
    lädt alle Transaktionen im gewählten Datumsbereich herunter
    (XLS-Format) und konvertiert sie in ein einheitliches CSV-Format.

    Ablauf:
        1. Login mit Benutzername + 4-stelliger PIN
        2. Öffnen der Transaktionsseite
        3. Setzen des gewünschten Zeitraums
        4. Herunterladen der Excel-Datei
        5. Zusammenführen / Bereinigen der Daten

    Erfordert:
        - gültige Zugangsdaten in `config.yaml`
        - hinterlegte URLs für `login` und `transactions`
        - funktionierenden Selenium-WebDriver (Edge / Chrome / Firefox)

    Beispiel:
        ```bash
        readtx run amazon --start 01.01.2024 --end 31.03.2024 --log_level DEBUG
        ```

    Parameter
    ----------
    logfile : str, optional
        Pfad zu einer Logdatei. Wenn `None`, wird nur in die Konsole geloggt.
    output_path : str, optional
        Verzeichnis, in dem die verarbeiteten Daten gespeichert werden.
        Standard: ``out``.
    start_date : str | pandas.Timestamp | datetime.date, optional
        Startdatum für den Download (Format: ``dd.mm.yyyy``).
        Standard: heutiges Datum.
    end_date : str | pandas.Timestamp | datetime.date, optional
        Enddatum für den Download (Format: ``dd.mm.yyyy``).
        Standard: sechs Monate vor `start_date`.
    logging_level : str, optional
        Log-Level der Crawler-Instanz (z. B. "DEBUG", "INFO", "WARNING").
        Standard: ``INFO``.
    global_log_level : str, optional
        Globales Log-Level für das gesamte Paket (Standard: ``INFO``).
    browser : str, optional
        Zu verwendender Browser-Treiber (``edge``, ``chrome`` oder ``firefox``).
        Standard: ``edge``.
    headless : bool, optional
        Falls `True`, wird der Browser im Hintergrundmodus gestartet.
        Standard: ``False``.
    user_agent : str, optional
        Optionaler User-Agent-String für den Browser.

    Attribute:
        account_balance (str): Aktueller Kontostand nach erfolgreichem Login.
        data (pd.DataFrame): Aufbereitete Transaktionsdaten.
    """

    def __init__(self, logfile=None, *args, **kwargs):
        super().__init__(name="amazon_visa", logfile=logfile, *args, **kwargs)
        self._verified = False
        self._load_config()  # lädt credentials + urls aus config.yaml

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------
    def login(self) -> None:
        """Führt Login bei Amazon Visa (Zinia) aus."""
        # ----------------------------------------------------------
        # Subfunktionen für einzelne Login-Schritte
        # ----------------------------------------------------------
        def _enter_username():
            """Gibt den Benutzernamen ein und klickt auf 'Weiter'."""
            username_field = self.wait_for_element(
                by="css", selector="input[data-testid='login-email-email']", timeout=10
            )
            username_field.send_keys(self._credentials["user"])
            self.wait_clickable_and_click(
                by="css", selector="button[data-testid='login-email-links']", timeout=10
            )
            self._logger.debug("Benutzername eingegeben und Weiter-Button geklickt.")

        def _enter_pin():
            """Gibt die 4-stellige PIN ein und bestätigt den Login."""
            # PIN sicher als String behandeln (falls int übergeben wurde)
            password = self._credentials.get("password", "")
            if isinstance(password, (int, float)):
                password = str(int(password)).zfill(4)  # z. B. 42 -> "0042"
            else:
                password = str(password)
            for i, char in enumerate(password):
                pin_field = self.wait_for_element(
                    by="css",
                    selector=f"input[data-testid='password-module-inputs-gap-{i}']",
                    timeout=5,
                )
                pin_field.send_keys(char)
            self.wait_clickable_and_click(
                by="css", selector="button[data-testid='login-gaps-button']", timeout=5
            )
            self._logger.debug("PIN eingegeben und Login-Button geklickt.")

        def _check_login_success():
            """Prüft, ob der Login erfolgreich war."""
            elem = self.wait_for_element(
                by="xpath",
                selector = (
                    "//p[@data-testid='credit-chart-label-consumed']"
                    "/ancestor::header/following-sibling::h5[@data-testid='credit-chart-label-value']"
                ),
                timeout=5,
            )
            self.account_balance = elem.text
            self._logger.info(f"Login erfolgreich – Kontostand: {self.account_balance}")

        # ------------------------------------------------------------------
        # Hilfsfunktionen
        # ------------------------------------------------------------------
        def _handle_cookie_banner() -> None:
            """Versucht, das Cookie-Banner bei Amazon Visa (Zinia) zu schließen."""
            self._logger.debug("Prüfe auf Cookie-Banner...")

            # Erst versuchen, bekannte Standard-Buttons zu klicken
            closed = self.accept_cookies_if_present((
                "button[onclick='handleDecline()']",
                "button[data-testid='uc-deny-all-button']",
                "button[data-testid='uc-accept-all-button']",
                "button:contains('Ablehnen')",
                "button:contains('Decline')",
            ), timeout_each=3)

            if closed:
                self._logger.debug("Cookie-Banner über accept_cookies_if_present() geschlossen.")
                return

            # Fallback: falls spezifischer XPath benötigt wird
            try:
                self.wait_clickable_and_click(
                    by="xpath",
                    selector="//button[@onclick='handleDecline()']",
                    timeout=5,
                )
                self._logger.debug("Cookie-Banner über Fallback-XPath geschlossen.")
            except Exception:
                self._logger.debug("Kein Cookie-Banner gefunden oder bereits geschlossen.")

        # ----------------------------------------------------------

        # Haupt-Login-Ablauf
        super().login()
        self.driver.get(self._urls["login"])
        _handle_cookie_banner()

        # ----------------------------------------------------------
        # Schrittweise Ausführung mit Retry
        # ----------------------------------------------------------
        try:
            self._retry_func(_enter_username, max_retries=2, wait_seconds=0.5)
            self._retry_func(_enter_pin, max_retries=2, wait_seconds=0.5)
            self._retry_func(_check_login_success, max_retries=2, wait_seconds=0.5)
        except Exception:
            self._logger.error("Login-Vorgang fehlgeschlagen.", exc_info=True)
            raise


    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------
    def download_data(self) -> None:
        """Navigiert zur Transaktionsseite und lädt XLS-Datei herunter."""
        # ----------------------------------------------------------
        # Subfunktionen für Download-Ablauf
        # ----------------------------------------------------------
        def _open_filter():
            """Öffnet das Filter-Menü."""
            self.wait_clickable_and_click(
                by="xpath",
                selector="//span[contains(text(),'Filter') or contains(@class,'Filter')]",
                timeout=10,
            )
            self._logger.debug("Filter-Menü geöffnet.")

        def _select_custom_date_range():
            """Wählt benutzerdefinierten Datumsbereich aus."""
            ratio = self.wait_for_element(
                by="xpath",
                selector=(
                    "//p[@data-testid='radio-button-helper-message'"
                    " and normalize-space()='Zeitraum auswählen']"
                    "/preceding::input[@type='radio'][1]"
                ),
                timeout=10,
            )
            self.click_js(ratio)
            self._logger.debug("Benutzerdefinierter Zeitraum ausgewählt.")

        def _enter_dates():
            """Trägt Start- und Enddatum ein (aktiviert DatePicker bei Bedarf)."""
            from selenium.webdriver.common.keys import Keys

            def fill_date(label_text, date_obj):
                # Öffnet DatePicker ("Von" oder "Bis")
                picker = self.wait_for_element(
                    "xpath",
                    f"//div[@data-testid='input-date-picker-component' and .//label[p[normalize-space()='{label_text}']]]"
                    "//div[@data-testid='input-date-picker-value-component']",
                    10,
                )
                self.click_js(picker)
                self._logger.debug(f"DatePicker '{label_text}' aktiviert.")

                # Inputs erscheinen nach Klick
                for ph, order, val in zip(
                        ("DD", "MM", "YYYY"), ("3", "2", "1"),
                        (date_obj.strftime("%d"), date_obj.strftime("%m"), date_obj.strftime("%Y")),
                ):
                    field = self.wait_for_element(
                        "xpath",
                        f"//input[@type='number' and (@placeholder='{ph}' or @data-orderid='{order}')]",
                        2,
                    )
                    field.send_keys(val)

                self._logger.debug(f"{label_text}-Datum gesetzt: {date_obj:%d.%m.%Y}")

            self.driver.maximize_window()
            fill_date("Von", self.end_date)
            fill_date("Bis", self.start_date)
            self.driver.minimize_window()

        def _apply_filter():
                """Klickt auf Anwenden im Filter."""
                self.wait_clickable_and_click(by="css",
                                              selector="button[data-testid='filter-modal-apply-button']",
                                              timeout=30)
                # self.click_js(filter_btn)
                self._logger.debug("Filter angewendet.")

        def _trigger_download():
            """Startet den Excel-Download."""
            self.wait_clickable_and_click(
                by="xpath",
                selector="//a[contains(@data-testid,'transactions-all-download')]",
                timeout=10)
            self._logger.debug("Download-Button geöffnet.")

            self.wait_clickable_and_click(
                by="xpath",
                selector="//button[contains(.,'Excel') or contains(.,'XLS')]",
                timeout=5,
            )
            self._logger.info("Excel-Download gestartet...")

        def _show_old_transactions():
            """Zeigt ggf. ältere Umsätze an."""
            try:
                self.wait_clickable_and_click(
                    by="xpath",
                    selector="//button[.//span[normalize-space()='Umsätze anzeigen']]",
                    timeout=10,
                )
                self._logger.debug("Ältere Umsätze angezeigt.")
            except TimeoutException:
                self._logger.debug("Keine älteren Umsätze vorhanden.")


        # ----------------------------------------------------------
        # Haupt-Download-Ablauf
        # ----------------------------------------------------------
        def _download_helper():
            """Hilfsfunktion für den Download mit Verifizierung."""
            driver.get(urls["transactions"])
            _open_filter()
            _select_custom_date_range()
            _enter_dates()
            _apply_filter()
            _trigger_download()
            _show_old_transactions()
            self._verify_identity()

        super().download_data()
        driver = self.driver
        urls = self._urls

        self._logger.debug("Öffne Transaktionsseite...")
        try:
            self._retry_func(_download_helper, max_retries=2, wait_seconds=0.5)
            self._wait_for_new_file(include_temp=False)
        except Exception:
            self._logger.error("Fehler im Download-Vorgang.", exc_info=True)


    # ------------------------------------------------------------------
    # Verarbeitung
    # ------------------------------------------------------------------
    def process_data(self) -> None:
        """Verarbeitet heruntergeladene XLS-Daten."""
        super().process_data(sep=',')
        merged_df = pd.DataFrame()

        try:
            if isinstance(self.data, dict):
                for key, df in self.data.items():
                    merged_df = pd.concat([merged_df, df], ignore_index=True)
                self.data = merged_df
            else:
                merged_df = self.data

            # Kopfzeilen-Bereinigung
            merged_df = merged_df.iloc[10:].rename(columns=merged_df.iloc[9]).dropna(subset=["Datum"])
            self.data = merged_df[["Datum", "Betrag", "Beschreibung", "Punkte", "Karte"]]
            self._logger.info(f"{len(self.data)} Transaktionen verarbeitet.")
        except Exception:
            self._logger.error("Fehler bei der Datenverarbeitung", exc_info=True)

    # ------------------------------------------------------------------
    # Hilfsfunktionen
    # ------------------------------------------------------------------
    def _verify_identity(self) -> None:
        """Führt den gesamten OTP-/2FA-Verifizierungsprozess durch (ohne Rekursion)."""
        from selenium.common.exceptions import TimeoutException, ElementNotInteractableException

        def _request_new_code():
            """Fordert einen neuen Code an (Erneut anfordern + Erneut versuchen)."""
            try:
                self.wait_clickable_and_click(
                    "xpath",
                    "//a[@data-testid='challenge-helper-composer' "
                    "and .//span[normalize-space()='Erneut anfordern']]",
                    5,
                )
                self._logger.info("Neuen Code angefordert ('Erneut anfordern').")
            except TimeoutException:
                self._logger.debug("Kein Link 'Erneut anfordern' gefunden.")

            try:
                self.wait_clickable_and_click(
                    "xpath",
                    "//button[@data-testid='challenge-message-fail-button' "
                    "and .//span[normalize-space()='Erneut versuchen']]",
                    5,
                )
                self._logger.info("Erneut versuchen geklickt.")
            except TimeoutException:
                self._logger.debug("Kein Button 'Erneut versuchen' gefunden.")

        def _enter_otp():
            """Fragt den Code ab und trägt ihn ein."""
            otp_field = self.wait_for_element(
                "xpath",
                "//input[@data-testid='challenge-otp-input' and @placeholder='Bestätigungscode']",
                10,
            )
            code = input("🔐 Bitte 4-stelligen Bestätigungscode eingeben (oder 'retry' für neuen Code): ").strip()
            if code.lower() == "retry" or len(code) != 4:
                self._logger.info("Code ungültig oder 'retry' gewählt → neuen Code anfordern.")
                _request_new_code()
                return False  # erneut versuchen
            otp_field.send_keys(code)
            self._logger.debug("Bestätigungscode eingegeben.")
            return True

        def _submit_code():
            """Klickt auf 'Weiter'."""
            try:
                self.wait_clickable_and_click(
                    "xpath",
                    "//button[@data-testid='challenge-sms-otp-button' and .//span[normalize-space()='Weiter']]",
                    10,
                )
                self._logger.debug("Button 'Weiter' geklickt.")
                return True
            except TimeoutException:
                self._logger.debug("Kein 'Weiter'-Button gefunden.")
                return False

        def _confirm():
            """Klickt abschließend auf 'Bestätigen', falls vorhanden."""
            try:
                # suche nach einem btn, falls code eingabe nicht erfolgreich
                self.wait_clickable_and_click(
                    by="xpath",
                    selector=(
                        "//button[@data-testid='challenge-message-fail-button'"
                        "and .//span[normalize-space()='Erneut versuchen']]"),
                    timeout=5)
                return False
            except TimeoutException:
                # btn war nicht da -> weiter
                pass
            try:
                self.wait_clickable_and_click(
                    "xpath",
                    "//button[.//span[normalize-space()='Bestätigen']]",
                    10,
                )
                self._logger.info("Identitätsverifizierung abgeschlossen ('Bestätigen' geklickt).")
                return True
            except TimeoutException:
                self._logger.debug("Kein 'Bestätigen'-Button gefunden – Verifizierung evtl. bereits erledigt.")
                return False
        # ------------------------------------------------------------
        # Hauptschleife
        # ------------------------------------------------------------
        try:
            # _request_new_code()
            for attempt in range(3):  # max. 3 Versuche
                try:
                    if not self.wait_for_element(
                            "xpath",
                            "//input[@data-testid='challenge-otp-input' and @placeholder='Bestätigungscode']",
                            timeout=5,
                    ):
                        self._logger.debug("Kein OTP-Feld sichtbar – keine Verifizierung erforderlich.")
                        break

                    self._logger.info(f"Starte OTP-Verifikation (Versuch {attempt + 1}/3)...")
                    if not _enter_otp():
                        continue  # ungültiger Code oder 'retry' gedrückt → nächste Runde
                    if _submit_code():
                        if not _confirm():
                            self._logger.info('Verifizierung fehlgeschlagen, erneut starten...')
                            continue
                        else:
                            break
                except ElementNotInteractableException:
                    self._logger.debug("OTP-Feld nicht interaktiv – übersprungen.")
                    break
            else:
                self._logger.warning("OTP-Verifikation nach 3 Versuchen abgebrochen.")
        except Exception as e:
            self._logger.error(f"Fehler bei der OTP-Verifizierung: {e}", exc_info=True)





# ------------------------------------------------------------------
# Direkter Test
# ------------------------------------------------------------------
if __name__ == "__main__":
    with AmazonVisaCrawler(logging_level="DEBUG") as crawler:
        # crawler._wait_for_manual_exit()
        crawler.login()
        # crawler._wait_for_manual_exit("Login abgeschlossen - browser bleibt offen")
        crawler.download_data()
        # crawler._wait_for_manual_exit("Daten-Download abgeschlossen - browser bleibt offen")
        crawler.process_data()
        crawler.save_data()

    # crawler = AmazonVisaCrawler(logging_level="DEBUG")
    # crawler.login()
    # crawler.close()

    # driver = crawler.driver
    # urls = crawler._urls
    #
    # driver.get(urls["transactions"])
    #
    # crawler.wait_clickable_and_click(
    #     by="xpath",
    #     selector="//span[contains(text(),'Filter') or contains(@class,'Filter')]",
    #     timeout=5,
    # )
    #
    # radio = crawler.wait_for_element(
    #     by="xpath",
    #     selector=(
    #         "//p[@data-testid='radio-button-helper-message' and "
    #         "normalize-space()='Zeitraum auswählen']"
    #         "/ancestor::div[contains(@class, 'sc-IqJVf')][1]"
    #         "//input[@type='radio']"
    #     ),
    #     timeout=5,
    # )
    # crawler.driver.execute_script("arguments[0].click();", radio)
    #
    # crawler.wait_clickable_and_click(
    #     by="xpath",
    #     selector=(
    #         "//div[@data-testid='input-date-picker-component' "
    #         "and .//label[p[normalize-space()='Von']]]"
    #         "//div[@data-testid='input-date-picker-value-component']"
    #     ),
    #     timeout=2,)
    #
    #
    # start_day = crawler.wait_for_element(
    #     by="xpath",
    #     selector="//input[@type='number' and (@placeholder='DD' or @data-orderid='3')]",
    #     timeout=2,
    # )
    # start_month = crawler.wait_for_element("xpath", "//input[@data-orderid='2']", timeout=2)
    # start_year = crawler.wait_for_element("xpath", "//input[@data-orderid='1']", timeout=2)
    # start_day.send_keys(crawler.end_date.strftime("%d"))
    # start_month.send_keys(crawler.end_date.strftime("%m"))
    # start_year.send_keys(crawler.end_date.strftime("%Y"))
    #
    # crawler.wait_clickable_and_click(
    #     by="css",
    #     selector="button[data-testid='filter-modal-apply-button']",
    #     timeout=5,
    # )
    #
    # crawler.wait_clickable_and_click(
    #     by="xpath",
    #     selector="//a[contains(@data-testid,'transactions-all-download')]",
    #     timeout=5,
    # )
    #
    # crawler.wait_clickable_and_click(
    #     by="xpath",
    #     selector="//button[contains(.,'Excel') or contains(.,'XLS')]",
    #     timeout=5,
    # )



    # def _open_filter():
    #     """Öffnet das Filter-Menü."""
    #     crawler.wait_clickable_and_click(
    #         by="xpath",
    #         selector="//span[contains(text(),'Filter') or contains(@class,'Filter')]",
    #         timeout=2,
    #     )
    #     crawler._logger.debug("Filter-Menü geöffnet.")

    # def _select_custom_date_range():
    #     """Wählt benutzerdefinierten Datumsbereich aus."""
    #     ratio = crawler.wait_for_element(
    #         by="xpath",
    #         selector=(
    #             "//p[@data-testid='radio-button-helper-message'"
    #             " and normalize-space()='Zeitraum auswählen']"
    #             "/preceding::input[@type='radio'][1]"
    #         ),
    #         timeout=2,
    #     )
    #     crawler.click_js(ratio)
    #     crawler._logger.debug("Benutzerdefinierter Zeitraum ausgewählt.")

    # def _apply_filter():
    #     """Klickt auf Anwenden im Filter."""
    #     crawler.wait_clickable_and_click(
    #         by="css",
    #         selector="button[data-testid='filter-modal-apply-button']",
    #         timeout=2,
    #     )
    #     crawler._logger.debug("Filter angewendet.")

    # def _trigger_download():
    #     """Startet den Excel-Download."""
    #     crawler.wait_clickable_and_click(
    #         by="xpath",
    #         selector="//a[contains(@data-testid,'transactions-all-download')]",
    #         timeout=2,
    #     )
    #     crawler._logger.debug("Download-Button geöffnet.")
    #
    #     crawler.wait_clickable_and_click(
    #         by="xpath",
    #         selector="//button[contains(.,'Excel') or contains(.,'XLS')]",
    #         timeout=2,
    #     )
    #     crawler._logger.info("Excel-Download gestartet.")





        # time.sleep(0.5)  # kleine Pause vor dem Download

        # download button muss gar nicht erneut geklickt werden
        # downloadbtn = crawler.wait_for_element(
        #     by="xpath",
        #     selector="//button[.//span[contains(normalize-space(),'XLS')]]",
        #     timeout=15)
        # crawler.click_js(downloadbtn)
        # crawler._logger.info("Excel-Download gestartet nach Verifizierung.")