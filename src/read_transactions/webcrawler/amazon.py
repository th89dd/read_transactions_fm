# -*- coding: utf-8 -*-
"""
:author: Tim Häberlein
:version: 2.1
:date: 26.10.2025
:organisation: TU Dresden, FZM
"""
from __future__ import annotations
import sys
import re
import time
from typing import Any, Dict, List, Optional

import pandas as pd
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from read_transactions.webcrawler import WebCrawler

"""
AmazonCrawler (Privatkunde, Bestellungen)
----------------------------------------
- Login gem. amazon.md (E-Mail → Weiter → **Passkey immer abbrechen** → Passwort → optional 2FA)
- 2FA: Verfahrenwechsel über "Du hast den Code nicht erhalten?" und Radiobuttons (auth-SMS/WhatsApp/VOICE/TOTP)
- Bestellungen: Filter nach Jahr (select#time-filter), Pagination, pro order-card js-order-card Felder extrahieren:
  Bestelldatum, Gesamtbetrag, Verwendungszweck (Artikel), Lieferdatum, Bestellnr., Versandadresse.

Benötigte config.yaml:
----------------------
credentials:
  amazon:
    user: "max.mustermann@example.com"
    password: "••••••••"

urls:
  amazon:
    login: "https://www.amazon.de/ap/signin?openid.pape.max_auth_age=0&openid.return_to=https%3A%2F%2Fwww.amazon.de%2F%3Fref_%3Dnav_signin&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.assoc_handle=deflex&openid.mode=checkid_setup&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0"
    orders: "https://www.amazon.de/gp/css/order-history?ref_=nav_AccountFlyout_orders"

Beispiel:
---------
with AmazonCrawler(logging_level="DEBUG", otp_method="sms") as crawler:
    crawler.login()
    crawler.download_data()
    crawler.process_data()
    crawler.save_data()
"""

class AmazonCrawler(WebCrawler):
    """
    Crawler für Umsätze aus dem Zahlungsbereich von **amazon.de**.

    Dieser Crawler automatisiert den Login-Flow (inkl. **Passkey/WebAuthn-Abbruch**
    und Umgang mit einem **verdeckt eingeblendeten Passwortfeld**), navigiert zur
    Zahlungs-/Transaktionsübersicht und extrahiert dort die sichtbaren
    Umsatz-Einträge (Datum, Beschreibung, Betrag). Die rohen Einträge werden im
    Anschluss mit den Standard-Helfern der Basisklasse normalisiert.

    **Wichtige Merkmale**
    - Bricht ggf. angezeigte *Passkey/WebAuthn*-Dialoge zuverlässig ab und wechselt
    in die Passwort-Anmeldung.
    - Erkennt und bedient ein verdecktes Passwortfeld (setzt notfalls den Wert via JS).
    - Optionales 2FA-/OTP-Handling über :meth:`_verify_identity` mit mehreren
    Eingabe-/Bezugsvarianten ("prompt", "env", "file", "totp", "external", "none").
    - Scrollt die Zahlungsübersicht und liest alle sichtbaren Transaktionen in den
    Zeitraum ein.

    **Konfiguration (config.yaml)**
    ``credentials.amazon.user``
    Amazon-Login (E‑Mail).
    ``credentials.amazon.password``
    Amazon-Passwort.
    ``urls.amazon.login``
    Login-URL (robuster Fallback ist die längere OpenID-URL von Amazon).
    ``urls.amazon.transactions``
    URL der Zahlungs-/Transaktionsübersicht.


    Parameters (übernommen von :class:`WebCrawler`)
    ----------------------------------------------
    output_path : str, optional
    Verzeichnis, in dem Ausgabedateien gespeichert werden (Standard: ``"out"``).
    start_date : str | pandas.Timestamp | datetime.date | None, optional
    Startdatum (Format bei ``str``: ``"DD.MM.YYYY"``). Standard: ``heute``.
    end_date : str | pandas.Timestamp | datetime.date | None, optional
    Enddatum (Format bei ``str``: ``"DD.MM.YYYY"``).
    Standard: heute minus **6 Monate**.
    logging_level : str, optional
    Log-Level (z. B. ``"DEBUG"``, ``"INFO"``). Standard: ``"INFO"``.
    logfile : str | None, optional
    Pfad zu einer Logdatei. Wenn gesetzt, wird File-Logging aktiviert.
    browser : str, optional
    Zu verwendender Browser (z. B. ``"edge"`` oder ``"chrome"``). Standard: ``"edge"``.
    headless : bool, optional
    Headless-Modus aktivieren/deaktivieren. Standard: ``False``.
    user_agent : str | None, optional
    Benutzerdefinierter User-Agent für den WebDriver.

    opt_method : str | None, optional
    Bevorzugtes 2FA-Verfahren (``"authenticator"``, ``"sms"``, ``"whatsapp"``, ``"call"``).
    Standard: ``None`` (kein Wechsel, Standardverfahren verwenden).
    max_items_per_order : int, optional
    Maximale Anzahl Artikel-Titel pro Bestellung (Standard: ``5``).
    title_max_chars : int, optional
    Maximale Zeichenanzahl für den Verwendungszweck (Standard: ``120``).


    Attributes
    ----------
    driver : selenium.webdriver.Remote
    """

    def __init__(
            self,
            otp_method: Optional[str] = None,  # "authenticator" | "sms" | "whatsapp" | "call"
            max_items_per_order: int = 5,
            title_max_chars: int = 40,
            *args,
            **kwargs,
    ):
        super().__init__(name="amazon",*args, **kwargs)
        self._load_config()
        self.otp_method = (otp_method or "").strip().lower() or None
        self.max_items_per_order = max(1, int(max_items_per_order))
        self.title_max_chars = max(30, int(title_max_chars))

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------
    def login(self) -> None:
        """Login inkl. Passkey-Abbruch, verdecktem Passwortfeld & 2FA-Verfahrenswechsel"""
        super().login()
        driver = self.driver
        creds = self._credentials

        # self._handle_cookie_banner()

        # E-Mail eintragen (id=ap_email_login oder ap_email)
        self._set_username_if_present(creds["user"])  # aus config.yaml

        # Passkey-/WebAuthn-Dialog **immer** abbrechen
        aborted = self._abort_windows_passkey()
        if not aborted:
            # entweder kein Dialog erschienen oder Abbruch nicht möglich
            self._logger.debug("Kein Passkey-Dialog erkannt oder Abbruch nicht möglich.")

        # Passwortfeldfüllen & absenden
        self._fill_password_and_submit(creds["password"])  # aus config.yaml

        # 2FA ggf. umstellen & bestätigen
        self._handle_2fa_if_present()

        # 7) Erfolg prüfen (z. B. Konto- oder Bestelllink)
        login = self._wait_for_login(timeout=120)
        if not login:
            raise RuntimeError("Login nicht erfolgreich.")


    def _set_username_if_present(self, username: str) -> None:
        """Setzt den Benutzernamen, falls das Feld sichtbar ist."""
        email_ok = False
        for by, sel in (("id", "ap_email_login"), ("id", "ap_email"), ("css", "input[type='email']")):
            try:
                email = self.wait_for_element(by, sel, timeout=8)
                email.clear(); email.send_keys(username)
                email_ok = True
                break
            except TimeoutException:
                continue
        if not email_ok:
            raise RuntimeError("E-Mail-Feld nicht gefunden.")

        # Weiter klicken (id=continue oder aria-labelledby=continue-announce)
        weiter = False
        for by, sel in (
                ("xpath", "//input[@type='submit' and @aria-labelledby='continue-announce']"),
                ("id", "continue"),
                ("css", "#continue input[type='submit']"),
        ):
            try:
                self.wait_clickable_and_click(by, sel, timeout=5)
                weiter = True
                break
            except TimeoutException:
                continue
        if not weiter:
            raise RuntimeError("Weiter-Button nach E-Mail nicht gefunden.")
        self._logger.debug("Benutzername erfolgreich eingetragen.")

    def _abort_windows_passkey(self, tries: int = 10, timeout: int = 10) -> bool:
        """
        Versucht, einen nativen Windows-Passkey/Hello/WebAuthn-Dialog zu schließen.
        Priorität: pywinauto -> ctypes SendInput -> pyautogui/keyboard -> ESC an Browser.
        Gibt True zurück, wenn mind. ein Abbruchversuch gesendet wurde.
        """
        def _press_esc_via_ctypes() -> bool:
            if sys.platform != "win32":
                return False
            try:
                import ctypes
                from ctypes import wintypes
                PUL = ctypes.POINTER(ctypes.c_ulong)
                class KEYBDINPUT(ctypes.Structure):
                    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                                ("dwExtraInfo", PUL)]
                class INPUT(ctypes.Structure):
                    _fields_ = [("type", wintypes.DWORD), ("ki", KEYBDINPUT), ("padding", wintypes.BYTE * 8)]
                SendInput = ctypes.windll.user32.SendInput
                INPUT_KEYBOARD = 1; KEYEVENTF_KEYUP = 0x0002; VK_ESCAPE = 0x1B
                def _key(vk, flags=0):
                    return INPUT(type=INPUT_KEYBOARD,
                                 ki=KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags, time=0, dwExtraInfo=None))
                arr = (INPUT * 2)(_key(VK_ESCAPE, 0), _key(VK_ESCAPE, KEYEVENTF_KEYUP))
                return SendInput(2, ctypes.byref(arr), ctypes.sizeof(INPUT)) == 2
            except Exception:
                return False

        def _get_active_window_info() -> tuple[int|None, str, str]:
            """
            Returns (hwnd, title, class_name) of the foreground window.
            On non-Windows returns (None, "", "").
            """
            if sys.platform != "win32":
                return None, "", ""
            import ctypes
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return None, "", ""
            # title
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            # class
            cls_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls_buf, 256)
            return hwnd, buf.value or "", cls_buf.value or ""

        def _is_windows_security_active() -> bool:
            """
            Heuristic: detects Windows Security / Hello / Security Key dialogs
            by foreground window title.
            """
            _, title, cls = _get_active_window_info()
            needles = (
                "Windows-Sicherheit", "Windows Sicherheit", "Windows Security",
                "Windows Hello", "Sicherheitsschlüssel", "Security Key"
            )
            title_l = title.lower()
            if any(n.lower() in title_l for n in needles):
                return True
        # def _close_passkey_window():
        #     """Versucht, das Passkey-Fenster via ESC zu schließen."""
        time.sleep(1)  # kurz warten, bis Dialog da ist
        window_was_active = False
        sleep = timeout / max(tries, 1)
        if sys.platform == "win32":
            for attempt in range(tries):
                # prüfe ob Dialog ("Windows-Sicherheit" o.ä.) im Vordergrund ist
                if _is_windows_security_active():
                    window_was_active = True
                    self._logger.debug(f"Passkey-Abbruchversuch {attempt + 1}/{tries} (Windows)...")

                    # Variante A: ctypes SendInput
                    if _press_esc_via_ctypes():
                        self._logger.debug("Passkey-Abbruch via ctypes SendInput gesendet.")
                        time.sleep(1)
                elif window_was_active:
                    break
                time.sleep(sleep)
            else:
                self._logger.debug("Passkey-Abbruchversuche (Windows) erschöpft.")
                return False
            return True if window_was_active else False
        if sys.platform in ("linux", "darwin"):
            self._logger.warning("Passkey-Abbruch unter Linux/macOS nicht implementiert.")
            return True
        return False

    def _fill_password_and_submit(self, password: str) -> None:
        """Füllt das Passwortfeld und sendet das Formular ab."""
        pw = self.wait_for_element("id", "ap_password", timeout=10)
        if not (pw.get_attribute("value") or "").strip():
            pw.clear(); pw.send_keys(password)
        # weiter
        weiter = False
        for by, sel in (("id", "signInSubmit"), ("xpath", "//input[@id='signInSubmit']")):
            try:
                self.wait_clickable_and_click(by, sel, timeout=3)
                weiter = True
                break
            except TimeoutException:
                continue
        if not weiter:
            raise RuntimeError("Anmelden-Button nach Passwort nicht gefunden.")
        self._logger.debug("Passwort erfolgreich eingetragen und Formular abgesendet.")

    def _handle_2fa_if_present(self) -> None:
        """Stellt OTP-Verfahren (optional) um & bestätigt Code (gem. amazon.md)."""
        def _choose_otp_method():
            try:
                try:
                    self.wait_clickable_and_click("id", "auth-get-new-otp-link", timeout=4)
                except TimeoutException:
                    self._logger.warning("'Neuen Code anfordern'-Link nicht gefunden.")
                    return
                time.sleep(0.4)
                # Radiobuttons innerhalb fieldset[data-a-input-name='otpDeviceContext']
                wanted_map = {
                    "sms": ["SMS"],
                    "whatsapp": ["WhatsApp"],
                    "call": ["VOICE", "anrufen"],
                    "authenticator": ["TOTP", "Authenticator", "Einmalkennwort"],
                }
                wanted = wanted_map.get(self.otp_method, [])
                radios = self.driver.find_elements(By.XPATH, "//div[@data-a-input-name='otpDeviceContext']//label")
                chosen = False
                for lab in radios:
                    t = (lab.text or "").strip()
                    if any(w.lower() in t.lower() for w in wanted):
                        self.scroll_into_view(lab)
                        self.click_js(lab)
                        chosen = True
                        self._logger.info(f"2FA-Verfahren gewählt: {t!r}")
                        break
                if chosen:
                    try:
                        self.wait_clickable_and_click("id", "auth-send-code", timeout=5)
                        # Eingabefeld taucht erneut auf (gleiche id)
                        self.wait_for_element("id", "auth-mfa-otpcode", timeout=10)
                    except TimeoutException:
                        self._logger.warning("'OTP senden' nicht gefunden.")
            except Exception:
                self._logger.error("Fehler beim Wechsel des 2FA-Verfahrens.", exc_info=True)

        def _get_code_from_prompt() -> str:
            return input("Bitte den 2FA/OTP-Code für Amazon eingeben: ").strip()

        # ----------------------------------------------------------------------------
        # --- Hauptlogik ---
        # ----------------------------------------------------------------------------
        try:
            self.wait_for_element("id", "auth-mfa-otpcode", timeout=5)
        except TimeoutException:
            self._logger.debug("Keine 2FA erkannt.")
            return

        self._logger.info("2FA erkannt – max. 3 Versuche – OTP-Eingabe erforderlich...")
        self._logger.info("Kann bei Eingabe eingabe eines keys (sms, whatsapp, call, authenticator, retry) geändert werden.")
        for attempt in range(3):
            if self.otp_method:
                _choose_otp_method()

            code = _get_code_from_prompt()
            if code.lower() in ("sms", "whatsapp", "call", "authenticator"):
                self.otp_method = code.lower()
                _choose_otp_method()
                self._logger.info(f"Wechsel des 2FA-Verfahrens zu: {self.otp_method}")
                code = _get_code_from_prompt()
            elif code == 'retry' or len(code) != 6:
                self._logger.info("Erneuter Versuch der 2FA.")
                continue
            try:
                code_input = self.wait_for_element("id", "auth-mfa-otpcode", timeout=5)
                code_input.send_keys(code)
                # wait for verify button and click
                self.wait_clickable_and_click("id", "auth-signin-button", timeout=5)
                return
            except Exception:
                self._logger.error("Fehler beim Eintragen des OTP-Codes.", exc_info=True)
                raise RuntimeError("Fehler beim Eintragen des OTP-Codes.")
        self._logger.debug("2FA-Versuche erschöpft.")

    def _wait_for_login(self, timeout: int = 120) -> bool:
        """
        Wartet, bis der Login abgeschlossen ist (Bestellübersicht geladen).

        :param timeout: Maximale Wartezeit in Sekunden.
        """

        login_successful = False
        start_time = time.time()
        while (time.time() - start_time < timeout) and not login_successful:
            try:
                self.wait_for_element(
                    "xpath",
                    "//a[@id='nav-orders' or contains(@href,'your-orders') or contains(@href,'order-history')]",
                    timeout=14,
                )
                login_successful = True
                self._logger.info("Login erfolgreich abgeschlossen.")
            except TimeoutException:
                time.sleep(1)
                self._logger.info(
                    "Es scheint ein Fehler im Login-Prozess aufgetreten zu sein. Evtl. Browser-Fenster prüfen...")
                self._logger.info(
                    f"Warte auf Login-Abschluss... (timout in {round(timeout-(time.time()-start_time), 2)} Sekunden)")
        if not login_successful:
            return False
        return True

    # ------------------------------------------------------------------
    # Download & Parsing der Bestellungen
    # ------------------------------------------------------------------
    def download_data(self) -> None:
        super().download_data()
        driver = self.driver
        url = self._urls.get("transactions")
        driver.get(url)

        # Jahreszahlen bestimmen
        start_year = self.start_date.year
        end_year = self.end_date.year
        # Liste der Jahre von max -> min (absteigend, inkl. beider Grenzwerte)
        years = list(range(max(start_year, end_year), min(start_year, end_year) - 1, -1))
        years = sorted(set(years), reverse=True)

        all_rows: List[Dict[str, Any]] = []
        for year in years:
            if not self._select_year(year):
                self._logger.debug(f"Jahr {year} nicht gefunden – weiter.")
                continue

            page = 1
            while True:
                rows = self._parse_orders_on_page(
                    max_items=self.max_items_per_order,
                    max_item_chars=self.title_max_chars,
                    order_year=year
                )
                self._logger.info(f"{len(rows)} Bestellungen (Jahr {year}, Seite {page}).")
                all_rows.extend(rows)
                try:
                    if pd.to_datetime(rows[-1]["Bestelldatum"], dayfirst=True) < self.end_date:
                        self._logger.info("Enddatum erreicht – Abbruch.")
                        all_rows = all_rows[:-1]  # letzte Bestellung entfernen
                        break
                except Exception:
                    self._logger.debug(f"Fehler beim Prüfen des Enddatums für {rows[-1]}", exc_info=True)
                    pass
                if not self._go_next_page():
                    break
                page += 1

        df = pd.DataFrame(all_rows)
        self.data = df

    def process_data(self) -> None:
        # super().process_data()
        self._state = "process_data"

        if not isinstance(self.data, pd.DataFrame) or self.data.empty:
            self._logger.warning("Keine Daten zum Verarbeiten vorhanden.")
            return

        self.data = self._normalize_dataframe(self.data, remove_nan=True)
        self.data['Betrag'] = self.data['Betrag']*-1  # Amazon-Bestellungen sind Ausgaben
        self._logger.info(f"{len(self.data)} Amazon-Bestellungen verarbeitet.")

    # ------------------------------------------------------------------
    # Interne Helfer (Bestellungen)
    # ------------------------------------------------------------------
    def _select_year(self, year: int) -> bool:
        """Wählt das Jahr im Dropdown (select#time-filter)."""
        driver = self.driver
        # Variante A: echtes <select id="time-filter">
        try:
            sel = driver.find_element(By.ID, "time-filter")
            self.scroll_into_view(sel)
            sel.click()
            try:
                opt = sel.find_element(By.XPATH, f".//option[@value='year-{year}' or contains(., '{year}')]")
                opt.click()
                time.sleep(1.0)
                return True
            except NoSuchElementException:
                pass
        except Exception:
            pass
        # Variante B: Amazon a-dropdown
        try:
            prompt = self.wait_for_element("xpath", "//span[contains(@class,'a-dropdown-prompt')]", timeout=5)
            self.scroll_into_view(prompt)
            self.click_js(prompt)
            time.sleep(0.3)
            options = self.driver.find_elements(By.XPATH, "//a[contains(@class,'a-dropdown-link')]")
            for a in options:
                txt = (a.text or "").strip()
                if str(year) in txt:
                    self.click_js(a)
                    time.sleep(1.0)
                    return True
        except TimeoutException:
            pass
        return False

    def _go_next_page(self) -> bool:
        try:
            nxt = self.wait_for_element(
                "xpath",
                "//ul[contains(@class,'a-pagination')]//li[contains(@class,'a-last')]/a",
                timeout=4,
            )
            self.scroll_into_view(nxt)
            self.click_js(nxt)
            time.sleep(0.7)
            return True
        except TimeoutException:
            return False

    def _parse_orders_on_page(self, max_items: int = 10, max_item_chars: int = 30, order_year: int = 2025) -> List[Dict[str, Any]]:
        """Parst alle Bestellungen auf der aktuellen Seite."""
        # -----------------------------
        # Regex-Extraktoren
        # -----------------------------
        _DATE_PATTERNS = [
            # e.g. "BESTELLUNG AUFGEGEBEN\n24. Oktober 2025"
            r"BESTELLUNG AUFGEGEBEN\s+(\d{1,2}\.\s*[A-Za-zÄÖÜäöü]+(?:\s+\d{4})?)",
            # e. g. audibe
            r"Abonnement abgerechnet am\s+(\d{1,2}\.\s*[A-Za-zÄÖÜäöü]+(?:\s+\d{4})?)",
            # r"Bestellt am\s+(\d{1,2}\.\s*[A-Za-zÄÖÜäöü]+(?:\s+\d{4})?)",
            # r"Bestelldatum\s+(\d{1,2}\.\s*[A-Za-zÄÖÜäöü]+(?:\s+\d{4})?)",
            # nur datum mit jahr
            r"(\d{1,2}\.\s*[A-Za-zÄÖÜäöü]+(?:\s+\d{4})?)",
            # numeric fallback
            r"(\d{1,2}\.\d{1,2}\.\d{4})",
        ]
        _AMOUNT_PATTERNS = [
            # "SUMME\n108,00 €"
            r"SUMME\s+([0-9\.\s]*\d{1,3}(?:[\.,]\d{2})\s*€)",
            r"(?:Gesamtsumme|Summe|Total)\s+([0-9\.\s]*\d{1,3}(?:[\.,]\d{2})\s*€)",
            r"([0-9\.\s]*\d{1,3}(?:[\.,]\d{2})\s*€)",
        ]
        _ORDERNO_PATTERNS = [
            r"BESTELLNR\.?\s*([A-Za-z0-9\-\/]+)",
            r"Bestellnummer\s*([A-Za-z0-9\-\/]+)",
            r"Order\s*#?\s*([A-Za-z0-9\-\/]+)",
        ]
        _DELIVERY_PATTERNS = [
            # "Zugestellt: 25. Oktober" (year optional)
            r"Zugestellt:\s*([0-9]{1,2}\.\s*[A-Za-zÄÖÜäöü]+(?:\s+\d{4})?)",
            r"Lieferdatum[^\dA-Za-zÄÖÜäöü]*(\d{1,2}\.\s*[A-Za-zÄÖÜäöü]+(?:\s+\d{4})?)",
            r"(?:Zugestellt|Geliefert|Lieferung am)[^\d]*(\d{1,2}\.\d{1,2}\.\d{4})",
        ]


        def _extract_amount(text: str) -> Optional[str]:
            """Extrahiert den Betrag aus dem Text."""
            for pat in _AMOUNT_PATTERNS:
                m = re.search(pat, text, flags=re.IGNORECASE)
                if m:
                    return m.group(1).replace(" ", "")
            return None

        def _extract_order_number(text: str) -> Optional[str]:
            """Extrahiert die Bestellnummer aus dem Text."""
            for pat in _ORDERNO_PATTERNS:
                m = re.search(pat, text, flags=re.IGNORECASE)
                if m:
                    return m.group(1)
            return None

        def _extract_date(text: str) -> str | None:
            """Extrahiert das Bestelldatum aus dem Text."""
            for pat in _DATE_PATTERNS:
                m = re.search(pat, text, flags=re.IGNORECASE)
                if m:
                    raw = m.group(1).strip()
                    return self._coerce_date_string_de(raw) if re.search(r"[A-Za-zÄÖÜäöü]", raw) else raw
            return None

        def _extract_delivery_date(text: str, default_year: int | None = None) -> str | None:
            """Extrahiert das Lieferdatum."""
            for pat in _DELIVERY_PATTERNS:
                m = re.search(pat, text, flags=re.IGNORECASE)
                if m:
                    raw = m.group(1).strip()
                    return self._coerce_date_string_de(raw, default_year=default_year) \
                        if re.search(r"[A-Za-zÄÖÜäöü]", raw) else raw
            return None

        def _extract_shipping_address_from_text(text: str) -> str:
            """Extrahiert die Versandadresse aus dem Text."""
            # capture block between VERSANDADRESSE and the next heading / blank / BESTELLNR.
            m = re.search(r"VERSANDADRESSE\s+([\s\S]*?)(?:\n\n|BESTELLNR\.|Bestelldetails anzeigen|Rechnung|Zugestellt:)", text)
            return (m.group(1).strip() if m else "")

        def _extract_items_from_text(text: str, max_items: int = 10, max_item_chars: int = 40) -> str:
            """Extrahiert Artikel-Titel aus dem Text."""
            # Versandadresse-Block entfernen, damit z. B. der Empfänger nicht als Item durchrutscht
            text_wo_addr = re.sub(
                r"VERSANDADRESSE[\s\S]*?(?:\n\n|BESTELLNR\.|Bestelldetails anzeigen|Rechnung)",
                "",
                text,
                flags=re.MULTILINE
            )
            lines = [ln.strip() for ln in text_wo_addr.splitlines()]
            # Muster, die wir NICHT als Items wollen
            date_word = re.compile(r"^\d{1,2}\.\s*[A-Za-zÄÖÜäöü]+(?:\s+\d{4})?\s*$", re.IGNORECASE)  # 24. Oktober 2025 | 25. Oktober
            date_num  = re.compile(r"^\d{1,2}\.\d{1,2}\.\d{4}\s*$")                                   # 24.10.2025
            amount    = re.compile(r"^[0-9\.\s]*\d{1,3}(?:[.,]\d{2})\s*€\s*$")                        # 108,00 €
            heading_uc= re.compile(r"^[A-ZÄÖÜ\s\.]{4,}$")                                            # GROB: reine Großbuchstaben-Überschriften
            ignore_prefix = (
                "BESTELLUNG AUFGEGEBEN", "SUMME", "BESTELLNR.", "Bestelldetails anzeigen",
                "Rechnung", "Zugestellt:", "Die Sendung", "Artikel zurück", "Artikel zurücksenden",
                "Nochmals kaufen", "Deinen Artikel anzeigen", "Produktsupport erhalten",
                "Lieferung verfolgen", "Geschenkbestätigung teilen", "Verkäufer-Feedback abgeben",
                "Schreib eine Produktrezension", "Zeitraum für Rückgabe", 'Eine Frage',
                "Automatisch geliefert", "Dein Spar-Abo", "Bestellung bearbeiten",
                "Rücksendung", "Deine Rücksendung", "Wann erhalte ich meine Gutschrift", 'Lieferdatum',
                'Ersatz bestellt', 'Ihr Ersatz wurde bestellt', 'Problem bei', 'Paket wurde'
            )

            items: list[str] = []
            for ln in lines:
                if not ln:
                    continue
                # Überschriften & bekannte Prefixe ausschließen
                if ln.startswith(ignore_prefix) or heading_uc.match(ln):
                    continue
                # reine Datums- oder Betragszeilen ausschließen
                if date_word.match(ln) or date_num.match(ln) or amount.match(ln):
                    continue
                # sehr kurze/technische Zeilen ausschließen
                # if len(ln) < 9 or ln.endswith(":"):
                #     continue
                # Heuristik: Produktzeilen sind meist mehrwortig
                # if " " not in ln:
                #     continue
                items.append(ln[:max_item_chars].strip())

            # Dedupe (Reihenfolge erhalten)
            out = list(dict.fromkeys(items))  # deduplication preserving order
            if len(out) > max_items:
                out = out[:max_items]
            # elemente als string mit | getrennt zurückgeben
            return " | ".join([it for it in out])

        # alle elemente mit class 'order-card js-order-card' laden
        selector = "//div[contains(@class,'order-card') and contains(@class,'js-order-card')]"
        self.wait_for_element('xpath', selector, timeout=10)
        cards = self.driver.find_elements(By.XPATH, selector)
        rows: List[Dict[str, Any]] = []

        # jedes element parsen
        reached_end_date = False
        for card in cards:
            try:
                text = card.text or ""
                bestelldatum = _extract_date(text)
                try:
                    if pd.to_datetime(bestelldatum, dayfirst=True) < self.end_date:
                        reached_end_date = True  # element muss hier eingeschlossen werden, da erneute Prüfung nach dem Loop
                except Exception:
                    pass
                betrag = _extract_amount(text)
                bestellnr = _extract_order_number(text)
                lieferdatum = _extract_delivery_date(text, default_year=order_year)
                lieferadresse = _extract_shipping_address_from_text(text)
                verwendungszweck = _extract_items_from_text(text, max_items=max_items, max_item_chars=max_item_chars)

                rows.append({
                    "Bestelldatum": bestelldatum or "",
                    "Betrag": betrag or "",
                    "Verwendungszweck": verwendungszweck,
                    "Lieferdatum": lieferdatum or "",
                    "Bestellnr": bestellnr or "",
                    "Versandadresse": lieferadresse,
                    "Quelle": "txt_parser",
                })
                if reached_end_date:
                    break
            except Exception:
                self._logger.debug("Fehler beim Parsen einer Bestellkarte.", exc_info=True)
                continue
        return rows

    def _parse_orders_on_page_by_dom(self, max_items: int = 10, max_item_chars: int = 30, order_year: int = 2025) -> List[Dict[str, Any]]:
        """
        Parsed ausschließlich über den DOM alle Bestell-Karten der **aktuellen Seite**.
        Keine Nutzung von `card.text` oder Regex – nur gezielte DOM-Selektoren.

        Erfasst je Karte:
          - Bestelldatum (Label → erstes folgendes Element)
          - Betrag/Summe (Label → erstes folgendes Element)
          - Bestellnummer (Label → erstes folgendes Element)
          - Lieferinfo (Knoten, der mit 'Zugestellt'/'Geliefert' beginnt oder 'Lieferung am' enthält)
          - Versandadresse (Label → folgender Block)
          - Items/Verwendungszweck (Produktlinks zu /dp/ oder /gp/product/, dedupliziert, limitiert)

        Returns:
            list[dict]: Eine Liste von Datensätzen (je Karte ein Dict).
        """
        # alle elemente mit class 'order-card js-order-card' laden
        selector = "//div[contains(@class,'order-card') and contains(@class,'js-order-card')]"
        self.wait_for_element('xpath', selector, timeout=10)
        cards = self.driver.find_elements(By.XPATH, selector)
        rows: List[Dict[str, Any]] = []

        selectors = {
            "bestelldatum": (".//li[contains(@class,'order-header__header-list-item')]"
                             "[.//span[normalize-space()='Bestellung aufgegeben' or normalize-space()='BESTELLUNG AUFGEGEBEN' "
                             " or normalize-space()='Abonnement abgerechnet am']]"
                             "/div[contains(@class,'a-row')][2]"
                             "/span[contains(@class,'a-size-base') and contains(@class,'a-color-secondary')]"
                             ),
            "betrag": (".//span[normalize-space()='Summe' or normalize-space()='SUMME']"
                       "/parent::div/following-sibling::div[1]"
                       "//span[contains(@class,'a-size-base') and contains(@class,'a-color-secondary')]"
                       ),
            "bestellnr": (".//span[normalize-space()='Bestellnr.' or normalize-space()='Bestellnummer' "
                          "or normalize-space()='Order #']/following-sibling::span[1]"
                          ),
            "lieferdatum": (".//div[contains(@class,'yohtmlc-shipment-status-primaryText')]"
                            "//span[contains(@class,'delivery-box__primary-text')]"
                            ),
            "versandadresse": (".//div[contains(@class,'yohtmlc-recipient')]//a[contains(@class,'a-popover-trigger') "
                               "and contains(@class,'insert-encrypted-trigger-text')]"
                               ),
        }
        for card in cards:
            # pro Karte parsen
            try:
                data_dict = {}
                for key, sel in selectors.items():
                    try:
                        elem = card.find_element(By.XPATH, sel)
                        val = (elem.text or "").strip()
                    except NoSuchElementException:
                        val = ""
                    data_dict[key] = val
                # items extrahieren
                selector =  (".//a[contains(@class,'a-link-normal') and "
                             "(contains(@href,'/dp/') or contains(@href,'/gp/product/'))]")

                items = card.find_elements(By.XPATH, selector)
                verwendungszweck = []
                for item in items:
                    verwendungszweck.append(item.accessible_name[:max_item_chars] or "")
                if len(verwendungszweck) > max_items:
                    verwendungszweck = verwendungszweck[:max_items]
                data_dict["verwendungszweck"] = list(dict.fromkeys(verwendungszweck))  # dedupe, order-preserving
                data_dict["quelle"] = "dom_parser"
                rows.append(data_dict)
            except Exception:
                self._logger.debug("Fehler beim Parsen einer Bestellkarte (DOM).", exc_info=True)
                continue

        return rows

    @staticmethod
    def _coerce_date_string_de(s: str, default_year: int | None = None) -> str:
        """
        Turns '24. Oktober 2025' or '25. Oktober' into '24.10.2025'.
        If year is missing, uses default_year or current year.
        """
        _MONTHS_DE = {
            "januar":1, "jan":1,
            "februar":2, "feb":2,
            "märz":3, "maerz":3, "mrz":3,
            "april":4, "apr":4,
            "mai":5,
            "juni":6, "jun":6,
            "juli":7, "jul":7,
            "august":8, "aug":8,
            "september":9, "sep":9, "sept":9,
            "oktober":10, "okt":10,
            "november":11, "nov":11,
            "dezember":12, "dez":12,
        }
        s = s.strip()
        m = re.match(r"(\d{1,2})\.\s*([A-Za-zÄÖÜäöü]+)(?:\s+(\d{4}))?", s)
        if not m:
            return s
        day = int(m.group(1))
        mon = (m.group(2) or "").lower()
        mon = (mon.replace("ä","ae").replace("ö","oe").replace("ü","ue").replace("ß","ss"))
        year = int(m.group(3)) if m.group(3) else (default_year or int(time.strftime("%Y")))
        month_num = _MONTHS_DE.get(mon)
        if not month_num:
            for k,v in _MONTHS_DE.items():
                if mon.startswith(k):
                    month_num = v; break
        if not month_num:
            return s
        return f"{day:02d}.{month_num:02d}.{year:04d}"


if __name__ == "__main__":
    print("Test Funktion für AmazonCrawler")
    end = pd.Timestamp.now() - pd.DateOffset(days=30)
    with AmazonCrawler(logging_level="DEBUG", otp_method="sms", end_date=end) as crawler:
        crawler.login()
        crawler.download_data()
        crawler.process_data()
        crawler.save_data()

    # crawler = AmazonCrawler(logging_level="DEBUG", otp_method="sms", end_date='26.10.2024')
    # crawler.login()

    # crawler.download_data()

    # crawler.process_data()
    # crawler.save_data()
    # crawler.close()

    # crawler._fill_password_and_submit(crawler._credentials["password"])


