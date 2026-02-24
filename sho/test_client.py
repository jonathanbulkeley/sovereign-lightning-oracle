# sho/test_client.py
"""
SHO Test Client — End-to-end x402 payment flow

Tests the full x402 flow:
  1. Request without payment → get 402 + payment requirements
  2. (Simulate) Submit payment on Base
  3. Retry with x402 payment header → get Ed25519-signed attestation
  4. Verify Ed25519 signature

For testing without real payments, use --mock to skip payment verification.
"""

import argparse
import hashlib
import base64
import json
import sys

import httpx


def test_info(base_url: str):
    """Fetch SHO info endpoint."""
    print("=== SHO Info ===")
    resp = httpx.get(f"{base_url}/sho/info")
    data = resp.json()
    print(f"  Protocol:    {data['protocol']}")
    print(f"  Signing:     {data['signing_scheme']}")
    print(f"  Pubkey:      {data['pubkey'][:32]}...")
    print(f"  Chain:       {data['payment_chain']}")
    print(f"  Asset:       {data['payment_asset']}")
    print(f"  Address:     {data['payment_address']}")
    print(f"  Depeg:       {data['depeg_active']}")
    print(f"  Endpoints:   {len(data['endpoints'])}")
    for ep, info in data["endpoints"].items():
        print(f"    {ep}: ${info['price_usd']}")
    return data


def test_402_challenge(base_url: str, endpoint: str = "/oracle/btcusd"):
    """Request an endpoint without payment — expect 402."""
    print(f"\n=== 402 Challenge: {endpoint} ===")
    resp = httpx.get(f"{base_url}{endpoint}")
    print(f"  Status: {resp.status_code}")
    data = resp.json()

    if resp.status_code == 402:
        x402 = data.get("x402", {})
        print(f"  Chain:     {x402.get('chain')}")
        print(f"  Asset:     {x402.get('asset')}")
        print(f"  Recipient: {x402.get('recipient')}")
        print(f"  Amount:    ${x402.get('amount')}")
        print(f"  Nonce:     {x402.get('nonce')}")
        print(f"  Expires:   {x402.get('expires_in')}s")
        return data
    else:
        print(f"  Unexpected response: {data}")
        return None


def test_paid_request(base_url: str, endpoint: str, tx_hash: str, nonce: str, from_addr: str = "0xtest"):
    """Submit a paid request with x402 payment header."""
    print(f"\n=== Paid Request: {endpoint} ===")
    payment_header = json.dumps({
        "tx_hash": tx_hash,
        "nonce": nonce,
        "from": from_addr,
    })

    resp = httpx.get(
        f"{base_url}{endpoint}",
        headers={"X-Payment": payment_header},
    )
    print(f"  Status: {resp.status_code}")
    data = resp.json()

    if resp.status_code == 200:
        print(f"  Domain:    {data.get('domain')}")
        print(f"  Signing:   {data.get('signing_scheme')}")
        print(f"  Pubkey:    {data.get('pubkey', '')[:32]}...")
        print(f"  Confirmed: {data.get('payment', {}).get('confirmed')}")

        # Parse canonical
        canonical = data.get("canonical", "")
        parts = canonical.split("|")
        if len(parts) >= 3:
            print(f"  Price:     {parts[2]}")
            print(f"  Timestamp: {parts[5] if len(parts) > 5 else 'N/A'}")

        # Verify Ed25519 signature
        if data.get("signing_scheme") == "ed25519":
            verified = verify_ed25519(canonical, data["signature"], data["pubkey"])
            print(f"  Sig Valid: {verified}")

        return data
    else:
        print(f"  Error: {data}")
        return None


def verify_ed25519(canonical: str, signature_b64: str, pubkey_hex: str) -> bool:
    """Verify an Ed25519 signature on a canonical message."""
    try:
        from nacl.signing import VerifyKey
        msg_hash = hashlib.sha256(canonical.encode()).digest()
        sig = base64.b64decode(signature_b64)
        vk = VerifyKey(bytes.fromhex(pubkey_hex))
        vk.verify(msg_hash, sig)
        return True
    except Exception as e:
        print(f"  Verification error: {e}")
        return False


def test_enforcement(base_url: str, address: str = "0xtest"):
    """Check enforcement status for an address."""
    print(f"\n=== Enforcement Status: {address} ===")
    resp = httpx.get(f"{base_url}/sho/enforcement/{address}")
    data = resp.json()
    print(f"  Allowed: {data.get('allowed')}")
    print(f"  Reason:  {data.get('reason')}")
    print(f"  Tier:    {data.get('tier')}")
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SHO x402 Test Client")
    parser.add_argument("--url", default="http://127.0.0.1:8402", help="SHO proxy URL")
    parser.add_argument("--endpoint", default="/oracle/btcusd", help="Oracle endpoint to test")
    parser.add_argument("--tx-hash", help="Real tx hash for paid request test")
    args = parser.parse_args()

    print("SHO x402 Test Client")
    print("=" * 50)

    # Test 1: Info endpoint
    info = test_info(args.url)

    # Test 2: 402 challenge
    challenge = test_402_challenge(args.url, args.endpoint)

    # Test 3: Enforcement check
    test_enforcement(args.url)

    # Test 4: Paid request (if tx_hash provided)
    if args.tx_hash and challenge:
        nonce = challenge.get("x402", {}).get("nonce", "")
        test_paid_request(args.url, args.endpoint, args.tx_hash, nonce)
    else:
        print("\n  Skipping paid request (no --tx-hash provided)")
        print("  To test full flow, submit a USDC payment on Base and provide the tx hash")

    print("\n" + "=" * 50)
    print("Done.")
