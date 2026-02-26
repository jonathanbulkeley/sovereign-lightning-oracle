"""
Sovereign Lightning Oracle — Unified Server
All price oracle endpoints in a single FastAPI application.
"""
import hashlib
import base64
import sys
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
from ecdsa import SigningKey, SECP256k1

from feeds.btcusd import get_btcusd_price
from feeds.btcusd_vwap import get_btcusd_vwap_price
from feeds.ethusd import get_ethusd_price
from feeds.eurusd import get_eurusd_price
from feeds.xauusd import get_xauusd_price

PRIVATE_KEY = SigningKey.generate(curve=SECP256k1)
PUBLIC_KEY = PRIVATE_KEY.get_verifying_key()

app = FastAPI(
    title="Sovereign Lightning Oracle",
    description="L402-gated price oracle — pay sats, get signed data",
)

ORACLES = {
    "btcusd": {
        "feed": get_btcusd_price,
        "domain": "BTCUSD",
        "decimals": 2,
        "nonce": "890123",
        "method": "median",
    },
    "btcusd_vwap": {
        "feed": get_btcusd_vwap_price,
        "domain": "BTCUSD",
        "decimals": 2,
        "nonce": "890123",
        "method": "vwap",
    },
    "ethusd": {
        "feed": get_ethusd_price,
        "domain": "ETHUSD",
        "decimals": 2,
        "nonce": "890123",
        "method": "median",
    },
    "eurusd": {
        "feed": get_eurusd_price,
        "domain": "EURUSD",
        "decimals": 5,
        "nonce": "901234",
        "method": "median",
    },
    "xauusd": {
        "feed": get_xauusd_price,
        "domain": "XAUUSD",
        "decimals": 2,
        "nonce": "912345",
        "method": "median",
    },
}


def sign_and_respond(oracle_key):
    cfg = ORACLES[oracle_key]
    result = cfg["feed"]()
    price = result["price"]
    sources = result["sources"]
    decimals = cfg["decimals"]
    method = cfg["method"]
    value = f"{price:.{decimals}f}"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    source_str = ",".join(sorted(sources))
    canonical = f"v1|{cfg['domain']}|{value}|USD|{decimals}|{ts}|{cfg['nonce']}|{source_str}|{method}"
    h = hashlib.sha256(canonical.encode()).digest()
    sig = PRIVATE_KEY.sign_digest(h)
    return JSONResponse({
        "domain": cfg["domain"],
        "canonical": canonical,
        "signature": base64.b64encode(sig).decode(),
        "pubkey": PUBLIC_KEY.to_string("compressed").hex(),
    })


@app.get("/oracle/btcusd")
def oracle_btcusd():
    return sign_and_respond("btcusd")


@app.get("/oracle/btcusd/vwap")
def oracle_btcusd_vwap():
    return sign_and_respond("btcusd_vwap")


@app.get("/oracle/ethusd")
def oracle_ethusd():
    return sign_and_respond("ethusd")


@app.get("/oracle/eurusd")
def oracle_eurusd():
    return sign_and_respond("eurusd")


@app.get("/oracle/xauusd")
def oracle_xauusd():
    return sign_and_respond("xauusd")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": "v2",
        "pubkey": PUBLIC_KEY.to_string("compressed").hex(),
        "endpoints": [
            "/oracle/btcusd",
            "/oracle/btcusd/vwap",
            "/oracle/ethusd",
            "/oracle/eurusd",
            "/oracle/xauusd",
        ],
    }


@app.get("/oracle/status")
def oracle_status():
    status = {}
    for key, cfg in ORACLES.items():
        try:
            result = cfg["feed"]()
            status[key] = {
                "status": "ok",
                "price": result["price"],
                "sources": result["sources"],
                "source_count": len(result["sources"]),
            }
        except Exception as e:
            status[key] = {
                "status": "error",
                "error": str(e),
            }
    return JSONResponse(status)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9100
    print(f"Sovereign Lightning Oracle v2 starting on :{port}")
    print(f"  Public key: {PUBLIC_KEY.to_string('compressed').hex()}")
    for key, cfg in ORACLES.items():
        print(f"    /oracle/{key.replace('_', '/')} — {cfg['domain']} ({cfg['method']})")
    uvicorn.run(app, host="0.0.0.0", port=port)
