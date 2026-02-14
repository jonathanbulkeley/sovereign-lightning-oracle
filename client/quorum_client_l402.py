"""
SLO Paid Oracle Client v1 — L402 Integration
- Pays oracles via L402 (Lightning) using lnget or Python fallback
- Enforces availability quorum
- Verifies oracle signatures
- Enforces price coherence
- Aggregates via median

Payment flow:
  1. Client sends GET to Aperture-fronted oracle endpoint
  2. Aperture returns HTTP 402 + Lightning invoice + macaroon
  3. Client pays invoice via Lightning, obtains preimage
  4. Client retries request with L402 token
  5. Oracle returns signed price assertion

Two payment backends are supported:
  A) lnget (preferred) — Lightning Labs CLI tool, handles L402 transparently
  B) Python L402 wrapper — uses RequestsL402Wrapper from LangChainBitcoin

Configure via PAYMENT_BACKEND below or --backend flag.
"""

import argparse
import base64
import hashlib
import json
import statistics
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

from ecdsa import SECP256k1, VerifyingKey

# -------------------------
# Configuration
# -------------------------
# These now point to the Aperture public proxy, NOT the oracle directly.
# Aperture handles L402 negotiation and proxies to the backend oracle.
ORACLES = [
    "http://127.0.0.1:8080/oracle/btcusd",  # Aperture -> oracle on :9100
    "http://127.0.0.1:8081/oracle/btcusd",  # Aperture -> oracle on :9101
    "http://127.0.0.1:8082/oracle/btcusd",  # Aperture -> oracle on :9102
]

# Expected public keys for each oracle (explicit trust per SLO protocol).
# In production, populate these from your config. Empty = skip pubkey check.
EXPECTED_PUBKEYS = {
    # "http://127.0.0.1:8080/oracle/btcusd": "02abcdef...",
}

MIN_RESPONSES = 2
MAX_DEVIATION_PCT = 0.5  # percent allowed deviation from median

# lnget configuration
LNGET_BIN = "lnget"  # Path to lnget binary
LNGET_MAX_COST = 100  # Max sats per request (safety cap)


# -------------------------
# Data structures
# -------------------------
@dataclass
class OracleResponse:
    url: str
    canonical: str
    price: float
    signature: bytes
    pubkey_hex: str
    valid: bool


# -------------------------
# Payment backends
# -------------------------
def fetch_via_lnget(url: str, max_cost: int = LNGET_MAX_COST) -> Optional[dict]:
    """
    Use lnget (Lightning Labs CLI) to fetch an L402-gated resource.

    lnget handles the full L402 flow transparently:
      - Sends initial GET
      - Receives 402 + invoice + macaroon
      - Pays invoice via connected LND node
      - Retries with L402 token
      - Returns the final response body

    --max-cost sets a per-request spending ceiling in sats.
    """
    try:
        result = subprocess.run(
            [
                LNGET_BIN,
                "--max-cost", str(max_cost),
                "--output", "-",  # stdout
                url,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"lnget failed: {result.stderr.strip()}")
        return json.loads(result.stdout)
    except FileNotFoundError:
        raise RuntimeError(
            f"lnget not found at '{LNGET_BIN}'. Install from: "
            "github.com/lightninglabs/lightning-agent-tools"
        )


def fetch_via_python_l402(url: str) -> Optional[dict]:
    """
    Fallback: Use LangChainBitcoin's RequestsL402Wrapper.

    Requires:
      pip install LangChainBitcoin
      LND node accessible via environment config.

    The wrapper intercepts 402 responses, pays the Lightning invoice
    using the configured LND node, and retries with the L402 token.
    """
    try:
        from lnurl import LndNode  # noqa
        from l402_wrapper import RequestsL402Wrapper  # noqa
    except ImportError:
        raise RuntimeError(
            "Python L402 fallback requires LangChainBitcoin. Install:\n"
            "  git clone https://github.com/lightninglabs/LangChainBitcoin.git\n"
            "  cd LangChainBitcoin && pip install -e ."
        )

    # Initialize LND connection from environment
    # Expects: LND_HOST, LND_MACAROON_PATH, LND_CERT_PATH
    import os

    lnd = LndNode(
        host=os.environ.get("LND_HOST", "localhost:10009"),
        macaroon_path=os.environ.get("LND_MACAROON_PATH", ""),
        cert_path=os.environ.get("LND_CERT_PATH", ""),
    )
    wrapper = RequestsL402Wrapper(lnd_node=lnd)
    response = wrapper.get(url, timeout=15)
    response.raise_for_status()
    return response.json()


def fetch_via_simulated(url: str) -> Optional[dict]:
    """
    Local simulation fallback for testing without Lightning.

    This reproduces the original 3-step flow (quote/pay/paid) for use
    with the non-Aperture version of the oracle. Useful for local dev
    before you have LND + Aperture running.
    """
    import requests

    # Derive base URL from the oracle URL
    # e.g., http://127.0.0.1:8080/oracle/btcusd -> http://127.0.0.1:8080
    from urllib.parse import urlparse

    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    quote = requests.get(f"{base_url}/quote", timeout=5).json()
    invoice_id = quote["invoice_id"]
    requests.post(f"{base_url}/pay/{invoice_id}", timeout=5)
    data = requests.get(f"{base_url}/paid/{invoice_id}", timeout=5).json()
    return data


BACKENDS = {
    "lnget": fetch_via_lnget,
    "python-l402": fetch_via_python_l402,
    "simulated": fetch_via_simulated,
}


# -------------------------
# Helpers
# -------------------------
def pct_diff(a, b):
    return abs(a - b) / b * 100


def verify_oracle_response(data: dict, url: str) -> OracleResponse:
    """Verify signature and parse canonical message per SLO v1 Protocol."""
    canonical = data["canonical"]
    signature = base64.b64decode(data["signature"])
    pubkey_hex = data["pubkey"]

    # Verify signature
    message_hash = hashlib.sha256(canonical.encode("utf-8")).digest()
    vk = VerifyingKey.from_string(bytes.fromhex(pubkey_hex), curve=SECP256k1)
    valid = False
    try:
        valid = vk.verify_digest(signature, message_hash)
    except Exception:
        valid = False

    # Verify pubkey matches expected (if configured)
    if url in EXPECTED_PUBKEYS:
        if pubkey_hex != EXPECTED_PUBKEYS[url]:
            valid = False

    # Parse price from canonical: v1|BTCUSD|<price>|USD|...
    price = float(canonical.split("|")[2])

    return OracleResponse(
        url=url,
        canonical=canonical,
        price=price,
        signature=signature,
        pubkey_hex=pubkey_hex,
        valid=valid,
    )


# -------------------------
# Client execution
# -------------------------
def run_quorum_client(backend_name: str = "lnget", oracles: list = None):
    if oracles is None:
        oracles = ORACLES

    fetch_fn = BACKENDS.get(backend_name)
    if not fetch_fn:
        raise ValueError(
            f"Unknown backend '{backend_name}'. Choose from: {list(BACKENDS.keys())}"
        )

    prices = []
    valid_oracles = 0

    print("=" * 80)
    print(f"SLO PAID ORACLE CLIENT v1 (L402 — backend: {backend_name})")
    print("=" * 80)

    for i, url in enumerate(oracles, start=1):
        print(f"\n[Oracle {i}] {url}")

        try:
            # Single call — L402 payment handled by backend
            print(f"  Fetching (L402 payment handled by {backend_name})...")
            data = fetch_fn(url)

            if "error" in data:
                print(f"  ✗ Oracle error: {data['error']}")
                continue

            # Verify signature and parse response
            result = verify_oracle_response(data, url)

            if not result.valid:
                print("  ✗ Invalid signature or pubkey mismatch")
                continue

            prices.append(result.price)
            valid_oracles += 1
            print(f"  Canonical: {result.canonical}")
            print(f"  Pubkey:    {result.pubkey_hex[:16]}...")
            print("  ✓ Signature: VALID")

        except Exception as e:
            print(f"  ✗ Oracle failed: {e}")

    # -------------------------
    # Quorum enforcement
    # -------------------------
    if valid_oracles < MIN_RESPONSES:
        raise RuntimeError(
            f"Availability quorum not met: {valid_oracles}/{len(oracles)}"
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

    return median_price


# -------------------------
# CLI
# -------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SLO Quorum Client (L402)")
    parser.add_argument(
        "--backend",
        choices=list(BACKENDS.keys()),
        default="lnget",
        help="Payment backend (default: lnget)",
    )
    parser.add_argument(
        "--oracles",
        nargs="+",
        default=None,
        help="Override oracle URLs (space-separated)",
    )
    parser.add_argument(
        "--max-cost",
        type=int,
        default=LNGET_MAX_COST,
        help="Max sats per request for lnget (default: 100)",
    )
    args = parser.parse_args()

    if args.max_cost != LNGET_MAX_COST:
        LNGET_MAX_COST = args.max_cost

    run_quorum_client(
        backend_name=args.backend,
        oracles=args.oracles,
    )