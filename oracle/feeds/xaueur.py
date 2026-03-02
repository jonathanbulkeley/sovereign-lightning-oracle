"""
XAUEUR Feed Module — Cross-rate derivation
XAUEUR = XAUUSD / EURUSD
Uses existing XAUUSD (8 sources) and EURUSD (8 sources) feeds.
"""
from oracle.feeds.xauusd import get_xauusd_price
from oracle.feeds.eurusd import get_eurusd_price


def get_xaueur_price():
    xauusd = get_xauusd_price()
    eurusd = get_eurusd_price()
    xaueur = round(xauusd["price"] / eurusd["price"], 2)
    return {
        "price": xaueur,
        "sources": sorted(xauusd["sources"] + eurusd["sources"]),
        "source_count": len(xauusd["sources"]) + len(eurusd["sources"]),
        "xauusd": xauusd["price"],
        "eurusd": eurusd["price"],
    }
