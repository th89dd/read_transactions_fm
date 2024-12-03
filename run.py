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
    kurse = ArivaKurse()
    tr = TradeRepublic()
    amex = Amex()
    amazon = AmazonVisa()

