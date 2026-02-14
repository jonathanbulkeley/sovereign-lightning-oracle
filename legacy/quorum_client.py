# quorum_client_l402.py
"""
SLO Quorum Client — L402 Edition

Queries multiple L402-gated oracles, verifies signatures,
and aggregates prices via median with coherence checks.

Backends:
  lnget   — Lightning Labs CLI (preferred, handles L402 transparently)
  sim     — Simulated backend for testing without Lightning
"""

import argparse
import json
import hashlib
import subprocess
import statistics
import sys
from ecdsa import VerifyingKey, SECP256k1
import base64

# --- Configuration ---

MIN_RESPONSES = 2
MAX_DEVIATION_PCT = 0.5

ORACLES = [
    {
        "name": "spot",
        "url": "http://104.197.109.246:8080/oracle/btcusd",
        "pubkey": None,
    },
    {
        "name": "vwap",
        "url": "http://104.197.109.246:8080/oracle/btcusd/vwap",
        "pubkey": None,
    },
]

# --- Signature verification ---

def verify_signature(canonical: str, signature_b64: str, pubkey_hex: str) -> bool:
    try:
        sig_bytes = base64.b64decode(signature_b64)
        pubkey_bytes = bytes.fromhex(pubkey_hex)
        vk = VerifyingKey.from_string(pubkey_bytes, curve=SECP256k1)
        h = hashlib.sha256(canonical.encode()).digest()
        return vk.verify_digest(sig_bytes, h)
    except Exception as e:
        print(f"  Signature verification failed: {e}")
        return False

# --- Backends ---

def fetch_lnget(url: str) -> dict:
    """Fetch via lnget (handles L402 payment automatically)."""
    result = subprocess.run(
        ["lnget", "-k", "-q", url],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        raise RuntimeError(f"lnget failed: {result.stderr.strip()}")
    return json.loads(result.stdout)

def fetch_sim(url: str) -> dict:
    """Simulated fetch — hits the oracle directly (no payment gate)."""
    import requests
    r = requests.get(url, timeout=10)
    return r.json()

BACKENDS = {
    "lnget": fetch_lnget,
    "sim": fetch_sim,
}

# --- Quorum logic ---

def query_oracles(backend: str):
    fetch = BACKENDS[backend]
    results = []

    for oracle in ORACLES:
        print(f"\nQuerying {oracle['name']} at {oracle['url']}...")
        try:
            data = fetch(oracle["url"])
            canonical = data["canonical"]
            signature = data["signature"]
            pubkey = data["pubkey"]

            if not verify_signature(canonical, signature, pubkey):
                print(f"  REJECTED: invalid signature")
                continue

            if oracle["pubkey"] and oracle["pubkey"] != pubkey:
                print(f"  REJECTED: pubkey mismatch (expected {oracle['pubkey'][:16]}...)")
                continue

            parts = canonical.split("|")
            price = float(parts[2])
            print(f"  Price: ${price:.2f}")
            print(f"  Signature: VALID")
            print(f"  Pubkey: {pubkey[:24]}...")

            results.append({"oracle": oracle["name"], "price": price, "data": data})

        except Exception as e:
            print(f"  ERROR: {e}")
            continue

    return results

def aggregate(results):
    if len(results) < MIN_RESPONSES:
        print(f"\nQUORUM FAILED: got {len(results)} responses, need {MIN_RESPONSES}")
        return None

    prices = [r["price"] for r in results]
    median_price = statistics.median(prices)

    for r in results:
        deviation = abs(r["price"] - median_price) / median_price * 100
        if deviation > MAX_DEVIATION_PCT:
            print(f"\nCOHERENCE FAILURE: {r['oracle']} deviates {deviation:.2f}% from median")
            return None

    print(f"\n{'='*50}")
    print(f"QUORUM RESULT")
    print(f"  Oracles:  {len(results)}/{len(ORACLES)}")
    print(f"  Median:   ${median_price:.2f}")
    print(f"  Prices:   {', '.join(f'${p:.2f}' for p in prices)}")
    print(f"{'='*50}")

    return median_price

# --- Main ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SLO Quorum Client (L402)")
    parser.add_argument("--backend", choices=["lnget", "sim"], default="lnget",
                        help="Payment backend (default: lnget)")
    args = parser.parse_args()

    print(f"SLO Quorum Client — backend: {args.backend}")
    results = query_oracles(args.backend)
    price = aggregate(results)

    if price is None:
        sys.exit(1)
