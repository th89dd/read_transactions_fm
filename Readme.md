<!-- docs:summary-start -->
![version](https://img.shields.io/badge/version-2.2.0-blue.svg)
![date](https://img.shields.io/badge/date-2025--11--05-green.svg)
![status](https://img.shields.io/badge/status-beta-yellow.svg)
![python](https://img.shields.io/badge/python-3.12-blue.svg)


# Read_Transactions für Finanzmanager

**read_transactions** – python Paket zum automatischen Abruf von Finanztransaktionen für den Finanzmanager.

Aktuell unterstützt:
- **Aktienkurse von Ariva**
- **Umsätze von Trade Republic**
- **Umsätze von American Express**
- **Umsätze von Amazon Visa (Zinia)**
- **Bestellungen von Amazon.de** (mit integration in Amazon Visa)
- **Umsätze von PayPal** (Beta)

Hier findest du die **[vollständige Dokumentation](https://th89dd.github.io/read_transactions_fm/)** des CLI-Interfaces und der Klassen.

Um schnell loszulegen, siehe den Abschnitt [Getting Started](#-getting-started-empfohlene-nutzung).

Für Fragen, Anmerkungen oder Probleme könnt ihr gern eine Diskussion im [GitHub-Repository](https://github.com/th89dd/read_transactions_fm/discussions) eröffnen. 

***

Diese Scriptsammlung dient dazu, Transaktionen via „WebCrawler“\
von verschiedenen Finanzdienstleistern automatisiert abzurufen und\
anschließend in ein einheitliches CSV-Format zu überführen,\
um diese z. B. im **Finanzmanager** zu importieren.

Alle abgeholten Umsätze werden nach Dienstleister sortiert im Ordner [`out`](out) gespeichert.\
Diese CSV-Dateien können anschließend im Finanzmanager über\
**Datei → Export/Import → Datenimport → Umsätze** eingelesen werden.\
Zur Vereinfachung können Importvorlagen genutzt werden – eine Beispielvorlage liegt unter [Vorlagen.dat](https://github.com/th89dd/read_transactions_fm/releases/download/v2.1.1/Vorlagen.dat).


<!-- docs:summary-end -->
***
***

## Content
1. [Getting-Started](#-getting-started-empfohlene-nutzung)
2. [CLI-Interface](#-cli-kommandos)
2. [Beispiele](#-beispiel-workflows)
3. [Installation](#installation)
4. [Für Entwicklung](#dev-section)
   1. [TODO](#todos)
   2. [Nützliche Kommandos](#usefull-commands)
5. [Versionshistorie](#versionshistorie)
6. [Lizenz](#lizenz)

***
<!-- docs:getting_started-start -->
## 🌟 Getting Started (empfohlene Nutzung)

Der einfachste Weg, das Tool zu verwenden, ist über das **vorkompilierte CLI-Programm**:

1. **Download der Windows-EXE**\
   Lade die Datei `readtx.exe` von der [Release-Seite](https://github.com/th89dd/read_transactions_fm/releases) herunter\
   und lege sie z. B. in einen eigenen Ordner (z. B. `C:\Tools\readtx`).

2. **Start über die Kommandozeile (CLI)**\
   Öffne die Eingabeaufforderung (`cmd`) oder PowerShell und rufe auf:

   ```bash
   readtx list
   ```

   Damit siehst du alle verfügbaren Crawler (z. B. `ariva`, `amex`, `amazon_visa`, `trade_republic`).

3. **Konfiguration anlegen**\
   Erstelle deine persönliche Konfigurationsdatei:

   ```bash
   readtx config init
   ```

   Dadurch wird automatisch eine Beispiel-`config.yaml` unter\
   `%USERPROFILE%\.config\read_transactions\config.yaml` erstellt.\
   Trage dort deine Zugangsdaten (Benutzername/Passwort) ein oder nutze z. B. für amazon_visa:
    
   ```bash
   readtx config set amazon_visa --user <USERNAME> --pwd <PASSWORT>
   ```
   
    >**Hinweis**:  
    Wenn du die Zugangsdaten über das CLI-Tool setzt, werden diese verschlüsselt in der Config-Datei gespeichert.
   

4. **Crawler starten**:
    
    Starte den gewünschten Crawler mit dem `run`-Befehl.
    
    Zum Beispiel den Amazon Visa-Crawler:
    ```bash
    readtx run amazon_visa
    ```
   
    Standardmäßig werden die Umsätze der letzten 6 Monate abgerufen.  
    Dabei werden die Umsätze mit den Bestellungen von Amazon.de abgeglichen und gespeichert 
    (``Details=True, save_orders=True``).
    
    Wenn du nur die Umsätze ohne Bestellungen abrufen möchtest, kannst du das so machen:
    ```bash
    readtx run amazon_visa --o details=False save_orders=False
    ```

    Du kannst start und End-Datum setzen, z. B. für das erste Quartal 2024:
    ```bash
    readtx run amazon_visa --start 01.01.2024 --end 31.03.2024
    ```

   oder den Trade-Republic-Crawler im Debug-Modus:

   ```bash
   readtx run trade_republic --l DEBUG
   ```

5. **Ergebnisse ansehen**\
   Nach Abschluss findest du die CSV-Dateien im aktuellen working-Dir unter dem Ordner:

   ```
   out\
   ```
<!-- docs:getting_started-end -->
***

<!-- docs:cli-start -->
## ⚙️ CLI-Kommandos

Das Tool ist vollständig über die Kommandozeile steuerbar.\
Alle Befehle folgen dem Schema:

```bash
readtx <command> [options]
```

### Verfügbare Hauptbefehle

| Befehl          | Beschreibung                                       | Beispiel                                                         |
| --------------- | -------------------------------------------------- | ---------------------------------------------------------------- |
| `list`          | Listet alle verfügbaren Crawler                    | `readtx list`                                                    |
| `run <crawler>` | Startet einen bestimmten Crawler                   | `readtx run ariva --start 01.01.2024 --end 31.03.2024`           |
| `config show`   | Zeigt die aktuelle Konfiguration an                | `readtx config show`                                             |
| `config set`    | Setzt Benutzername und/oder Passwort verschlüsselt | `readtx config set amex --user max --pwd geheim`                 |
| `config edit`   | Ändert beliebige Einträge in der Config            | `readtx config edit urls.ariva.login https://www.ariva.de/login` |
| `config clear`  | Löscht Config-Cache oder Datei                     | `readtx config clear --delete`                                   |
| `config init`   | Erstellt eine neue Standard-Config                 | `readtx config init --overwrite`                                 |

### Parameter beim `run`-Befehl

| Option    | Bedeutung                               | Beispiel                                                  |
| --------- | --------------------------------------- |-----------------------------------------------------------|
| `--start` | Startdatum (Standard: heute)            | `--start 01.01.2024`                                      |
| `--end`   | Enddatum (Standard: heute − 6 Monate)   | `--end 31.03.2024`                                        |
| `--l`     | Log-Level (DEBUG, INFO, WARNING, ERROR) | `--l DEBUG`                                               |
| `--o`     | Zusätzliche Parameter (key=value)       | `--o output_path='myout' browser='chrome' headless=False` |

<!-- docs:cli-end -->
***

<!-- docs:examples-start -->
## 🧩 Beispiel-Workflows

### Ariva-Kurse für Q1 2024 abrufen

```bash
readtx run ariva --start 01.01.2024 --end 31.03.2024
```

### Alle Kreditkartenumsätze der letzten 6 Monate abrufen

```bash
readtx run amex
readtx run amazon_visa
```

### Amazon Visa-Umsätze mit Bestellungen von Amazon.de abgleichen

```bash
readtx run amazon_visa
```
ohne orders von amazon.de zu speichern (default ist save_orders=True):
```bash
readtx run amazon_visa --o save_orders=False
```

ohne speichern und ohne amazon orders abzurufen (default ist details=True):
```bash
readtx run amazon_visa --o details=False save_orders=False
```

### TradeRepublic-Umsätze abrufen

ohne zusätzliche Details der Transaktionen mit Trades (default ist details=True) - wesentlich schneller:
```bash
readtx run trade_republic --o details=False
```

### Config prüfen

```bash
readtx config show --credentials
```
<!-- docs:examples-end -->
<!-- docs:installation-start -->
## Installation

You can use the following methods to install and use the package.
1. Install it in your Python environment
    - set up a Python environment (see [Setting-up Python Environment](#setting-up-python-environment))
    - install the package
      - from github (see [install from github](#install-from-github))
      - from wheel file (see [install from wheel file](#install-from-wheel-file))

2. Use the provided readtx.exe (Windows only)

### install from github
- aktivate your python environment
- install the package with pip:
```bash
pip install git+https://github.com/th89dd/read_transactions_fm.git
```

### install from wheel file
- download the wheel from [releases](https://github.com/th89dd/read_transactions_fm/releases)
- aktivate your python environment
- install the wheel file with pip:
```bash
pip read_transactions_fm-1.0.0-py3-none-any.whl
```

### Setting-up Python Environment

You can use the following steps, or you can use the **[bat-file](setup.bat)** to set up the Python environment on your computer (with Windows).

1. Install Python 3.12 (or newer)
    - download Python 3.12 from [Python.org](https://www.python.org/downloads/)
    - install Python
    - you can check if Python is installed correctly:
    ```bash
    python --version
    ```

1. Create a virtual environment:
    - create a virtual environment in the project folder:
    - open a terminal in the project folder and run:
    ```bash
    python -m venv venv
    ```

1. Activate the virtual environment:
     ```bash
     venv\Scripts\activate
     ```

1. Deactivate the virtual environment:
    ```bash
    deactivate
    ```
<!-- docs:installation-end -->
***
***

## Dev-Section

Stuff for development

### TODOs

- [ ] design Icon
    - [ ] for exe file
    - [ ] for sphinx docs

- [ ] Improve performance of web scraping
    - [ ] Read data from out -> update only nessesary (new) entries
    - [ ] Check some stuff (async requests, headless browser options etc.)
    - [ ] Check if start_date is before end_date -> eg swap them automatically


- [ ] Add more Crawler (e.g., other banks, brokers)
- [ ] Add tests for Crawler
- [ ] Improve error handling and logging
- [ ] Add more examples and documentation
- [ ] Create Docker image for easier deployment
- [ ] Add CI/CD pipeline for automated testing and deployment

  
- [ ] Add support for more output formats (e.g., JSON, Excel)
- [ ] Add GUI for easier usage

### Usefull Commands
#### Use Package in Editable Mode
Um read_transactions im "editable mode" zu installieren, sodass Änderungen am Code sofort wirksam werden,
kann folgendes Kommando genutzt werden:
```bash
pip install -e .
```
Das Paket kann ist dann als read_transactions in Python nutzbar aber Code-Änderungen werden sofort übernommen.

Über das Kommando `pip uninstall read_transactions` kann die Installation wieder entfernt werden.


#### Build Package
Folgende Pakete müssen installiert sein, um das Projekt zu bauen:
```bash
pip install setuptools build
```

Um read_transactions nur als wheel zu bauen, kann folgendes Kommando genutzt werden.  
Es wird eine Wheel-Datei im Ordner `dist/` erstellt.

```bash
python -m build --wheel
```

Um read_transactions als Paket zu bauen, kann folgendes Kommando genutzt werden.  
Es werden sowohl eine Wheel-Datei als auch ein Source-Distribution-Paket im Ordner `dist/` erstellt.

```bash
python -m build
```

#### Build Standalone Executable (Windows)
Um eine standalone ausführbare Datei (exe) für Windows zu bauen, muss folgendes paket installiert sein: 
```bash
pip install pyinstaller
```
Um read_transactions als ausführbare Datei zu bauen, kann folgendes Kommando genutzt werden.
Es wird eine ausführbare Datei im Ordner `dist/` erstellt.
```bash
pyinstaller --onefile src/read_transactions/cli.py -n readtx
```
dabei funktionieren aber keine relativen Pfade mehr, die vom paket ausgehen (from .base import webcrawler etc)

im Projektroot ausführen (da wo "src/" liegt):
````bash
pyinstaller --onefile --name readtx --paths src src/read_transactions/__main__.py --collect-submodules read_transactions --icon assets/readtx.ico
````

#### Get Required Packages
Bei bestehendem venv können alle pakete mit pip ausgelesen werden:
```bash
pip freeze > requirements.txt
```

Installation von ``pip-tools`` (falls noch nicht installiert) und Synchronisation der benötigten Pakete:
```bash 
pip install pip-tools
```
Generate the `requirements.txt` file from `pyproject.toml`:
```bash
pip-compile pyproject.toml --output-file=requirements.txt
```

Install required packages from `requirements.txt`:
```bash
pip install -r requirements.txt
```

### Icon-Datei erstellen
das Icon ist in der svg datei unter [assets/icon.svg]('assets/icon.svg') gespeichert.

### Konvertierung in .ico
1. Install Imagemagick 
   - [Website](https://imagemagick.org/script/download.php)
   - mit winget:
       ```bash
       winget install -e --id ImageMagick.ImageMagick
       ```
2. Konvertierung
    aus svg erzeugen (kein transparenter hintergrund):
    ```bash
    magick assets/readtx_icon.svg -background none -alpha on -define icon:auto-resize=16,24,32,48,64,128,256 -define icon:format=png assets/readtx.ico
    ```

    oder aus png erzeugen:
    ````bash
    magick assets/readtx.png -define icon:auto-resize=16,24,32,48,64,128,256 -define icon:format=png assets\readtx.ico
    ````


***
<!-- docs:about-start -->

## Versionshistorie
| Version | Datum      | Beschreibung                          |
|---------|------------|---------------------------------------|
| 2.2.0   | 2025-11-05 | add paypal crawler - beta             |
| 2.1.1   | 2025-10-27 | bugfixes (amazon_visa) - stable       |
| 2.1.0   | 2025-10-26 | add amazon.de crawler                 |
| 2.0.0   | 2025-10-25 | Major Release mit neuem CLI-Interface |
| 1.0.0   | 2024       | Initiale Veröffentlichung             |   

### version 2.2.0 (2025-11-05)
- Neuer Crawler: paypal - für PayPal Umsätze
- Vereinheitlichungen der process Methoden in allen Crawlern
- spezifisches Datenhandling in preprocess Methode umgesetzt

### version 2.1.1 (2025-10-27)
- amazon_visa wird jetzt in Intervallen runtergeladen, da die xls scheinbar nur 100-110 Einträge pro Datei zulässt
- amazon_visa: erkennt jetzt Amazon als Empfänger und vereinheitlicht den Namen mit Amazon.de
- Kleinere Bugfixes

### version 2.1.0 (2025-10-26)
- Neuer Crawler: amazon - für Amazon.de Bestellungen
- Integration von Amazon Visa Umsätzen mit Amazon.de Bestellungen

### version 2.0.0 (2025-10-26)
- Major Release mit neuem CLI-Interface
- Verbesserte Konfigurationsverwaltung
- Neue Crawler-Optionen

### version 1.0.0 (2024)
- Initiale Veröffentlichung mit Crawlern für:
  - Ariva Aktienkurse
  - Trade Republic Umsätze
  - American Express Umsätze
  - Amazon Visa Umsätze

***
***

## Lizenz
Dieses Projekt ist unter der MIT-Lizenz lizenziert.  
Weitere Informationen finden Sie in der [LICENSE](LICENSE)-Datei.

## Nutzungs- und Compliance-Hinweis

> **Nur für Test- und Privatgebrauch**  
Dieses Projekt und die bereitgestellten Werkzeuge (z. B. Crawler, Parser, CLI) sind ausschließlich für **Testzwecke** sowie die **private, nicht-kommerzielle Nutzung** gedacht.

Die Nutzung automatisierter Zugriffe auf Drittanbieter-Dienste (z. B. Banking-Portale, Kreditkarten-Webseiten, Kurs-/Finanzportale) kann gegen deren AGB, technische Nutzungsbedingungen oder geltendes Recht verstoßen. **Du bist selbst verantwortlich**, vor der Verwendung die anwendbaren Bedingungen zu prüfen und diese einzuhalten.

- **Kein Umgehen von Schutzmechanismen.** Captchas, 2FA und ähnliche Sicherheitsmaßnahmen dürfen nicht umgangen werden.
- **Offizielle Exportpfade bevorzugen.** Wenn verfügbar, nutze die vom Anbieter vorgesehenen Export-/Downloadfunktionen.
- **Keine Weiterveröffentlichung.** Von Drittanbietern stammende Daten (z. B. Kurse, Kontoauszüge) dürfen nicht weiterverbreitet oder kommerziell genutzt werden, sofern dies nicht ausdrücklich erlaubt ist.
- **Keine Affiliation.** Dieses Projekt steht in **keiner Verbindung** zu den genannten Anbietern und wird von diesen **weder unterstützt noch geprüft**.

> **Haftungsausschluss:** Die Software wird **„as is“** ohne Gewähr bereitgestellt. Die Autor:innen übernehmen **keine Haftung** für etwaige Schäden, Kontosperren, Vertragsverletzungen oder Datenverluste, die aus der Nutzung entstehen.

> **Hinweis zur Lizenz:** Die Open-Source-Lizenz dieses Repos (z. B. MIT) bleibt unberührt. Dieser Abschnitt dient der **Aufklärung/Compliance** und begründet **keine** zusätzlichen Rechte.

<!-- docs:about-end -->