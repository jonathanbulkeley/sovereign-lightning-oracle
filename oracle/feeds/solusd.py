# feeds/solusd.py
"""
SOLUSD Price Feed — 9 Sources with USDT Normalization
SLO v1

Tier 1 (USD-native):
  1. Coinbase          api.exchange.coinbase.com
  2. Kraken            api.kraken.com
  3. Bitstamp          www.bitstamp.net
  4. Gemini            api.gemini.com
  5. Bitfinex          api-pub.bitfinex.com

Tier 2 (USDT → normalized to USD):
  6. Binance global    data-api.binance.vision
  7. OKX              www.okx.com
  8. Gate.io           api.gateio.ws
  9. Bybit             api.bybit.com

USDT/USD rate sourced from Kraken + Bitstamp (median).
If USDT median and USD median diverge > 0.5%, USDT sources are dropped.
Minimum 5 of 9 sources required (or 3 of 5 USD-only if USDT dropped).
"""

import statistics
import requests

TIMEOUT = 5
USDT_DIVERGENCE_THRESHOLD = 0.005
MIN_SOURCES = 5
MIN_USD_SOURCES = 3


# === USDT/USD rate fetchers ===

def fetch_usdt_kraken():
    r = requests.get("https://api.kraken.com/0/public/Ticker?pair=USDTZUSD", timeout=TIMEOUT)
    return float(r.json()["result"]["USDTZUSD"]["c"][0])

def fetch_usdt_bitstamp():
    r = requests.get("https://www.bitstamp.net/api/v2/ticker/usdtusd/", timeout=TIMEOUT)
    return float(r.json()["last"])

def get_usdt_rate():
    rates = []
    for name, fn in [("kraken", fetch_usdt_kraken), ("bitstamp", fetch_usdt_bitstamp)]:
        try:
            rates.append(fn())
        except Exception:
            pass
    if len(rates) == 0:
        return None
    return statistics.median(rates)


# === Tier 1: USD pair fetchers ===

def fetch_coinbase():
    r = requests.get("https://api.exchange.coinbase.com/products/SOL-USD/ticker", timeout=TIMEOUT)
    return float(r.json()["price"])

def fetch_kraken():
    r = requests.get("https://api.kraken.com/0/public/Ticker?pair=SOLUSD", timeout=TIMEOUT)
    d = r.json()["result"]
    k = list(d.keys())[0]
    return float(d[k]["c"][0])

def fetch_bitstamp():
    r = requests.get("https://www.bitstamp.net/api/v2/ticker/solusd/", timeout=TIMEOUT)
    return float(r.json()["last"])

def fetch_gemini():
    r = requests.get("https://api.gemini.com/v1/pubticker/solusd", timeout=TIMEOUT)
    return float(r.json()["last"])

def fetch_bitfinex():
    r = requests.get("https://api-pub.bitfinex.com/v2/ticker/tSOLUSD", timeout=TIMEOUT)
    return float(r.json()[6])


# === Tier 2: USDT pair fetchers (raw USDT, not yet normalized) ===

def fetch_binance_global():
    r = requests.get("https://data-api.binance.vision/api/v3/ticker/price?symbol=SOLUSDT", timeout=TIMEOUT)
    return float(r.json()["price"])

def fetch_okx():
    r = requests.get("https://www.okx.com/api/v5/market/ticker?instId=SOL-USDT", timeout=TIMEOUT)
    return float(r.json()["data"][0]["last"])

def fetch_gateio():
    r = requests.get("https://api.gateio.ws/api/v4/spot/tickers?currency_pair=SOL_USDT", timeout=TIMEOUT)
    return float(r.json()[0]["last"])

def fetch_bybit():
    r = requests.get("https://api.bybit.com/v5/market/tickers?category=spot&symbol=SOLUSDT", timeout=TIMEOUT)
    return float(r.json()["result"]["list"][0]["lastPrice"])


# === Source definitions ===

USD_SOURCES = [
    ("coinbase", fetch_coinbase),
    ("kraken", fetch_kraken),
    ("bitstamp", fetch_bitstamp),
    ("gemini", fetch_gemini),
    ("bitfinex", fetch_bitfinex),
]

USDT_SOURCES = [
    ("binance", fetch_binance_global),
    ("okx", fetch_okx),
    ("gateio", fetch_gateio),
    ("bybit", fetch_bybit),
]


# === Main price function ===

def get_solusd_price():
    """Fetch SOLUSD from up to 9 sources with USDT normalization.

    Returns dict with: price, sources, usd_prices, usdt_prices, usdt_rate, usdt_dropped
    Raises RuntimeError if insufficient sources.
    """

    # Fetch USD sources
    usd_prices = {}
    for name, fn in USD_SOURCES:
        try:
            usd_prices[name] = fn()
        except Exception:
            pass

    # Fetch USDT sources and rate
    usdt_rate = get_usdt_rate()
    usdt_normalized = {}

    if usdt_rate is not None:
        for name, fn in USDT_SOURCES:
            try:
                raw = fn()
                usdt_normalized[name] = round(raw * usdt_rate, 4)
            except Exception:
                pass

    # Divergence check
    usdt_dropped = False
    if len(usd_prices) >= 2 and len(usdt_normalized) >= 1:
        usd_median = statistics.median(usd_prices.values())
        usdt_median = statistics.median(usdt_normalized.values())
        divergence = abs(usd_median - usdt_median) / usd_median
        if divergence > USDT_DIVERGENCE_THRESHOLD:
            usdt_dropped = True
            usdt_normalized = {}

    # Combine and compute
    all_prices = {}
    all_prices.update(usd_prices)
    if not usdt_dropped:
        all_prices.update(usdt_normalized)

    source_names = sorted(all_prices.keys())
    total_sources = len(source_names)

    min_required = MIN_USD_SOURCES if usdt_dropped else MIN_SOURCES
    if total_sources < min_required:
        raise RuntimeError(
            f"insufficient sources: {total_sources}, need {min_required} (usdt_dropped={usdt_dropped})"
        )

    median_price = round(statistics.median(all_prices.values()), 4)

    return {
        "price": median_price,
        "sources": source_names,
        "usd_prices": usd_prices,
        "usdt_prices": usdt_normalized if not usdt_dropped else {},
        "usdt_rate": usdt_rate,
        "usdt_dropped": usdt_dropped,
    }


# === CLI test ===

if __name__ == "__main__":
    print("Fetching SOLUSD from 9 sources...\n")
    result = get_solusd_price()

    print("=== USD Sources ===")
    for name, price in sorted(result["usd_prices"].items()):
        print(f"  {name:15s} ${price:,.4f}")

    if result["usdt_prices"]:
        print(f"\n=== USDT Sources (normalized at {result['usdt_rate']:.5f}) ===")
        for name, price in sorted(result["usdt_prices"].items()):
            print(f"  {name:15s} ${price:,.4f}")

    if result["usdt_dropped"]:
        print("\n⚠  USDT sources DROPPED due to divergence > 0.5%")

    print(f"\n=== Result ===")
    print(f"  Median:  ${result['price']:,.4f}")
    print(f"  Sources: {', '.join(result['sources'])} ({len(result['sources'])})")
