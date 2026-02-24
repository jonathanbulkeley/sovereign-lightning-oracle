# sho/cross_certify.py
"""
Cross-Certification Statement Generator

Produces a deterministic statement signed by both the existing SLO secp256k1 key
and the new SHO Ed25519 key, proving common ownership under a single oracle identity.

Usage:
    python cross_certify.py --secp256k1-key <path> --ed25519-key <path>
"""

import argparse
import hashlib
import base64
import json
from datetime import datetime, timezone
from pathlib import Path

from nacl.signing import SigningKey as Ed25519SigningKey
from nacl.encoding import HexEncoder


def generate_cross_certification(secp256k1_key_path: str, ed25519_key_path: str, oracle_id: str = "mycelia-signal"):
    """Generate and sign a cross-certification statement with both keys."""

    # Load Ed25519 key
    ed25519_hex = Path(ed25519_key_path).read_text().strip()
    ed25519_sk = Ed25519SigningKey(bytes.fromhex(ed25519_hex))
    ed25519_pk_hex = ed25519_sk.verify_key.encode(HexEncoder).decode()

    # Load secp256k1 key
    from ecdsa import SigningKey, SECP256k1
    secp256k1_hex = Path(secp256k1_key_path).read_text().strip()
    secp256k1_sk = SigningKey.from_string(bytes.fromhex(secp256k1_hex), curve=SECP256k1)
    secp256k1_pk_hex = secp256k1_sk.get_verifying_key().to_string("compressed").hex()

    # Build deterministic statement
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    statement = (
        f"Oracle cross-certification | "
        f"oracle_id: {oracle_id} | "
        f"secp256k1: {secp256k1_pk_hex} | "
        f"ed25519: {ed25519_pk_hex} | "
        f"timestamp: {timestamp}"
    )

    # Hash the statement
    msg_hash = hashlib.sha256(statement.encode()).digest()

    # Sign with secp256k1
    secp256k1_sig = secp256k1_sk.sign_digest(msg_hash)
    secp256k1_sig_b64 = base64.b64encode(secp256k1_sig).decode()

    # Sign with Ed25519
    ed25519_signed = ed25519_sk.sign(msg_hash)
    ed25519_sig_b64 = base64.b64encode(ed25519_signed.signature).decode()

    cross_cert = {
        "oracle_id": oracle_id,
        "statement": statement,
        "secp256k1_pubkey": secp256k1_pk_hex,
        "ed25519_pubkey": ed25519_pk_hex,
        "secp256k1_signature": secp256k1_sig_b64,
        "ed25519_signature": ed25519_sig_b64,
        "timestamp": timestamp,
    }

    return cross_cert


def verify_cross_certification(cross_cert: dict) -> bool:
    """Verify both signatures on a cross-certification statement."""

    statement = cross_cert["statement"]
    msg_hash = hashlib.sha256(statement.encode()).digest()

    # Verify secp256k1
    try:
        from ecdsa import VerifyingKey, SECP256k1
        secp256k1_pk = VerifyingKey.from_string(
            bytes.fromhex(cross_cert["secp256k1_pubkey"]), curve=SECP256k1
        )
        secp256k1_sig = base64.b64decode(cross_cert["secp256k1_signature"])
        secp256k1_pk.verify_digest(secp256k1_sig, msg_hash)
    except Exception as e:
        print(f"secp256k1 verification failed: {e}")
        return False

    # Verify Ed25519
    try:
        from nacl.signing import VerifyKey
        ed25519_pk = VerifyKey(bytes.fromhex(cross_cert["ed25519_pubkey"]))
        ed25519_sig = base64.b64decode(cross_cert["ed25519_signature"])
        ed25519_pk.verify(msg_hash, ed25519_sig)
    except Exception as e:
        print(f"Ed25519 verification failed: {e}")
        return False

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate oracle cross-certification")
    parser.add_argument("--secp256k1-key", required=True, help="Path to secp256k1 private key (hex)")
    parser.add_argument("--ed25519-key", required=True, help="Path to Ed25519 private key (hex)")
    parser.add_argument("--oracle-id", default="mycelia-signal", help="Oracle identifier")
    parser.add_argument("--output", default="cross_certification.json", help="Output file")
    args = parser.parse_args()

    print("Generating cross-certification statement...")
    cert = generate_cross_certification(args.secp256k1_key, args.ed25519_key, args.oracle_id)

    print(f"\n  Oracle ID:    {cert['oracle_id']}")
    print(f"  secp256k1 PK: {cert['secp256k1_pubkey']}")
    print(f"  Ed25519 PK:   {cert['ed25519_pubkey']}")
    print(f"  Timestamp:    {cert['timestamp']}")

    print("\nVerifying...")
    valid = verify_cross_certification(cert)
    print(f"  Both signatures valid: {valid}")

    if valid:
        output_path = Path(args.output)
        output_path.write_text(json.dumps(cert, indent=2))
        print(f"\nSaved to {output_path}")
