1️⃣ Quorum Specification

File: docs/QUORUM_SPEC.md

Sovereign Lightning Oracle (SLO) — Client Quorum Specification v1
1. Scope

This specification defines the client-side quorum rules for resolving assertions from multiple independent SLO oracles.
It applies to any client or agent consuming signed assertions via the SLO protocol.

The protocol itself does not enforce quorum.
All trust decisions are explicitly delegated to the client.

2. Definitions

Oracle: An independent operator that returns signed assertions.

Assertion: A canonical, signed statement of a metric (e.g. BTCUSD).

Availability quorum: Minimum number of valid oracle responses required.

Price coherence: Acceptable agreement between oracle-reported values.

Resolution: A successful aggregation resulting in an actionable value.

3. Preconditions

For an oracle response to be considered valid:

The oracle must require payment prior to releasing data.

The response must include:

canonical string

signature

public key

The signature must verify against the canonical string.

The canonical string must conform to the expected format.

Responses failing any precondition MUST be discarded.

4. Availability Quorum

The client MUST define a minimum availability quorum.

Reference implementation:

MIN_RESPONSES = 2

Resolution MUST abort if fewer than MIN_RESPONSES valid oracle responses are obtained.

Availability quorum failure MUST be explicit and MUST NOT fall back to cached or default values.

5. Aggregation Method

For numeric price assertions, the reference aggregation method is:

Median of all valid oracle-reported values

The aggregation method MUST be deterministic and MUST be documented.

6. Price Coherence Enforcement

After aggregation, the client MUST enforce price coherence.

Reference implementation:

MAX_DEVIATION_PCT = 0.5%

For each oracle-reported value p and aggregated value m:

|p - m| / m ≤ MAX_DEVIATION_PCT


If any value violates the deviation threshold, resolution MUST abort.

The client MUST NOT attempt to reweight, override, or selectively ignore oracle responses.

7. Failure Semantics

The client MUST abort resolution if:

Availability quorum is not met

Any signature fails verification

Price coherence is violated

Any required field is missing or malformed

Aborting resolution is considered correct behavior, not an error condition.

8. Rationale

These quorum rules ensure:

Explicit trust assumptions

Resistance to outliers and manipulation

Clear failure modes

No hidden authority

Deterministic, auditable behavior

9. Extensibility

Future versions MAY introduce:

oracle weighting

reputation systems

dynamic thresholds

Such extensions are explicitly out of scope for v1.
