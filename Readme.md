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
2. [Use Ariva Crawler](#use-ariva-crawler)


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
   
   - the name can be anything you want, but the link must be a valid link to the security on ariva.de
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

