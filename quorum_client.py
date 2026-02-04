"""
SLO Paid Oracle Client v1
- Enforces availability quorum
- Verifies oracle signatures
- Enforces price coherence
- Aggregates via median
"""

import requests
import hashlib
import base64
import statistics
from ecdsa import VerifyingKey, SECP256k1

# -------------------------
# Configuration
# -------------------------

ORACLES = [
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8001",
    "http://127.0.0.1:8002",
]

MIN_RESPONSES = 2
MAX_DEVIATION_PCT = 0.5  # percent allowed deviation from median

# -------------------------
# Helpers
# -------------------------

def pct_diff(a, b):
    return abs(a - b) / b * 100

# -------------------------
# Client execution
# -------------------------

prices = []
valid_oracles = 0

print("=" * 80)
print("SLO PAID ORACLE CLIENT v1 (TIGHT QUORUM)")
print("=" * 80)

for i, base_url in enumerate(ORACLES, start=1):
    print(f"\n[Oracle {i}] Resolving from {base_url}")

    try:
        # Request quote
        quote = requests.get(f"{base_url}/quote", timeout=5).json()
        invoice_id = quote["invoice_id"]
        invoice = quote["invoice"]

        print(f"  Invoice: {invoice}")
        print("  Paying invoice (simulated)...")

        # Pay invoice
        requests.post(f"{base_url}/pay/{invoice_id}", timeout=5)

        # Fetch paid data
        data = requests.get(f"{base_url}/paid/{invoice_id}", timeout=5).json()

        canonical = data["canonical"]
        signature = base64.b64decode(data["signature"])
        pubkey_hex = data["pubkey"]

        # Verify signature
        message_hash = hashlib.sha256(canonical.encode("utf-8")).digest()
        vk = VerifyingKey.from_string(bytes.fromhex(pubkey_hex), curve=SECP256k1)

        if not vk.verify_digest(signature, message_hash):
            print("  ✗ Invalid signature")
            continue

        price = float(canonical.split("|")[2])
        prices.append(price)
        valid_oracles += 1

        print(f"  Canonical: {canonical}")
        print("  ✓ Signature: VALID")

    except Exception as e:
        print(f"  ✗ Oracle failed: {e}")

# -------------------------
# Quorum enforcement
# -------------------------

if valid_oracles < MIN_RESPONSES:
    raise RuntimeError(
        f"Availability quorum not met: {valid_oracles}/{len(ORACLES)}"
    )

median_price = statistics.median(prices)

for p in prices:
    if pct_diff(p, median_price) > MAX_DEVIATION_PCT:
        raise RuntimeError(
            f"Price coherence failure: {p} deviates > {MAX_DEVIATION_PCT}% "
            f"from median {median_price}"
        )

# -------------------------
# Final output
# -------------------------

print("\n" + "=" * 80)
print(f"AGGREGATED PRICE (median): ${median_price:,.2f}")
print(
    f"Quorum satisfied: {valid_oracles} responses within "
    f"{MAX_DEVIATION_PCT}% deviation"
)
print("=" * 80)