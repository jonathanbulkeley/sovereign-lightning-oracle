# Quorum Specification

How clients aggregate responses from multiple SLO oracles to arrive at a trusted price.

## Why Quorum?

A single oracle can lie, fail, or be compromised. Querying multiple independent oracles and aggregating their responses provides:

- **Fault tolerance** — One oracle going down doesn't break your application
- **Manipulation resistance** — An attacker must compromise multiple oracles simultaneously
- **Accuracy** — Outliers are filtered by the aggregation method

SLO does not enforce quorum at the protocol level. Quorum is a client-side responsibility. This specification defines the recommended approach.

## Parameters

| Parameter | Default | Description |
|---|---|---|
| `MIN_RESPONSES` | 2 | Minimum number of valid responses required |
| `MAX_DEVIATION_PCT` | 0.5% | Maximum allowed deviation from median |
| `MAX_STALENESS_SEC` | 60 | Maximum age of a response in seconds |

Clients should tune these parameters to their risk tolerance. A DeFi contract settling large amounts may require 3+ responses with 0.1% deviation. A dashboard displaying approximate prices may accept 1 response with 2% deviation.

## Oracle Set

The client maintains a list of trusted oracles:
```python
ORACLES = [
    {
        "name": "spot",
        "url": "https://api.myceliasignal.com/oracle/btcusd",
        "pubkey": "0220a2222aae...",   # pin for identity verification
        "weight": 1.0,                  # optional: weight in aggregation
    },
    {
        "name": "vwap",
        "url": "https://api.myceliasignal.com/oracle/btcusd/vwap",
        "pubkey": "03f1b2c3d4e5...",
        "weight": 1.0,
    },
    # Add third-party operators as they come online
]
```

There is no oracle registry. The client decides which oracles to trust. This is a feature, not a limitation — it means no governance attack can force bad oracles into your trust set.

## Query Phase

For each oracle in the set:

1. Send HTTP GET request (with L402 payment)
2. If the request fails (timeout, connection error, 500), skip this oracle
3. If the request succeeds, proceed to validation
```
for each oracle in ORACLES:
    try:
        response = l402_fetch(oracle.url)
    except (Timeout, ConnectionError, PaymentFailed):
        log("oracle {oracle.name} unreachable, skipping")
        continue
    validate(response)
```

## Validation Phase

Each response must pass four checks before inclusion in aggregation:

### 1. Signature Verification
```
hash = SHA256(response.canonical)
valid = ECDSA_verify(hash, response.signature, response.pubkey)
if not valid:
    REJECT("invalid signature")
```

A failed signature means the data was tampered with in transit or the oracle is broken. Always reject.

### 2. Pubkey Pinning
```
if oracle.pinned_pubkey and response.pubkey != oracle.pinned_pubkey:
    REJECT("pubkey mismatch — possible impersonation")
```

If you have previously recorded an oracle's public key, reject responses signed by a different key. This prevents an attacker from substituting a different oracle at the same URL.

### 3. Staleness Check
```
assertion_time = parse_timestamp(response.canonical)
age = now_utc() - assertion_time
if age > MAX_STALENESS_SEC:
    REJECT("assertion too old: {age} seconds")
```

Stale data may reflect prices that have moved significantly. Reject assertions older than your threshold.

### 4. Format Validation
```
parts = response.canonical.split("|")
assert parts[0] == "v1"           # known protocol version
assert parts[1] == "BTCUSD"       # expected asset pair
assert parts[3] == "USD"          # expected quote currency
assert len(parts) == 9            # correct field count
price = float(parts[2])           # parseable price
assert price > 0                  # positive price
```

Reject any response that doesn't conform to the expected canonical format.

## Aggregation Phase

After validation, the client has a set of accepted prices. Aggregation proceeds as follows:

### Step 1: Check Minimum Responses
```
if len(valid_prices) < MIN_RESPONSES:
    FAIL("quorum not met: got {n}, need {MIN_RESPONSES}")
```

If too few oracles responded with valid data, the client should not produce a price. Fail loudly.

### Step 2: Compute Median
```
median_price = median(valid_prices)
```

Median is preferred over mean because it is resistant to outliers. A single manipulated oracle cannot move the median significantly.

### Step 3: Coherence Check
```
for each price in valid_prices:
    deviation = abs(price - median_price) / median_price * 100
    if deviation > MAX_DEVIATION_PCT:
        FAIL("coherence failure: {oracle} deviates {deviation}% from median")
```

If any accepted oracle deviates too far from the median, something is wrong. Possible causes:

- One oracle is using stale data
- One oracle's source API is returning bad data
- One oracle is compromised

The safe response is to reject the entire batch and alert the operator.

### Step 4: Return Result
```
RESULT = {
    "price": median_price,
    "oracles_queried": len(ORACLES),
    "oracles_accepted": len(valid_prices),
    "prices": valid_prices,
    "timestamp": now_utc(),
}
```

## Decision Matrix

| Scenario | Oracles Queried | Valid Responses | Coherent? | Result |
|---|---|---|---|---|
| All good | 2 | 2 | Yes | Accept median |
| One down | 2 | 1 | N/A | Reject (below MIN_RESPONSES) |
| Both down | 2 | 0 | N/A | Reject |
| One diverges | 2 | 2 | No | Reject (coherence failure) |
| Bad signature | 2 | 1 | N/A | Reject (below MIN_RESPONSES) |
| Stale response | 2 | 1 | N/A | Reject (below MIN_RESPONSES) |
| All good (3 oracles) | 3 | 3 | Yes | Accept median |
| One diverges (3 oracles) | 3 | 3 | No | Reject or drop outlier* |

*With 3+ oracles, an advanced client may choose to drop the outlier and proceed with the remaining 2, provided they still meet `MIN_RESPONSES` and coherence checks.

## Failure Modes

### Quorum Not Met

Fewer than `MIN_RESPONSES` valid responses. Client should:
- Retry after a delay
- Alert the operator
- Use a cached price with an explicit staleness warning
- **Never** silently use a single unverified source

### Coherence Failure

Valid responses diverge beyond `MAX_DEVIATION_PCT`. Client should:
- Reject all prices
- Log which oracles diverged and by how much
- Alert the operator
- **Never** average the divergent prices — divergence means something is wrong

### Total Failure

No oracles respond. Client should:
- Retry with exponential backoff
- Fall back to a cached price with clear staleness marking
- Halt operations that depend on fresh price data

## Weighted Aggregation (Advanced)

For clients with more than two oracles, weighted median can reflect differing levels of trust:
```python
def weighted_median(prices, weights):
    sorted_pairs = sorted(zip(prices, weights))
    cumulative = 0
    total = sum(weights)
    for price, weight in sorted_pairs:
        cumulative += weight
        if cumulative >= total / 2:
            return price
```

Weight assignment is subjective. Factors to consider:
- Historical accuracy of the oracle
- Diversity of underlying sources
- Uptime track record
- Methodology (VWAP may deserve higher weight than spot for certain use cases)

## Reference Implementation

The included quorum client implements this specification:
```bash
python client/quorum_client_l402.py --backend lnget
```

Source: [client/quorum_client_l402.py](../client/quorum_client_l402.py)

## Design Principles

1. **Client sovereignty.** The client chooses oracles, parameters, and failure behavior. No protocol-level governance.
2. **Fail loud.** When quorum fails, the client knows immediately. Silent fallbacks are dangerous.
3. **Median over mean.** Median resists manipulation. Mean amplifies it.
4. **Coherence over consensus.** SLO doesn't ask oracles to agree. It asks the client to check whether they agree.
5. **Explicit thresholds.** Every parameter (`MIN_RESPONSES`, `MAX_DEVIATION_PCT`, `MAX_STALENESS_SEC`) is visible, tunable, and auditable.
```

---

That's all the docs. Full set:

| File | Description |
|---|---|
| `README.md` | Project overview, benefits, live endpoint |
| `docs/Protocol.md` | Canonical format, signing, L402 flow |
| `docs/Quorum_Specification.md` | Client aggregation rules |
| `docs/DEMO.md` | Step-by-step live walkthrough |
| `docs/CLIENT_INTEGRATION.md` | Python, JS, Go integration |
| `docs/OPERATOR_GUIDE.md` | How to run your own oracle |
| `docs/DEPLOYMENT.md` | GCP + Voltage production setup |
| `docs/POLAR_SETUP.md` | Local demo with Polar |

Check the channel:
```
curl -k --header "Grpc-Metadata-macaroon: %MAC%" https://mycelia.m.voltageapp.io:8080/v1/channels/pending
