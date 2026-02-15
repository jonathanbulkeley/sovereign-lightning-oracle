# liveoracle_ethusd_spot.py
"""
Live ETHUSD Spot Oracle (Median of Last Trades)
SLO v1 - L402-gated via Aperture
5 sources: Coinbase, Kraken, Bitstamp, Gemini, Bitfinex
"""
import hashlib, base64, sys, statistics, requests
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
from ecdsa import SigningKey, SECP256k1
app = FastAPI()
PRIVATE_KEY = SigningKey.generate(curve=SECP256k1)
PUBLIC_KEY = PRIVATE_KEY.get_verifying_key()
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
def get_price():
    prices = []
    sources = []
    for name, f in [("coinbase", fetch_coinbase), ("kraken", fetch_kraken),
                     ("bitstamp", fetch_bitstamp), ("gemini", fetch_gemini),
                     ("bitfinex", fetch_bitfinex)]:
        try:
            prices.append(f())
            sources.append(name)
        except Exception:
            pass
    if len(prices) < 3:
        raise RuntimeError("insufficient sources")
    return round(statistics.median(prices), 2), ",".join(sources)
@app.get("/oracle/ethusd")
def oracle_ethusd():
    value_raw, source_str = get_price()
    value = f"{value_raw:.2f}"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    canonical = f"v1|ETHUSD|{value}|USD|2|{ts}|890123|{source_str}|median"
    h = hashlib.sha256(canonical.encode()).digest()
    sig = PRIVATE_KEY.sign_digest(h)
    return JSONResponse({"domain":"ETHUSD","canonical":canonical,"signature":base64.b64encode(sig).decode(),"pubkey":PUBLIC_KEY.to_string("compressed").hex()})
@app.get("/health")
def health():
    return {"status":"ok","domain":"ETHUSD","version":"v1"}
if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv)>1 else 9102
    uvicorn.run(app, host="0.0.0.0", port=port)
