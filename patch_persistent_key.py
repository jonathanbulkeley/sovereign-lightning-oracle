#!/usr/bin/env python3
"""
Patch all oracle backends to use the shared persistent signing key.
Run from the repo root: python3 patch_persistent_key.py
"""

import re
from pathlib import Path

ORACLE_DIR = Path(__file__).parent / "oracle"
FILES = list(ORACLE_DIR.glob("liveoracle_*.py"))

OLD_IMPORT = "from ecdsa import SigningKey, SECP256k1"
OLD_KEYGEN = re.compile(r"PRIVATE_KEY = SigningKey\.generate\(curve=SECP256k1\)\nPUBLIC_KEY = PRIVATE_KEY\.get_verifying_key\(\)")

NEW_IMPORT = "from ecdsa import SigningKey, SECP256k1\nfrom oracle.keys import PRIVATE_KEY, PUBLIC_KEY"
NEW_KEYGEN = "# Key loaded from oracle/keys/ (persistent, shared across all backends)"

patched = 0
for f in sorted(FILES):
    text = f.read_text()

    if "from oracle.keys import" in text:
        print(f"  SKIP {f.name} (already patched)")
        continue

    if "SigningKey.generate" not in text:
        print(f"  SKIP {f.name} (no key generation found)")
        continue

    # Replace import line
    text = text.replace(OLD_IMPORT, NEW_IMPORT)

    # Replace key generation
    text = OLD_KEYGEN.sub(NEW_KEYGEN, text)

    f.write_text(text)
    patched += 1
    print(f"  PATCHED {f.name}")

print(f"\nDone. Patched {patched} files.")
print(f"Key will be stored at: oracle/keys/oracle_secp256k1.key")
print(f"Key is generated on first startup and reused thereafter.")
