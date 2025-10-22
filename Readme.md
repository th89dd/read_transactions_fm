![version](https://img.shields.io/badge/version-1.0-blue.svg)
![date](https://img.shields.io/badge/date-2024--11--13-green.svg)
![status](https://img.shields.io/badge/status-development-yellow.svg)
![python](https://img.shields.io/badge/python-3.12-blue.svg)



# Read Transactions für Finanzmanager

Aktuell unterstützt:
- **Aktienkurse von Ariva**
- **Umsätze von Trade Republic**
- **Umsätze von American Express**
- **Umsätze von Amazon Visa (Zinia)**
***

Diese Scriptsammlung dient dazu, Transaktionen via "WebCrawler" 
von verschiedenen Finanzdienstleistern abzurufen und 
anschließend in ein einheitliches Format zu bringen, 
um diese in das Tool Finanzmanager importieren zu können. 

Alle abgeholten Umsätze werden nach Dienstleister sortiert in CSV-Files im Folder [out](out) gespeichert.

Die CSV-Dateien können anschließend zB im Finanzmanager importiert werden.
Dazu über Datei -> Export/Import -> Datenimport  -> **Umsätze** über den Dialog importieren.

Zur einfacheren Verwendung, lohnt es sich Vorlagen zu erzeugen, damit die Umsätze schneller in den Finanzmanager importiert werden können. Das kann  im Rahmen des Dialogs erfolgen.
Zur einfacheren Verwendung habe ich meine [Vorlagen](Vorlagen.dat) angehängt.

***

## Quick Start
- was auch immer

---
## Content
1. [Installation/Setting-up python](#setting-up-python-environment)
2. [Use the main script](#use-the-main-script)
2. [Use Ariva Crawler](#use-ariva-crawler)
3. [Use the other Crawler](#use-the-other-crawler)


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

### Build Package
Folgende Pakete müssen installiert sein:
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


