# -*- coding: utf-8 -*-
"""
:author: Tim Häberlein
:version: 1.0
:date: 03.11.2025
:organisation: TU Dresden, FZM

Paypal Crawler
-------------
Crawler für Paypal.com – lädt Transaktionen im csv Format herunter.

Verwendung:
    from read_transactions.webcrawler.paypal import PaypalCrawler

    with PaypalCrawler(logging_level="DEBUG") as crawler:
        crawler.login()
        crawler.download_data()
        crawler.process_data()
        crawler.save_data()
"""
import dataclasses
from calendar import day_abbr

# -------- start import block ---------
import pandas as pd
import re
from datetime import datetime
import time
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.remote.webelement import WebElement
from typing import Optional, Any
# from collections import deque  # doppel-ended queue

from read_transactions.webcrawler import WebCrawler
# -------- /import block ---------

# -------- Hilfsfunktionen/Klassen --------------
@dataclasses.dataclass
class Report:
    """
    Repräsentiert einen Berichtseintrag auf der Archiv Seite von Paypal.

    Attributes:
        row (WebElement): Die Tabellenzeile des Berichts.
        download_btn (WebElement): Der Download-Button für den Bericht.
        start_date (Optional[pd.Timestamp]): Startdatum des Berichts.
        end_date (Optional[pd.Timestamp]): Enddatum des Berichts.
        gen_date (Optional[pd.Timestamp]): Erstellungsdatum des Berichts.
        raw_date (str): Rohtext des Datumsbereichs.
        raw_gen_date (str): Rohtext des Erstellungsdatums.
    """
    row: WebElement
    download_btn: WebElement
    start_date: Optional[pd.Timestamp]
    end_date: Optional[pd.Timestamp]
    gen_date: Optional[pd.Timestamp]
    raw_date: str
    raw_gen_date: str
# -------- /end Hilfsfunktionen/Klassen ---------

# --------------------------------------------------------------------------------------------------------------------
# Paypal Crawler Klasse
# --------------------------------------------------------------------------------------------------------------------
class PaypalCrawler(WebCrawler):
    """
     Crawler für Paypal.

    Der Crawler automatisiert den Login auf `paypal.com`,
    lädt alle Transaktionen im gewählten Datumsbereich herunter
    und konvertiert sie in ein einheitliches CSV-Format.

    Ablauf:
        1. Login mit Benutzername + 4-stelliger PIN
        2. Öffnen der Transaktionsseite
        3. ...

    Erfordert:
        - gültige Zugangsdaten in `config.yaml`
        - hinterlegte URLs für `login` und `transactions`
        - funktionierenden Selenium-WebDriver (Edge / Chrome / Firefox)

    Beispiel:
        ```bash
        readtx run paypal --start 01.01.2024 --end 31.03.2024 --log_level DEBUG
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

    def __init__(self, *args, **kwargs):
        super().__init__(name="paypal", *args, **kwargs)
        self._load_config()
        self._verified = False  # ob die 2fa erfolgreich war


    def login(self):
        """Führt den Login auf Paypal durch."""
        super().login()  # ruf login der basis klasse auf -> öffnet die login url

        # username eingeben
        entered_username = self._login_enter_username()
        if not entered_username:
            raise RuntimeError("Fehler beim Eingeben des Benutzernamens.")

        # Passkey-/WebAuthn-Dialog **immer** abbrechen
        aborted = self._abort_windows_passkey()
        if not aborted:
            # entweder kein Dialog erschienen oder Abbruch nicht möglich
            self._logger.debug("Kein Passkey-Dialog erkannt oder Abbruch nicht möglich.")

        # Passwort eingeben
        entered_pwd = self._login_enter_password()
        if not entered_pwd:
            raise RuntimeError("Fehler beim Eingeben des Passworts.")

        # 2FA durchführen
        verified = self._verify_identity(timeout=180)
        if not verified:
            raise RuntimeError("Fehler bei der 2-Faktor-Authentifizierung.")

        # self.driver.minimize_window()

    def download_data(self):
        """Lädt die Transaktionsdaten im CSV-Format herunter."""
        super().download_data()  # ruf download der basis klasse auf -> printet nur log
        driver = self.driver
        url = self._urls.get("transactions")
        driver.get(url)

        # start und end datum in jahre zerlegen (reports werden immer ganzjährig erstellt)
        # bspw. start: 15.03.2024, end: 20.08.2022 -> jahre: 2022, 2023 + 1.1.2024 - 15.03.2024
        dates = self.split_dates()
        self._logger.info(f"Zerlege Datumsbereich in {len(dates)} Segmente für die Berichtserstellung.")

        # prüfen, welche segmente bereits vorhanden sind
        available_reports = self._check_available_reports()
        self._logger.info(f"Es sind {len(available_reports)} Berichte im Archiv verfügbar.")
        for start_date, end_date in dates:
            # prüfen, ob bericht für diesen bereich bereits existiert
            # -> nimm das erste aus der 'available_repots' liste
            exists = False
            for report in available_reports:
                if report.start_date.date() == start_date.date() and report.end_date.date() == end_date.date():
                    exists = True
                    self._logger.debug(f"Bericht für {start_date.date()} - {end_date.date()} bereits vorhanden.")
                    # download button klicken
                    try:
                        report.download_btn.click()
                        self._logger.info(
                            f"Starte Download für vorhandenen Bericht {start_date.date()} - {end_date.date()}.")
                        self._wait_for_new_file(include_temp=True)
                        break
                    except Exception:
                        self._logger.error(
                            f"Fehler beim Starten des Downloads für vorhandenen Bericht "
                            f"{start_date.date()} - {end_date.date()}.", exc_info=True)

                elif report.end_date.date() == end_date.date():
                    # im aktuellen jahr existiert bereits ein bericht mit gleichem enddatum
                    # → nur bericht von dem startdatum bis self.start erzeugen
                    try:
                        report.download_btn.click()
                        self._logger.info(
                            f"Starte Download für vorhandenen Bericht "
                            f"{report.start_date.date()} - {report.end_date.date()}.")
                        self._wait_for_new_file(include_temp=True)
                        # noch einen weiteren bricht bis start_date erstellen
                        end_date = report.start_date + pd.DateOffset(days=1)
                        break
                    except Exception:
                        self._logger.error(
                            f"Fehler beim Starten des Downloads für vorhandenen Bericht "
                            f"{start_date.date()} - {end_date.date()}.", exc_info=True)
            if not exists:
                self._logger.info(f"Erstelle neuen Bericht für {start_date.date()} - {end_date.date()}.")
                success = self._generate_new_report(start_date=start_date, end_date=end_date, timeout=300)
                if not success:
                    raise RuntimeError(f"Fehler beim Erstellen des Berichts für {start_date.date()} - {end_date.date()}.")
            else:
                self._logger.info(f"Überspringe Erstellung für {start_date.date()} - {end_date.date()}.")

    def process_data(self, *args, **kwargs):
        """Verarbeitet die heruntergeladenen CSV-Dateien und konsolidiert sie in ein DataFrame."""
        # basis funktion der basis klasse aufrufen (log + read_temp_files + preprocess data)
        super().process_data(sep=',', *args, **kwargs)
        # Dataframe normalisieren
        self.data = self._normalize_dataframe(self.data)
        # daten nach datum sortieren
        self.data.sort_values(by="Datum", ascending=False, inplace=True)
        self._logger.info(f"{len(self.data)} PayPal Transactionen verarbeitet.")

    def preprocess_data(self, key: str, df: pd.DataFrame) -> pd.DataFrame:
        """
        Überschreibt die preprocess_data Methode der Basis-Klasse für Paypal-spezifische Anpassungen.
        - Filtert und benennt Spalten um
        - Bereinigt bestimmte Transaktionstypen
        - Integriert Hinweise in den Verwendungszweck
        """
        df = super().preprocess_data(key, df)
        idx_wanted = ['Datum', 'Brutto', 'Name', 'Typ', 'Lieferadresse', 'Artikelbezeichnung',
                      'Guthaben', 'Telefon', 'Empfänger E-Mail-Adresse']
        idx_process = ['Zahlungsquelle', 'Auswirkung auf Guthaben','Hinweis']
        rename_map = {"Brutto": "Betrag", "Name": "Empfänger", "Typ": "Verwendungszweck",
                      'Empfänger E-Mail-Adresse': 'E-Mail'}

        # Spalten bereinigen
        df = self._filter_columns_by_names(df, idx_wanted+idx_process)

        # memo zahlungen filtern
        mask_contains = df["Auswirkung auf Guthaben"].str.contains("Memo", na=False, case=True)
        df = df.loc[~mask_contains]

        # einzahlungen umbenennen
        # Maske für betroffene Zeilen
        mask = df["Typ"].astype(str).str.strip() == "Allgemeine Gutschrift auf Kreditkarte"
        # Kreditnummer aus 'Zahlungsquelle' extrahieren: matcht "PayPal [...]" und nimmt den Inhalt der Klammern
        credit = df.loc[mask, "Zahlungsquelle"].astype(str).str.extract(r"PayPal\s*\[([^\]]+)\]", expand=False)
        # Name setzen
        df.loc[mask, "Name"] = "PayPal"
        # Typ setzen: "Kreditkarte mit <num>" wenn gefunden, sonst "Kreditkarte"
        df.loc[mask, "Typ"] = (("Einzahlung von Kreditkarte mit " + credit.fillna("")).where(credit.notna(), "Kreditkarte"))

        # Auszahlungen umbenennen
        mask = df["Typ"].astype(str).str.strip() == "Allgemeine Abbuchung von Kreditkarte"
        # Kreditnummer aus 'Zahlungsquelle' extrahieren: matcht "PayPal [...]" und nimmt den Inhalt der Klammern
        credit = df.loc[mask, "Zahlungsquelle"].astype(str).str.extract(r"PayPal\s*\[([^\]]+)\]", expand=False)
        # Name setzen
        df.loc[mask, "Name"] = "PayPal"
        # Typ setzen: "Kreditkarte mit <num>" wenn gefunden, sonst "Kreditkarte"
        df.loc[mask, "Typ"] = (("Auszahlung auf Kreditkarte mit " + credit.fillna("")).where(credit.notna(), "Kreditkarte"))

        # Einzahlungen via Bankkonto umbenennen
        mask = df["Typ"].astype(str).str.strip() == "Bankgutschrift auf PayPal-Konto"
        df.loc[mask, "Name"] = "PayPal"
        df.loc[mask, "Typ"] = "Einzahlung von Bankkonto"

        # Hinweis in Typ integrieren
        df["Typ"] = (
            df.filter(items=["Typ", "Hinweis"])           # nimmt nur existierende Spalten
            .astype("string")
            .apply(lambda r: " - ".join(x for x in r.dropna().str.strip() if x), axis=1)
            .replace("", pd.NA)
        )

        # Spalten nochmal bereinigen (nach processing)
        df = self._filter_columns_by_names(df, idx_wanted)

        # Spalten umbenennen
        df = self._rename_columns_by_map(df, rename_map)

        return df

    # ----------------------------------------------------------------------------------------------------------------
    # Hilfsfunktionen für den Login
    # ----------------------------------------------------------------------------------------------------------------
    def _login_enter_username(self, timeout: int = 180) -> bool:
        """
        Gibt den Benutzernamen auf der Login-Seite ein und drückt "Weiter".
        """
        # ------ selectoren definieren ------
        # E-Mail-Feld
        sel_email = [
            ("css", "input#email"),
            ("css", "input[name='login_email']"),
            ("xpath", "//input[@type='email' and (@id='email' or @name='login_email')]"),
        ]

        # Weiter-Button
        sel_next = [
            ("css", "#btnNext"),
            ("xpath", "//button[@type='submit' and (@id='btnNext' or @name='btnNext')]"),
            ("xpath", "//button[normalize-space()='Weiter']"),  # Sprachfallback
        ]

        # ------ Hilfsfunktionen ------
        def _wait_for_login_page():
            """warte bis die login seite geladen ist"""
            start_time = time.time()
            last_time_logged = time.time()
            while (time.time() - start_time) < timeout:
                # ausgabe alle 5 Sekunden
                if (time.time() - last_time_logged) >= 5:
                    last_time_logged = time.time()
                    self._logger.info(
                        f"Warte auf Login-Seite... (timeout in: "
                        f"{round(timeout - (time.time() - start_time), 2)} Sekunden)")
                # prüfen, ob email feld vorhanden ist
                try:
                    self.find_first_matching_element(selectors=sel_email, timeout_each=2)
                    return True
                except TimeoutException:
                    time.sleep(0.5)
            return False

        # ------ Hauptlogik ------
        try:
            # Benutzername eingeben
            try:
                user_field = self.find_first_matching_element(selectors=sel_email, timeout_each=2)
            except TimeoutException:
                # warte auf login seite
                self._logger.info("Login-Seite nicht wie gewohnt gefunden. Warte auf Laden der Seite...")
                self._logger.info("Bitte überprüfe das Browser-Fenster - Bis zur Eingabe des Benutzernames navigieren.")
                self.driver.maximize_window()
                page_loaded = _wait_for_login_page()
                self.driver.minimize_window()
                if not page_loaded:
                    self._logger.error("Login-Seite konnte nicht geladen werden.")
                    return False
            user_field = self.find_first_matching_element(selectors=sel_email, timeout_each=2)
            user_field.clear()
            user_field.send_keys(self._credentials['user'])

            # Weiter-Button klicken
            self.click_first_matching_element(selectors=sel_next, timeout_each=5)
        except Exception:
            self._log_error_with_debug_msg()
            return False
        return True

    def _login_enter_password(self):
        """Gibt das Passwort auf der Login-Seite ein und drückt "Anmelden"."""
        # ------ selectoren definieren ------
        # Passwort-Feld
        sel_password = [
            ("css", "input#password"),
            ("css", "input[name='login_password']"),
            ("xpath", "//input[@type='password' and (@id='password' or @name='login_password')]"),
        ]
        # Anmelden-Button
        sel_login = [
            ("css", "#btnLogin"),
            ("xpath", "//button[@type='submit' and (@id='btnLogin' or @name='btnLogin')]"),
            ("xpath", "//button[normalize-space()='Einloggen']"),  # Sprachfallback
        ]
        # ------ Hauptlogik ------
        try:

            # Passwort eingeben - # sollte eigentl. schon vorhanden sein
            pwd_field = self.find_first_matching_element(selectors=sel_password, timeout_each=5)
            pwd_field.clear()
            pwd_field.send_keys(self._credentials['password'])

            self.click_first_matching_element(selectors=sel_login, timeout_each=5)
            return True
        except Exception:
            self._log_error_with_debug_msg()
            return False

    def _verify_identity(self, timeout: int = 180) -> bool:
        """Führt die 2-Faktor-Authentifizierung durch (z. B. PIN-Eingabe)."""
        # ------ selectoren definieren ------
        sel_push_visible = [
            # Text-basiert (stabilste Variante)
            ("xpath", "//h2[normalize-space()='Um fortzufahren, gehe zur PayPal-App']"),
        ]
        sel_balance = [
            # stabil & eindeutig über data-test-id
            ("css", "[data-test-id='available-balance']"),
            ("xpath", "//*[@data-test-id='available-balance']"),
        ]

        # ------ Hilfsfunktionen ------
        def _is_push_message_visible() -> bool:
            """prüft ob die push nachricht sichtbar ist"""
            try:
                self.find_first_matching_element(selectors=sel_push_visible, timeout_each=5)
                return True
            except TimeoutException:
                return False

        def _check_login_successful() -> bool:
            try:
                balance = self.find_first_matching_element(selectors=sel_balance, timeout_each=5)
                self.account_balance = balance.text
                self._logger.info(f"Login erfolgreich. Kontostand: {self.account_balance}")
                return True
            except TimeoutException:
                return False

        def _wait_for_login() -> bool:
            """warte bis login bestätigt wurde oder timeout erreicht ist"""
            # warte auf Login
            start_time = time.time()
            last_time_logged = time.time()
            while (time.time() - start_time) < timeout:
                # ausgabe alle 5 Sekunden
                if (time.time() - last_time_logged) >= 5:
                    last_time_logged = time.time()
                    self._logger.info(
                        f"Warte auf Login... (timeout in: "
                        f"{round(timeout - (time.time() - start_time), 2)} Sekunden)")
                # prüfen, ob login erfolgreich war
                if _check_login_successful():
                    return True
                time.sleep(0.5)
            return False


        # ----- Hauptlogik -----
        # wenn push-nachricht sichtbar ist -> warte bis login bestätigt wurde
        try:
            if _is_push_message_visible():
                self._logger.info("Push-Nachricht erkannt. Warte auf Bestätigung...")
                if _wait_for_login():
                    self._verified = True
                    return True
                else:
                    return False
            # wenn keine push-nachricht sichtbar ist -> warte auf login (browser fenster durch nutzer prüfen lassen)
            else:
                self._logger.info("Keine Push-Nachricht erkannt - vermutlich andere 2FA-Methode.")
                self._logger.info("Bitte überprüfe das Browser-Fenster und bestätige den Login.")
                self.driver.maximize_window()
                if _wait_for_login():
                    self._verified = True
                    self.driver.minimize_window()
                    return True
                else:
                    return False
        except Exception:
            self._log_error_with_debug_msg()
            return False
    # ----------------------------------------------------------------------------------------------------------------

    # ----------------------------------------------------------------------------------------------------------------
    # Hilfsfunktionen für den Download und die Verarbeitung
    # ----------------------------------------------------------------------------------------------------------------

    def _check_available_reports(self) -> list[Report]:
        """prüft verfügbare Berichte auf der Transaktionsseite

        Returns:
            list[Report]: Liste der verfügbaren Berichte mit Metadaten.
        """
        sel_table = [
            ("xpath", "//table[@data-testid='table']"),
        ]
        sel_rows = [
            # sichtbare Datenzeilen (Spinner ist 'hidden', aber sicherheitshalber filtern)
            ("xpath", "//table[@data-testid='table']//tbody/tr[not(contains(@class,'hidden'))]")
        ]
        # 1. Spalte = Berichtstyp
        sel_type_cell_in_row = [
            ("xpath", "./td[1]"),
        ]
        # 2. Spalte = Generiert am
        sel_gen_date_cell_in_row = [
            ("xpath", "./td[2]"),
        ]
        # 3. Spalte = Datumsbereich
        sel_date_cell_in_row = [
            ("xpath", "./td[3]"),
        ]
        # 4. Spalte = Format
        sel_format_cell_in_row = [
            ("xpath", "./td[4]"),
        ]
        # Download-Button in derselben Zeile
        sel_download_btn_in_row = [
            ("xpath", ".//button[@data-testid='linkButton' or contains(.,'Herunterladen')]"),
        ]

        # warte auf Tabelle
        table = self.find_first_matching_element(sel_table)
        rows = self.find_all_in(table, sel_rows)

        date_ranges = []
        for r in rows:
            try:

                # typ finden
                cell = self.find_first_in(r, sel_type_cell_in_row)
                report_type = (cell.text or "").strip().lower()
                if report_type != "alle transaktionen" and report_type != "all transactions":
                    continue  # nur "Alle Transaktionen" berücksichtigen

                # format finden
                cell = self.find_first_in(r, sel_format_cell_in_row)
                report_format = (cell.text or "").strip().lower()
                # nur "CSV" berücksichtigen
                if report_format != "csv":
                    continue

                # datum finden
                cell = self.find_first_in(r, sel_date_cell_in_row)
                raw = (cell.text or "").strip()
                # Beispiel: "Jan 1, 2025 - Sep 30, 2025"
                m = re.match(r"^\s*([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})\s*-\s*([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})\s*$", raw)
                if not m:
                    # Fallback für andere Formate (z. B. "1. Jan. 2025 - 30. Sep. 2025")
                    m = re.match(r"^\s*([\d\.]+\s*[A-Za-zäöüÄÖÜ\.]+\.?\s*\d{4})\s*-\s*([\d\.]+\s*[A-Za-zäöüÄÖÜ\.]+\.?\s*\d{4})\s*$", raw)
                end_s, start_s = (m.group(1), m.group(2)) if m else (None, None)

                def parse_ts(s):
                    if not s: return None
                    for fmt in ("%b %d, %Y", "%d. %b %Y", "%d.%m.%Y", "%d. %B %Y"):
                        try:
                            return pd.to_datetime(s.replace("  ", " "), format=fmt)# .date()
                        except ValueError:
                            continue
                    return None

                start_ts = parse_ts(start_s)
                end_ts   = parse_ts(end_s)

                # optional gen date finden
                cell = self.find_first_in(r, sel_gen_date_cell_in_row)
                gen_date_s = (cell.text or "").strip()
                # Beispiel: Nov 3, 2025
                m = re.match(r"^\s*([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})\s*$", gen_date_s)
                gen_date_ts = None
                if m:
                    try:
                        gen_date_ts = pd.to_datetime(m.group(1), format="%b %d, %Y")
                        # Falls datum vor dem 10.03.2025 liegt, ignoriere es (buggy angaben)
                        if gen_date_ts < pd.to_datetime('3.10.2025', dayfirst=True):
                            continue
                    except ValueError:
                        pass

                # optional: Download-Button der Zeile referenzieren
                try:
                    btn = self.find_first_in(r, sel_download_btn_in_row)
                except Exception:
                    btn = None

                date_ranges.append(
                    Report(row=r, download_btn=btn,
                           start_date=start_ts, end_date=end_ts,
                           raw_date=raw,
                           gen_date=gen_date_ts, raw_gen_date=gen_date_s)
                )
            except Exception:
                continue
        return date_ranges

    def _generate_new_report(self,
                             start_date: pd.Timestamp | None = None,
                             end_date: pd.Timestamp | None = None,
                             timeout: int = 180
                             ) -> bool:
        """
        Erstellt einen neuen Bericht für den gewünschten datumsbereich

        Args:
            start_date (pd.Timestamp | None): Startdatum (inklusive). Wenn None, wird der Standardwert verwendet.
            end_date (pd.Timestamp | None): Enddatum (inklusive). Wenn None, wird der Standardwert verwendet.
            timeout (int): Maximale Wartezeit in Sekunden für den Berichtserstellungsprozess.
        """
        if not start_date:
            start_date = pd.to_datetime("31.12.2023", dayfirst=True)
        if not end_date:
            end_date = pd.to_datetime("01.01.2023", dayfirst=True)
        # Dropdown-Button öffnen (zeigt aktuell "Guthaben-relevant")
        sel_txn_type_button = [
            ("css", "#dropdownMenuButton_Transaktionstyp"),
            ("css", "button[data-testid='TransactionType']"),
        ]

        # Option "Alle Transaktionen"
        sel_option_all = [
            # Eindeutig über Attribut (sprachunabhängig)
            ("css", "[role='option'][data-value='All transactions']"),

            # Textbasiert (sprachabhängig, robust gegen Klassenänderungen)
            ("xpath", "//*[@role='option'][.//p[normalize-space()='Alle Transaktionen']]"),

            # Gescoped innerhalb der geöffneten Listbox (falls mehrere Menüs existieren)
            ("xpath", "//*[@role='listbox']//*[@role='option' and @data-value='All transactions']"),
        ]
        # Download-Button in der Ergebnis-Tabelle
        sel_download_btn_in_row = [
            ("xpath", ".//button[@data-testid='linkButton' or contains(.,'Herunterladen')]"),
        ]
        # Input "Datumsbereich"
        sel_date_range_input = [
            # stabil über Label → Input (id kann 'undefined' sein und sich ändern)
            ("xpath", "//label[normalize-space()='Datumsbereich']/preceding-sibling::input"),
            # direkter Fallback über aktuelle id + Klassen
            ("css", "input#text-input-undefined.upo0hta"),
        ]
        # Selektoren für Datumsbereicheingabe
        sel_end = [
            ("css", "input#start"),
            ("css", "input[data-testid='startInputBox']"),
            ("xpath", "//input[@id='start' or @data-testid='startInputBox']"),
        ]

        sel_start = [
            ("css", "input#end"),
            ("css", "input[data-testid='endInputBox']"),
            ("xpath", "//input[@id='end' or @data-testid='endInputBox']"),
        ]
        # Bericht erstellen Btn
        sel_create_report = [
            ("xpath", "//*[normalize-space()='Bericht erstellen']"),
            ("xpath", "//*[contains(@class,'pmr2te') and normalize-space()='Bericht erstellen']"),  # Klassen-Fallback
        ]
        # Aktualisieren Btn
        sel_refresh_btn = [
            ("xpath", "//button[@data-testid='linkButton' and normalize-space()='Aktualisieren']"),
            ("xpath", "//button[normalize-space()='Aktualisieren']"),  # Text-Fallback
        ]
        sel_success_alert = [
            ("xpath", "//*[contains(normalize-space(.),'Ihre Anforderung wird verarbeitet.')]"),
            ("xpath", "//div[@role='alert' and .//*[@aria-label='success']]"),
        ]

        def _choose_all_transactions_option() -> bool:
            """wählt die option 'alle transaktionen' im dropdown aus"""
            try:
                # 1) Dropdown öffnen (bei Bedarf doppelt versuchen, falls Click das erste Mal nicht greift)
                btn = self.find_first_matching_element(sel_txn_type_button)
                btn.click()

                # 2) Option "Alle Transaktionen" anklicken
                self.click_first_matching_element(sel_option_all)  # primärer, textbasierter Selektor

                # 3) verifizieren, dass der Button-Text umgestellt wurde
                current = btn.text.strip()
                if current.lower() not in ["alle transaktionen", "all transactions"]:
                    self._logger.debug("Konnte Transaktionstyp nicht auf 'Alle Transaktionen' setzen.")
                    return False
            except TimeoutException:
                return False
            except Exception:
                self._log_error_with_debug_msg()
                return False
            return True

        def js_set_input(el, value: str):
            js = """
                const el = arguments[0];
                const val = arguments[1];
                
                // 1) Fokus & Auswahl (optional – „alles markieren“)
                try { el.focus(); } catch(e) {}
                try {
                  if (typeof el.select === 'function') el.select();
                  else if (typeof el.setSelectionRange === 'function') el.setSelectionRange(0, (el.value||'').length);
                } catch(e) {}
                
                // 2) React-/Vue-korrekt: nativen Setter verwenden
                const proto = Object.getPrototypeOf(el);
                const desc = Object.getOwnPropertyDescriptor(proto, 'value');
                if (desc && desc.set) {
                  desc.set.call(el, '');       // sicher leeren
                  desc.set.call(el, val);      // neuen Wert setzen
                } else {
                  el.value = val;
                }
                
                // 3) Events feuern (damit UI/Validator reagiert)
                el.dispatchEvent(new Event('input',  { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                el.dispatchEvent(new Event('blur',   { bubbles: true }));
                """
            self.driver.execute_script(js, el, value)

        def _enter_dates_and_submit() -> bool:
            """gibt die datumswerte ein und bestätigt den filter"""
            try:
                # Datumseingabe-Feld finden
                date_input = self.find_first_matching_element(sel_date_range_input)
                self.scroll_into_view(date_input)
                date_input.click()
                time.sleep(0.1)
                # Startdatum eingeben
                start_input = self.find_first_matching_element(sel_start)
                # start_input.click()
                js_set_input(start_input, start_date.strftime("%d.%m.%Y"))
                time.sleep(0.1)
                # Enddatum eingeben
                end_input = self.find_first_matching_element(sel_end)
                # end_input.click()
                js_set_input(end_input, end_date.strftime("%d.%m.%Y"))
                time.sleep(0.1)
                # außerhalb klicken, um Eingabe zu bestätigen
                date_input = self.find_first_matching_element(sel_date_range_input)
                self.scroll_into_view(date_input)
                date_input.click()
                time.sleep(0.1)
                # Bericht erstellen Button klicken
                self.click_first_matching_element(sel_create_report)
                time.sleep(1)
                self.find_first_matching_element(sel_success_alert)

            except TimeoutException:
                return False

            return True

        def _wait_for_download() -> bool:
            """wartet bis der download button aktiv ist"""
            status = "unbekannt"
            report = self._check_available_reports()[0]
            download_btn = report.download_btn
            downloaded = False
            start_time = time.time()
            last_time_logged = time.time()
            # warte auf 'download' im button in der tabelle
            while not downloaded and ((time.time() - start_time) < timeout):
                try:
                    download_btn = self.find_first_in(report.row, sel_download_btn_in_row)
                    status = download_btn.text
                    if status == 'Herunterladen' or download_btn.text == 'Download':
                        download_btn.click()
                        downloaded = True
                        self._logger.info("Download gestartet.")
                except Exception:
                    pass
                # ausgabe alle 10 Sekunden
                if (time.time() - last_time_logged) >= 10:
                    refresh_btn = self.find_first_matching_element(sel_refresh_btn, timeout_each=5)
                    refresh_btn.click()
                    refresh_btn = self.find_first_matching_element(sel_refresh_btn, timeout_each=5)
                    last_time_logged = time.time()
                    self._logger.info(
                        f"Warte auf aktiven Download-Button - Status: {status}... (timeout in: "
                        f"{round(timeout - (time.time() - start_time), 2)} Sekunden)")

                time.sleep(1)

            self._wait_for_new_file(include_temp=True)
            return True


        # ------ Hauptlogik -----
        # Alle Transaktionen auswählen
        success = _choose_all_transactions_option()
        if not success:
            self._logger.error("Fehler beim Auswählen von 'Alle Transaktionen' im Filter.", exc_info=True)
            raise RuntimeError("Fehler beim Auswählen von 'Alle Transaktionen' im Filter.")
        # Datum eingeben
        success = _enter_dates_and_submit()
        if not success:
            self._logger.error("Fehler beim Eingeben des Datumsbereichs.", exc_info=True)
            raise RuntimeError("Fehler beim Eingeben des Datumsbereichs.")
        # Kopf der Seite wird neu geladen
        # refresh_btn = self.find_first_matching_element(sel_refresh_btn, timeout_each=5)
        # auf download button warten
        success = _wait_for_download()
        if not success:
            self._logger.error("Fehler beim Warten auf den Download-Button.", exc_info=True)
            raise RuntimeError("Fehler beim Warten auf den Download-Button.")
        # warten bis download button aktiv ist

        # download button selektoren
        return True

    def split_dates(self) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
        """
        Zerlegt den aktuellen Datumsbereich des Crawlers in Jahressegmente.
        Sofern der Bereich über mehrere Jahre geht, werden die vollen Jahre
        als eigene Segmente zurückgegeben. Teiljahre am Anfang und Ende werden ebenfalls berücksichtigt.
        Sollte das erste Jahr das aktuelle Jahr sein, wird das Enddatum auf das heutige Datum begrenzt.

        Returns:
            list[tuple[pd.Timestamp, pd.Timestamp]]: Liste von Tupeln mit (start_date, end_date) für jedes Segment.
        """
        from datetime import datetime
        s = self.start_date
        e = self.end_date
        # sicherstellen: s >= e
        if s < e:
            s, e = e, s
            self._logger.debug("Warnung: start_date war kleiner als end_date - Werte wurden vertauscht.")

        def add_slice(acc: list, a: pd.Timestamp, b: pd.Timestamp):
            if a <= b:  # nur nicht-leere Intervalle übernehmen
                acc.append((b, a))

        # gleicher Jahrgang und aktuelles jahr → nur ein Segment zurückgeben
        if s.year == e.year and s.year == pd.Timestamp.now().year:
            y_start: pd.Timestamp = pd.to_datetime(datetime(year=s.year, month=1, day=1))
            y_end: pd.Timestamp   = pd.Timestamp.now()
            return [(y_end, y_start)]
        # gleicher Jahrgang, aber nicht aktuelles jahr → volles Jahr zurückgeben
        elif s.year == e.year and s.year != pd.Timestamp.now().year:
            y_start: pd.Timestamp = pd.to_datetime(datetime(year=s.year, month=1, day=1))
            y_end: pd.Timestamp   = pd.to_datetime(datetime(year=s.year, month=12, day=31))
            return [(y_end, y_start)]

        slices: list[tuple[pd.Timestamp, pd.Timestamp]] = []

        # 1) erstes (unteres) Teiljahr -> weglassen, da volles jahr auch geht
        # y_start: pd.Timestamp = pd.to_datetime(datetime(year=e.year, month=1, day=1))
        # add_slice(slices, y_start, e)

        # 2) volle Zwischenjahre
        # for y in range(e.year + 1, s.year): -> erstes jahr als volles miteinbeziehen
        for y in range(e.year, s.year):
            y_start: pd.Timestamp = pd.to_datetime(datetime(year=y, month=1, day=1))
            y_end: pd.Timestamp   = pd.to_datetime(datetime(year=y, month=12, day=31))
            add_slice(slices, y_start, y_end)

        # 3) letztes (oberes) Teiljahr
        if s.year != e.year:
            if s.year == pd.Timestamp.now().year:
                # check if date now >= s
                if pd.Timestamp.now() >= s:
                    # aktuelles jahr, genauso übernehmen
                    add_slice(slices, pd.to_datetime(datetime(year=s.year, month=1, day=1)), s)
                else:
                    # aktuelles jahr, aber s liegt in der zukunft -> bis heute
                    add_slice(slices, pd.to_datetime(datetime(year=s.year, month=1, day=1)), pd.Timestamp.now())
            else:
                # volles jahr bis start
                y_start: pd.Timestamp = pd.to_datetime(datetime(year=s.year, month=1, day=1))
                y_end: pd.Timestamp   = pd.to_datetime(datetime(year=s.year, month=12, day=31))
                add_slice(slices, y_start, y_end)
        return slices



# ausführung nur bei direktem Script-Aufruf
if __name__ == '__main__':
    print("Starte PaypalCrawler im Direkt-Testmodus...")
    from read_transactions.config import ConfigManager
    config = ConfigManager.load(ignore_cache=True)
    # start = pd.Timestamp.now() - pd.DateOffset(months=6)
    start = '31.08.2024'
    end = '01.01.2024'
    output_path = "../../../out"
    # end = pd.Timestamp.now() - pd.DateOffset(months=7)

    # with PaypalCrawler(logging_level="DEBUG", start_date=start, end_date=end, output_path=output_path) as crawler:
    #     crawler.login()
    #     crawler.download_data()
    #     crawler.process_data()
    #     crawler.save_data()

    # einzel Test ohne context manager
    crawler = PaypalCrawler(logging_level="DEBUG", start_date=start, end_date=end, output_path=output_path)
    crawler.login()
    # crawler.download_data()
    # crawler.process_data()
    # crawler.save_data()
    # crawler.close()

    # crawler.driver.get(crawler._urls['transactions'])
    # dates = crawler.split_dates()
    # reports = crawler._check_available_reports()
    # for start, end in dates:
    #     print(f"Segment: {start.date()} - {end.date()}")
    #     for r in reports:
    #         print(f"  Verfügbarer Bericht: {r.start_date.date()} - {r.end_date.date()}")
    #         if start.date()==r.start_date.date() and end.date()==r.end_date.date():
    #             print("    Match gefunden!")
    #             break
    #         elif end.date() == r.end_date.date():
    #             print("     Teil-Match gefunden!")
    #             end = r.start_date + pd.DateOffset(days=1)
    #             print(f"    Neues Berichtsdatum:{start.date()} - {end.date()}")
    #             break

    # self = crawler
    # reports = crawler._check_available_reports()
    #
    # def print_out():
    #     mystr = f"start: {self.start_date}\nend: {self.end_date}\nsplit: {split_years_and_top_remainder(self)}"
    #     print(mystr)
    # filepath = 'c:/users/s7285521/Downloads/Download.CSV'
    # data: pd.DataFrame = pd.read_csv(filepath, sep=',')
    # full_idx = ['Datum', 'Uhrzeit', 'Zeitzone', 'Name', 'Typ', 'Status', 'Währung',
    #        'Brutto', 'Gebühr', 'Netto', 'Absender E-Mail-Adresse',
    #        'Empfänger E-Mail-Adresse', 'Transaktionscode', 'Status Gegenpartei',
    #        'Lieferadresse', 'Adress-Status', 'Artikelbezeichnung', 'Artikelnummer',
    #        'Versand- und Bearbeitungsgebühr', 'Versicherungsbetrag',
    #        'Umsatzsteuer', 'Option 1 Name', 'Option 1 Wert', 'Option 2 Name',
    #        'Option 2 Wert', 'Auktions-Site', 'Käufer-ID', 'Artikel-URL',
    #        'Enddatum', 'Zugehöriger Transaktionscode', 'Rechnungsnummer',
    #        'Zollnummer', 'Anzahl', 'Empfangsnummer', 'Guthaben', 'Adresszeile 1',
    #        'Adresszusatz', 'Ort', 'Bundesland', 'PLZ', 'Land', 'Telefon',
    #        'Betreff', 'Hinweis', 'Zahlungsquelle', 'Kartentyp',
    #        'Transaktionsereigniscode', 'Zahlungsverfolgungs-ID', 'Bankreferenz',
    #        'Ländercode des Käufers', 'Gutscheine', 'Sonderangebote',
    #        'Kundenkartennummer', 'Ländervorwahl', 'Auswirkung auf Guthaben',
    #        'E-Börse des Käufers', 'Trinkgeld', 'Rabatt', 'Verkäufer-ID',
    #        'Risikofilter', 'Transaktionsgebühr für Ratenzahlungen',
    #        'Zusatzgebühr für Null-Prozent-Finanzierung', 'Zahlungsziel',
    #        'Art des Kreditangebots', 'Ursprüngliche Rechnungsnummer',
    #        'Unterart der Zahlungsquelle', 'Kampagnengebühr', 'Name der Kampagne',
    #        'Kampagnenrabatt', 'Währung des Kampagnenrabatts', 'Ablehnungscode',
    #        'Fastlane-Checkout-Transaktion', 'Prämienpunkte']
