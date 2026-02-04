# Sovereign Lightning Oracle (SLO)

SLO is a minimal protocol that allows agents and contracts to purchase signed, verifiable BTCUSD price assertions using Lightning payments, with a design that generalizes to other metrics with variable truth, without trusting any single oracle.

The protocol is intentionally narrow in scope and favors explicit trust boundaries over discovery, governance, or reputation systems.

[![License: MIT (planned)](https://img.shields.io/badge/License-MIT%20(planned)-yellow.svg)](LICENSE)  
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)

What this is

* A paid oracle protocol using Lightning
* Client-selected oracle sets
* Deterministic aggregation (median)
* Canonical, signed factual assertions
* Reference oracle and reference client implementations

SLO is designed to be boring, explicit, and composable.

What this is not

* A price feed API
* A global oracle registry
* A governance system
* A token network
* A consensus protocol
* A source of “the true price”

SLO does not attempt to decide which oracle is correct. That responsibility belongs entirely to the client.

v1 Scope (Frozen)
v1 is intentionally limited and frozen.

* Domain: BTCUSD only
* Payments: Lightning only
* Aggregation: median
* Oracles: independently operated, stateless HTTP services
* Clients: explicitly configured oracle lists
* No discovery
* No reputation
* No persistence requirements

If something is not listed here, it is out of scope for v1.

Core Invariants
SLO enforces the following invariants:

1. Payment before release\
   No signed data is returned unless Lightning payment is verified.

2. Explicit trust\
   Clients choose which oracles to query. There is no registry.

3. Deterministic verification\
   All oracle responses are signed and verifiable.

4. Deterministic aggregation\
   Clients aggregate results using a fixed rule (median in v1).

Repository Contents

* quorum_client.py\
  Quorum-aware client reference

* liveoracle_btcusd_spot.py\
  Live BTCUSD oracle (spot median from real sources)

* liveoracle_btcusd_liquidity.py\
  Live BTCUSD oracle (liquidity-weighted)

* liveoracle_btcusd_vwap.py\
  Live BTCUSD oracle (time-windowed VWAP)

* Protocol.md\
  Canonical protocol specification

* Quorum Specification.md\
  Detailed client quorum and aggregation rules

* CLIENT_INTEGRATION.md\
  How clients integrate SLO

* DEMO.md\
  Step-by-step demo instructions

* ORACLE_OPERATORS_GUIDE/\
  Directory with guide(s) for running/operating an oracle

* VERSION.txt\
  Version and freeze status

* LICENSE\
  License file (MIT planned)

Demo
A local demo runs three independent oracles and a client that:

* pays each oracle via simulated Lightning
* verifies signatures
* aggregates prices deterministically

See DEMO.md for exact commands.

Design Philosophy
SLO favors:

* explicit failure over hidden retries
* local configuration over global coordination
* payment over access control
* plural oracles over singular truth

Disagreement between oracles is expected and handled by clients.

Status

* Version: v1
* Status: Frozen
* Purpose: Protocol validation and external operator testing

No new features will be added to v1.

External Operators
The project is actively looking for one external oracle operator to run the reference oracle and expose an endpoint, in order to validate independence and protocol clarity.
No commitments or incentives are implied.

License
MIT License — see [`LICENSE`](LICENSE) for full text (forthcoming).

The protocol specification and reference implementations are intended for public use, improvement, and independent operation. Once external validation is underway, the full MIT license will be applied to enable broader adoption.license will be applied to enable broader adoption.
