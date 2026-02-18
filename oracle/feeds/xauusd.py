"""
XAUUSD Feed Module — Median of up to 8 sources
Tier 1 — Traditional Gold: Kitco, JM Bullion, GoldBroker
Tier 2 — Tokenized Gold (PAXG): Coinbase, Kraken, Gemini, Binance, OKX
USDT normalization on Binance/OKX. Divergence check at 0.5%.
"""
import re
import statistics
import requests


def fetch_kitco():
    r = requests.get("https://proxy.kitco.com/getPM?symbol=AU&currency=USD", timeout=5)
    parts = r.text.strip().split(",")
    return float(parts[5])


def fetch_jm_bullion():
    r = requests.get(
        "https://www.jmbullion.com/charts/gold-price/",
        timeout=10,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    matches = re.findall(r"\$[\d,]+\.\d+", r.text)
    if not matches:
        raise ValueError("No price found on JM Bullion")
    price = float(matches[0].replace("$", "").replace(",", ""))
    if price < 1000 or price > 20000:
        raise ValueError(f"JM Bullion price out of range: {price}")
    return price


def fetch_goldbroker():
    r = requests.get(
        "https://www.goldbroker.com/charts/gold-price/usd",
        timeout=10,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    matches = re.findall(r"\$[\d,]+\.\d+", r.text)
    prices = []
    for m in matches:
        val = float(m.replace("$", "").replace(",", ""))
        if 1000 < val < 20000:
            prices.append(val)
    if not prices:
        raise ValueError("No valid price found on GoldBroker")
    return prices[0]


def fetch_coinbase_paxg():
    r = requests.get("https://api.coinbase.com/v2/prices/PAXG-USD/spot", timeout=5)
    return float(r.json()["data"]["amount"])


def fetch_kraken_paxg():
    r = requests.get("https://api.kraken.com/0/public/Ticker?pair=PAXGUSD", timeout=5)
    d = r.json()["result"]
    k = list(d.keys())[0]
    return float(d[k]["c"][0])


def fetch_gemini_paxg():
    r = requests.get("https://api.gemini.com/v1/pubticker/paxgusd", timeout=5)
    return float(r.json()["last"])


def fetch_binance_paxg():
    r = requests.get(
        "https://data-api.binance.vision/api/v3/ticker/price?symbol=PAXGUSDT", timeout=5
    )
    return float(r.json()["price"])


def fetch_okx_paxg():
    r = requests.get(
        "https://www.okx.com/api/v5/market/ticker?instId=PAXG-USDT", timeout=5
    )
    return float(r.json()["data"][0]["last"])


def get_usdt_rate():
    rates = []
    try:
        r = requests.get("https://api.kraken.com/0/public/Ticker?pair=USDTUSD", timeout=5)
        d = r.json()["result"]
        k = list(d.keys())[0]
        rates.append(float(d[k]["c"][0]))
    except Exception:
        pass
    try:
        r = requests.get("https://www.bitstamp.net/api/v2/ticker/usdtusd/", timeout=5)
        rates.append(float(r.json()["last"]))
    except Exception:
        pass
    if rates:
        return statistics.median(rates)
    return 1.0


TRADITIONAL_SOURCES = [
    ("kitco", fetch_kitco),
    ("jmbullion", fetch_jm_bullion),
    ("goldbroker", fetch_goldbroker),
]

PAXG_USD_SOURCES = [
    ("coinbase", fetch_coinbase_paxg),
    ("kraken", fetch_kraken_paxg),
    ("gemini", fetch_gemini_paxg),
]

PAXG_USDT_SOURCES = [
    ("binance", fetch_binance_paxg),
    ("okx", fetch_okx_paxg),
]


def get_xauusd_price():
    traditional_prices = {}
    paxg_prices = {}

    for name, fn in TRADITIONAL_SOURCES:
        try:
            p = fn()
            traditional_prices[name] = p
        except Exception:
            pass

    for name, fn in PAXG_USD_SOURCES:
        try:
            p = fn()
            paxg_prices[name] = p
        except Exception:
            pass

    usdt_rate = get_usdt_rate()
    for name, fn in PAXG_USDT_SOURCES:
        try:
            p = fn()
            paxg_prices[name] = round(p * usdt_rate, 2)
        except Exception:
            pass

    paxg_dropped = False
    if traditional_prices and paxg_prices:
        trad_median = statistics.median(traditional_prices.values())
        paxg_median = statistics.median(paxg_prices.values())
        divergence = abs(trad_median - paxg_median) / trad_median
        if divergence > 0.005:
            paxg_dropped = True
            paxg_prices = {}

    all_prices = list(traditional_prices.values()) + list(paxg_prices.values())
    all_sources = list(traditional_prices.keys()) + list(paxg_prices.keys())

    min_required = 2 if paxg_dropped else 3
    if len(all_prices) < min_required:
        raise RuntimeError(
            f"XAUUSD: insufficient sources ({len(all_prices)}, need {min_required})"
        )

    return {
        "price": round(statistics.median(all_prices), 2),
        "sources": all_sources,
        "traditional": traditional_prices,
        "paxg_prices": paxg_prices,
        "usdt_rate": usdt_rate,
        "paxg_dropped": paxg_dropped,
    }
