# oracle/keys/__init__.py
"""
Persistent secp256k1 signing key for all oracle backends.
Key is generated once and stored alongside this file.
All oracle backends share the same key — consumers can pin it.
"""

import os
from pathlib import Path
from ecdsa import SigningKey, SECP256k1

KEYS_DIR = Path(__file__).parent
KEY_PATH = KEYS_DIR / "oracle_secp256k1.key"


def load_or_create_key() -> SigningKey:
    """Load existing secp256k1 key or generate a new persistent one."""
    if KEY_PATH.exists():
        sk_hex = KEY_PATH.read_text().strip()
        return SigningKey.from_string(bytes.fromhex(sk_hex), curve=SECP256k1)

    sk = SigningKey.generate(curve=SECP256k1)
    KEY_PATH.write_text(sk.to_string().hex())
    os.chmod(str(KEY_PATH), 0o600)
    return sk


PRIVATE_KEY = load_or_create_key()
PUBLIC_KEY = PRIVATE_KEY.get_verifying_key()
