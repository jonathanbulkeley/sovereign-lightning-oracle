"""
Sovereign Lightning Oracle (SLO) — Reference Oracle v1

This oracle serves signed BTCUSD price data gated by Lightning payment.

Lightning is treated as an external dependency via a backend interface.
This file ships with a simulated Lightning backend suitable for v1 demos.
"""

import hashlib
import base64
import sys
import uuid
from datetime import datetime, timezone
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

from ecdsa import SigningKey, SECP256k1

# ------------------------------------------------------------------------------
# Lightning backend interface
# ------------------------------------------------------------------------------

class LightningBackend:
    """
    Abstract Lightning interface.

    v1 requirements:
    - create_invoice(amount_sats, memo) -> invoice_id, invoice_string
    - is_paid(invoice_id) -> bool
    """

    def create_invoice(self, amount_sats: int, memo: str):
        raise NotImplementedError

    def is_paid(self, invoice_id: str) -> bool:
        raise NotImplementedError


class SimulatedLightningBackend(LightningBackend):
    """
    Simulated Lightning backend for v1 demos.

    Invoices are stored in memory and manually marked as paid.
    """

    def __init__(self):
        self._invoices: Dict[str, bool] = {}

    def create_invoice(self, amount_sats: int, memo: str):
        invoice_id = str(uuid.uuid4())
        self._invoices[invoice_id] = False
        invoice = f"ln_sim_{invoice_id}"
        return invoice_id, invoice

    def mark_paid(self, invoice_id: str):
        if invoice_id in self._invoices:
            self._invoices[invoice_id] = True

    def is_paid(self, invoice_id: str) -> bool:
        return self._invoices.get(invoice_id, False)


# ------------------------------------------------------------------------------
# Key handling
#
# NOTE:
# v1 generates a fresh key at startup.
# Operators MAY replace this with persisted key storage.
# ------------------------------------------------------------------------------

PRIVATE_KEY = SigningKey.generate(curve=SECP256k1)
PUBLIC_KEY = PRIVATE_KEY.get_verifying_key()

# ------------------------------------------------------------------------------
# Application setup
# ------------------------------------------------------------------------------

app = FastAPI()

PRICE_SATS = 10  # price per signed response

# Select Lightning backend (swap this later for a real node)
lightning = SimulatedLightningBackend()

# ------------------------------------------------------------------------------
# Oracle endpoints
# ------------------------------------------------------------------------------

@app.get("/quote")
def quote():
    """
    Request a Lightning invoice for BTCUSD price data.
    """
    invoice_id, invoice = lightning.create_invoice(
        amount_sats=PRICE_SATS,
        memo="SLO BTCUSD price"
    )

    return {
        "domain": "BTCUSD",
        "price_sats": PRICE_SATS,
        "invoice_id": invoice_id,
        "invoice": invoice,
    }


@app.post("/pay/{invoice_id}")
def pay(invoice_id: str):
    """
    Simulate payment of a Lightning invoice.

    NOTE:
    This endpoint exists only for the simulated backend.
    """
    if not isinstance(lightning, SimulatedLightningBackend):
        raise HTTPException(status_code=400, detail="Payment endpoint not supported")

    lightning.mark_paid(invoice_id)
    return {"status": "paid"}


@app.get("/paid/{invoice_id}")
def fetch_signed_price(invoice_id: str):
    """
    Return signed BTCUSD price data after payment verification.

    Invariant:
    - No signed data is released unless payment is confirmed.
    """
    if not lightning.is_paid(invoice_id):
        raise HTTPException(status_code=402, detail="Payment required")

    # --------------------------------------------------------------------------
    # Canonical price construction (simplified for v1)
    # --------------------------------------------------------------------------

    value = "43250.67"
    blockheight = "890123"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    canonical = (
        f"v1|BTCUSD|{value}|USD|2|{timestamp}|"
        f"{blockheight}|coinbase,kraken,bitstamp|median"
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


# ------------------------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1:
        port = int(sys.argv[1])

    print("SLO Reference Oracle v1")
    print(f"Public Key (hex): {PUBLIC_KEY.to_string('compressed').hex()}")
    print(f"Listening on http://127.0.0.1:{port}")

    uvicorn.run(app, host="127.0.0.1", port=port)