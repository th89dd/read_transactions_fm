# -*- coding: utf-8 -*-
"""
:author: Tim Häberlein
:version: 1.0
:date: 21.10.2025
:organisation: TU Dresden, FZM

WebDriverFactory
----------------
Kapselt die Erstellung und Konfiguration von Selenium WebDriver-Instanzen.

Unterstützte Browser:
- Edge
- Chrome
- Firefox

Verwendung:
    from read_transactions.webcrawler.webdriver import WebDriverFactory

    driver = WebDriverFactory.create(
        browser="chrome",
        headless=True,
        download_dir="/tmp",
        user_agent="MyCustomAgent/1.0"
    )
"""

import os
from selenium import webdriver


class WebDriverFactory:
    """Erzeugt und konfiguriert Selenium WebDriver-Instanzen."""

    @staticmethod
    def create(
            browser: str = "edge",
            headless: bool = False,
            download_dir: str = os.getcwd(),
            user_agent: str | None = None,
            extra_args: list[str] | None = None,
    ) -> webdriver.Remote:
        """
        Erzeugt eine WebDriver-Instanz für den gewünschten Browser.

        Args:
            browser: Name des Browsers ("edge", "chrome", "firefox").
            headless: Aktiviert Headless-Modus (falls unterstützt).
            download_dir: Zielverzeichnis für Downloads.
            user_agent: Optionaler User-Agent-String.
            extra_args: Liste zusätzlicher Argumente für den Browser.

        Returns:
            webdriver.Remote: Eine konfigurierte Selenium-WebDriver-Instanz.

        Raises:
            ValueError: Wenn ein nicht unterstützter Browsername übergeben wird.
        """
        browser = browser.lower()
        extra_args = extra_args or []

        if browser == "edge":
            options = webdriver.EdgeOptions()
            options.add_argument("--log-level=3")
            options.add_argument("--disable-blink-features=AutomationControlled")
            # options.add_argument("--start-minimized")
            if headless:
                options.add_argument("--headless=new")
            if user_agent:
                options.add_argument(f"--user-agent={user_agent}")
            for arg in extra_args:
                options.add_argument(arg)
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            options.add_experimental_option("prefs", {
                "download.default_directory": download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": False,
            })
            return webdriver.Edge(options=options)

        elif browser == "chrome":
            options = webdriver.ChromeOptions()
            options.add_argument("--log-level=3")
            options.add_argument("--disable-blink-features=AutomationControlled")
            # options.add_argument("--start-minimized")
            if headless:
                options.add_argument("--headless=new")
            if user_agent:
                options.add_argument(f"--user-agent={user_agent}")
            for arg in extra_args:
                options.add_argument(arg)
            options.add_experimental_option("prefs", {
                "download.default_directory": download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": False,
            })
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            return webdriver.Chrome(options=options)

        elif browser == "firefox":
            options = webdriver.FirefoxOptions()
            # options.add_argument('--start-minimized')
            if headless:
                options.add_argument("-headless")
            profile = webdriver.FirefoxProfile()
            profile.set_preference("browser.download.folderList", 2)
            profile.set_preference("browser.download.dir", download_dir)
            profile.set_preference("browser.download.manager.showWhenStarting", False)
            profile.set_preference("browser.helperApps.neverAsk.saveToDisk",
                                   "text/csv,application/vnd.ms-excel,application/octet-stream")
            if user_agent:
                profile.set_preference("general.useragent.override", user_agent)
            return webdriver.Firefox(options=options, firefox_profile=profile)

        else:
            raise ValueError(f"Unsupported browser: {browser}")
