import json
import subprocess
import hashlib
import base64
import urllib.request
from fastmcp import FastMCP

mcp = FastMCP(
    name="Sovereign Lightning Oracle",
    instructions="You have access to a live Bitcoin, Ethereum, EUR/USD, Gold, Solana, and BTC/EUR price oracle on the Lightning Network. Each query costs real sats (10 for spot, 20 for VWAP) paid automatically via Lightning. Responses are cryptographically signed and independently verifiable. You also have access to the DLC oracle for Schnorr-signed hourly BTC/USD attestations with 5-digit numeric decomposition."
)

SLO_BASE = "http://104.197.109.246:8080"
SLO_SPOT_URL = f"{SLO_BASE}/oracle/btcusd"
SLO_VWAP_URL = f"{SLO_BASE}/oracle/btcusd/vwap"
SLO_ETHUSD_URL = f"{SLO_BASE}/oracle/ethusd"
SLO_EURUSD_URL = f"{SLO_BASE}/oracle/eurusd"
SLO_XAUUSD_URL = f"{SLO_BASE}/oracle/xauusd"
SLO_BTCEUR_URL = f"{SLO_BASE}/oracle/btceur"
SLO_SOLUSD_URL = f"{SLO_BASE}/oracle/solusd"

# DLC endpoints
SLO_DLC_PUBKEY_URL = f"{SLO_BASE}/dlc/oracle/pubkey"
SLO_DLC_STATUS_URL = f"{SLO_BASE}/dlc/oracle/status"
SLO_DLC_ANNOUNCEMENTS_URL = f"{SLO_BASE}/dlc/oracle/announcements"
SLO_DLC_ATTESTATIONS_URL = f"{SLO_BASE}/dlc/oracle/attestations"

LNGET_PATH = r"C:\Users\JBulkeley\lnget\lnget.exe"


def _clear_tokens():
    try:
        subprocess.run(
            [LNGET_PATH, "tokens", "clear", "--force"],
            capture_output=True, text=True, timeout=10
        )
    except Exception:
        pass


def _fetch_oracle(url):
    _clear_tokens()
    result = subprocess.run(
        [LNGET_PATH, "-k", "-q", url],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        raise RuntimeError(f"lnget failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def _fetch_free(url):
    """Fetch a free (no L402) endpoint via simple HTTP GET."""
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


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
    Costs 10 sats paid via Lightning. Returns median price from 9 exchanges
    with a cryptographic signature."""
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
    Costs 20 sats paid via Lightning."""
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


@mcp.tool()
def get_ethusd_spot() -> dict:
    """Get the current ETHUSD spot price from the Sovereign Lightning Oracle.
    Costs 10 sats paid via Lightning. Returns median price from
    Coinbase, Kraken, Bitstamp, Gemini, and Bitfinex."""
    data = _fetch_oracle(SLO_ETHUSD_URL)
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
def get_eurusd_spot() -> dict:
    """Get the current EURUSD spot price from the Sovereign Lightning Oracle.
    Costs 10 sats paid via Lightning. Returns median price from
    ECB, Bank of Canada, RBA, Norges Bank, Czech National Bank, Kraken,
    and Bitstamp."""
    data = _fetch_oracle(SLO_EURUSD_URL)
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
def get_xauusd_spot() -> dict:
    """Get the current XAU/USD (gold) spot price from the Sovereign Lightning Oracle.
    Costs 10 sats paid via Lightning. Returns median price from
    Kitco, JM Bullion, GoldBroker, Coinbase, Kraken, Gemini, Binance, and OKX."""
    data = _fetch_oracle(SLO_XAUUSD_URL)
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
def get_btceur_spot() -> dict:
    """Get the current BTC/EUR spot price from the Sovereign Lightning Oracle.
    Costs 10 sats paid via Lightning. Cross-rate derived from
    BTCUSD (9 sources) and EURUSD (7 sources)."""
    data = _fetch_oracle(SLO_BTCEUR_URL)
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
def get_solusd_spot() -> dict:
    """Get the current SOL/USD spot price from the Sovereign Lightning Oracle.
    Costs 10 sats paid via Lightning. Returns median price from
    Coinbase, Kraken, Bitstamp, Gemini, Bitfinex, Binance, OKX, Gate.io,
    and Bybit."""
    data = _fetch_oracle(SLO_SOLUSD_URL)
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


# ── DLC Oracle Tools ──────────────────────────────────────────────────────────


@mcp.tool()
def get_dlc_pubkey() -> dict:
    """Get the DLC oracle's public key (BIP-340 Schnorr).
    Free endpoint — no Lightning payment required."""
    return _fetch_free(SLO_DLC_PUBKEY_URL)


@mcp.tool()
def get_dlc_status() -> dict:
    """Get the DLC oracle status: announcement count, attestation count,
    pending events, and supported pairs.
    Free endpoint — no Lightning payment required."""
    return _fetch_free(SLO_DLC_STATUS_URL)


@mcp.tool()
def get_dlc_announcements() -> dict:
    """Get all DLC oracle announcements (pre-committed nonces for upcoming events).
    Each announcement contains R-points (public nonces) committed before the
    attestation is published. Free endpoint — no Lightning payment required."""
    return _fetch_free(SLO_DLC_ANNOUNCEMENTS_URL)


@mcp.tool()
def get_dlc_attestation(event_id: str) -> dict:
    """Get a specific DLC attestation by event ID (e.g. 'BTCUSD-2026-02-22T17:00:00Z').
    Returns Schnorr-signed 5-digit price decomposition with per-digit s-values.
    Costs 1000 sats paid via Lightning."""
    url = f"{SLO_DLC_ATTESTATIONS_URL}/{event_id}"
    return _fetch_oracle(url)


if __name__ == "__main__":
    mcp.run()
