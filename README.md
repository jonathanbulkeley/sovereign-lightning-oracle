# Sovereign Lightning Oracle (SLO)

**Pay 10 sats. Get a signed BTCUSD price.**

SLO is a protocol for purchasing signed, verifiable price assertions over Lightning micropayments. No API keys. No accounts. No trust. Just payment and proof.

## Try It Now

### Live (mainnet — any Lightning wallet)
```
curl -v http://104.197.109.246:8080/oracle/btcusd
```

You'll get a `402 Payment Required` with a Lightning invoice for 10 sats. Pay it, get a cryptographically signed BTCUSD spot price sourced from Coinbase, Kraken, and Bitstamp.

> ⚡ **Status: Beta** — Live on Bitcoin mainnet. The endpoint may go down for maintenance.

### Local demo (no Lightning node needed)

Clone this repo and run the [Polar Setup Guide](docs/POLAR_SETUP.md) to simulate the full L402 flow on your machine in ~30 minutes. No real bitcoin required.

## How It Works
```
Client                       Aperture (L402 proxy)           Oracle (FastAPI)
  │                                │                              │
  │  GET /oracle/btcusd            │                              │
  │ ─────────────────────────────► │                              │
  │                                │                              │
  │  402 + Lightning invoice       │                              │
  │ ◄───────────────────────────── │                              │
  │                                │                              │
  │  ⚡ Pay invoice (10 sats)      │                              │
  │ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─► │                              │
  │                                │                              │
  │  Retry with L402 token         │                              │
  │ ─────────────────────────────► │  GET /oracle/btcusd          │
  │                                │ ───────────────────────────► │
  │                                │                              │
  │                                │  Signed price assertion      │
  │                                │ ◄─────────────────────────── │
  │  { canonical, signature,       │                              │
  │    pubkey }                    │                              │
  │ ◄───────────────────────────── │                              │
```

1. Client requests price data
2. [Aperture](https://github.com/lightninglabs/aperture) returns HTTP 402 with a Lightning invoice
3. Client pays the invoice (any Lightning wallet or L402 client like [lnget](https://github.com/lightninglabs/lnget))
4. Client retries with proof of payment (L402 token)
5. Aperture verifies payment and proxies to the oracle backend
6. Oracle returns a signed BTCUSD price assertion

## Response Format
```json
{
  "domain": "BTCUSD",
  "canonical": "v1|BTCUSD|66249.33|USD|2|2026-02-13T07:36:30Z|890123|coinbase,kraken,bitstamp|median",
  "signature": "YpUmtkKAFrpTPD9tJaXueYc8IdMM7+M2R7365yu/hsxn...",
  "pubkey": "0220a2222aae4390e6921f77a8785cbfedd500de477eda58..."
}
```

The `canonical` field is the signed message. The `signature` is a secp256k1 ECDSA signature over `SHA256(canonical)`. Any client can verify the signature using the `pubkey`.

## Endpoints

| Path | Method | Price | Description |
|---|---|---|---|
| `/oracle/btcusd` | Spot median | 10 sats | Median of last trades from Coinbase, Kraken, Bitstamp |
| `/oracle/btcusd/vwap` | VWAP | 20 sats | Volume-weighted average from Coinbase, Kraken |
| `/health` | — | Free | Health check (not gated) |

## Repository Structure
```
slo/
├── oracle/
│   ├── liveoracle_btcusd_spot.py       # Spot price oracle (L402-ready)
│   └── liveoracle_btcusd_vwap.py       # VWAP oracle (L402-ready)
├── client/
│   └── quorum_client_l402.py           # L402-aware quorum client
├── config/
│   └── aperture.yaml                   # Aperture config template
├── docs/
│   ├── POLAR_SETUP.md                  # Local demo guide (Polar + regtest)
│   ├── DEPLOYMENT.md                   # Production deployment guide (GCP + Voltage)
│   ├── Protocol.md                     # Canonical protocol specification
│   └── Quorum_Specification.md         # Client quorum and aggregation rules
├── legacy/
│   ├── liveoracle_btcusd_spot.py       # Original with simulated payments
│   ├── liveoracle_btcusd_liquidity.py  # Original liquidity oracle
│   ├── liveoracle_btcusd_vwap.py       # Original VWAP oracle
│   └── quorum_client.py               # Original client
└── README.md
```

## Protocol (v1)

### Canonical Message
```
v1|BTCUSD|<price>|USD|<decimals>|<timestamp>|<nonce>|<sources>|<method>
```

### Core Invariants

1. **Payment before release** — No signed data without Lightning payment (enforced by Aperture)
2. **Explicit trust** — Clients choose which oracles to query (no registry, no governance)
3. **Deterministic verification** — Every response is signed (secp256k1) and verifiable
4. **Deterministic aggregation** — Clients aggregate via median across multiple oracles

### What SLO Is Not

- Not a price feed (you pay per query, not per subscription)
- Not a global oracle registry
- Not a governance system
- Not a consensus protocol

SLO does not decide which oracle is correct. That responsibility belongs to the client.

## Architecture

SLO uses [Lightning Labs' L402 protocol](https://github.com/lightninglabs/L402) to gate API access behind Lightning micropayments:

- **[Aperture](https://github.com/lightninglabs/aperture)** — Reverse proxy that creates invoices and verifies payments
- **[lnget](https://github.com/lightninglabs/lnget)** — CLI client that handles L402 payments transparently
- **Oracle servers** — Stateless FastAPI services that fetch prices, sign assertions, and return JSON

The oracle servers contain zero payment logic. Aperture enforces the "payment before data" invariant at the proxy layer.

## For AI Agents

SLO is designed to be consumed by machines. The L402 protocol lets AI agents pay for data programmatically — no API keys, no OAuth, no accounts. An agent with a Lightning wallet can:
```bash
lnget -k http://104.197.109.246:8080/oracle/btcusd
```

10 sats spent, signed price received, cryptographically verified. This is what machine-payable data looks like.

## Design Philosophy

SLO favors:
- explicit failure over hidden retries
- local configuration over global coordination
- payment over access control
- plural oracles over singular truth

## Quick Start (Legacy — Simulated Payments)

No Lightning node required:
```bash
pip install fastapi uvicorn ecdsa requests

# Terminal 1-2: Start oracles
python legacy/liveoracle_btcusd_spot.py 8000
python legacy/liveoracle_btcusd_vwap.py 8002

# Terminal 3: Run quorum client
python legacy/quorum_client.py
```

## License

MIT — see [LICENSE](LICENSE)
