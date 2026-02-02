docs/PROTOCOL.md
PROTOCOL.md


Sovereign Lightning Oracle Protocol — v1
Domain
BTCUSD

Canonical Message Format
v1|BTCUSD|<value>|USD|<decimals>|<timestamp>|<blockheight>|<sources>|median

Example:
v1|BTCUSD|43250.67|USD|2|2026-02-02T16:00:00Z|890456|coinbase,kraken,bitstamp|median


Signing
secp256k1


SHA256 hash of canonical string


Signature returned base64-encoded


Public key provided in compressed hex



Payment Rule
Oracle must not release signed data before payment


One Lightning invoice per request


Payment verification precedes response



Aggregation
Client computes median of oracle values


No weighting in v1


Client must verify all signatures



Failure Semantics
If quorum not met → fail deterministically


Partial oracle responses do not settle contracts


Clients define fallback behavior



Out of Scope (v1)
Discovery


Reputation


Governance


Non-price data


Multi-asset support



