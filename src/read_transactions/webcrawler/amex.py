# -*- coding: utf-8 -*-
"""
:author: Tim Häberlein
:version: 2.0
:date: 22.10.2025
:organisation: TU Dresden, FZM

AmexCrawler
-----------
Crawler für American Express – lädt Transaktionen (CSV) im gewählten Zeitraum herunter
und führt sie in ein einheitliches Format über.

Der Crawler orientiert sich an der Architektur der `ArivaCrawler`- und `AmazonVisaCrawler`-Klassen.
Er nutzt Selenium zur Browsersteuerung, greift auf Anmeldedaten aus der zentralen `config.yaml` zu
und setzt auf die generische Basisklasse `WebCrawler`, die Standardfunktionen wie Logging,
Fehlerbehandlung, Warte- und Retry-Mechanismen, Datendownload und Dateiverarbeitung bereitstellt.
"""

# -------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------

from __future__ import annotations
import time
import pandas as pd
from typing import Any
from selenium.common.exceptions import TimeoutException, ElementNotInteractableException

from read_transactions.webcrawler import WebCrawler
# -------------------------------------------------------------------

# AmexCrawler Klasse
# -------------------------------------------------------------------
class AmexCrawler(WebCrawler):
    """American Express TransaktionsCrawler

    Diese Klasse automatisiert den Login, Download und die Aufbereitung von
    Transaktionsdaten der American Express Webseite (https://www.americanexpress.com).

    Sie erbt von der generischen Basisklasse `WebCrawler`, welche die Standardmechanismen
    für Selenium-gestützte Webautomatisierung kapselt.

    Hauptfunktionen:
        - **Login:**
            Führt den vollständigen Loginprozess aus (Cookies → Benutzername/Passwort → OTP-Verifikation).
            Erkennt Zwei-Faktor-Authentifizierungen automatisch und fordert ggf. einen Bestätigungscode an.

        - **Download:**
            Öffnet die Transaktionsübersicht, setzt den gewünschten Datumsbereich,
            lädt alle sichtbaren Datensätze (über „Mehr anzeigen“) und startet den CSV-Export.

        - **Processing:**
            Vereinheitlicht und bereinigt heruntergeladene CSV-Dateien:
            - Zusammenführen mehrerer Dateien zu einem DataFrame.
            - Konvertiert Datum „dd/mm/yyyy“ → „dd.mm.yyyy“.
            - Ersetzt Komma in Beträgen (z. B. „1,23“ → „1.23“).
            - Vereinheitlicht Spaltennamen zu `Datum`, `Betrag`, `Beschreibung`.

        - **OTP/2FA:**
            Bietet interaktive Eingabe des 4-stelligen Sicherheitscodes, mit Optionen
            zum erneuten Anfordern oder Wiederholen bei Falscheingabe.

    Erwartete Konfigurationseinträge in `config.yaml`:
        ```yaml
        credentials:
          amex:
            user: <AMEX Benutzername>
            password: <AMEX Passwort>

        urls:
          amex:
            login: https://www.americanexpress.com/de-de/account/login
            transactions: https://global.americanexpress.com/activity/search
            transactions_recent: https://global.americanexpress.com/activity/recent
        ```

    Rückgabewerte und Attribute:
        - **self.data:** Enthält den verarbeiteten pandas.DataFrame nach `process_data()`.
        - **self._credentials:** Enthält die aus der config geladenen Zugangsdaten.
        - **self._urls:** Beinhaltet alle relevanten Ziel-URLs.

    Abhängigkeiten:
        - Selenium (WebDriver, By, Keys)
        - pandas
        - yaml (über Konfigurationslade-Mechanismus)
        - logging (über `logger.py`)

    Beispiel:
        ```python
        from read_transactions.webcrawler.amex import AmexCrawler

        with AmexCrawler(logging_level="DEBUG") as crawler:
            crawler.login()
            crawler.download_data()
            crawler.process_data()
            crawler.save_data()
        ```
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(name="amex", *args, **kwargs)
        self._verified: bool = False
        self._load_config()

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------
    def login(self) -> None:
        """Führt den Login bei American Express aus (User + Passwort + ggf. OTP)."""
        super().login()
        self.driver.get(self._urls["login"])
        self._handle_cookie_banner()

        try:
            self._retry_func(self._enter_username_password, max_retries=2, wait_seconds=0.5)
        except Exception:
            self._logger.error("Eingabe Benutzername/Passwort fehlgeschlagen.", exc_info=True)
            raise

        self._verify_identity()
        try:
            self._retry_func(self._wait_for_account_balance, max_retries=3, wait_seconds=1.0)
            self._logger.info(f"Login erfolgreich. Aktueller Kontostand: {self.account_balance}")
        except Exception:
            self._logger.error('Login fehlgeschlagen - Kontostand nicht gefunden.', exc_info=True)
            raise

        self._logger.info("Login bei American Express abgeschlossen.")

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------
    def download_data(self) -> None:
        """Öffnet die Transaktionsseite, setzt den Datumsbereich und startet den CSV-Download."""
        super().download_data()
        self.driver.get(self._urls["transactions"])
        try:
            self._fill_dates_and_search()
            # self._load_all_transactions()
            self._select_all_and_download()
            self._wait_for_new_file(include_temp=False)
        except Exception:
            self._logger.error("Fehler im Download-Vorgang (Amex).", exc_info=True)
            raise

    # ------------------------------------------------------------------
    # Verarbeitung
    # ------------------------------------------------------------------
    def process_data(self, *arg, **kwargs) -> None:
        """Führt die geladenen CSV-Dateien zusammen und harmonisiert die Spalten."""
        super().process_data(*args, **kwargs)
        try:
            merged = self.data
            merged = self._normalize_dataframe(merged)
            merged["Betrag"] = merged["Betrag"] * -1  # Amex zeigt Ausgaben als positiv an
            self.data = merged
            self._logger.info(f"{len(self.data)} Amex-Transaktionen verarbeitet.")
        except Exception:
            self._logger.error("Fehler beim Zusammenführen/Transformieren der Amex-Daten.", exc_info=True)

    # ------------------------------------------------------------------
    # Private Helper-Methoden (Login, Download, Verarbeitung)
    # ------------------------------------------------------------------

    def _enter_username_password(self) -> None:
        user_el = self.wait_for_element(by="id", selector="eliloUserID", timeout=10)
        user_el.clear()
        user_el.send_keys(self._credentials["user"])
        pw_el = self.wait_for_element(by="id", selector="eliloPassword", timeout=10)
        pw_el.clear()
        pw_el.send_keys(self._credentials["password"])
        pw_el.submit()
        self._logger.debug("Login-Formular abgeschickt (Benutzername + Passwort).")

    def _handle_cookie_banner(self) -> None:
        try:
            self.wait_clickable_and_click(
                by="css",
                selector="button[data-testid='granular-banner-button-decline-all']",
                timeout=5,
            )
            self._logger.debug("Cookie-Banner: 'Ablehnen' geklickt.")
        except Exception:
            self._logger.debug("Kein Cookie-Banner sichtbar – weiter.")

    def _wait_for_account_balance(self) -> None:
        el = self.wait_for_element(
            by="xpath",
            selector="//h2[normalize-space()='Aktueller Kontostand']/ancestor::div[contains(@class, 'header-container')]/following-sibling::div//h4",
            timeout=20,
        )
        # raw = el.text.strip().replace(".", "")
        self.account_balance = el.text

    def _fill_dates_and_search(self) -> None:
        """Befüllt die AMEX-Datumsfelder (Start/End date) kompakt mit Tag, Monat, Jahr."""
        try:
            for label, date_obj in [("End date", self.start_date), ("Start date", self.end_date)]:
                for part, value in zip(["Day", "Month", "Year"],
                                       [f"{date_obj.day:02d}", f"{date_obj.month:02d}", str(date_obj.year)]):
                    field = self.wait_for_element(
                        by="xpath",
                        selector=f"//div[@role='group' and @aria-label='{label}']//input[@aria-label='{part}']",
                        timeout=15,
                    )
                    field.clear()
                    field.send_keys(value)
                self._logger.debug(f"📅 {label}: {date_obj.strftime('%d/%m/%Y')}")
            self.wait_clickable_and_click(
                by="xpath",
                selector="//button[@type='button' and normalize-space()='Suchen']",
                timeout=5)
        except Exception:
            self._logger.error("Fehler beim Befüllen der Datumsfelder (Start/End).", exc_info=True)

    def _load_all_transactions(self) -> None:
        end_reached = False
        while not end_reached:
            try:
                count_el = self.wait_for_element(by="css", selector="div[data-module-name='axp-activity-count']", timeout=10)
                txt = (count_el.text or "").strip()
                parts = [p.strip() for p in txt.split("von")]
                if len(parts) == 2:
                    current = int(parts[0].split()[0])
                    total = int(parts[1].split()[0])
                    if current >= total:
                        end_reached = True
                    else:
                        self.wait_clickable_and_click(by="xpath", selector="//button[normalize-space()='Mehr anzeigen']", timeout=10)
                        time.sleep(1.0)
                else:
                    self.wait_clickable_and_click(by="xpath", selector="//button[normalize-space()='Mehr anzeigen']", timeout=5)
                    time.sleep(1.0)
            except Exception:
                end_reached = True

    def _select_all_and_download(self) -> None:
        # self.driver.execute_script("window.scrollTo(0, 0);")
        # time.sleep(0.5)
        try:
            btn_all = self.wait_for_element(
                by="xpath",
                selector="//button[@aria-label='Filter transactions by All Transactions' or normalize-space()='Alle Transaktionen']",
                timeout=10)
            self.click_js(btn_all)
        except TimeoutException:
            self._logger.debug("Checkbox 'Alle auswählen' nicht gefunden.")
        self.wait_clickable_and_click(
            by="xpath",
            selector="//button[@data-testid='icon-button' and .//span[normalize-space()='Herunterladen']]",
            timeout=10)
        try:
            radio_excel = self.wait_for_element(
                by="xpath",
                selector="//input[@id='axp-activity-download-body-selection-options-type_excel']",
                timeout=5,
            )
            self.click_js(radio_excel)
            self._logger.debug("📊 Radiobutton 'Excel' per JS-Klick aktiviert.")
        except TimeoutException:
            self._logger.debug("Kein 'Excel'-Radiobutton gefunden.")
            pass
        # try:
        #     self.wait_clickable_and_click(by="xpath", selector="//label[@for='axp-activity-download-body-checkbox-options-includeAll']", timeout=5)
        # except TimeoutException:
        #     pass
        self.wait_clickable_and_click(
            by="xpath",
            selector="//button[@data-test-id='axp-activity-download-footer-download-confirm' and normalize-space()='Herunterladen']",
            timeout=10)

    # ------------------------------------------------------------------
    # OTP / 2FA
    # ------------------------------------------------------------------
    def _verify_identity(self) -> None:
        def _otp_field_present() -> bool:
            try:
                self.wait_for_element(
                    by="xpath",
                    selector= "//input[@data-testid='question-value' and @id='question-value']",
                    timeout=10)
                return True
            except TimeoutException:
                return False

        def _request_new_code() -> None:
            try:
                self.wait_clickable_and_click(
                    by="xpath",
                    selector="//button[@data-testid='resend-button' and normalize-space()='Verifizierungscode erneut senden']",
                    timeout=5)
                self._logger.info("Neuen Code angefordert.")
            except TimeoutException:
                pass

        def _request_email_code() -> None:
            try:
                self.wait_clickable_and_click(
                    by="xpath",
                    selector="//button[@data-testid='change-method-button' and normalize-space()='Verifizierungsmethode ändern']",
                    timeout=10
                )
                self.wait_clickable_and_click(
                    by="xpath",
                    selector="//button[@data-testid='option-button' and .//h3[normalize-space()='Einmaliger Verifizierungscode (E-Mail)']]",
                    timeout=10)
                self._logger.info("Code per E-Mail angefordert.")
            except TimeoutException:
                pass

        def _enter_and_submit_code() -> bool:
            try:
                otp_el = self.wait_for_element(
                    by="xpath",
                    selector="//input[@data-testid='question-value' and @id='question-value']",
                    timeout=10)
                code = input("🔐 Bitte 6-stelligen SMS Bestätigungscode eingeben ('retry'-erneut senden, 'email'-für e-mail code senden): ").strip()
                if code.lower() == "retry":
                    _request_new_code()
                    return False
                elif code.lower() == "email":
                    _request_email_code()
                    return False
                elif len(code) != 6:
                    self._logger.warning("Ungültiger Code eingegeben.")
                    return False
                otp_el.send_keys(code)
                self.wait_clickable_and_click(
                    by="xpath",
                    selector="//button[@data-testid='continue-button' and normalize-space()='Verifizieren']",
                    timeout=10)
                # weiter button nach verifizierung
                self.wait_clickable_and_click(
                    by="xpath",
                    selector="//button[@type='submit' and normalize-space()='Weiter']",
                    timeout=10)
                return True
            except TimeoutException:
                return False

        def _wait_for_push_confirmation(timeout: int = 120) -> bool:
            """Wartet darauf, dass die Push-Mitteilung bestätigt oder abläuft."""
            try:
                el = self.wait_for_element(
                    by="xpath",
                    selector="//h2[normalize-space()='Wir haben eine Push-Mitteilung an Ihr Gerät gesendet:']",
                    timeout=10,
                )
                if el:
                    try:
                        self._logger.info("📲 Push-Verifizierung erkannt – warte auf Bestätigung in der App...")
                        _get_push_details()
                        # kurze Wartezeit, damit der Nutzer bestätigen kann
                        self._wait_for_condition(lambda: not _is_push_message_visible(), timeout)
                        self._logger.info("✅ Push-Verifizierung abgeschlossen.")
                        # weiter button nach verifizierung
                        self.wait_clickable_and_click(
                            by="xpath",
                            selector="//button[@type='submit' and normalize-space()='Weiter']",
                            timeout=10)
                        return True
                    except Exception:
                        self._logger.warning("⏳ Push-Verifizierung nicht abgeschlossen (Zeitüberschreitung).")
                        return False
            except TimeoutException:
                self._logger.debug("Keine Push-Mitteilung angezeigt.")
            return False

        def _is_push_message_visible() -> bool:
            try:
                self.wait_for_element(
                    by="xpath",
                    selector="//h2[normalize-space()='Wir haben eine Push-Mitteilung an Ihr Gerät gesendet:']",
                    timeout=5,
                )
                return True
            except TimeoutException:
                return False

        def _get_push_details() -> dict[str, str]:
            """Liest Nickname, Gerätedetails und Zeit der Push-Verifikation aus."""
            details = {}
            try:
                details["nickname"] = self.wait_for_element(
                    by="xpath",
                    selector="//h5[normalize-space()='Nickname Gerät:']/following-sibling::p",
                    timeout=5,
                ).text.strip()

                details["device_details"] = self.wait_for_element(
                    by="xpath",
                    selector="//h5[normalize-space()='Gerätedetails:']/following-sibling::p",
                    timeout=5,
                ).text.strip()

                details["sent_time"] = self.wait_for_element(
                    by="xpath",
                    selector="//h5[normalize-space()='Gesendet um:']/following-sibling::p",
                    timeout=5,
                ).text.strip()

                self._logger.info(
                    f"📱 Push-Gerät: {details['nickname']} | {details['device_details']} | Gesendet um {details['sent_time']}"
                )
            except Exception:
                self._logger.debug("Push-Verifikationsdetails konnten nicht ausgelesen werden.", exc_info=True)
            return details

        try:
            # unterscheidung ob sms/email ausgewählt werden muss oder es eine push nachricht auf das telefon gibt
            # check if push
            if _wait_for_push_confirmation(timeout=120):
                return
            self.wait_clickable_and_click(
                by="xpath",
                selector="//button[@data-testid='option-button' and .//h3[normalize-space()='Einmaliger Verifizierungscode (SMS)']]",
                timeout=10
            )
            if not _otp_field_present():
                return
            for attempt in range(3):
                self._logger.info(f"Starte OTP-Verifikation (Versuch {attempt+1}/3)…")
                if _enter_and_submit_code():
                    break
            else:
                self._logger.warning("OTP-Verifikation nach 3 Versuchen abgebrochen.")
        except Exception:
            self._logger.error("Fehler während der OTP-Verifizierung (Amex).", exc_info=True)



if __name__ == "__main__":
    print("AmexCrawler Testlauf")
    # with AmexCrawler(logging_level="DEBUG") as crawler:
    #     crawler.login()
    #     # crawler._wait_for_manual_exit()
    #     crawler.download_data()
    #     # crawler.wait_clickable_and_click('download')
    #     crawler.process_data()
    #     crawler.save_data()

    crawler = AmexCrawler(logging_level="DEBUG")
    crawler.login()
    crawler.download_data()
    crawler.process_data()
    crawler.save_data()
    crawler.close()


    # crawler.driver.get(crawler._urls["login"])
    # crawler._handle_cookie_banner()
    # crawler._enter_username_password()
    # crawler._verify_identity()
    # crawler._wait_for_account_balance()
    # crawler.driver.get(crawler._urls['transactions'])
    #
    # crawler._fill_dates_and_search()
