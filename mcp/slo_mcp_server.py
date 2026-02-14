import json
import subprocess
import hashlib
import base64
from fastmcp import FastMCP

mcp = FastMCP(
    name="Sovereign Lightning Oracle",
    instructions="You have access to a live Bitcoin price oracle on the Lightning Network. Each query costs real sats (10 for spot, 20 for VWAP) paid automatically via Lightning. Responses are cryptographically signed and independently verifiable."
)

SLO_SPOT_URL = "http://104.197.109.246:8080/oracle/btcusd"
SLO_VWAP_URL = "http://104.197.109.246:8080/oracle/btcusd/vwap"


def _fetch_oracle(url):
    result = subprocess.run(
        ["lnget", "-k", "-q", url],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        raise RuntimeError(f"lnget failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def _parse_canonical(canonical):
    parts = canonical.split("|")
    return {
        "version": parts[0],
        "pair": parts[1],
        "price": parts[2],
        "currency": parts[3],
        "decimals": int(parts[4]),
        "timestamp": parts[5],
        "nonce": parts[6],
        "sources": parts[7].split(","),
        "method": parts[8],
    }


def _verify_signature(canonical, signature_b64, pubkey_hex):
    try:
        from ecdsa import VerifyingKey, SECP256k1
        sig_bytes = base64.b64decode(signature_b64)
        pubkey_bytes = bytes.fromhex(pubkey_hex)
        vk = VerifyingKey.from_string(pubkey_bytes, curve=SECP256k1)
        h = hashlib.sha256(canonical.encode()).digest()
        return vk.verify_digest(sig_bytes, h)
    except Exception:
        return False


@mcp.tool()
def get_btcusd_spot() -> dict:
    """Get the current BTCUSD spot price from the Sovereign Lightning Oracle.
    Costs 10 sats paid via Lightning. Returns median price from
    Coinbase, Kraken, and Bitstamp with a cryptographic signature."""
    data = _fetch_oracle(SLO_SPOT_URL)
    parsed = _parse_canonical(data["canonical"])
    sig_valid = _verify_signature(data["canonical"], data["signature"], data["pubkey"])
    return {
        "price": parsed["price"],
        "currency": parsed["currency"],
        "timestamp": parsed["timestamp"],
        "sources": parsed["sources"],
        "method": parsed["method"],
        "signature_valid": sig_valid,
        "canonical": data["canonical"],
        "pubkey": data["pubkey"],
    }


@mcp.tool()
def get_btcusd_vwap() -> dict:
    """Get the current BTCUSD volume-weighted average price (VWAP).
    Costs 20 sats paid via Lightning. More accurate than spot for
    large orders or volatile markets."""
    data = _fetch_oracle(SLO_VWAP_URL)
    parsed = _parse_canonical(data["canonical"])
    sig_valid = _verify_signature(data["canonical"], data["signature"], data["pubkey"])
    return {
        "price": parsed["price"],
        "currency": parsed["currency"],
        "timestamp": parsed["timestamp"],
        "sources": parsed["sources"],
        "method": parsed["method"],
        "signature_valid": sig_valid,
        "canonical": data["canonical"],
        "pubkey": data["pubkey"],
    }


if __name__ == "__main__":
    mcp.run()
