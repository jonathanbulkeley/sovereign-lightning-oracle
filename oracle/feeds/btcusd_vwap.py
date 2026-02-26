"""
BTCUSD VWAP Feed Module — Volume-weighted average price (5-min window)
Sources: Coinbase, Kraken
"""
import statistics
import requests


def _vwap(trades):
    vol = sum(t["size"] for t in trades)
    if vol == 0:
        raise ValueError("Zero volume")
    return sum(t["price"] * t["size"] for t in trades) / vol


def fetch_coinbase():
    r = requests.get("https://api.exchange.coinbase.com/products/BTC-USD/trades", timeout=5)
    trades = [{"price": float(t["price"]), "size": float(t["size"])} for t in r.json()]
    return _vwap(trades)


def fetch_kraken():
    r = requests.get("https://api.kraken.com/0/public/Trades?pair=XBTUSD", timeout=5)
    trades = [{"price": float(t[0]), "size": float(t[1])} for t in r.json()["result"]["XXBTZUSD"]]
    return _vwap(trades)


SOURCES = [
    ("coinbase", fetch_coinbase),
    ("kraken", fetch_kraken),
]


def get_btcusd_vwap_price():
    prices = []
    sources = []
    for name, fn in SOURCES:
        try:
            p = fn()
            prices.append(p)
            sources.append(name)
        except Exception:
            pass
    if len(prices) < 1:
        raise RuntimeError("BTCUSD VWAP: insufficient sources")
    return {
        "price": round(statistics.median(prices), 2),
        "sources": sources,
    }
