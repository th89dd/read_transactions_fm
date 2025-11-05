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
from xmlrpc.client import DateTime

import pandas as pd
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException

from typing import Any, List, Tuple

# Import der eigenen Klassen über relativen Pfad
from read_transactions.webcrawler import WebCrawler
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
    save_amazon_order : bool, optional
        Falls `True`, werden die detaillierten Umsatzinformationen zusätzlich von Amazon gespeichert
        Achtung: nur, wenn details ebenfalls `True` ist.
        Standard: ``True``.
    details : bool, optional
        Falls `True`, werden detaillierte Umsatzinformationen zusätzlich von Amazon abgerufen.
        Diese werden anhand von Betrag und Datum den Umsätzen zugeordnet.
        Standard: ``True``.
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

    def __init__(self, save_amazon_order: bool = True, *args, **kwargs):
        super().__init__(name="amazon_visa", *args, **kwargs)
        self._verified = False
        self._load_config()  # lädt credentials + urls aus config.yaml
        self._save_amazon_order = save_amazon_order

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

        def _enter_dates(start_date: pd.Timestamp, end_date: pd.Timestamp):
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
            fill_date("Von", start_date)
            fill_date("Bis", end_date)
            time.sleep(0.5)  # kleine Pause, damit Eingaben registriert werden
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
                selector="//button[contains(.,'XLS herunterladen')]",
                timeout=5,
            )
            self._logger.debug("Excel-Download-Buttn gedrückt...")

        def _show_old_transactions() -> bool:
            """Zeigt ggf. ältere Umsätze an."""
            if self._verified:
                return False  # bereits bestätigt
            elif (pd.Timestamp.now() - start) >= pd.Timedelta(days=90):
                # Zeitraum > 90 Tage, ältere Umsätze anzeigen muss wahrscheinlich bestätigt werden
                timeout = 20
            else:
                timeout = 5
            try:
                sel = "//button[.//span[normalize-space()='Umsätze anzeigen']]"
                self.wait_clickable_and_click("xpath", sel, timeout=timeout)
                self._logger.debug("Ältere Umsätze anzeigen geklickt.")
                return True
            except StaleElementReferenceException:
                # btn war nicht mehr klickbar -> evtl. Seite neu geladen
                time.sleep(1)  # kleine Pause, damit btn stabil ist
                self.wait_clickable_and_click("xpath", sel, timeout=5)
                return True
            except TimeoutException:
                self._logger.debug("Keine älteren Umsätze vorhanden.")
                return False

        def _split_date_ranges(
                start_date: pd.Timestamp,
                end_date: pd.Timestamp,
                max_months: int = 2) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
            """
            Teilt den Zeitraum [start, end] in Intervalle zu jeweils `months` Monaten (inklusive).
            Rückgabe: Liste von (interval_start, interval_end) als pd.Timestamp.
            """
            intervals: List[Tuple[pd.Timestamp, pd.Timestamp]] = []
            start_ts = start_date
            end_ts = end_date

            current = start_ts
            while current <= end_ts:
                next_start = current + pd.DateOffset(months=max_months)
                interval_end = min(end_ts, next_start - pd.Timedelta(days=1))
                intervals.append((current, interval_end))
                current = next_start

            return intervals


        # ----------------------------------------------------------
        # Haupt-Download-Ablauf
        # ----------------------------------------------------------
        def _download_helper(start, end):
            """Hilfsfunktion für den Download mit Verifizierung."""
            driver.get(url)
            _open_filter()
            _select_custom_date_range()
            _enter_dates(start, end)
            _apply_filter()
            _trigger_download()
            if _show_old_transactions():
                self._verify_identity()

        super().download_data()
        driver = self.driver
        url = self._urls["transactions"]

        # self.__show_old_transactions_confirmed = False  # Flag, ob alte Transaktionen anzeigen bereits bestätigt wurde

        # da downloads nicht immer vollstädnig sind, unterteilung in 2 monate intervalle
        intervals = _split_date_ranges(self.end_date, self.start_date, max_months=2)
        self._logger.info(f"Starte Download in {len(intervals)} Intervallen...")

        self._logger.debug("Öffne Transaktionsseite...")
        for idx, (start, end) in enumerate(intervals):
            self._logger.info(f"Download-Intervall: {start:%d.%m.%Y} bis {end:%d.%m.%Y}")
            try:
                # self._retry_func(_download_helper, max_retries=2, wait_seconds=2, args=(start, end))
                _download_helper(start, end)

                if idx < len(intervals) - 1:
                    self._wait_for_new_file(include_temp=True)
                else:
                    self._wait_for_new_file(include_temp=False)
            except Exception:
                self._logger.error("Fehler im Download-Vorgang.", exc_info=True)
                time.sleep(2)
                continue

        # try:
        #     self._retry_func(_download_helper, max_retries=2, wait_seconds=0.5, args=(start, end))
        #     self._wait_for_new_file(include_temp=False)
        # except Exception:
        #     self._logger.error("Fehler im Download-Vorgang.", exc_info=True)


    # ------------------------------------------------------------------
    # Verarbeitung
    # ------------------------------------------------------------------
    def process_data(self, *args, **kwargs) -> None:
        """Verarbeitet heruntergeladene XLS-Daten."""

        super().process_data(sep=',', *args, **kwargs)  # process der basis klasse aufrufen (log + read files + preprocess)

        # daten nach dem preprocessing normalisieren
        self.data = self._normalize_dataframe(self.data)
        # daten nach datum sortieren
        self.data.sort_values(by="Datum", ascending=False, inplace=True)
        self._logger.info(f"{len(self.data)} Transaktionen verarbeitet.")
        try:
            if self.with_details:
                self._logger.info("Starte Abruf detaillierter Umsatzinformationen...")
                self._fetch_transaction_details(key_columns=["Betrag", "Datum"])
                self._logger.info("Detaillierte Umsatzinformationen abgerufen.")

        except Exception:
            self._logger.error("Fehler bei der Datenverarbeitung", exc_info=True)

    def preprocess_data(self,key: str, df: pd.DataFrame) -> pd.DataFrame:
        """Überschreibt die Clean-Funktion der Basis-Klasse."""
        def _change_amazon_usage(df: pd.DataFrame) -> pd.DataFrame:
            """
            Falls Amazon | AMZN Mktp | AMAZON im Empfänger steht - Empfänger auf "Amazon.de" setzen
            und Rest in Beschreibung übernehmen.

            :param df: DataFrame mit Transaktionsdaten
            :return: DataFrame mit angepassten Beschreibungsspalte
            """
            # masken definieren
            mask_amzn = df["Empfänger"].fillna("").str.contains("Amazon|AMZN Mktp|AMAZON", case=True, na=False)
            # mask_empty_vzweck = df["Verwendungszweck"].fillna("").str.strip().eq("")

            # zeilen auswählen, wo das zutrifft
            mask = mask_amzn # & mask_empty_vzweck

            # Verwendungszweck aus Empfänger übernehmen, bereinigt
            df.loc[mask, "id"] = (
                df.loc[mask, "Empfänger"]
                .str.replace(r"Amazon(\.de)?|AMZN Mktp(\sDE)?|AMAZON", "", regex=True)
                .str.strip()
            )

            # 4️⃣ Empfänger angleichen
            df.loc[mask_amzn, "Empfänger"] = "Amazon.de"
            return df

        df = super().preprocess_data(key, df)  # Basis-Cleaning
        # Spalten bereinigen
        df.drop(["Umsatzkategorie", "Unterkategorie"], axis=1, inplace=True, errors='ignore')
        df.rename(columns={'Beschreibung': 'Empfänger'}, inplace=True)
        # Datenbereinigung
        df = _change_amazon_usage(df)
        df = self._normalize_dataframe(df)
        return df

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

        def _enter_otp() -> bool:
            """Fragt den Code ab und trägt ihn ein."""
            try:
                otp_field = self.wait_for_element(
                    "xpath",
                    "//input[@data-testid='challenge-otp-input' and @placeholder='Bestätigungscode']",
                    5,
                )
                code = input("🔐 Bitte 4-stelligen Bestätigungscode eingeben (oder 'retry' für neuen Code): ").strip()
                if code.lower() == "retry" or len(code) != 4:
                    self._logger.info("Code ungültig oder 'retry' gewählt → neuen Code anfordern.")
                    _request_new_code()
                    return False  # erneut versuchen
                otp_field.send_keys(code)
                self._logger.debug("Bestätigungscode eingegeben.")
                return True
            except Exception:
                self._logger.debug("Fehler beim Eingeben des Bestätigungscodes.", exc_info=True)
                return False

        def _submit_code() -> bool:
            """Klickt auf 'Weiter'."""
            try:
                self.wait_clickable_and_click(
                "xpath",
                "//button[@data-testid='challenge-sms-otp-button' and .//span[normalize-space()='Weiter']]",
                5,
                )
                self._logger.debug("Button 'Weiter' geklickt.")
                return True
            except TimeoutException:
                self._logger.debug("Kein 'Weiter'-Button gefunden.")
                return False

        def _try_again() -> bool:
            """Klickt auf 'Erneut versuchen', falls vorhanden."""
            try:
                self.wait_clickable_and_click(
                    by="xpath",
                    selector=(
                        "//button["
                        "(@data-testid='challenge-wrapper-message-fail-button'"
                        "or @data-testid='challenge-message-fail-button')"
                        "and .//span[normalize-space()='Erneut versuchen']"
                        "]"),
                    timeout=3)
                self._logger.debug("'Erneut versuchen' geklickt.")
                return True
            except TimeoutException:
                self._logger.debug("Kein 'Erneut versuchen'-Button gefunden.")
                return False

        def _confirm() -> bool:
            """Klickt abschließend auf 'Bestätigen', falls vorhanden."""
            try:
                self.wait_clickable_and_click(
                    "xpath",
                    "//button[.//span[normalize-space()='Bestätigen']]",
                    5,
                )
                self._logger.info("Identitätsverifizierung abgeschlossen ('Bestätigen' geklickt).")
                return True
            except TimeoutException:
                self._logger.debug("Kein 'Bestätigen'-Button gefunden – Verifizierung evtl. bereits erledigt.")
            except ElementNotInteractableException:
                self._logger.debug("'Bestätigen'-Button nicht interaktiv")
            return False

        def _wait_for_xls_btn() -> bool:
            """Wartet auf das Vorhandensein des XLS-Download-Buttons als Indikator für erfolgreiche Verifizierung."""
            try:
                xls_btn = self.wait_for_element(
                    by="xpath",
                    selector="//button[contains(.,'XLS herunterladen')]",
                    timeout=5,
                )
                return True
            except TimeoutException:
                return False

        def _manual_wait(timeout: int = 120) -> None:
            """Wartet manuell auf Benutzereingabe im Terminal."""
            start_time = time.time()
            self._logger.info("Bitte führen Sie die OTP-Verifikation manuell im Browser durch...")
            while (time.time() - start_time) < timeout:
                self._logger.info(
                    f"Warte auf manuelle OTP-Verifikation... timeout in: "
                    f"{round(timeout-(time.time() - start_time), 2)}s")
                if _wait_for_xls_btn():
                    self._verified = True
                    self._logger.info("OTP-Verifikation erfolgreich (manuell).")
                    return
                time.sleep(2)
            self._logger.warning("Timeout beim Warten auf manuelle OTP-Verifikation.")
            raise RuntimeError("Timeout bei der OTP-Verifikation.")

        # ------------------------------------------------------------
        # Hauptschleife
        # ------------------------------------------------------------
        max_runs = 2
        attempt = 0
        try:
            _request_new_code()     # inital gleich 2. versuch anfordern, da 1. immer fehlschlägt
            for attempt in range(max_runs):  # max. 3 Versuche
                try:
                    otp_field = self.wait_for_element(
                        "xpath",
                        "//input[@data-testid='challenge-otp-input' and @placeholder='Bestätigungscode']",
                        timeout=5)
                    if not (otp_field.is_displayed() and otp_field.is_enabled()):
                        self._logger.debug("OTP-Feld nicht sichtbar oder nicht interaktiv.")
                        if not _try_again():
                            continue
                except TimeoutException:
                    self._logger.debug("Kein OTP-Feld sichtbar – keine Verifizierung möglich.")
                    break

                self._logger.info(f"Starte OTP-Verifikation (Versuch {attempt + 1}/{max_runs})...")
                if not _enter_otp():
                    continue  # ungültiger Code oder 'retry' gedrückt → nächste Runde
                if _submit_code():
                    if _try_again():
                        continue  # Fehler beim Absenden → erneut versuchen
                    if not _confirm():
                        # schauen, ob erneut versuchen nötig ist
                        continue
                    else:
                        if _try_again():
                            continue
                            self._logger.info('Verifizierung fehlgeschlagen, erneut starten...')
                        if _wait_for_xls_btn():
                            self._verified = True
                            self._logger.info("OTP-Verifikation erfolgreich.")
                            break
                        else:
                            continue
            else:
                self._logger.warning(
                    f"OTP-Verifikation nach {(attempt+1) if attempt >0 else 0} Versuchen abgebrochen.")
                _manual_wait()
        except ElementNotInteractableException:
            self._logger.debug("OTP-Feld nicht interaktiv – übersprungen.")
        except Exception as e:
            self._logger.error(f"Fehler bei der OTP-Verifizierung: {e}", exc_info=True)

    def _fetch_transaction_details(self, key_columns=["Betrag", "Datum"]) -> pd.DataFrame:
        """
        Detaillierte Umsatzinformationen über amazon.de abrufen
        - load orders from amazon.de with amazon crowler
        - match transactions by amount + date
        - for each match, get details (verwendungszweck, verwendungszweck2) from amazon data
        - merge details into self.data verwendungszweck as verwendungszweck, verwendungszweck 2 as verwendungszweck 3
        """
        try:
            from .amazon import AmazonCrawler
        except ImportError:
            from src.read_transactions.webcrawler.amazon import AmazonCrawler
        with AmazonCrawler(logging_level=self._logging_lvl, start_date=self.start_date,
                           end_date=self.end_date) as amazon_crawler:
            amazon_crawler.login()
            amazon_crawler.download_data()
            amazon_crawler.process_data()
            if self._save_amazon_order:
                amazon_crawler.save_data()

        amazon_data = amazon_crawler.data
        if amazon_data is None or amazon_data.empty:
            self._logger.warning("Keine Amazon-Daten zum Abgleich gefunden.")
            return

        # Merge der Daten basierend auf den Schlüsselspalten
        merged_df = pd.merge(
            self.data,
            amazon_data[["Datum", "Betrag", "Verwendungszweck", "Verwendungszweck 2"]],
            on=key_columns,
            how="left",
            suffixes=("", "_amazon"),
        )
        # weitere Verarbeitung
        self.data = merged_df
        self.data.sort_values(by="Datum", ascending=False, inplace=True)





# ------------------------------------------------------------------
# Direkter Test
# ------------------------------------------------------------------
if __name__ == "__main__":
    print("Starte AmazonVisaCrawler im Direkt-Testmodus...")
    end = pd.Timestamp.now() - pd.DateOffset(months=12)
    # with AmazonVisaCrawler(logging_level="DEBUG", end_date=end) as crawler:
    #     # crawler._wait_for_manual_exit()
    #     crawler.login()
    #     # crawler._wait_for_manual_exit("Login abgeschlossen - browser bleibt offen")
    #     crawler.download_data()
    #     # crawler._wait_for_manual_exit("Daten-Download abgeschlossen - browser bleibt offen")
    #     crawler.process_data()
    #     crawler.save_data()


    crawler = AmazonVisaCrawler(logging_level="DEBUG", details=False)
    crawler.login()
    crawler.download_data()
    # crawler.process_data()
    # crawler.save_data()
    # crawler.close()
    self = crawler
    # indexed_intervals = [(idx, (start, end)) for idx, (start, end) in enumerate(intervals)]
    # idx, (start, end) = indexed_intervals[0]
    #
    # for idx, (start, end) in indexed_intervals:
    #     print(f"Intervall {idx}: {start:%d.%m.%Y} bis {end:%d.%m.%Y}")
    #     if (pd.Timestamp.now() - start) >= pd.Timedelta(days=90):
    #         print(f"mehr als 90 tage: {pd.Timestamp.now() - start}")
    #         #print(pd.Timestamp.now() - start)
    #     else:
    #         print("weniger als 90 tage")






