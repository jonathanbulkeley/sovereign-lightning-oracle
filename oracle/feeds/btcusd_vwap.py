"""
BTCUSD VWAP Feed Module — Volume-weighted average price (5-minute window)
Sources: Coinbase, Kraken, Bitstamp, Gemini, Bitfinex (USD direct)
         OKX, Gate.io (USDT-normalized)
"""
import statistics
import time
import requests
from datetime import datetime, timezone

TIMEOUT = 5
WINDOW_SECONDS = 300  # 5 minutes

# === USDT rate (shared logic with spot feed) ===

def get_usdt_rate():
    """Fetch USDT/USD rate for normalizing USDT-quoted trades."""
    fetchers = [
        lambda: float(requests.get(
            "https://api.kraken.com/0/public/Ticker?pair=USDTZUSD", timeout=TIMEOUT
        ).json()["result"]["USDTZUSD"]["c"][0]),
        lambda: float(requests.get(
            "https://www.bitstamp.net/api/v2/ticker/usdtusd/", timeout=TIMEOUT
        ).json()["last"]),
    ]
    rates = []
    for fn in fetchers:
        try:
            rates.append(fn())
        except Exception:
            pass
    if not rates:
        return None
    return statistics.median(rates)


# === VWAP helper ===

def _vwap(trades):
    """Compute VWAP from list of {price, size} dicts."""
    vol = sum(t["size"] for t in trades)
    if vol == 0:
        raise ValueError("Zero volume")
    return sum(t["price"] * t["size"] for t in trades) / vol


# === USD sources (trade history endpoints) ===

def fetch_coinbase():
    """Coinbase returns last 100 trades; filter to 5-min window."""
    cutoff = time.time() - WINDOW_SECONDS
    r = requests.get(
        "https://api.exchange.coinbase.com/products/BTC-USD/trades",
        timeout=TIMEOUT,
    )
    trades = []
    for t in r.json():
        ts = datetime.fromisoformat(t["time"].replace("Z", "+00:00")).timestamp()
        if ts >= cutoff:
            trades.append({"price": float(t["price"]), "size": float(t["size"])})
    if not trades:
        raise ValueError("No trades in window")
    return _vwap(trades)


def fetch_kraken():
    """Kraken returns recent trades; filter to 5-min window."""
    cutoff = time.time() - WINDOW_SECONDS
    r = requests.get(
        "https://api.kraken.com/0/public/Trades?pair=XBTUSD",
        timeout=TIMEOUT,
    )
    trades = []
    for t in r.json()["result"]["XXBTZUSD"]:
        if float(t[2]) >= cutoff:
            trades.append({"price": float(t[0]), "size": float(t[1])})
    if not trades:
        raise ValueError("No trades in window")
    return _vwap(trades)


def fetch_bitstamp():
    """Bitstamp transactions endpoint; filter to 5-min window."""
    cutoff = time.time() - WINDOW_SECONDS
    r = requests.get(
        "https://www.bitstamp.net/api/v2/transactions/btcusd/?time=hour",
        timeout=TIMEOUT,
    )
    trades = []
    for t in r.json():
        if float(t["date"]) >= cutoff:
            trades.append({"price": float(t["price"]), "size": float(t["amount"])})
    if not trades:
        raise ValueError("No trades in window")
    return _vwap(trades)


def fetch_gemini():
    """Gemini trades endpoint; filter to 5-min window."""
    cutoff = time.time() - WINDOW_SECONDS
    r = requests.get(
        "https://api.gemini.com/v1/trades/btcusd?limit_trades=500",
        timeout=TIMEOUT,
    )
    trades = []
    for t in r.json():
        if float(t["timestamp"]) >= cutoff:
            trades.append({"price": float(t["price"]), "size": float(t["amount"])})
    if not trades:
        raise ValueError("No trades in window")
    return _vwap(trades)


def fetch_bitfinex():
    """Bitfinex trades endpoint; filter to 5-min window."""
    cutoff_ms = (time.time() - WINDOW_SECONDS) * 1000
    r = requests.get(
        "https://api-pub.bitfinex.com/v2/trades/tBTCUSD/hist?limit=500",
        timeout=TIMEOUT,
    )
    trades = []
    for t in r.json():
        if float(t[1]) >= cutoff_ms:
            trades.append({"price": float(t[3]), "size": abs(float(t[2]))})
    if not trades:
        raise ValueError("No trades in window")
    return _vwap(trades)


# === USDT sources (need normalization) ===

def fetch_okx_raw():
    """OKX BTC-USDT trades; returns raw USDT-denominated VWAP."""
    cutoff_ms = (time.time() - WINDOW_SECONDS) * 1000
    r = requests.get(
        "https://www.okx.com/api/v5/market/trades?instId=BTC-USDT&limit=100",
        timeout=TIMEOUT,
    )
    trades = []
    for t in r.json()["data"]:
        if float(t["ts"]) >= cutoff_ms:
            trades.append({"price": float(t["px"]), "size": float(t["sz"])})
    if not trades:
        raise ValueError("No trades in window")
    return _vwap(trades)


def fetch_gateio_raw():
    """Gate.io BTC_USDT trades; returns raw USDT-denominated VWAP."""
    cutoff = time.time() - WINDOW_SECONDS
    r = requests.get(
        "https://api.gateio.ws/api/v4/spot/trades?currency_pair=BTC_USDT&limit=100",
        timeout=TIMEOUT,
    )
    trades = []
    for t in r.json():
        if float(t["create_time"]) >= cutoff:
            trades.append({"price": float(t["price"]), "size": float(t["amount"])})
    if not trades:
        raise ValueError("No trades in window")
    return _vwap(trades)


# === Source registry ===

USD_SOURCES = [
    ("coinbase", fetch_coinbase),
    ("kraken", fetch_kraken),
    ("bitstamp", fetch_bitstamp),
    ("gemini", fetch_gemini),
    ("bitfinex", fetch_bitfinex),
]

USDT_SOURCES = [
    ("okx", fetch_okx_raw),
    ("gateio", fetch_gateio_raw),
]

MIN_SOURCES = 4
MIN_USD_SOURCES = 3


# === Main VWAP function ===

def get_btcusd_vwap_price():
    """Fetch BTCUSD VWAP from up to 7 sources with USDT normalization.
    Returns dict with: price, sources
    Raises RuntimeError if insufficient sources.
    """
    # Fetch USD sources
    usd_prices = {}
    for name, fn in USD_SOURCES:
        try:
            usd_prices[name] = fn()
        except Exception:
            pass

    # Fetch USDT sources and normalize
    usdt_rate = get_usdt_rate()
    usdt_normalized = {}
    if usdt_rate is not None:
        for name, fn in USDT_SOURCES:
            try:
                raw = fn()
                usdt_normalized[name] = round(raw * usdt_rate, 2)
            except Exception:
                pass

    # Divergence check — drop USDT sources if they diverge >1% from USD median
    usdt_dropped = False
    if len(usd_prices) >= 2 and len(usdt_normalized) >= 1:
        usd_median = statistics.median(usd_prices.values())
        usdt_median = statistics.median(usdt_normalized.values())
        if abs(usdt_median - usd_median) / usd_median > 0.01:
            usdt_normalized = {}
            usdt_dropped = True

    # Combine
    all_prices = {**usd_prices, **usdt_normalized}
    total_sources = len(all_prices)
    min_required = MIN_USD_SOURCES if usdt_dropped else MIN_SOURCES

    if total_sources < min_required:
        raise RuntimeError(
            f"BTCUSD VWAP: insufficient sources ({total_sources}/{min_required})"
        )

    return {
        "price": round(statistics.median(all_prices.values()), 2),
        "sources": sorted(all_prices.keys()),
    }
