# liveoracle_btcusd_spot.py
"""
Live BTCUSD Spot Oracle (Median of 9 sources with USDT normalization)
"""
import hashlib, base64, sys
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
from ecdsa import SigningKey, SECP256k1

sys.path.insert(0, str(Path(__file__).parent.parent))
from oracle.feeds.btcusd import get_btcusd_price

app = FastAPI()
PRIVATE_KEY = SigningKey.generate(curve=SECP256k1)
PUBLIC_KEY = PRIVATE_KEY.get_verifying_key()

@app.get("/oracle/btcusd")
def oracle_btcusd():
    result = get_btcusd_price()
    value = f"{result['price']:.2f}"
    sources = result["sources"]
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    canonical = f"v1|BTCUSD|{value}|USD|2|{ts}|890123|{','.join(sorted(sources))}|median"
    h = hashlib.sha256(canonical.encode()).digest()
    sig = PRIVATE_KEY.sign_digest(h)
    return JSONResponse({
        "domain": "BTCUSD",
        "canonical": canonical,
        "signature": base64.b64encode(sig).decode(),
        "pubkey": PUBLIC_KEY.to_string("compressed").hex(),
    })

@app.get("/health")
def health():
    return {"status": "ok", "domain": "BTCUSD", "version": "v1"}

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9100
    uvicorn.run(app, host="0.0.0.0", port=port)
