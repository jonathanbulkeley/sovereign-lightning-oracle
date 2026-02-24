# liveoracle_solusd_spot.py
"""
Live SOLUSD Spot Oracle (Median of 9 sources with USDT normalization)
SLO v1 — L402-gated via L402 proxy

9 sources:
  Tier 1 (USD): Coinbase, Kraken, Bitstamp, Gemini, Bitfinex
  Tier 2 (USDT normalized): Binance, OKX, Gate.io, Bybit

Port: 9107
Path: /oracle/solusd
"""
import hashlib, base64, sys
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
from ecdsa import SigningKey, SECP256k1
import sys; sys.path.insert(0, "/home/jonathan_bulkeley/slo"); from oracle.keys import PRIVATE_KEY, PUBLIC_KEY

sys.path.insert(0, str(Path(__file__).parent.parent))
from oracle.feeds.solusd import get_solusd_price

app = FastAPI()
# Key loaded from oracle/keys/ (persistent, shared across all backends)

@app.get("/oracle/solusd")
def oracle_solusd():
    result = get_solusd_price()
    value = f"{result['price']:.4f}"
    sources = result["sources"]
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    canonical = f"v1|SOLUSD|{value}|USD|4|{ts}|890123|{','.join(sorted(sources))}|median"
    h = hashlib.sha256(canonical.encode()).digest()
    sig = PRIVATE_KEY.sign_digest(h)
    return JSONResponse({
        "domain": "SOLUSD",
        "canonical": canonical,
        "signature": base64.b64encode(sig).decode(),
        "pubkey": PUBLIC_KEY.to_string("compressed").hex(),
    })

@app.get("/health")
def health():
    return {"status": "ok", "domain": "SOLUSD", "version": "v1"}

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9107
    print(f"SLO SOLUSD Oracle (L402-backed) starting on :{port}")
    print(f"  Public key: {PUBLIC_KEY.to_string('compressed').hex()}")
    print(f"  Sources: Coinbase, Kraken, Bitstamp, Gemini, Bitfinex, Binance, OKX, Gate.io, Bybit")
    print(f"  Endpoint:   GET /oracle/solusd (gated by L402 proxy)")
    print(f"  Health:     GET /health (ungated)")
    uvicorn.run(app, host="0.0.0.0", port=port)
