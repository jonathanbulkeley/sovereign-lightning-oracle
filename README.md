Sovereign Lightning Oracle (SLO)
Pay sats. Get signed data. Trust math, not middlemen.
SLO is a protocol for purchasing signed, verifiable data assertions over Lightning micropayments. No API keys. No accounts. No trust. Just payment and proof.
BTCUSD, ETHUSD, and EURUSD are live on Bitcoin mainnet — alongside the first production DLC oracle with L402 payment gating. The EUR/USD oracle aggregates rates from 5 central banks across 4 continents plus 2 live exchanges. The DLC attestor publishes hourly Schnorr-signed price attestations for non-custodial Bitcoin-native derivatives. The design generalizes to any metric where truth is contested and verification matters.
Try It Now
Live (mainnet — any Lightning wallet)
curl -v http://104.197.109.246:8080/oracle/btcusd
curl -v http://104.197.109.246:8080/oracle/ethusd
curl -v http://104.197.109.246:8080/oracle/eurusd
You'll get a 402 Payment Required with a Lightning invoice. Pay it with any Lightning wallet, get a cryptographically signed price sourced from major exchanges and central banks.
L402-gated endpoints (pay per query)
EndpointAssetMethodPriceSources/oracle/btcusdBTC/USDSpot median10 sats9 sources: Coinbase, Kraken, Bitstamp, Gemini, Bitfinex, Binance, Binance US, OKX, Gate.io/oracle/btcusd/vwapBTC/USDVolume-weighted average20 satsCoinbase, Kraken/oracle/ethusdETH/USDSpot median10 satsCoinbase, Kraken, Bitstamp, Gemini, Bitfinex/oracle/eurusdEUR/USDSpot median10 satsECB, Bank of Canada, RBA, Norges Bank, Czech National Bank, Kraken, Bitstamp/dlc/oracle/attestations/{id}BTC/USDSchnorr attestation1000 sats9 sources (same as BTCUSD spot)
The VWAP oracle costs more because it processes full trade history rather than a single last-trade price — more computation, more data, more signal. The DLC attestation costs 1000 sats because it settles real financial contracts.
Free DLC endpoints (no payment required)
EndpointDescriptionhttp://104.197.109.246:9104/dlc/oracle/pubkeyOracle's persistent Schnorr public keyhttp://104.197.109.246:9104/dlc/oracle/announcementsList upcoming events with nonce commitmentshttp://104.197.109.246:9104/dlc/oracle/announcements/{id}Single announcement with R-pointshttp://104.197.109.246:9104/dlc/oracle/statusOracle status and statistics
Announcements are free to encourage adoption — the more contracts built against SLO, the more attestation revenue.

⚡ Status: Beta — Live on Bitcoin mainnet. Endpoints may go down for maintenance.

Local demo (no Lightning node needed)
Clone this repo and run the Polar Setup Guide to simulate the full L402 flow on your machine in ~30 minutes. No real bitcoin required.
Why SLO?
Oracles today are broken. Most price feeds are free — which means you're not the customer, you're the product. Free oracles create hidden dependencies: opaque update schedules, silent failures, governance capture, and single points of trust that defeat the purpose of building on Bitcoin.
SLO takes a different approach:

Payment replaces trust. Every query costs sats. Every response is signed. If the data is wrong, stop paying. The market decides which oracles survive.
No accounts, no API keys. A Lightning payment is your authentication. Any machine with a wallet can buy data — humans, bots, smart contracts, AI agents.
Multiple oracles, client aggregation. You choose which oracles to query. You aggregate the results. No single oracle can lie to you without detection.
Cryptographic proof at every layer. Signed assertions (secp256k1/Schnorr) mean you can verify data independently, store it, forward it, or submit it on-chain — all without trusting the transport.
Censorship resistant. No platform can revoke your access. If you can reach the endpoint and pay the invoice, you get the data. No terms of service, no rate limits, no deplatforming.
Aligned incentives. Oracle operators earn sats per query. More accurate data attracts more paying clients. Bad data means lost revenue. The economic feedback loop enforces quality without governance.

How It Works
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

Client requests price data
Aperture returns HTTP 402 with a Lightning invoice
Client pays the invoice (any Lightning wallet or L402 client like lnget)
Client retries with proof of payment (L402 token)
Aperture verifies payment and proxies to the oracle backend
Oracle returns a signed price assertion

Response Formats
L402 Oracle Response (ECDSA)
json{
  "domain": "BTCUSD",
  "canonical": "v1|BTCUSD|69005.00|USD|2|2026-02-15T17:55:46Z|890123|binance,binance_us,bitfinex,bitstamp,coinbase,gateio,gemini,kraken,okx|median",
  "signature": "Fc9m9prAixo1DeZh1xNwkzSXD0zLw6BNlTutaBj/03F7...",
  "pubkey": "02b9b8ec862ee9ca1ab6293f67c473b327a45ed0988d..."
}
The canonical field is the signed message. The signature is a secp256k1 ECDSA signature over SHA256(canonical). Any client can verify the signature using the pubkey.
DLC Attestation Response (Schnorr)
json{
  "event_id": "BTCUSD-2026-02-15T17:00:00Z",
  "pair": "BTCUSD",
  "maturity": "2026-02-15T17:00:00Z",
  "oracle_pubkey": "03ec3f43aa21878c55c2838fbf54aa2408d25abdcacd4cef6f32c48f3a53eda843",
  "price": 69005,
  "price_digits": [6, 9, 0, 0, 5],
  "s_values": ["801e97...", "a1d83e...", "4a7406...", "f4f672...", "d461cd..."],
  "attested_at": "2026-02-15T16:50:56Z"
}
Five Schnorr s-values, one per digit. Verifiable against the R-points published in the announcement. DLC clients use these to settle contracts without trusting the oracle at execution time.
DLC Oracle
SLO includes a fully functional DLC (Discreet Log Contract) oracle for non-custodial Bitcoin-native derivatives. No production-grade DLC oracle existed on Bitcoin mainnet before SLO.
How DLC attestations work

Announcement (free): Oracle pre-publishes nonce commitments (R-points) for the next 24 hours of hourly price events
Contract setup: Two parties build CETs (Contract Execution Transactions) using the R-points, locking bitcoin in a 2-of-2 multisig
Attestation (1000 sats via L402): At maturity, oracle fetches the BTCUSD price from 9 sources and publishes Schnorr s-values decomposed into 5 digits
Settlement: The winning party combines the s-values with their adaptor signature to claim funds — no oracle involvement required

Oracle identity
Pubkey:   03ec3f43aa21878c55c2838fbf54aa2408d25abdcacd4cef6f32c48f3a53eda843
Format:   Compressed secp256k1 (33 bytes)
Digits:   5 (covers $10,000–$99,999)
Schedule: Hourly attestations, 24h rolling announcements
Verification
For each digit i with value d, verify:
e = SHA256("{event_id}/{i}/{d}")
s*G == R + e*P
Where R is the nonce commitment from the announcement and P is the oracle pubkey.
BTCUSD 9-Source Feed
The BTCUSD spot oracle and DLC attestor share the same price feed (oracle/feeds/btcusd.py), aggregating from 9 exchanges:
Tier 1 — USD pairs: Coinbase, Kraken, Bitstamp, Gemini, Bitfinex, Binance US
Tier 2 — USDT pairs (normalized to USD via live USDT/USD rate): Binance, OKX, Gate.io
The USDT/USD rate is sourced from Kraken and Bitstamp (median). If the USD median and USDT median diverge by more than 0.5%, USDT sources are dropped automatically. Minimum 6 of 9 sources required for a valid price.
Repository Structure
slo/
├── oracle/
│   ├── feeds/
│   │   ├── __init__.py
│   │   └── btcusd.py                  # 9-source BTCUSD feed with USDT normalization
│   ├── liveoracle_btcusd_spot.py      # BTC spot oracle (10 sats, 9 sources)
│   ├── liveoracle_btcusd_vwap.py      # BTC VWAP oracle (20 sats, 2 sources)
│   ├── liveoracle_ethusd_spot.py      # ETH spot oracle (10 sats, 5 sources)
│   └── liveoracle_eurusd_spot.py      # EUR/USD oracle (10 sats, 7 sources)
├── dlc/
│   ├── __init__.py
│   ├── attestor.py                    # Schnorr nonce commitment & attestation
│   ├── server.py                      # DLC API server (FastAPI, port 9104)
│   └── scheduler.py                   # Hourly attestation loop
├── mcp/
│   └── slo_mcp_server.py             # MCP server for AI agents
├── client/
│   └── quorum_client_l402.py          # L402-aware quorum client
├── config/
│   └── aperture.yaml                  # Aperture L402 proxy config
├── docs/
│   ├── POLAR_SETUP.md                 # Local demo guide (Polar + regtest)
│   ├── DEPLOYMENT.md                  # Production deployment guide
│   ├── DEMO.md                        # Live demo walkthrough
│   ├── CLIENT_INTEGRATION.md          # Python, JS, Go integration guide
│   ├── OPERATOR_GUIDE.md              # How to run your own oracle
│   ├── Protocol.md                    # Canonical protocol specification
│   └── Quorum_Specification.md        # Client quorum and aggregation rules
├── legacy/                            # Original oracles with simulated payments
├── .gitignore
├── LICENSE
└── README.md
Protocol (v1)
Canonical Message
v1|<PAIR>|<price>|USD|<decimals>|<timestamp>|<nonce>|<sources>|<method>
Core Invariants

Payment before release — No signed data without Lightning payment (enforced by Aperture)
Explicit trust — Clients choose which oracles to query (no registry, no governance)
Deterministic verification — Every response is signed (secp256k1/Schnorr) and verifiable
Deterministic aggregation — Clients aggregate via median across multiple oracles

What SLO Is Not

Not a price feed (you pay per query, not per subscription)
Not a global oracle registry
Not a governance system
Not a consensus protocol

SLO does not decide which oracle is correct. That responsibility belongs to the client.
Architecture
SLO uses Lightning Labs' L402 protocol to gate API access behind Lightning micropayments:

Aperture — Reverse proxy that creates invoices and verifies payments
lnget — CLI client that handles L402 payments transparently
Oracle servers — Stateless FastAPI services that fetch prices, sign assertions, and return JSON
DLC attestor — Scheduled Schnorr signing service with persistent oracle key and hourly attestation loop

The oracle servers contain zero payment logic. Aperture enforces the "payment before data" invariant at the proxy layer.
For AI Agents
SLO is designed to be consumed by machines. The L402 protocol lets AI agents pay for data programmatically — no API keys, no OAuth, no accounts. An agent with a Lightning wallet can:
bashlnget -k -q http://104.197.109.246:8080/oracle/btcusd
lnget -k -q http://104.197.109.246:8080/oracle/ethusd
lnget -k -q http://104.197.109.246:8080/oracle/eurusd
10 sats spent, signed price received, cryptographically verified. This is what machine-payable data looks like.
MCP Server (Claude Desktop / Cursor)
SLO includes an MCP (Model Context Protocol) server that lets AI assistants like Claude buy signed price data automatically.
Setup

Install dependencies:

pip install fastmcp ecdsa

Ensure lnget is installed and configured
Add to your Claude Desktop config (%APPDATA%\Claude\claude_desktop_config.json):

json{
  "mcpServers": {
    "slo": {
      "command": "python",
      "args": ["/absolute/path/to/mcp/slo_mcp_server.py"]
    }
  }
}

Restart Claude Desktop and ask: "What's the current Bitcoin price?" or "What's the EUR/USD rate?"

Claude will pay sats over Lightning and return a cryptographically signed price. No API key. No configuration beyond a Lightning wallet.
Available Tools
ToolCostDescriptionget_btcusd_spot10 satsMedian BTC spot price from 9 sourcesget_btcusd_vwap20 satsVolume-weighted average from Coinbase, Krakenget_ethusd_spot10 satsMedian ETH spot price from 5 exchangesget_eurusd_spot10 satsMedian EUR/USD from 5 central banks + 2 exchanges
Roadmap

 BTCUSD spot oracle (median, 9 sources)
 BTCUSD VWAP oracle
 ETHUSD spot oracle (5 sources)
 EURUSD spot oracle (7 sources, 5 central banks, 4 continents)
 L402 payment gating (Aperture)
 Mainnet deployment
 MCP server for AI agents
 DLC oracle with Schnorr attestations (hourly, 5-digit decomposition, 1000 sats)
 9-source BTCUSD feed with USDT normalization
 Commodity oracles (gold via PAXG, oil)
 Interest rate oracles (Fed funds, SOFR)
 Multi-operator federation
 Domain name + TLS

Design Philosophy
SLO favors:

explicit failure over hidden retries
local configuration over global coordination
payment over access control
plural oracles over singular truth

Quick Start (Legacy — Simulated Payments)
No Lightning node required:
bashpip install fastapi uvicorn ecdsa requests

# Terminal 1-2: Start oracles
python legacy/liveoracle_btcusd_spot.py 8000
python legacy/liveoracle_btcusd_vwap.py 8002

# Terminal 3: Run quorum client
python legacy/quorum_client.py
License
MIT — see LICENSE
