"""
Live ETHEUR Spot Oracle — Hybrid: 3 direct EUR pairs + cross-rate
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
from oracle.feeds.etheur import get_etheur_price

app = FastAPI()

@app.get("/oracle/etheur")
def oracle_etheur():
    result = get_etheur_price()
    value = f"{result['price']:.2f}"
    sources = result["sources"]
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    canonical = f"v1|ETHEUR|{value}|EUR|2|{ts}|890123|{','.join(sorted(sources))}|median"
    h = hashlib.sha256(canonical.encode()).digest()
    sig = PRIVATE_KEY.sign_digest(h)
    return JSONResponse({
        "domain": "ETHEUR",
        "canonical": canonical,
        "signature": base64.b64encode(sig).decode(),
        "pubkey": PUBLIC_KEY.to_string("compressed").hex(),
    })

@app.get("/health")
def health():
    return {"status": "ok", "domain": "ETHEUR"}

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9108
    print(f"ETHEUR oracle on :{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
