"""
ETHUSD Feed Module — Median of 5 exchanges
Sources: Coinbase, Kraken, Bitstamp, Gemini, Bitfinex
"""
import statistics
import requests


def fetch_coinbase():
    r = requests.get("https://api.exchange.coinbase.com/products/ETH-USD/ticker", timeout=5)
    return float(r.json()["price"])


def fetch_kraken():
    r = requests.get("https://api.kraken.com/0/public/Ticker?pair=ETHUSD", timeout=5)
    pair = list(r.json()["result"].keys())[0]
    return float(r.json()["result"][pair]["c"][0])


def fetch_bitstamp():
    r = requests.get("https://www.bitstamp.net/api/v2/ticker/ethusd/", timeout=5)
    return float(r.json()["last"])


def fetch_gemini():
    r = requests.get("https://api.gemini.com/v1/pubticker/ethusd", timeout=5)
    return float(r.json()["last"])


def fetch_bitfinex():
    r = requests.get("https://api-pub.bitfinex.com/v2/ticker/tETHUSD", timeout=5)
    return float(r.json()[6])


SOURCES = [
    ("coinbase", fetch_coinbase),
    ("kraken", fetch_kraken),
    ("bitstamp", fetch_bitstamp),
    ("gemini", fetch_gemini),
    ("bitfinex", fetch_bitfinex),
]


def get_ethusd_price():
    prices = []
    sources = []
    for name, fn in SOURCES:
        try:
            p = fn()
            prices.append(p)
            sources.append(name)
        except Exception:
            pass
    if len(prices) < 3:
        raise RuntimeError(f"ETHUSD: insufficient sources ({len(prices)}/5, need 3)")
    return {
        "price": round(statistics.median(prices), 2),
        "sources": sources,
    }
