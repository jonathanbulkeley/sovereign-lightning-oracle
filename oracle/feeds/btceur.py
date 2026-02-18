"""
BTCEUR Feed Module — Cross-rate derivation
BTCEUR = BTCUSD / EURUSD
Uses existing BTCUSD (9 sources) and EURUSD (7 sources) feeds.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from oracle.feeds.btcusd import get_btcusd_price
from oracle.feeds.eurusd import get_eurusd_price


def get_btceur_price():
    btcusd = get_btcusd_price()
    eurusd = get_eurusd_price()

    btceur = round(btcusd["price"] / eurusd["price"], 2)

    # Combine source lists with prefix
    sources = [f"btcusd:{s}" for s in btcusd["sources"]] + \
              [f"eurusd:{s}" for s in eurusd["sources"]]

    return {
        "price": btceur,
        "sources": btcusd["sources"] + eurusd["sources"],
        "source_count": len(btcusd["sources"]) + len(eurusd["sources"]),
        "btcusd": btcusd["price"],
        "eurusd": eurusd["price"],
    }
