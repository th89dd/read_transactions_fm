# -*- coding: utf-8 -*-
"""
:author: Tim Häberlein
:version: 1.0
:date: 06.10.2024
:organisation: TU Dresden, FZM
"""

# -------- start import block ---------
from WebCrawler.WebCrawler import TradeRepublic, ArivaKurse, Amex

# -------- end import block ---------


if __name__ == '__main__':
    # a = ArivaKurse(autosave=False, perform_download=False)
    # a._read_credentials()
    # a.login()
    # a.download_data()
    ariva = ArivaKurse()
    traderepublic = TradeRepublic()
    amex = Amex()

