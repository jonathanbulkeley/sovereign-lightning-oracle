# dlc/attestor.py
"""
DLC Oracle Attestor - Schnorr Nonce Commitment & Attestation
SLO v1

Uses full compressed public keys (33 bytes) throughout to avoid
y-coordinate ambiguity in verification.
"""

import hashlib
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from coincurve import PrivateKey, PublicKeyXOnly
from coincurve import PublicKey as FullPublicKey

KEYS_DIR = Path(__file__).parent / "keys"
DATA_DIR = Path(__file__).parent / "data"
NUM_DIGITS = 5
CURVE_ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141


def load_oracle_key():
    sk_path = KEYS_DIR / "oracle_sk.hex"
    if not sk_path.exists():
        raise FileNotFoundError(f"Oracle key not found at {sk_path}")
    sk_hex = sk_path.read_text().strip()
    sk = PrivateKey(bytes.fromhex(sk_hex))
    return sk


def generate_nonce():
    k = PrivateKey()
    R_full = k.public_key
    return k.secret, R_full.format()


def event_id(pair, timestamp_str):
    return f"{pair}-{timestamp_str}"


def next_hours(n=24):
    now = datetime.now(timezone.utc)
    next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return [
        (next_hour + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ")
        for i in range(n)
    ]


def create_announcement(pair, maturity_ts):
    eid = event_id(pair, maturity_ts)
    nonce_secrets = []
    r_points = []
    for i in range(NUM_DIGITS):
        k_bytes, R_bytes = generate_nonce()
        nonce_secrets.append(k_bytes.hex())
        r_points.append(R_bytes.hex())

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    secret_path = DATA_DIR / f"{eid}.nonces.json"
    with open(secret_path, "w") as f:
        json.dump({"event_id": eid, "nonce_secrets": nonce_secrets}, f)
    os.chmod(str(secret_path), 0o600)

    sk = load_oracle_key()
    oracle_pubkey = sk.public_key.format().hex()

    announcement = {
        "event_id": eid,
        "pair": pair,
        "maturity": maturity_ts,
        "oracle_pubkey": oracle_pubkey,
        "num_digits": NUM_DIGITS,
        "r_points": r_points,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    ann_path = DATA_DIR / f"{eid}.announcement.json"
    with open(ann_path, "w") as f:
        json.dump(announcement, f, indent=2)
    return announcement


def create_attestation(pair, maturity_ts, price):
    eid = event_id(pair, maturity_ts)
    secret_path = DATA_DIR / f"{eid}.nonces.json"
    if not secret_path.exists():
        raise FileNotFoundError(f"No nonces found for event {eid}")
    with open(secret_path) as f:
        nonce_data = json.load(f)
    nonce_secrets = nonce_data["nonce_secrets"]

    sk = load_oracle_key()
    oracle_pubkey = sk.public_key.format().hex()

    price_int = int(round(price))
    price_str = str(price_int).zfill(NUM_DIGITS)
    if len(price_str) != NUM_DIGITS:
        raise ValueError(f"Price {price_int} does not fit in {NUM_DIGITS} digits")
    digits = [int(d) for d in price_str]

    s_values = []
    for i, digit in enumerate(digits):
        k_bytes = bytes.fromhex(nonce_secrets[i])
        k_int = int.from_bytes(k_bytes, "big")
        msg_str = f"{eid}/{i}/{digit}"
        msg_hash = hashlib.sha256(msg_str.encode()).digest()
        x_int = int.from_bytes(sk.secret, "big")
        e_int = int.from_bytes(msg_hash, "big") % CURVE_ORDER
        s_int = (k_int + e_int * x_int) % CURVE_ORDER
        s_values.append(s_int.to_bytes(32, "big").hex())

    attestation = {
        "event_id": eid,
        "pair": pair,
        "maturity": maturity_ts,
        "oracle_pubkey": oracle_pubkey,
        "price": price_int,
        "price_digits": digits,
        "s_values": s_values,
        "attested_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    att_path = DATA_DIR / f"{eid}.attestation.json"
    with open(att_path, "w") as f:
        json.dump(attestation, f, indent=2)
    secret_path.unlink()
    return attestation


def verify_attestation(announcement, attestation):
    P = FullPublicKey(bytes.fromhex(announcement["oracle_pubkey"]))
    eid = attestation["event_id"]
    digits = attestation["price_digits"]
    s_values = attestation["s_values"]
    r_points = announcement["r_points"]

    for i, digit in enumerate(digits):
        s_int = int.from_bytes(bytes.fromhex(s_values[i]), "big")
        R = FullPublicKey(bytes.fromhex(r_points[i]))

        msg_str = f"{eid}/{i}/{digit}"
        msg_hash = hashlib.sha256(msg_str.encode()).digest()
        e_int = int.from_bytes(msg_hash, "big") % CURVE_ORDER

        sG = PrivateKey(s_int.to_bytes(32, "big")).public_key
        eP = P.multiply(e_int.to_bytes(32, "big"))
        RpluseP = FullPublicKey.combine_keys([R, eP])

        if sG.format() != RpluseP.format():
            return False
    return True


if __name__ == "__main__":
    print("=== DLC Attestor Test ===")
    print()
    hours = next_hours(1)
    ts = hours[0]
    print(f"Creating announcement for BTCUSD at {ts}...")
    ann = create_announcement("BTCUSD", ts)
    print(f"  Event ID:  {ann['event_id']}")
    print(f"  R-points:  {len(ann['r_points'])} nonces")
    print(f"  Pubkey:    {ann['oracle_pubkey']}")

    test_price = 68867.00
    print()
    print(f"Attesting price ${test_price:,.0f}...")
    att = create_attestation("BTCUSD", ts, test_price)
    print(f"  Price:     ${att['price']:,}")
    print(f"  Digits:    {att['price_digits']}")
    print(f"  S-values:  {len(att['s_values'])}")

    print()
    print("Verifying attestation...")
    valid = verify_attestation(ann, att)
    print(f"  Valid:     {valid}")
