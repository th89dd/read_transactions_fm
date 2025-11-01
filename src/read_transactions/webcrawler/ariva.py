# -*- coding: utf-8 -*-
"""
:author: Tim Häberlein
:version: 2.0
:date: 21.10.2025
:organisation: TU Dresden, FZM

ArivaCrawler
------------
Crawler für Kursdaten von ariva.de.

Verwendung:
    from read_transactions.webcrawler.ariva import ArivaCrawler

    with ArivaCrawler() as crawler:
        crawler.login()
        crawler.download_data()
        crawler.process_data()
        crawler.save_data()
"""

# -------- start import block ---------

import os
import time
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver import ActionChains

from read_transactions.webcrawler import WebCrawler

# -------- /import block ---------

class ArivaCrawler(WebCrawler):
    """
    Crawler für Kursdaten von ariva.de.

    Der Crawler automatisiert den Login auf ariva.de, öffnet für alle in der
    Konfiguration hinterlegten Wertpapiere die Kursseiten, lädt CSV-Dateien
    herunter und führt sie zu einem einheitlichen Datensatz zusammen.

    Ablauf:
        1. Optionaler Login (sofern Zugangsdaten vorhanden)
        2. Aufruf aller in der Konfiguration definierten URLs
        3. Auswahl von Währung, Zeitraum und Trenner
        4. Start des CSV-Downloads
        5. Zusammenführung und Bereinigung der Daten

    Voraussetzungen:
        - gültige Zugangsdaten und URL-Mappings in `config.yaml`
        - funktionierender Selenium-WebDriver (Edge, Chrome oder Firefox)

    CLI-Beispiel:
        ```bash
        readtx run ariva --start 01.01.2024 --end 31.03.2024 --log_level DEBUG
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

    Attribute
    ----------
    data : pandas.DataFrame
        Zusammengeführte Kursdaten aller Wertpapiere.
    _urls : dict
        Enthält alle Kurs-URLs aus der Konfiguration.
    _logger : logging.Logger
        Instanzspezifischer Logger.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(name="ariva", *args, **kwargs)
        self._load_config()

    # ----------------------------------------------------------
    # Login
    # ----------------------------------------------------------
    def login(self) -> None:
        """
        Meldet sich auf ariva.de an, falls Zugangsdaten vorhanden sind.

        Öffnet die Login-Seite, füllt Benutzername und Passwort aus,
        sendet das Formular ab und schließt anschließend eventuelle
        Werbe-Overlays (über handle_ad_banner).
        """
        # zuverlässige Login-Erkennung über Profilmenü
        def _is_logged_in() -> bool:
            try:
                profile = self.wait_for_element("id", "navigation__profile", timeout=15)

                # 2) Logged-In Marker ohne Hover (stabil & schnell)
                try:
                    driver.find_element(By.CSS_SELECTOR, ".navigation__profile__item__user--loggedIn")
                    self._logger.debug("Logged-In Marker gefunden (ohne Hover).")
                    return True
                except NoSuchElementException:
                    pass

                # 3) Menü per Hover öffnen und nach „Abmelden“ oder Profil-Link schauen
                try:
                    ActionChains(driver).move_to_element(profile).perform()
                    # kleines Fokus-Div fokussieren, damit onfocus ausgelöst wird (toggleUserPreferences())
                    try:
                        focus_div = profile.find_element(By.CSS_SELECTOR, "div[tabindex='0']")
                        focus_div.click()
                    except Exception:
                        pass

                    # a) „Abmelden“-Button sichtbar?
                    sel = "//ul[@id='preferences']//button[normalize-space()='Abmelden' or contains(., 'Abmelden')]"
                    self.wait_for_element("xpath", sel, 5)
                    self._logger.debug("Abmelden-Button im Profilmenü gefunden – eingeloggt.")
                    return True
                except TimeoutException:
                    # b) Alternativ: Profil-Link mit Benutzername sichtbar?
                    try:
                        driver.find_element(
                            By.XPATH,
                            "//ul[@id='preferences']//a[contains(@href, '/profil/')]"
                        )
                        self._logger.debug("Profil-Link im Menü gefunden – eingeloggt.")
                        return True
                    except NoSuchElementException:
                        return False
            except TimeoutException:
                return False
            except Exception:
                self._logger.debug("Fehler bei _is_logged_in()", exc_info=True)
                return False

        def _wait_for_login(timeout: int = 120) -> bool:
            """
            Wartet bis zum erfolgreichen Login oder Timeout.

            Args:
                timeout (int): Maximale Wartezeit in Sekunden.

            Returns:
                bool: True, wenn Login erfolgreich, sonst False.
            """
            start_time = time.time()
            while time.time() - start_time < timeout:
                self._logger.info("Autologin ist fehlgeschlagen. Bitte den Browser öffnen und einloggen.")
                if _is_logged_in():
                    return True
                self._logger.info(
                    f"Warte auf manuellen Login... (timeout in {round(timeout - (time.time() - start_time), 2)} s)")
                time.sleep(1)
            return False

        def _single_login() -> None:
            """
            Führt den Login-Vorgang auf ariva.de durch.

            Öffnet die Login-Seite, füllt Benutzername und Passwort aus,
            sendet das Formular ab und schließt anschließend eventuelle
            Werbe-Overlays (über handle_ad_banner).
            """
            # time.sleep(0.5)  # kurze Pause für Initialisierung
            # Ad-Banner / Werbe-Overlay nach Login schließen
            self._handle_ad_banner()
            # Login anklicken
            sel = "//span[contains(@class,'prgLink') and normalize-space()='Login']"
            # btn = self.wait_for_element("xpath", sel)
            self.wait_clickable_and_click("xpath", sel, 10)

            # Warte, bis Eingabefelder erscheinen
            self.wait_for_element(by='id', selector="username", timeout=10)

            # Felder befüllen und abschicken
            username_field = driver.find_element(By.ID, "username")
            password_field = driver.find_element(By.ID, "password")

            username_field.send_keys(creds["user"])
            password_field.send_keys(creds["password"])
            password_field.send_keys(Keys.RETURN)

            self._logger.debug("Anmeldedaten eingegeben, Formular abgeschickt.")

            # prüfen, ob login erfolgreich war
            if not _is_logged_in():
                if not _wait_for_login():
                    raise RuntimeError("Login bei ariva.de fehlgeschlagen (manueller Login Timeout).")
            self._logger.info("Erfolgreich bei ariva.de eingeloggt.")



        super().login()
        driver = self.driver
        creds = self._credentials
        if not creds or "user" not in creds or "password" not in creds:
            self._logger.info("Keine Login-Daten konfiguriert – Login wird übersprungen.")
            return

        login_sucess = self._retry_func(func=_single_login, max_retries=5, wait_seconds=0.5)
        if not login_sucess:
            raise RuntimeError("Login bei ariva.de fehlgeschlagen nach mehreren Versuchen.")

    # ----------------------------------------------------------
    # Download
    # ----------------------------------------------------------
    def download_data(self) -> None:
        """
        Lädt Kursdaten (CSV) von allen in der Konfiguration definierten URLs.

        Für jede URL:
          - öffnet die Seite,
          - setzt optional die Währung auf EUR,
          - trägt Start- und Enddatum ein,
          - wählt Trenner ';',
          - startet den Download und wartet auf Abschluss.
        """
        try:
            super().download_data()

            for idx, (key, url) in enumerate(self._urls['kurse'].items(), start=1):
                self._logger.info(f"({idx}/{len(self._urls['kurse'])}) Navigiere zu {key}-Kursseite und lade Daten...")
                self.driver.get(url)


                # Optionales Dropdown für Währung
                try:
                    currency_dropdown = self.driver.find_element(By.CLASS_NAME, "waehrung")
                    select_currency = Select(currency_dropdown)
                    select_currency.select_by_value("EUR")
                    self._logger.debug("Währung auf EUR gesetzt.")
                except NoSuchElementException:
                    self._logger.debug("Kein Währungs-Dropdown vorhanden – wird übersprungen.")
                except Exception as e:
                    self._logger.warning(f"Währungsfeld gefunden, aber konnte nicht gesetzt werden: {e}")

                # Pflichtfelder ausfüllen
                start_date_field = self.driver.find_element(By.ID, "minTime")
                start_date_field.clear()
                start_date_field.send_keys(self.end_date.strftime('%d.%m.%Y'))

                end_date_field = self.driver.find_element(By.ID, "maxTime")
                end_date_field.clear()
                end_date_field.send_keys(self.start_date.strftime('%d.%m.%Y'))

                delimiter_field = self.driver.find_element(By.ID, "trenner")
                delimiter_field.clear()
                delimiter_field.send_keys(";")


                try:
                    # Download starten
                    xpath_sel =  "//input[@type='submit' and @value='Download']"
                    btn = self.wait_for_element("xpath", xpath_sel, timeout=15)
                    self.scroll_into_view(btn)
                    btn.click()
                    # download_button = self.driver.find_element(
                    #     By.XPATH, "//input[@type='submit' and @value='Download']"
                    # )
                    # download_button.click()
                    self._logger.debug("Download-Button geklickt, CSV wird heruntergeladen.")
                    # warten, bis die Datei heruntergeladen ist (maximal 30 Sekunden)
                    new_file = self._wait_for_new_file(timeout=30)
                    if new_file:
                        continue
                    else:
                        self._logger.warning(f"Kein Download erkannt für {key} innerhalb des Timeouts.")
                except TimeoutException:
                    self._logger.error(f"Download-Button nicht gefunden auf der Seite für {key}.")
                    continue

        except Exception as e:
            self._logger.error(
                f"Fehler beim Ausfüllen oder Absenden des Formulars für {key}",
                exc_info=True
            )


    # ----------------------------------------------------------
    # Verarbeitung
    # ----------------------------------------------------------
    def process_data(self) -> None:
        """
        Führt alle eingelesenen CSV-Dateien zu einem einheitlichen DataFrame zusammen.

        Für jede Datei:
          - Daten vorverarbeiten (Datumsformat, Zahlenkonvertierung)
          - WKN aus dem Dateinamen extrahieren
        Anschließend werden alle Daten zusammengeführt und in self.data gespeichert.
        """

        # ----------------------------------------------------------
        # processing helper
        # ----------------------------------------------------------
        def preprocess_data(df: pd.DataFrame) -> pd.DataFrame:
            """
            Bereinigt und konvertiert Datenspalten:
              - Datum in '%d.%m.%Y'-Format
              - numerische Spalten (Hoch, Tief, Schlusskurs) in float

            Args:
                df (pandas.DataFrame): Eingabedaten

            Returns:
                pandas.DataFrame: Bereinigte und formatierte Daten
            """
            df = df.copy()
            # Spaltennamen vereinheitlichen
            df.columns = [c.strip() for c in df.columns]

            # Datumskonvertierung
            date_col = next((c for c in df.columns if "Datum" in c or "date" in c.lower()), None)
            if date_col:
                try:
                    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
                    df[date_col] = df[date_col].dt.strftime("%d.%m.%Y")
                except Exception:
                    raise ValueError(f"Fehler bei der Datumsumwandlung in Spalte '{date_col}'")

            # Numerische Spalten bereinigen
            num_cols = [c for c in df.columns if any(k in c for k in ["Hoch", "Tief", "Schluss"])]
            for c in num_cols:
                try:
                    df[c] = df[c].astype(str).str.replace(",", ".").astype(float)
                except Exception:
                    raise ValueError(f"Fehler bei der Zahlenkonvertierung in Spalte '{c}'")

            # Ausgabe sortieren und Spaltenreihenfolge festlegen
            cols = [col for col in ["Datum", "Schlusskurs", "Hoch", "Tief"] if col in df.columns]
            return df[cols]

        def extract_wkn(filename: str) -> str:
            """
            Extrahiert die WKN (Wertpapierkennnummer) aus dem Dateinamen.

            Erwartetes Format: <prefix>_<WKN>_...

            Args:
                filename (str): Name der Datei

            Returns:
                str: erkannte WKN oder 'UNKNOWN'
            """
            try:
                parts = filename.split("_")
                for part in parts:
                    if part.isalnum() and len(part) in (6, 7):  # typische WKN-Länge
                        return part
                return "UNKNOWN"
            except Exception:
                return "UNKNOWN"

        super().process_data()

        if not isinstance(self.data, dict) or not self.data:
            self._logger.warning("Keine Daten zum Verarbeiten gefunden (self.data leer oder kein dict).")
            return

        merged_df = pd.DataFrame()

        for idx, (filename, df) in enumerate(self.data.items(), start=1):
            try:
                self._logger.debug(f"({idx}/{len(self.data)}) Verarbeite Datei: {filename}")

                processed = preprocess_data(df)
                processed["WKN"] = extract_wkn(filename)

                merged_df = pd.concat([merged_df, processed], ignore_index=True)

            except Exception as e:
                self._logger.error(f"Fehler beim Verarbeiten von {filename}: {e}", exc_info=True)
                continue

        if merged_df.empty:
            self._logger.warning("Kein gültiger Datensatz nach Verarbeitung erstellt.")
            return

        self.data = merged_df
        self._logger.info(f"Verarbeitung abgeschlossen – {len(merged_df)} Zeilen zusammengeführt.")


    # ----------------------------------------------------------
    # Banner-Handhabung
    # ----------------------------------------------------------
    def _handle_ad_banner(self) -> bool:
        """
        Schließt das Werbe-iFrame auf ariva.de, falls es sichtbar ist.

        Durchsucht alle iFrames nach dem 'Akzeptieren und weiter'-Button
        und klickt ihn. Schaltet dabei automatisch den Frame-Kontext um.

        Returns:
            bool: True, wenn ein Banner gefunden und geschlossen wurde, sonst False.
        """
        driver = self.driver
        closed = False

        try:
            # Warte kurz, ob überhaupt ein iFrame existiert
            wait_sec = 5
            WebDriverWait(driver, wait_sec).until(
                EC.presence_of_element_located((By.TAG_NAME, "iframe"))
            )

            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            self._logger.debug(f"Anzahl iFrames gefunden: {len(iframes)}")

            for idx, iframe in enumerate(iframes):
                try:
                    driver.switch_to.frame(iframe)
                    # Beispiel-XPath für den „Akzeptieren“-Button (ggf. anpassen)
                    accept_xpath = "//button[contains(., 'Akzeptieren') or contains(., 'weiter')]"
                    accept_button = driver.find_element(By.XPATH, accept_xpath)
                    if accept_button.is_displayed():
                        self.scroll_into_view(accept_button)
                        self.click_js(accept_button)
                        self._logger.debug(f"Werbebanner geschlossen im iFrame {idx}.")
                        closed = True
                        break
                    driver.switch_to.default_content()
                except NoSuchElementException:
                    driver.switch_to.default_content()
                    continue
                except Exception:
                    driver.switch_to.default_content()
                    continue

            driver.switch_to.default_content()
            if not closed:
                self._logger.info("Kein 'Akzeptieren'-Button in iFrames gefunden oder bereits geschlossen.")

        except TimeoutException:
            self._logger.debug("Kein iFrame für Werbung gefunden – kein Banner aktiv.")
        except Exception:
            self._logger.error("Fehler beim Suchen oder Schließen des Werbe-iFrames", exc_info=True)

        return closed


if __name__ == "__main__":
    print("Starte ArivaCrawler im Debug-Modus...")
    # with ArivaCrawler(logging_level="DEBUG") as crawler:
    #     crawler.login()
    #     crawler.download_data()
    #     crawler.process_data()
    #     crawler.save_data()
    # crawler = ArivaCrawler(logging_level='DEBUG')
    # crawler.login()
    # crawler.download_data()
    # crawler.close()