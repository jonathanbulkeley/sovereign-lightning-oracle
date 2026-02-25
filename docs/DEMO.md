# SLO Live Demo

A step-by-step walkthrough of purchasing signed BTCUSD price data for Lightning sats.

## What You'll See

1. An HTTP 402 (Payment Required) with a Lightning invoice
2. A Lightning payment for 10 sats
3. A signed BTCUSD price assertion you can verify independently

## Step 1: Request Price Data
```bash
curl -v https://api.myceliasignal.com/oracle/btcusd
```

Response:
```
HTTP/1.1 402 Payment Required
Www-Authenticate: L402 macaroon="AgEEbHNhdA...", invoice="lnbc100n1p5c..."
```

The server returns a 402 with two things:
- A **macaroon** (your access token, locked until payment)
- A **Lightning invoice** for 10 sats (the `lnbc100n` prefix means 10 sats on mainnet)

No data is released. Payment first.

## Step 2: Pay the Invoice

### Option A: lnget (automatic)
```bash
lnget -k https://api.myceliasignal.com/oracle/btcusd
```

lnget handles the full L402 flow — receives the 402, pays the invoice, retries with the token, and prints the response. One command.

### Option B: Any Lightning wallet

Copy the invoice string (`lnbc100n1p5c...`) from the 402 response and paste it into any Lightning wallet:
- Phoenix Wallet (mobile)
- Zeus (mobile)
- Alby (browser extension)
- BlueWallet (mobile)

After payment, retry the request with the L402 token:
```bash
curl -H "Authorization: L402 <macaroon>:<preimage>" https://api.myceliasignal.com/oracle/btcusd
```

## Step 3: Receive Signed Data

After payment, the oracle returns:
```json
{
  "domain": "BTCUSD",
  "canonical": "v1|BTCUSD|96482.15|USD|2|2026-02-13T18:44:30Z|890123|coinbase,kraken,bitstamp|median",
  "signature": "MEUCIQDr7y8Hx...",
  "pubkey": "0220a2222aae..."
}
```

### Reading the canonical message
```
v1|BTCUSD|96482.15|USD|2|2026-02-13T18:44:30Z|890123|coinbase,kraken,bitstamp|median
│  │      │        │  │ │                      │      │                        │
│  │      │        │  │ │                      │      │                        └─ method: median
│  │      │        │  │ │                      │      └─ sources: coinbase, kraken, bitstamp
│  │      │        │  │ │                      └─ nonce
│  │      │        │  │ └─ timestamp (UTC)
│  │      │        │  └─ decimal places
│  │      │        └─ quote currency
│  │      └─ price
│  └─ asset pair
└─ protocol version
```

## Step 4: Verify the Signature

The response is self-verifying. No trust in the transport required.
```python
import hashlib, base64
from ecdsa import VerifyingKey, SECP256k1

canonical = "v1|BTCUSD|96482.15|USD|2|2026-02-13T18:44:30Z|890123|coinbase,kraken,bitstamp|median"
signature = "MEUCIQDr7y8Hx..."  # from response
pubkey = "0220a2222aae..."       # from response

sig_bytes = base64.b64decode(signature)
pubkey_bytes = bytes.fromhex(pubkey)
vk = VerifyingKey.from_string(pubkey_bytes, curve=SECP256k1)
h = hashlib.sha256(canonical.encode()).digest()

assert vk.verify_digest(sig_bytes, h)
print("Signature valid — this price was signed by this oracle.")
```

If the signature verifies, the oracle committed to this price at this timestamp. If it doesn't, reject it.

## Step 5: Query Multiple Oracles (Quorum)

For higher assurance, query both the spot and VWAP oracles and compare:
```bash
lnget -k https://api.myceliasignal.com/oracle/btcusd
lnget -k https://api.myceliasignal.com/oracle/btcusd/vwap
```

Cost: 30 sats total (10 + 20). If both prices are within 0.5% of each other, take the median. If they diverge, something is wrong — don't trust either.

The included quorum client automates this:
```bash
python client/quorum_client_l402.py --backend lnget
```

Output:
```
SLO Quorum Client — backend: lnget

Querying spot at https://api.myceliasignal.com/oracle/btcusd...
  Price: $96482.15
  Signature: VALID
  Pubkey: 0220a2222aae4390e6...

Querying vwap at https://api.myceliasignal.com/oracle/btcusd/vwap...
  Price: $96479.88
  Signature: VALID
  Pubkey: 03f1b2c3d4e5f6a7b8...

==================================================
QUORUM RESULT
  Oracles:  2/2
  Median:   $96481.02
  Prices:   $96482.15, $96479.88
==================================================
```

Two oracles. Two signatures. Two methodologies. One price you can trust.

## Local Demo (No Bitcoin Required)

If you don't have a Lightning wallet, you can run the full L402 flow locally using Polar (Bitcoin regtest):

1. Install [Polar](https://lightningpolar.com)
2. Follow the [Polar Setup Guide](POLAR_SETUP.md)
3. Create a local Lightning network, start the oracles, and test payments

Same protocol, same code, zero real sats.

## What Just Happened

You paid a machine 10 sats (~$0.007) and received a cryptographically signed price assertion that you verified independently. No API key. No account. No trust. The oracle can't revoke your access. You can't use the data without paying. The incentives are aligned by construction.

This is what machine-payable, verifiable data looks like on the Lightning Network.
```

---

Add that to `docs/DEMO.md`. Now check your channel:
```
curl -k --header "Grpc-Metadata-macaroon: %MAC%" https://mycelia.m.voltageapp.io:8080/v1/channels/pending
