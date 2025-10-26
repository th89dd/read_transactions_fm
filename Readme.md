![version](https://img.shields.io/badge/version-2.0.0-blue.svg)
![date](https://img.shields.io/badge/date-2025--10--26-green.svg)
![status](https://img.shields.io/badge/status-running-green.svg)
![python](https://img.shields.io/badge/python-3.12-blue.svg)



# Read Transactions für Finanzmanager

Aktuell unterstützt:
- **Aktienkurse von Ariva**
- **Umsätze von Trade Republic**
- **Umsätze von American Express**
- **Umsätze von Amazon Visa (Zinia)**
***

Diese Scriptsammlung dient dazu, Transaktionen via „WebCrawler“\
von verschiedenen Finanzdienstleistern automatisiert abzurufen und\
anschließend in ein einheitliches CSV-Format zu überführen,\
um diese z. B. im **Finanzmanager** zu importieren.

Alle abgeholten Umsätze werden nach Dienstleister sortiert im Ordner [`out`](out) gespeichert.\
Diese CSV-Dateien können anschließend im Finanzmanager über\
**Datei → Export/Import → Datenimport → Umsätze** eingelesen werden.\
Zur Vereinfachung können Importvorlagen genutzt werden – eine Beispielvorlage liegt unter [Vorlagen.dat](Vorlagen.dat).

***
***
## Content
1. [Getting-Started](#-getting-started-empfohlene-nutzung)
2. [CLI-Interface](#use-the-main-script)
2. [Use Ariva Crawler](#use-ariva-crawler)
3. [Use the other Crawler](#use-the-other-crawler)

***

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
   Trage dort deine Zugangsdaten (Benutzername/Passwort) ein oder nutze:

   ```bash
   readtx config set amex --user <USERNAME> --pwd <PASSWORT>
   ```

4. **Crawler starten** Beispiel – Starte den Ariva-Crawler:

   ```bash
   readtx run ariva --start 01.01.2024 --end 31.03.2024 --l INFO
   ```

   oder den Trade-Republic-Crawler im Debug-Modus:

   ```bash
   readtx run trade_republic --l DEBUG
   ```

5. **Ergebnisse ansehen**\
   Nach Abschluss findest du die CSV-Dateien im Ordner:

   ```
   %USERPROFILE%\out\
   ```

***

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

***

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

### TradeRepublic-Umsätze abrufen

ohne zusätzliche Details der Transaktionen mit Trades (default ist details=True) - wesentlich schneller:
```bash
readtx run trade_republic --o details=False
```

### Config prüfen

```bash
readtx config show --credentials
```


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
## Entwicklung

### Use Package in Editable Mode
Um read_transactions im "editable mode" zu installieren, sodass Änderungen am Code sofort wirksam werden,
kann folgendes Kommando genutzt werden:
```bash
pip install -e .
```
Das Paket kann ist dann als read_transactions in Python nutzbar aber Code-Änderungen werden sofort übernommen.

Über das Kommando `pip uninstall read_transactions` kann die Installation wieder entfernt werden.


### Build Package
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

### Build Standalone Executable (Windows)
Um eine standalone ausführbare Datei (exe) für Windows zu bauen, muss folgendes paket installiert sein: 
```bash
pip install pyinstaller
```
Um read_transactions als ausführbare Datei zu bauen, kann folgendes Kommando genutzt werden.
Es wird eine ausführbare Datei im Ordner `dist/` erstellt.
```bash
pyinstaller --onefile src/read_transactions/cli.py -n readtx
```




### Get Required Packages
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




## Use the Main Script
you can use the main script to run all configured crawler at once
1. Create all credential files for the crawler you want to use  
see [Use Ariva Crawler](#use-ariva-crawler) and [Use the other Crawler](#use-the-other-crawler) for details

2. Configure all crawler in the [run.py file](run.py) in the main folder
   - you can add or remove crawler by adding or removing the following lines or comment them out with `#`:
    ```python
    kurse = ArivaKurse()  # Ariva Kurse - comment in or comment out (with #) if you didnt want to use
    tr = TradeRepublic()  # Trade Republic
    amex = Amex()  # American Express
    amazon = AmazonVisa()  # new Amazon Visa by Zinia (2024)
    ```
   - example if you dont want to use AmericanExpress:
    ```python
    kurse = ArivaKurse()  # Ariva Kurse - comment in or comment out (with #) if you didnt want to use
    tr = TradeRepublic()  # Trade Republic
    # amex = Amex()  # American Express
    amazon = AmazonVisa()  # new Amazon Visa by Zinia (2024)
    ```
3. Run the main script:
   - open a terminal in the project folder and run:
    ```bash
    start.bat
    ```
   - the script will run all configured crawler and save the data in the [out](out) folder

## Use Ariva Crawler
1. Make a ariva.de account
   - go to [ariva.de](https://www.ariva.de/registrierung/)
   - fill out the form and create an account
   - save your credentials
2. Create a file named `credentials_ariva.txt` in the root folder of the project
   - you can use the [example_file](credentials_ariva_example.txt) as template
   - add your ariva.de credentials to the file in the following format:
     ```
     username: your_username
     password: your_password
     ```
   - add your desired stocks and other securities in the following format:
   
      ```
      name: link to ariva.de
      ``` 
   
   - the *name* can be anything you want, but the *link* must be a valid link to the security on ariva.de
   for example:
     ```
     MyStockApple: https://www.ariva.de/apple-aktie
     ```
   
3. Run the ariva crawler:  
   run avira crawler with default options:
   - start_date = today
   - end_date = today - 6 month
   - standard output path (./data)
   - automatically start download & save data
    ```python
   from WebCrawler.ArivaCrawler import ArivaKurse
   ariva = ArivaKurse()  # start ariva crawler with default options
    ```
   run avira crawler with custom options:
   ````python
    from WebCrawler.ArivaCrawler import ArivaKurse
    ariva = ArivaKurse(start_date='1.11.2024', perform_download=False, output_path='../out')  # if perform_download is True, the following steps will done automatically
    ariva.end_date = '13.10.2024'  # you can also set the date by property, not only by constructor
    ariva.credentials_file = '../credentials_ariva.txt'  # if you want to use another credentials file or path
    ariva._read_credentials()
    ariva.login()
    ariva.download_data()
    ariva.close()
    ariva.process_data()
    ariva.save_data()      
   ````

## Use the other crawler
1. Create a file named `credentials_<crawler>.txt` in the root folder of the project
   - you can use the [example_file](credentials_example.txt) as template
   - add your credentials to the file in the following format:
     ```
     username: your_username
     password: your_password
     ```
2. Run the crawler:
   - the crawler is used in the same way as the ariva crawler
   - see [use ariva crawler](#use-ariva-crawler) for more information


