"""
Oracle server with simulated Lightning payment gate
and live BTCUSD price fetch (reference implementation).
"""

import hashlib
from datetime import datetime, timezone
import base64
import sys
import uuid
import statistics
import requests

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

from ecdsa import SigningKey, SECP256k1

app = FastAPI()

PRIVATE_KEY = SigningKey.generate(curve=SECP256k1)
PUBLIC_KEY = PRIVATE_KEY.get_verifying_key()

# In-memory "invoices"
invoices = {}

PRICE_SATS = 10  # fake price for demo


# -------------------------
# Price fetch helpers
# -------------------------

def fetch_coinbase():
    # Coinbase BTC-USD last trade price
    r = requests.get("https://api.exchange.coinbase.com/products/BTC-USD/ticker", timeout=5)
    data = r.json()
    return float(data["price"])


def fetch_kraken():
    # Kraken BTC/USD last trade price
    r = requests.get("https://api.kraken.com/0/public/Ticker?pair=XBTUSD", timeout=5)
    data = r.json()
    pair = list(data["result"].keys())[0]
    return float(data["result"][pair]["c"][0])


def fetch_bitstamp():
    # Bitstamp BTC/USD last trade price
    r = requests.get("https://www.bitstamp.net/api/v2/ticker/btcusd/", timeout=5)
    data = r.json()
    return float(data["last"])


def get_live_btcusd_price():
    prices = []

    for fetch in (fetch_coinbase, fetch_kraken, fetch_bitstamp):
        try:
            prices.append(fetch())
        except Exception:
            pass

    if len(prices) < 2:
        raise RuntimeError("Insufficient price sources")

    median_price = statistics.median(prices)
    return round(median_price, 2)


# -------------------------
# API endpoints
# -------------------------

@app.get("/quote")
def get_quote():
    invoice_id = str(uuid.uuid4())
    invoices[invoice_id] = False  # unpaid

    return {
        "domain": "BTCUSD",
        "price_sats": PRICE_SATS,
        "invoice_id": invoice_id,
        "invoice": f"ln_sim_{invoice_id}",
    }


@app.post("/pay/{invoice_id}")
def pay_invoice(invoice_id: str):
    if invoice_id in invoices:
        invoices[invoice_id] = True
        return {"status": "paid"}
    return {"error": "unknown invoice"}


@app.get("/paid/{invoice_id}")
def get_paid_price(invoice_id: str):
    if invoice_id not in invoices:
        return {"error": "unknown invoice"}

    if not invoices[invoice_id]:
        return {"error": "invoice not paid"}

    try:
        value = f"{get_live_btcusd_price():.2f}"
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": "price fetch failed"},
        )

    blockheight = "890123"  # placeholder
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    canonical = (
        f"v1|BTCUSD|{value}|USD|2|{timestamp}|{blockheight}"
        f"|coinbase,kraken,bitstamp|median"
    )

    message_hash = hashlib.sha256(canonical.encode("utf-8")).digest()
    signature = PRIVATE_KEY.sign_digest(message_hash)

    response = {
        "domain": "BTCUSD",
        "canonical": canonical,
        "signature": base64.b64encode(signature).decode("utf-8"),
        "pubkey": PUBLIC_KEY.to_string("compressed").hex(),
    }

    return JSONResponse(content=response)


# -------------------------
# Entrypoint
# -------------------------

if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1:
        port = int(sys.argv[1])

    print(f"Public Key (hex): {PUBLIC_KEY.to_string('compressed').hex()}")
    print(f"Starting server on http://127.0.0.1:{port}")

    uvicorn.run(app, host="127.0.0.1", port=port)