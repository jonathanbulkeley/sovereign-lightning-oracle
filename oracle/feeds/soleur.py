"""
SOLEUR Feed Module — Hybrid: direct EUR pairs + cross-rate
Direct sources: Coinbase, Kraken, Bitstamp (SOL/EUR)
Cross-rate: SOLUSD / EURUSD
"""
import statistics
import requests

TIMEOUT = 5


# === Direct EUR sources ===

def fetch_coinbase():
    r = requests.get("https://api.exchange.coinbase.com/products/SOL-EUR/ticker", timeout=TIMEOUT)
    return float(r.json()["price"])


def fetch_kraken():
    r = requests.get("https://api.kraken.com/0/public/Ticker?pair=SOLEUR", timeout=TIMEOUT)
    pair = list(r.json()["result"].keys())[0]
    return float(r.json()["result"][pair]["c"][0])


def fetch_bitstamp():
    r = requests.get("https://www.bitstamp.net/api/v2/ticker/soleur/", timeout=TIMEOUT)
    return float(r.json()["last"])


# === Cross-rate ===

def fetch_crossrate():
    from oracle.feeds.solusd import get_solusd_price
    from oracle.feeds.eurusd import get_eurusd_price
    solusd = get_solusd_price()
    eurusd = get_eurusd_price()
    return round(solusd["price"] / eurusd["price"], 2)


SOURCES = [
    ("coinbase", fetch_coinbase),
    ("kraken", fetch_kraken),
    ("bitstamp", fetch_bitstamp),
    ("crossrate", fetch_crossrate),
]

MIN_SOURCES = 2


def get_soleur_price():
    """Fetch SOLEUR from up to 4 sources (3 direct + 1 cross-rate).
    Returns dict with: price, sources
    Raises RuntimeError if insufficient sources.
    """
    prices = {}
    for name, fn in SOURCES:
        try:
            prices[name] = fn()
        except Exception:
            pass

    if len(prices) < MIN_SOURCES:
        raise RuntimeError(
            f"SOLEUR: insufficient sources ({len(prices)}/{MIN_SOURCES})"
        )

    return {
        "price": round(statistics.median(prices.values()), 2),
        "sources": sorted(prices.keys()),
    }
