Sovereign Lightning Oracle (SLO)

Pay sats. Get signed data. Trust math, not middlemen.

SLO is a protocol for purchasing signed, verifiable data assertions over Lightning micropayments. No API keys. No accounts. No trust. Just payment and proof.
BTCUSD, ETHUSD, and EURUSD are live on Bitcoin mainnet. The EUR/USD oracle aggregates rates from 5 central banks across 4 continents plus 2 live exchanges — proving the SLO pattern works beyond crypto. Future versions will support additional asset pairs, commodities, and any metric where truth is contested and verification matters.

Why SLO?
Oracles today are broken. Most price feeds are free — which means you're not the customer, you're the product. Free oracles create hidden dependencies: opaque update schedules, silent failures, governance capture, and single points of trust that defeat the purpose of building on Bitcoin.
SLO takes a different approach:

Payment replaces trust. Every query costs sats. Every response is signed. If the data is wrong, stop paying. The market decides which oracles survive.
No accounts, no API keys. A Lightning payment is your authentication. Any machine with a wallet can buy data — humans, bots, smart contracts, AI agents.
Multiple oracles, client aggregation. You choose which oracles to query. You aggregate the results. No single oracle can lie to you without detection.
Cryptographic proof at every layer. Signed assertions (secp256k1) mean you can verify data independently, store it, forward it, or submit it on-chain — all without trusting the transport.
Censorship resistant. No platform can revoke your access. If you can reach the endpoint and pay the invoice, you get the data. No terms of service, no rate limits, no deplatforming.
Aligned incentives. Oracle operators earn sats per query. More accurate data attracts more paying clients. Bad data means lost revenue. The economic feedback loop enforces quality without governance.

Try It Now
Live (mainnet — any Lightning wallet)
curl -v http://104.197.109.246:8080/oracle/btcusd
curl -v http://104.197.109.246:8080/oracle/ethusd
curl -v http://104.197.109.246:8080/oracle/eurusd
You'll get a 402 Payment Required with a Lightning invoice. Pay it with any Lightning wallet, get a cryptographically signed price sourced from major exchanges and central banks.
Four oracles are live, each using different methodologies and price points:
EndpointAssetMethodPriceSources/oracle/btcusdBTC/USDSpot median10 satsCoinbase, Kraken, Bitstamp/oracle/btcusd/vwapBTC/USDVolume-weighted average20 satsCoinbase, Kraken/oracle/ethusdETH/USDSpot median10 satsCoinbase, Kraken, Bitstamp, Gemini, Bitfinex/oracle/eurusdEUR/USDSpot median10 satsECB, Bank of Canada, RBA, Norges Bank, Czech National Bank, Kraken, Bitstamp
The VWAP oracle costs more because it processes full trade history rather than a single last-trade price — more computation, more data, more signal.
The EUR/USD oracle is the first non-crypto oracle on SLO. It aggregates rates from 5 central banks (European Central Bank, Bank of Canada, Reserve Bank of Australia, Norges Bank, Czech National Bank) across 4 continents plus 2 live forex exchanges (Kraken, Bitstamp). Central bank rates are derived via cross-rate math where needed — for example, EUR/USD from Bank of Canada is computed as EURCAD / USDCAD.

⚡ Status: Beta — Live on Bitcoin mainnet. The endpoint may go down for maintenance.

Local demo (no Lightning node needed)
Clone this repo and run the Polar Setup Guide to simulate the full L402 flow on your machine in ~30 minutes. No real bitcoin required.
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

Response Format
json{
  "domain": "EURUSD",
  "canonical": "v1|EURUSD|1.18620|USD|5|2026-02-15T09:38:19Z|901234|ecb,bankofcanada,rba,norgesbank,cnb,kraken,bitstamp|median",
  "signature": "cfOS+6O9juqAstevylkIF7ySJWqt4p0jxKDtzsTDiIA...",
  "pubkey": "03eae218cdc9ea9490b4e5de82a16c07a6472b762481..."
}
The canonical field is the signed message. The signature is a secp256k1 ECDSA signature over SHA256(canonical). Any client can verify the signature using the pubkey.
Repository Structure
slo/
├── mcp/
│   └── slo_mcp_server.py              # MCP server for AI agents
├── oracle/
│   ├── liveoracle_btcusd_spot.py       # BTC spot oracle (10 sats, 3 sources)
│   ├── liveoracle_btcusd_vwap.py       # BTC VWAP oracle (20 sats, 2 sources)
│   ├── liveoracle_ethusd_spot.py       # ETH spot oracle (10 sats, 5 sources)
│   └── liveoracle_eurusd_spot.py       # EUR/USD spot oracle (10 sats, 7 sources)
├── client/
│   └── quorum_client_l402.py           # L402-aware quorum client
├── config/
│   └── aperture.yaml                   # Aperture config template
├── docs/
│   ├── POLAR_SETUP.md                  # Local demo guide (Polar + regtest)
│   ├── DEPLOYMENT.md                   # Production deployment guide (GCP + Voltage)
│   ├── DEMO.md                         # Live demo walkthrough
│   ├── CLIENT_INTEGRATION.md           # Python, JS, Go integration guide
│   ├── OPERATOR_GUIDE.md               # How to run your own oracle
│   ├── Protocol.md                     # Canonical protocol specification
│   └── Quorum_Specification.md         # Client quorum and aggregation rules
├── legacy/
│   ├── liveoracle_btcusd_liquidity.py  # Original liquidity oracle
│   └── quorum_client.py               # Original client
├── README.md
└── LICENSE
Protocol (v1)
Canonical Message
v1|<PAIR>|<price>|USD|<decimals>|<timestamp>|<nonce>|<sources>|<method>
Core Invariants

Payment before release — No signed data without Lightning payment (enforced by Aperture)
Explicit trust — Clients choose which oracles to query (no registry, no governance)
Deterministic verification — Every response is signed (secp256k1) and verifiable
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

The oracle servers contain zero payment logic. Aperture enforces the "payment before data" invariant at the proxy layer.
For AI Agents
SLO is designed to be consumed by machines. The L402 protocol lets AI agents pay for data programmatically — no API keys, no OAuth, no accounts. An agent with a Lightning wallet can:
bashlnget -k http://104.197.109.246:8080/oracle/btcusd
lnget -k http://104.197.109.246:8080/oracle/ethusd
lnget -k http://104.197.109.246:8080/oracle/eurusd
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
ToolCostDescriptionget_btcusd_spot10 satsMedian BTC spot price from Coinbase, Kraken, Bitstampget_btcusd_vwap20 satsVolume-weighted average from Coinbase, Krakenget_ethusd_spot10 satsMedian ETH spot price from Coinbase, Kraken, Bitstamp, Gemini, Bitfinexget_eurusd_spot10 satsMedian EUR/USD rate from ECB, Bank of Canada, RBA, Norges Bank, CNB, Kraken, Bitstamp
Roadmap

 BTCUSD spot oracle (median)
 BTCUSD VWAP oracle
 ETHUSD spot oracle (5 sources)
 EURUSD spot oracle (7 sources, 5 central banks, 4 continents)
 L402 payment gating (Aperture)
 Mainnet deployment
 MCP server for AI agents
 Additional asset pairs (SOLUSD, GBPUSD, etc.)
 Commodity oracles (gold, oil)
 Interest rate oracles (Fed funds, SOFR)
 DLC-compatible attestations
 Persistent signing keys (HSM-backed)
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
