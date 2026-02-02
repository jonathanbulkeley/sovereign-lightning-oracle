"""
Sovereign Lightning Oracle (SLO) — Reference Client v1

This client:
- queries multiple paid oracles
- verifies signatures
- aggregates BTCUSD prices deterministically

Design goals:
- explicit trust boundaries
- explicit failure modes
- no retries, caching, or discovery
"""

import requests
import hashlib
import base64
import statistics
from ecdsa import VerifyingKey, SECP256k1

# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------

ORACLES = [
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8001",
    "http://127.0.0.1:8002",
]

# v1 requires all configured oracles to respond successfully
QUORUM = len(ORACLES)

# ------------------------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------------------------

def resolve_oracle(base_url: str):
    """
    Resolve BTCUSD price from a single oracle.

    Steps:
    1. Request quote
    2. Pay invoice (simulated)
    3. Fetch signed data
    4. Verify signature
    """
    # Step 1: request quote
    quote_resp = requests.get(f"{base_url}/quote")
    quote_resp.raise_for_status()
    quote = quote_resp.json()

    invoice_id = quote["invoice_id"]
    invoice = quote["invoice"]

    print(f"  Invoice: {invoice}")
    print("  Paying invoice (simulated)...")

    # Step 2: simulate payment
    pay_resp = requests.post(f"{base_url}/pay/{invoice_id}")
    pay_resp.raise_for_status()

    # Step 3: fetch signed data
    data_resp = requests.get(f"{base_url}/paid/{invoice_id}")
    data_resp.raise_for_status()
    data = data_resp.json()

    canonical = data["canonical"]
    signature = base64.b64decode(data["signature"])
    pubkey_hex = data["pubkey"]

    # Step 4: verify signature
    message_hash = hashlib.sha256(canonical.encode("utf-8")).digest()
    vk = VerifyingKey.from_string(bytes.fromhex(pubkey_hex), curve=SECP256k1)

    if not vk.verify_digest(signature, message_hash):
        raise RuntimeError("Signature verification failed")

    price = float(canonical.split("|")[2])
    return canonical, price


# ------------------------------------------------------------------------------
# Main resolution flow
# ------------------------------------------------------------------------------

print("=" * 80)
print("SLO PAID ORACLE CLIENT v1 (SIMULATED LIGHTNING)")
print("=" * 80)

resolved_prices = []

for i, base_url in enumerate(ORACLES, start=1):
    print(f"\n[Oracle {i}] Resolving from {base_url}")

    try:
        canonical, price = resolve_oracle(base_url)
        print(f"  Canonical: {canonical}")
        print("  ✓ Signature: VALID")
        resolved_prices.append(price)

    except Exception as e:
        print(f"  ✗ Oracle failed: {e}")

# ------------------------------------------------------------------------------
# Aggregation
# ------------------------------------------------------------------------------

if len(resolved_prices) < QUORUM:
    raise RuntimeError(
        f"Quorum not met: {len(resolved_prices)}/{QUORUM} valid responses"
    )

median_price = statistics.median(resolved_prices)

print("\n" + "=" * 80)
print(f"AGGREGATED PRICE (median): ${median_price:,.2f}")
print("=" * 80)