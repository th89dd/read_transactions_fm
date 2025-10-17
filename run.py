# -*- coding: utf-8 -*-
"""
:author: Tim Häberlein
:version: 1.0
:date: 06.10.2024
:organisation: TU Dresden, FZM
"""

# -------- start import block ---------
from WebCrawler import TradeRepublic, ArivaKurse, Amex, AmazonVisa
# -------- end import block ---------


if __name__ == '__main__':
    kurse = ArivaKurse()  # Ariva Kurse - comment in or comment out (with #) if you didnt want to use
    tr = TradeRepublic()  # Trade Republic
    # amex = Amex()  # American Express
    amazon = AmazonVisa()  # new Amazon Visa by Zinia (2024)
    # example comment



