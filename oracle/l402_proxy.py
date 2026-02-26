"""
L402 REST Proxy for SLO — uses LND REST API + real macaroons.
"""
import base64
import hashlib
import json
import os
import secrets
import traceback
import requests
from pymacaroons import Macaroon, Verifier
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
import uvicorn
import sys

app = FastAPI()

LND_REST = "https://mycelia.m.voltageapp.io:8080"
TLS_CERT = "/home/jonathan_bulkeley/slo/creds/tls.cert"
MACAROON_PATH = "/home/jonathan_bulkeley/slo/creds/admin.macaroon"

with open(MACAROON_PATH, "rb") as f:
    MACAROON_HEX = f.read().hex()

MACAROON_SECRET = os.environ.get("MACAROON_SECRET", secrets.token_hex(32))

ROUTES = {
    "/oracle/btcusd": {"backend": "http://127.0.0.1:9100/oracle/btcusd", "price": 10},
    "/oracle/btcusd/vwap": {"backend": "http://127.0.0.1:9101/oracle/btcusd/vwap", "price": 20},
    "/oracle/ethusd": {"backend": "http://127.0.0.1:9102/oracle/ethusd", "price": 10},
    "/oracle/eurusd": {"backend": "http://127.0.0.1:9103/oracle/eurusd", "price": 10},
    "/oracle/xauusd": {"backend": "http://127.0.0.1:9100/oracle/xauusd", "price": 10},
}


def create_invoice(amount_sats, memo="L402"):
    resp = requests.post(
        f"{LND_REST}/v1/invoices",
        headers={"Grpc-Metadata-macaroon": MACAROON_HEX},
        json={"value": str(amount_sats), "memo": memo},
        verify=TLS_CERT,
        timeout=10,
    )
    data = resp.json()
    r_hash = base64.b64decode(data["r_hash"])
    return data["payment_request"], r_hash


def mint_macaroon(payment_hash):
    mac = Macaroon(
        location="slo",
        identifier=payment_hash.hex(),
        key=MACAROON_SECRET,
    )
    raw = mac.serialize()
    mac_bytes = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    return base64.b16encode(mac_bytes).decode().lower()


def verify_l402(macaroon_hex, preimage_hex):
    try:
        mac_bytes = bytes.fromhex(macaroon_hex)
        mac_b64 = base64.urlsafe_b64encode(mac_bytes).decode().rstrip("=")
        mac = Macaroon.deserialize(mac_b64)
        payment_hash_hex = mac.identifier
        preimage = bytes.fromhex(preimage_hex)
        expected_hash = bytes.fromhex(payment_hash_hex)
        actual_hash = hashlib.sha256(preimage).digest()
        if actual_hash != expected_hash:
            return False
        v = Verifier()
        v.verify(mac, MACAROON_SECRET)
        return True
    except Exception as e:
        print(f"Verify error: {e}")
        return False


@app.get("/health")
async def health():
    try:
        resp = requests.get("http://127.0.0.1:9100/health", timeout=10)
        return JSONResponse(json.loads(resp.text))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)


@app.get("/oracle/status")
async def status():
    try:
        resp = requests.get("http://127.0.0.1:9100/oracle/status", timeout=30)
        return JSONResponse(json.loads(resp.text))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)


@app.api_route("/{path:path}", methods=["GET"])
async def proxy(request: Request, path: str):
    full_path = f"/{path}"

    if full_path not in ROUTES:
        return JSONResponse({"error": "not found"}, status_code=404)

    route = ROUTES[full_path]

    auth = request.headers.get("Authorization", "")
    if auth.startswith("L402 ") or auth.startswith("LSAT "):
        try:
            token = auth.split(" ", 1)[1]
            macaroon_hex, preimage_hex = token.split(":")
            if verify_l402(macaroon_hex, preimage_hex):
                resp = requests.get(route["backend"], timeout=15)
                return JSONResponse(json.loads(resp.text))
        except Exception as e:
            print(f"Auth parse error: {e}")
        return JSONResponse({"error": "invalid token"}, status_code=401)

    try:
        payment_request, payment_hash = create_invoice(route["price"], f"SLO {full_path}")
        mac_hex = mint_macaroon(payment_hash)
        return Response(
            content="Payment Required",
            status_code=402,
            headers={
                "WWW-Authenticate": f'L402 macaroon="{mac_hex}", invoice="{payment_request}"',
            },
        )
    except Exception as e:
        traceback.print_exc()
        return JSONResponse({"error": f"invoice creation failed: {e}"}, status_code=500)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print(f"SLO L402 REST Proxy on :{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
