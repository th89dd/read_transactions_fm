![version](https://img.shields.io/badge/version-1.0-blue.svg)
![date](https://img.shields.io/badge/date-2024--11--13-green.svg)
![status](https://img.shields.io/badge/status-development-yellow.svg)
![python](https://img.shields.io/badge/python-3.12-blue.svg)



# Readme zur Scripsammlung "read transactions" für Finanzmanagerimport

Diese Scriptsammlung dient dazu, Transaktionen via "WebCrawler" 
von verschiedenen Finanzdienstleistern abzurufen und 
anschließend in ein einheitliches Format zu bringen, 
um diese in das Tool Finanzmanager importieren zu können. 

## Content
1. [Installation](#setting-up-python-environment)


## Setting-up Python Environment
1. Install Python 3.12 (or newer) 
   - download Python 3.12 from [Python.org](https://www.python.org/downloads/)
   - install Python
   - you can check if Python 3.8.5 is installed correctly:
    ```bash
    python --version
    ```
   
2. Create a virtual environment:
   - create a virtual environment in the project folder:
   - open a terminal in the project folder and run:
    ```bash
    python -m venv venv
    ```

3. Install required packages:
    ```bash
    pip install -r requirements.txt
    ```

## Use Ariva Crawler
1. Make a ariva.de account
    - go to [ariva.de](https://www.ariva.de/registrierung/)
    - fill out the form and create an account
   - save your credentials
2. Create a file named `credentials_ariva.txt` in the root folder of the project
   - you can use the example_file as template
   - add your ariva.de credentials to the file in the following format:
     ```
     username: your_username
     password: your_password
     ```
   - add your desired stocks and other securities in the following format:
   
      ```
      name: link to ariva.de
      ``` 
   
   - the name can be anything you want, but the link must be a valid link to the security on ariva.de
   for example:
     ```
     MyStockApple: https://www.ariva.de/apple-aktie
     ```
   
3. Run the ariva crawler:
4. 