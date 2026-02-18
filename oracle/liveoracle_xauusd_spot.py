"""
Live XAUUSD Spot Oracle (Median of up to 8 sources)
Tier 1: Kitco, JM Bullion, GoldBroker
Tier 2: PAXG on Coinbase, Kraken, Gemini, Binance, OKX
"""
import hashlib, base64, sys
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
from ecdsa import SigningKey, SECP256k1

sys.path.insert(0, str(Path(__file__).parent.parent))
from oracle.feeds.xauusd import get_xauusd_price

app = FastAPI()

PRIVATE_KEY = SigningKey.generate(curve=SECP256k1)
PUBLIC_KEY = PRIVATE_KEY.get_verifying_key()


@app.get("/oracle/xauusd")
def oracle_xauusd():
    result = get_xauusd_price()
    value = f"{result['price']:.2f}"
    sources = result["sources"]
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    canonical = f"v1|XAUUSD|{value}|USD|2|{ts}|890123|{','.join(sorted(sources))}|median"
    h = hashlib.sha256(canonical.encode()).digest()
    sig = PRIVATE_KEY.sign_digest(h)
    return JSONResponse({
        "domain": "XAUUSD",
        "canonical": canonical,
        "signature": base64.b64encode(sig).decode(),
        "pubkey": PUBLIC_KEY.to_string("compressed").hex(),
    })


@app.get("/health")
def health():
    return {"status": "ok", "domain": "XAUUSD"}


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9105
    print(f"XAUUSD oracle on :{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
