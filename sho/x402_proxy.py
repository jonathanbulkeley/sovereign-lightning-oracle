# sho/x402_proxy.py
"""
SHO — Sovereign HTTP Oracle x402 Proxy
Phase 1 MVP

x402-compatible payment proxy for the Sovereign Lightning Oracle.
Sits alongside the L402 proxy, routing to the same oracle backends.
Handles USDC payment verification on Base, Ed25519 re-signing,
optimistic delivery, and tiered enforcement for failed payments.

Architecture:
  Consumer → SHO x402 Proxy (:8402) → Oracle Backend (:9100-9107)
                                    ↕
                              Base RPC (USDC verification)
"""

import hashlib
import json
import os
import time
import base64
import secrets
import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from nacl.signing import SigningKey, VerifyKey
from nacl.encoding import HexEncoder

# ── Configuration ─────────────────────────────────────────────────────────────

BASE_RPC_URL = os.environ.get("BASE_RPC_URL", "https://mainnet.base.org")
USDC_CONTRACT = os.environ.get("USDC_CONTRACT", "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913")  # USDC on Base
PAYMENT_ADDRESS = os.environ.get("SHO_PAYMENT_ADDRESS", "")  # Oracle's USDC receiving address on Base
DEPEG_THRESHOLD = float(os.environ.get("DEPEG_THRESHOLD", "0.02"))  # 2%

SHO_PORT = int(os.environ.get("SHO_PORT", "8402"))
KEYS_DIR = Path(os.environ.get("SHO_KEYS_DIR", str(Path(__file__).parent / "keys")))

# ── Oracle Backend Routes (same backends as L402 proxy) ───────────────────────

ROUTES = {
    "/oracle/btcusd":      {"backend": "http://127.0.0.1:9100/oracle/btcusd",      "price_usd": 0.001},
    "/oracle/btcusd/vwap":  {"backend": "http://127.0.0.1:9101/oracle/btcusd/vwap", "price_usd": 0.002},
    "/oracle/ethusd":      {"backend": "http://127.0.0.1:9102/oracle/ethusd",      "price_usd": 0.001},
    "/oracle/eurusd":      {"backend": "http://127.0.0.1:9103/oracle/eurusd",      "price_usd": 0.001},
    "/oracle/xauusd":      {"backend": "http://127.0.0.1:9105/oracle/xauusd",      "price_usd": 0.001},
    "/oracle/btceur":      {"backend": "http://127.0.0.1:9106/oracle/btceur",      "price_usd": 0.001},
    "/oracle/solusd":      {"backend": "http://127.0.0.1:9107/oracle/solusd",      "price_usd": 0.001},
}

FREE_ROUTES = {
    "/health":   "http://127.0.0.1:9100/health",
    "/sho/info": None,  # handled internally
}

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s [SHO] %(message)s")
log = logging.getLogger("sho")


# ══════════════════════════════════════════════════════════════════════════════
# Ed25519 Key Management
# ══════════════════════════════════════════════════════════════════════════════

def load_or_create_ed25519_key() -> SigningKey:
    """Load existing Ed25519 key or generate a new one."""
    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    sk_path = KEYS_DIR / "sho_ed25519.key"

    if sk_path.exists():
        sk_hex = sk_path.read_text().strip()
        sk = SigningKey(bytes.fromhex(sk_hex))
        log.info(f"Loaded Ed25519 key: {sk.verify_key.encode(HexEncoder).decode()[:16]}...")
        return sk

    sk = SigningKey.generate()
    sk_path.write_text(sk.encode(HexEncoder).decode())
    os.chmod(str(sk_path), 0o600)
    log.info(f"Generated new Ed25519 key: {sk.verify_key.encode(HexEncoder).decode()[:16]}...")
    return sk


ED25519_SK = load_or_create_ed25519_key()
ED25519_PK = ED25519_SK.verify_key


def ed25519_sign(canonical: str) -> str:
    """Sign a canonical message string with Ed25519, return base64 signature."""
    msg_hash = hashlib.sha256(canonical.encode()).digest()
    signed = ED25519_SK.sign(msg_hash)
    return base64.b64encode(signed.signature).decode()


# ══════════════════════════════════════════════════════════════════════════════
# Base USDC Payment Verification
# ══════════════════════════════════════════════════════════════════════════════

# ERC-20 Transfer event signature: Transfer(address,address,uint256)
TRANSFER_EVENT_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

# USDC has 6 decimals
USDC_DECIMALS = 6


async def verify_usdc_transfer(tx_hash: str, expected_amount_usd: float) -> dict:
    """
    Verify a USDC transfer on Base.
    Returns: {"valid": bool, "confirmed": bool, "error": str|None}
    """
    expected_amount_raw = int(expected_amount_usd * (10 ** USDC_DECIMALS))

    async with httpx.AsyncClient(timeout=10) as client:
        # Get transaction receipt
        resp = await client.post(BASE_RPC_URL, json={
            "jsonrpc": "2.0",
            "method": "eth_getTransactionReceipt",
            "params": [tx_hash],
            "id": 1,
        })
        data = resp.json()

        if "error" in data:
            return {"valid": False, "confirmed": False, "error": data["error"]["message"]}

        receipt = data.get("result")
        if receipt is None:
            # Transaction pending — not yet mined
            # For optimistic delivery, also check the raw transaction
            return await _verify_pending_tx(client, tx_hash, expected_amount_raw)

        # Transaction mined — check status
        if receipt["status"] != "0x1":
            return {"valid": False, "confirmed": True, "error": "transaction_reverted"}

        # Check logs for USDC Transfer event
        for log_entry in receipt.get("logs", []):
            if (log_entry["address"].lower() == USDC_CONTRACT.lower()
                    and len(log_entry["topics"]) >= 3
                    and log_entry["topics"][0] == TRANSFER_EVENT_TOPIC):

                # Decode recipient (topic[2]) — 32-byte padded address
                recipient = "0x" + log_entry["topics"][2][-40:]
                if recipient.lower() != PAYMENT_ADDRESS.lower():
                    continue

                # Decode amount from data
                amount_hex = log_entry["data"]
                amount = int(amount_hex, 16)

                if amount >= expected_amount_raw:
                    return {"valid": True, "confirmed": True, "error": None}
                else:
                    return {"valid": False, "confirmed": True, "error": "insufficient_amount"}

        return {"valid": False, "confirmed": True, "error": "no_usdc_transfer_found"}


async def _verify_pending_tx(client: httpx.AsyncClient, tx_hash: str, expected_amount_raw: int) -> dict:
    """Check a pending (unconfirmed) transaction for optimistic delivery."""
    resp = await client.post(BASE_RPC_URL, json={
        "jsonrpc": "2.0",
        "method": "eth_getTransactionByHash",
        "params": [tx_hash],
        "id": 1,
    })
    data = resp.json()
    tx = data.get("result")

    if tx is None:
        return {"valid": False, "confirmed": False, "error": "transaction_not_found"}

    # Check it's a call to the USDC contract
    if tx.get("to", "").lower() != USDC_CONTRACT.lower():
        return {"valid": False, "confirmed": False, "error": "not_usdc_contract"}

    # Decode ERC-20 transfer calldata: transfer(address,uint256)
    # Function selector: 0xa9059cbb
    input_data = tx.get("input", "")
    if not input_data.startswith("0xa9059cbb"):
        return {"valid": False, "confirmed": False, "error": "not_transfer_call"}

    # Decode recipient (bytes 4-36) and amount (bytes 36-68)
    recipient = "0x" + input_data[34:74]
    amount = int(input_data[74:138], 16)

    if recipient.lower() != PAYMENT_ADDRESS.lower():
        return {"valid": False, "confirmed": False, "error": "wrong_recipient"}

    if amount < expected_amount_raw:
        return {"valid": False, "confirmed": False, "error": "insufficient_amount"}

    # Pending but looks valid — optimistic delivery
    return {"valid": True, "confirmed": False, "error": None}


# ══════════════════════════════════════════════════════════════════════════════
# Tiered Enforcement
# ══════════════════════════════════════════════════════════════════════════════

# In-memory enforcement state (production: use Redis or SQLite)
# Key: payment_address (lowercase), Value: list of failure timestamps
_failure_log: dict[str, list[float]] = {}
_hard_blocked: set[str] = set()

GRACE_COOLDOWN_SECONDS = 600        # 10 minutes
HARD_BLOCK_THRESHOLD = 10           # failures in rolling window
HARD_BLOCK_WINDOW_SECONDS = 604800  # 7 days


def check_enforcement(payment_address: str) -> dict:
    """
    Check if a payment address is blocked or in cooldown.
    Returns: {"allowed": bool, "reason": str|None, "tier": int}
    """
    addr = payment_address.lower()

    # Tier 3: Hard block
    if addr in _hard_blocked:
        return {"allowed": False, "reason": "hard_blocked", "tier": 3}

    # Clean old entries outside rolling window
    now = time.time()
    if addr in _failure_log:
        _failure_log[addr] = [
            t for t in _failure_log[addr]
            if now - t < HARD_BLOCK_WINDOW_SECONDS
        ]

        failures = _failure_log[addr]

        # Check hard block threshold
        if len(failures) >= HARD_BLOCK_THRESHOLD:
            _hard_blocked.add(addr)
            log.warning(f"HARD BLOCK: {addr} ({len(failures)} failures in 7d)")
            return {"allowed": False, "reason": "hard_blocked", "tier": 3}

        # Tier 1: Grace cooldown
        if failures and (now - failures[-1]) < GRACE_COOLDOWN_SECONDS:
            remaining = int(GRACE_COOLDOWN_SECONDS - (now - failures[-1]))
            return {"allowed": False, "reason": f"cooldown_{remaining}s", "tier": 1}

    return {"allowed": True, "reason": None, "tier": 0}


def record_failure(payment_address: str):
    """Record a payment failure for tiered enforcement."""
    addr = payment_address.lower()
    if addr not in _failure_log:
        _failure_log[addr] = []
    _failure_log[addr].append(time.time())
    log.info(f"Payment failure recorded: {addr} (total: {len(_failure_log[addr])})")


def record_success(payment_address: str):
    """Record a successful payment (clears cooldown timer effectively)."""
    # We don't clear history — just let the rolling window expire naturally
    pass


# ══════════════════════════════════════════════════════════════════════════════
# Depeg Circuit Breaker
# ══════════════════════════════════════════════════════════════════════════════

_depeg_active = False
_last_depeg_check = 0.0
DEPEG_CHECK_INTERVAL = 60  # seconds


async def check_depeg() -> dict:
    """
    Check USDC/USD peg using 5 exchange sources (median, minimum 2 required).
    Returns: {"pegged": bool, "rate": float|None, "sources": int}
    """
    global _depeg_active, _last_depeg_check

    now = time.time()
    if now - _last_depeg_check < DEPEG_CHECK_INTERVAL:
        return {"pegged": not _depeg_active, "rate": None, "sources": 0}

    _last_depeg_check = now

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            rates = []

            # 1. Kraken USDC/USD
            try:
                r = await client.get("https://api.kraken.com/0/public/Ticker?pair=USDCUSD")
                d = r.json()
                rates.append(float(d["result"]["USDCUSD"]["c"][0]))
            except Exception:
                pass

            # 2. Bitstamp USDC/USD
            try:
                r = await client.get("https://www.bitstamp.net/api/v2/ticker/usdcusd/")
                rates.append(float(r.json()["last"]))
            except Exception:
                pass

            # 3. Coinbase USDC/USD
            try:
                r = await client.get("https://api.exchange.coinbase.com/products/USDC-USD/ticker")
                rates.append(float(r.json()["price"]))
            except Exception:
                pass

            # 4. Gemini USDC/USD
            try:
                r = await client.get("https://api.gemini.com/v1/pubticker/usdcusd")
                rates.append(float(r.json()["last"]))
            except Exception:
                pass

            # 5. Bitfinex USDC/USD
            try:
                r = await client.get("https://api-pub.bitfinex.com/v2/ticker/tUDCUSD")
                rates.append(float(r.json()[6]))
            except Exception:
                pass

            if len(rates) < 2:
                # Insufficient sources — fail safe, keep current state
                log.warning(f"Depeg check: only {len(rates)} sources available, need 2")
                return {"pegged": not _depeg_active, "rate": None, "sources": len(rates)}

            import statistics
            usdc_rate = statistics.median(rates)
            deviation = abs(usdc_rate - 1.0)

            if deviation > DEPEG_THRESHOLD:
                if not _depeg_active:
                    log.warning(f"DEPEG CIRCUIT BREAKER ACTIVE: USDC/USD = {usdc_rate:.4f} (deviation: {deviation:.4f}, {len(rates)} sources)")
                _depeg_active = True
                return {"pegged": False, "rate": usdc_rate, "sources": len(rates)}
            else:
                if _depeg_active:
                    log.info(f"Depeg circuit breaker cleared: USDC/USD = {usdc_rate:.4f} ({len(rates)} sources)")
                _depeg_active = False
                return {"pegged": True, "rate": usdc_rate, "sources": len(rates)}
                _depeg_active = False
                return {"pegged": True, "rate": usdc_rate}

    except Exception as e:
        log.error(f"Depeg check error: {e}")
        return {"pegged": not _depeg_active, "rate": None}


# ══════════════════════════════════════════════════════════════════════════════
# Request Nonces (replay protection)
# ══════════════════════════════════════════════════════════════════════════════

# In-memory nonce store (production: use Redis with TTL)
_nonces: dict[str, float] = {}  # nonce -> created_at timestamp
NONCE_TTL_SECONDS = 300  # 5 minutes


def create_nonce() -> str:
    """Generate a unique request nonce."""
    nonce = secrets.token_hex(16)
    _nonces[nonce] = time.time()
    # Prune expired nonces
    now = time.time()
    expired = [k for k, v in _nonces.items() if now - v > NONCE_TTL_SECONDS]
    for k in expired:
        del _nonces[k]
    return nonce


def validate_nonce(nonce: str) -> bool:
    """Validate and consume a request nonce."""
    if nonce not in _nonces:
        return False
    created = _nonces[nonce]
    if time.time() - created > NONCE_TTL_SECONDS:
        del _nonces[nonce]
        return False
    del _nonces[nonce]  # consume — single use
    return True


# ══════════════════════════════════════════════════════════════════════════════
# Async Payment Confirmation (background task)
# ══════════════════════════════════════════════════════════════════════════════

# Pending payments to confirm asynchronously
_pending_confirmations: list[dict] = []


async def process_pending_confirmations():
    """Background task: check pending payments for confirmation or failure."""
    confirmed = []
    for entry in _pending_confirmations:
        if time.time() - entry["created_at"] > 300:  # 5 minute timeout
            record_failure(entry["from_address"])
            log.warning(f"Payment timeout: {entry['tx_hash']} from {entry['from_address']}")
            confirmed.append(entry)
            continue

        result = await verify_usdc_transfer(entry["tx_hash"], entry["expected_amount"])
        if result["confirmed"]:
            if result["valid"]:
                record_success(entry["from_address"])
                log.info(f"Payment confirmed: {entry['tx_hash']}")
            else:
                record_failure(entry["from_address"])
                log.warning(f"Payment failed: {entry['tx_hash']} - {result['error']}")
            confirmed.append(entry)

    for entry in confirmed:
        _pending_confirmations.remove(entry)


# ══════════════════════════════════════════════════════════════════════════════
# FastAPI Application
# ══════════════════════════════════════════════════════════════════════════════

app = FastAPI(title="SHO — Sovereign HTTP Oracle", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok", "protocol": "x402", "version": "0.1.0"}


@app.get("/sho/info")
async def sho_info():
    """Public info endpoint — no payment required."""
    depeg = await check_depeg()
    return {
        "protocol": "x402",
        "version": "0.1.0",
        "signing_scheme": "ed25519",
        "pubkey": ED25519_PK.encode(HexEncoder).decode(),
        "payment_chain": "base",
        "payment_asset": "USDC",
        "payment_address": PAYMENT_ADDRESS,
        "usdc_contract": USDC_CONTRACT,
        "depeg_active": not depeg["pegged"],
        "endpoints": {path: {"price_usd": r["price_usd"]} for path, r in ROUTES.items()},
    }


@app.get("/sho/enforcement/{address}")
async def enforcement_status(address: str):
    """Check enforcement status for a payment address (public)."""
    status = check_enforcement(address)
    return status


@app.api_route("/{path:path}", methods=["GET"])
async def main_handler(request: Request, path: str):
    """Main x402 handler for oracle endpoints."""
    route_path = "/" + path

    # Check if it's a free route
    if route_path in FREE_ROUTES:
        backend = FREE_ROUTES[route_path]
        if backend is None:
            return JSONResponse({"error": "use specific endpoint"}, status_code=404)
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(backend)
            return JSONResponse(resp.json())

    # Check if it's a paid route
    route = ROUTES.get(route_path)
    if route is None:
        return JSONResponse({"error": "not_found"}, status_code=404)

    # ── Depeg circuit breaker ──
    depeg = await check_depeg()
    if not depeg["pegged"]:
        return JSONResponse({
            "error": "depeg_circuit_breaker",
            "message": "USDC payment suspended — stablecoin deviation exceeds threshold",
            "usdc_rate": depeg["rate"],
            "threshold": DEPEG_THRESHOLD,
        }, status_code=503)

    # ── Check for x402 payment header ──
    x402_header = request.headers.get("X-Payment") or request.headers.get("x-payment")

    if not x402_header:
        # No payment — return 402 with payment requirements
        nonce = create_nonce()
        payment_body = {
            "x402Version": 1,
            "accepts": [{
                "scheme": "exact",
                "network": "eip155:8453",
                "maxAmountRequired": str(int(float(route["price_usd"]) * 1_000_000)),
                "asset": USDC_CONTRACT,
                "payTo": PAYMENT_ADDRESS,
                "resource": f"https://api.myceliasignal.com{request.url.path}",
                "mimeType": "application/json",
                "description": "Signed price attestation",
                "outputSchema": {"input": {"type": "http", "method": "GET", "url": f"https://api.myceliasignal.com{request.url.path}"}, "output": {"type": "object", "description": "Signed price attestation with canonical verification string"}},
                "maxTimeoutSeconds": NONCE_TTL_SECONDS,
            }],
            "error": "X-PAYMENT header is required",
            "x402": {
                "version": "1",
                "chain": "base",
                "asset": "USDC",
                "contract": USDC_CONTRACT,
                "recipient": PAYMENT_ADDRESS,
                "amount": str(route["price_usd"]),
                "nonce": nonce,
                "expires_in": NONCE_TTL_SECONDS,
            }
        }
        payment_header_value = base64.b64encode(json.dumps({
            "x402Version": 1,
            "accepts": [{
                "scheme": "exact",
                "network": "eip155:8453",
                "maxAmountRequired": str(int(float(route["price_usd"]) * 1_000_000)),
                "asset": USDC_CONTRACT,
                "payTo": PAYMENT_ADDRESS,
                "resource": f"https://api.myceliasignal.com{request.url.path}",
                "mimeType": "application/json",
                "description": "Signed price attestation",
                "outputSchema": {"input": {"type": "http", "method": "GET", "url": f"https://api.myceliasignal.com{request.url.path}"}, "output": {"type": "object", "description": "Signed price attestation with canonical verification string"}},
                "maxTimeoutSeconds": NONCE_TTL_SECONDS,
            }]
        }).encode()).decode()
        return JSONResponse(
            payment_body,
            status_code=402,
            headers={"Payment-Required": payment_header_value}
        )

    # ── Parse x402 payment header ──
    try:
        payment = json.loads(x402_header)
        tx_hash = payment["tx_hash"]
        nonce = payment["nonce"]
        from_address = payment.get("from", "unknown")
    except (json.JSONDecodeError, KeyError) as e:
        return JSONResponse({"error": "invalid_payment_header", "detail": str(e)}, status_code=400)

    # ── Validate nonce ──
    if not validate_nonce(nonce):
        return JSONResponse({"error": "invalid_or_expired_nonce"}, status_code=400)

    # ── Check enforcement ──
    enforcement = check_enforcement(from_address)
    if not enforcement["allowed"]:
        return JSONResponse({
            "error": "payment_address_blocked",
            "reason": enforcement["reason"],
            "tier": enforcement["tier"],
        }, status_code=403)

    # ── Verify payment (optimistic) ──
    verification = await verify_usdc_transfer(tx_hash, route["price_usd"])

    if not verification["valid"]:
        record_failure(from_address)
        return JSONResponse({
            "error": "payment_verification_failed",
            "detail": verification["error"],
        }, status_code=402)

    # ── Payment accepted — fetch attestation from backend ──
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(route["backend"])
            backend_data = resp.json()
    except Exception as e:
        log.error(f"Backend error: {e}")
        return JSONResponse({"error": "oracle_backend_error"}, status_code=502)

    # ── Re-sign with Ed25519 ──
    canonical = backend_data.get("canonical", "")
    if not canonical:
        return JSONResponse({"error": "backend_missing_canonical"}, status_code=502)

    ed25519_sig = ed25519_sign(canonical)

    # ── Queue for async confirmation if payment was pending ──
    if not verification["confirmed"]:
        _pending_confirmations.append({
            "tx_hash": tx_hash,
            "from_address": from_address,
            "expected_amount": route["price_usd"],
            "created_at": time.time(),
        })

    record_success(from_address)

    # ── Return attestation with Ed25519 signature ──
    return JSONResponse({
        "domain": backend_data.get("domain", ""),
        "canonical": canonical,
        "signature": ed25519_sig,
        "signing_scheme": "ed25519",
        "pubkey": ED25519_PK.encode(HexEncoder).decode(),
        "payment": {
            "protocol": "x402",
            "tx_hash": tx_hash,
            "confirmed": verification["confirmed"],
        },
    })


# ── Background task for pending confirmations ─────────────────────────────────

@app.on_event("startup")
async def startup():
    import asyncio

    async def confirmation_loop():
        while True:
            try:
                await process_pending_confirmations()
            except Exception as e:
                log.error(f"Confirmation loop error: {e}")
            await asyncio.sleep(15)

    asyncio.create_task(confirmation_loop())
    log.info(f"SHO x402 Proxy starting on :{SHO_PORT}")
    log.info(f"Ed25519 pubkey: {ED25519_PK.encode(HexEncoder).decode()}")
    log.info(f"Payment address: {PAYMENT_ADDRESS}")
    log.info(f"Base RPC: {BASE_RPC_URL}")


# ══════════════════════════════════════════════════════════════════════════════
# Entry Point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if not PAYMENT_ADDRESS:
        print("ERROR: Set SHO_PAYMENT_ADDRESS environment variable")
        print("  export SHO_PAYMENT_ADDRESS=0xYourUSDCAddressOnBase")
        exit(1)

    uvicorn.run(app, host="0.0.0.0", port=SHO_PORT)
