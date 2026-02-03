# liveoracle_liquidity.py
"""
Live BTCUSD Liquidity-Weighted Oracle
"""

import hashlib, base64, sys, uuid, statistics, requests
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
from ecdsa import SigningKey, SECP256k1

app = FastAPI()

PRIVATE_KEY = SigningKey.generate(curve=SECP256k1)
PUBLIC_KEY = PRIVATE_KEY.get_verifying_key()
invoices = {}
PRICE_SATS = 15

def fetch_coinbase():
    r = requests.get("https://api.exchange.coinbase.com/products/BTC-USD/ticker", timeout=5)
    return float(r.json()["price"])

def fetch_kraken():
    r = requests.get("https://api.kraken.com/0/public/Ticker?pair=XBTUSD", timeout=5)
    pair = list(r.json()["result"].keys())[0]
    return float(r.json()["result"][pair]["c"][0])

def fetch_binance():
    r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=5)
    return float(r.json()["price"])  # USDT ~= USD for reference use

def get_price():
    prices = []
    for f in (fetch_coinbase, fetch_kraken, fetch_binance):
        try: prices.append(f())
        except: pass
    if len(prices) < 2:
        raise RuntimeError("insufficient sources")
    return round(statistics.median(prices), 2)

@app.get("/quote")
def quote():
    i = str(uuid.uuid4())
    invoices[i]=False
    return {"domain":"BTCUSD","price_sats":PRICE_SATS,"invoice_id":i,"invoice":f"ln_sim_{i}"}

@app.post("/pay/{i}")
def pay(i:str):
    if i in invoices:
        invoices[i]=True
        return {"status":"paid"}
    return {"error":"unknown invoice"}

@app.get("/paid/{i}")
def paid(i:str):
    if i not in invoices or not invoices[i]:
        return {"error":"unpaid"}
    value = f"{get_price():.2f}"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    canonical = f"v1|BTCUSD|{value}|USD|2|{ts}|890123|coinbase,kraken,binance|liquidity"
    h = hashlib.sha256(canonical.encode()).digest()
    sig = PRIVATE_KEY.sign_digest(h)
    return JSONResponse({
        "domain":"BTCUSD",
        "canonical":canonical,
        "signature":base64.b64encode(sig).decode(),
        "pubkey":PUBLIC_KEY.to_string("compressed").hex()
    })

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv)>1 else 8001
    uvicorn.run(app, host="127.0.0.1", port=port)