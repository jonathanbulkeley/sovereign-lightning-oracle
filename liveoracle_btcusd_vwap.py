# liveoracle_btcusd_vwap.py
"""
Live BTCUSD VWAP Oracle (5-minute window)
"""

import hashlib, base64, sys, uuid, statistics, requests, time
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
from ecdsa import SigningKey, SECP256k1

app = FastAPI()

PRIVATE_KEY = SigningKey.generate(curve=SECP256k1)
PUBLIC_KEY = PRIVATE_KEY.get_verifying_key()
invoices = {}
PRICE_SATS = 20

def vwap(trades):
    vol = sum(t["size"] for t in trades)
    return sum(t["price"] * t["size"] for t in trades) / vol

def fetch_coinbase():
    r = requests.get("https://api.exchange.coinbase.com/products/BTC-USD/trades", timeout=5)
    trades = [{"price":float(t["price"]), "size":float(t["size"])} for t in r.json()]
    return vwap(trades)

def fetch_kraken():
    since = int(time.time() - 300)
    r = requests.get("https://api.kraken.com/0/public/Trades?pair=XBTUSD", timeout=5)
    trades = [{"price":float(t[0]), "size":float(t[1])} for t in r.json()["result"]["XXBTZUSD"]]
    return vwap(trades)

def get_price():
    prices=[]
    for f in (fetch_coinbase, fetch_kraken):
        try: prices.append(f())
        except: pass
    if len(prices)<1:
        raise RuntimeError("insufficient sources")
    return round(statistics.median(prices),2)

@app.get("/quote")
def quote():
    i=str(uuid.uuid4())
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
    value=f"{get_price():.2f}"
    ts=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    canonical=f"v1|BTCUSD|{value}|USD|2|{ts}|890123|coinbase,kraken|vwap"
    h=hashlib.sha256(canonical.encode()).digest()
    sig=PRIVATE_KEY.sign_digest(h)
    return JSONResponse({
        "domain":"BTCUSD",
        "canonical":canonical,
        "signature":base64.b64encode(sig).decode(),
        "pubkey":PUBLIC_KEY.to_string("compressed").hex()
    })

if __name__=="__main__":
    port=int(sys.argv[1]) if len(sys.argv)>1 else 8002

    uvicorn.run(app, host="127.0.0.1", port=port)
