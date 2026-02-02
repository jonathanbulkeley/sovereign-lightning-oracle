docs/CLIENT_INTEGRATION.md

# Client Integration Guide  
## Sovereign Lightning Oracle (SLO) — v1

---

## Purpose

This document describes how a client integrates with SLO v1 to resolve
BTCUSD pricing using paid, signed oracle assertions.

SLO does not provide a hosted service or SDK. Clients retain full control
over oracle selection, trust assumptions, and failure handling.

---

## What the Client Is Responsible For

An SLO client is responsible for:

1. Selecting which oracles to query
2. Paying each oracle via Lightning
3. Verifying cryptographic signatures
4. Aggregating oracle responses deterministically
5. Handling failure conditions explicitly

SLO intentionally does not automate these decisions.

---

## Integration Model (v1)

### Oracle Selection

Clients configure a fixed list of oracle endpoints, for example:



http://oracle-a:8000

http://oracle-b:8001

http://oracle-c:8002


There is no discovery mechanism and no global registry.
Oracle selection is an explicit trust decision made by the client.

---

### Request Flow

For each oracle, the client performs the following steps:

1. Request a quote  
   `GET /quote`

2. Receive a Lightning invoice and invoice ID

3. Pay the invoice using Lightning

4. Fetch signed data  
   `GET /paid/{invoice_id}`

If payment has not occurred, the oracle must not release signed data.

---

### Signature Verification

Clients must verify:

- the signature is valid for the canonical message
- the public key matches the expected oracle identity
- the canonical message format matches the protocol specification

Unsigned or unverifiable responses must be rejected.

---

### Aggregation

In v1, clients aggregate BTCUSD prices using the **median** of valid oracle
responses.

Aggregation rules are deterministic and client-controlled.

SLO does not:
- weight oracle responses
- rank oracles
- decide which oracle is “correct”

---

## Failure Semantics

If one or more oracles fail, clients must decide how to proceed.

Examples of failure include:
- oracle unavailable
- payment rejected
- malformed response
- invalid signature

In the reference client, failure to meet quorum results in a hard failure.

Clients may choose different policies, but these are outside the protocol.

---

## Quorum

The reference client requires all configured oracles to respond successfully.

This is a policy choice, not a protocol requirement.

Clients may:
- require a strict quorum
- tolerate partial responses
- abort immediately on any failure

SLO does not enforce quorum policy.

---

## What SLO Does Not Do

SLO intentionally does not provide:

- retries or fallback logic
- oracle discovery
- reputation or scoring
- caching
- time synchronization
- SLAs or uptime guarantees

These concerns belong to client logic, not the protocol.

---

## Reference Implementation

A minimal reference client is provided in `client.py`.

The reference client is intended to demonstrate:
- correct payment flow
- signature verification
- deterministic aggregation

It is not intended to be production-ready.

---

## v1 Scope Reminder

This guide applies only to SLO v1, which is frozen and limited to:

- BTCUSD pricing
- Lightning-based payments
- Stateless oracle endpoints

Future versions may introduce additional domains or client tooling,
but these are explicitly out of scope for v1.

---

## Summary

Integrating with SLO means explicitly choosing:
- who you trust
- how much you pay
- how you resolve disagreement

SLO provides the protocol mechanics.
Clients provide the judgment.
