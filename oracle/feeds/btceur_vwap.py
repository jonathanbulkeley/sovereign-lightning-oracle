"""
BTCEUR VWAP Feed Module — Cross-rate derivation
BTCEUR_VWAP = BTCUSD_VWAP / EURUSD
Uses existing BTCUSD VWAP (7 sources) and EURUSD (8 sources) feeds.
"""
from oracle.feeds.btcusd_vwap import get_btcusd_vwap_price
from oracle.feeds.eurusd import get_eurusd_price


def get_btceur_vwap_price():
    btcusd_vwap = get_btcusd_vwap_price()
    eurusd = get_eurusd_price()
    btceur = round(btcusd_vwap["price"] / eurusd["price"], 2)
    return {
        "price": btceur,
        "sources": sorted(btcusd_vwap["sources"] + eurusd["sources"]),
        "source_count": len(btcusd_vwap["sources"]) + len(eurusd["sources"]),
        "btcusd_vwap": btcusd_vwap["price"],
        "eurusd": eurusd["price"],
    }
