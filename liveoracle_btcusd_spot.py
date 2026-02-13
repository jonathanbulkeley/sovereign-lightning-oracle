# liveoracle_btcusd_spot.py
"""
Live BTCUSD Spot Oracle (Median of Last Trades)
SLO v1 — L402-gated via Aperture
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
    r = requests.get("https://api.exchange.coinbase.com/products/BTC-USD/ticker", timeout=5)
    return float(r.json()["price"])
def fetch_kraken():
    r = requests.get("https://api.kraken.com/0/public/Ticker?pair=XBTUSD", timeout=5)
    pair = list(r.json()["result"].keys())[0]
    return float(r.json()["result"][pair]["c"][0])
def fetch_bitstamp():
    r = requests.get("https://www.bitstamp.net/api/v2/ticker/btcusd/", timeout=5)
    return float(r.json()["last"])
def get_price():
    prices = []
    for f in (fetch_coinbase, fetch_kraken, fetch_bitstamp):
        try: prices.append(f())
        except: pass
    if len(prices) < 2:
        raise RuntimeError("insufficient sources")
    return round(statistics.median(prices), 2)
@app.get("/oracle/btcusd")
def oracle_btcusd():
    value = f"{get_price():.2f}"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    canonical = f"v1|BTCUSD|{value}|USD|2|{ts}|890123|coinbase,kraken,bitstamp|median"
    h = hashlib.sha256(canonical.encode()).digest()
    sig = PRIVATE_KEY.sign_digest(h)
    return JSONResponse({"domain":"BTCUSD","canonical":canonical,"signature":base64.b64encode(sig).decode(),"pubkey":PUBLIC_KEY.to_string("compressed").hex()})
@app.get("/health")
def health():
    return {"status":"ok","domain":"BTCUSD","version":"v1"}
if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv)>1 else 9100
    print(f"SLO Spot Oracle starting on :{port}")
    print(f"  Public key: {PUBLIC_KEY.to_string('compressed').hex()}")
    print(f"  Endpoint:   GET /oracle/btcusd")
    uvicorn.run(app, host="0.0.0.0", port=port)
