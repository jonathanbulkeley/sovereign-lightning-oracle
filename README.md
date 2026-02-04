# Sovereign Lightning Oracle (SLO)

**Bitcoin-native protocol for paid, verifiable, agent-to-agent real-world data via Lightning micropayments.**

SLO is a minimal protocol that allows agents and contracts to purchase signed, verifiable **BTCUSD** price assertions using Lightning payments. The design generalizes to other metrics with variable truth, without trusting any single oracle.

The protocol is intentionally narrow in scope and favors **explicit trust boundaries** over discovery, governance, or reputation systems.

[![License: Unlicensed (validation phase)](https://img.shields.io/badge/License-Unlicensed-blue.svg)](https://github.com/jonathanbulkeley/sovereign-lightning-oracle)  
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)

### What this is

- A paid oracle protocol using Lightning
- Client-selected oracle sets
- Deterministic aggregation (median in v1)
- Canonical, signed factual assertions
- Reference oracle and client implementations (plus live BTCUSD variants)

SLO is designed to be **boring, explicit, and composable**.

### What this is not

- A price feed API
- A global oracle registry
- A governance system
- A token network
- A consensus protocol
- A source of “the true price”

SLO does **not** decide which oracle is correct. That responsibility belongs entirely to the client.

### v1 Scope (Frozen)

v1 is limited and frozen to ensure clarity and testability.

- Domain: BTCUSD only
- Payments: Lightning only (simulated in reference; real in live oracles)
- Aggregation: median
- Oracles: independently operated, stateless HTTP services
- Clients: explicitly configured oracle lists
- No discovery
- No reputation
- No persistence requirements

If something is not listed here, it is **out of scope** for v1.

### Core Invariants

1. **Payment before release** — No signed data is returned unless Lightning payment is verified.
2. **Explicit trust** — Clients choose which oracles to query. There is no registry.
3. **Deterministic verification** — All oracle responses are signed and verifiable (secp256k1).
4. **Deterministic aggregation** — Clients aggregate using a fixed rule (median in v1).

### Repository Contents


- `quorum_client.py` — Reference client implementation (queries, verifies, aggregates from 3 live oracles)
- `liveoracle_btcusd_spot.py` — Live BTCUSD oracle (spot median from real sources)
- `liveoracle_btcusd_liquidity.py` — Live BTCUSD oracle (liquidity-weighted)
- `liveoracle_btcusd_vwap.py` — Live BTCUSD oracle (time-windowed VWAP)
- `Protocol.md` — Canonical protocol specification
- `Quorum Specification.md` — Detailed client quorum and aggregation rules
- `CLIENT_INTEGRATION.md` — How clients integrate SLO
- `DEMO.md` — Step-by-step local demo instructions
- `ORACLE_OPERATORS_GUIDE` (directory) — Guide for running/operating an oracle
- `VERSION.txt` — Version and freeze status

### Quick Start (Local Demo)

Run three independent oracles and a client that pays (simulated Lightning), verifies signatures, and aggregates medians.

See [`DEMO.md`](DEMO.md) for exact commands and expected output (shows real-time variance and explicit success/failure).

### Design Philosophy

SLO favors:

- Explicit failure over hidden retries
- Local configuration over global coordination
- Payment over access control
- Plural oracles over singular truth

Disagreement between oracles is **expected** and handled by clients.

### Status

- Version: v1
- Status: Frozen
- Purpose: Protocol validation, reference implementations, and external operator testing

No new features will be added to v1. Feedback welcome on protocol clarity and operator experience.

### Seeking External Operators

Actively looking for **one (or more) external oracle operators** to:

- Run one of the live reference oracles (spot, liquidity, or VWAP)
- Expose a public endpoint
- Validate independence, payment flow, and protocol behavior under real conditions

No commitments, incentives, or equity implied—just mutual validation of the design.  
Contact via Nostr (npub...) or open an issue.

### License

The v1 reference implementation is **currently unlicensed** during protocol validation and external testing. Once independence is proven (e.g., via external operators), MIT licensing will be applied to enable broader adoption.

The protocol specification itself (in `Protocol.md`) is intended for public use and improvement.

### Next Steps (Community-Driven)

- Run the demo and provide feedback
- Operate an independent oracle and share your endpoint
- Integrate into a Lightning agent or DLC prototype
- Suggest improvements to trust bundles or client patterns (via issues)

Truth is not enforced. It is purchased, verified, and chosen.
