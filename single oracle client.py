

"""
SLO Single-Oracle Client (Demo / Bootstrap Mode)

- Queries exactly one oracle
- Requires payment before disclosure
- Verifies signature and canonical format
- No quorum, no aggregation
- Explicitly trusts a single oracle
"""

import sys
import requests
import hashlib
import base64
from ecdsa import VerifyingKey, SECP256k1

# -------------------------
# Configuration
# -------------------------

DEFAULT_ORACLE = "http://127.0.0.1:8000"

# -------------------------
# Helpers
# -------------------------

def verify_signature(canonical, signature_b64, pubkey_hex):
    message_hash = hashlib.sha256(canonical.encode("utf-8")).digest()
    signature = base64.b64decode(signature_b64)
    vk = VerifyingKey.from_string(bytes.fromhex(pubkey_hex), curve=SECP256k1)
    return vk.verify_digest(signature, message_hash)

# -------------------------
# Main
# -------------------------

oracle_url = DEFAULT_ORACLE
if len(sys.argv) > 1:
    oracle_url = sys.argv[1]

print("=" * 80)
print("SLO SINGLE-ORACLE CLIENT v1 (DEMO MODE)")
print(f"Oracle: {oracle_url}")
print("=" * 80)

try:
    # Request quote
    quote = requests.get(f"{oracle_url}/quote", timeout=5).json()

    invoice_id = quote["invoice_id"]
    invoice = quote["invoice"]

    print(f"Invoice: {invoice}")
    print("Paying invoice (simulated)...")

    # Pay invoice
    requests.post(f"{oracle_url}/pay/{invoice_id}", timeout=5)

    # Fetch paid data
    data = requests.get(f"{oracle_url}/paid/{invoice_id}", timeout=5).json()

    canonical = data["canonical"]
    signature = data["signature"]
    pubkey = data["pubkey"]

    # Verify
    valid = verify_signature(canonical, signature, pubkey)

    print("\nCanonical assertion:")
    print(canonical)
    print(f"\nSignature verification: {'VALID' if valid else 'INVALID'}")

    if not valid:
        raise RuntimeError("Signature verification failed")

    # Extract value
    parts = canonical.split("|")
    domain = parts[1]
    value = parts[2]
    unit = parts[3]

    print("\n" + "=" * 80)
    print(f"RESOLVED ({domain}): {value} {unit}")
    print("Trust model: SINGLE ORACLE (explicit)")
    print("=" * 80)

except Exception as e:
    print("\n✗ Resolution failed")
    print(str(e))

