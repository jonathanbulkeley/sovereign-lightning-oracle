# Oracle Operator's Guide

How to run your own Sovereign Lightning Oracle and sell signed data for sats.

## Overview

An SLO operator runs one or more oracle servers behind an Aperture L402 proxy, connected to a Lightning node. Clients pay Lightning invoices to receive signed price assertions. You earn sats for every query.

## What You Need

1. **A Linux server** — Cloud VM (GCP, AWS, etc.) or your own hardware
2. **A Lightning node** — LND (self-hosted or Voltage/hosted)
3. **Aperture** — L402 reverse proxy (open source, by Lightning Labs)
4. **Python 3** — For running the oracle servers

Estimated costs:
- Cloud VM: ~$15/month (GCP e2-small)
- Lightning node: ~$27/month (Voltage Standard) or free (self-hosted)
- Channel liquidity: 3-4M sats (~$2,000 at current prices) for inbound capacity

## Architecture
```
Internet → Aperture (:8080) → Oracle backend (:9100)
                ↕
          Your LND node
```

Aperture handles all payment logic. Your oracle code is a simple HTTP server that fetches prices, signs them, and returns JSON. Zero payment logic in the oracle itself.

## Step 1: Set Up Your Lightning Node

### Option A: Voltage (hosted, easiest)

1. Create a mainnet node at https://app.voltage.cloud
2. Download `tls.cert` and `admin.macaroon`
3. Fund the node and open channels (see [DEPLOYMENT.md](DEPLOYMENT.md))

### Option B: Self-hosted LND

1. Install LND: https://github.com/lightningnetwork/lnd
2. Sync to chain, create wallet
3. Open channels to well-connected peers

Either way, you need **inbound liquidity** to receive payments. Open a channel with `push_sat` to give the remote side funds that can flow back to you when clients pay.

## Step 2: Install and Build
```bash
# System packages
sudo apt install -y python3 python3-pip golang-go git

# Python dependencies
pip3 install fastapi uvicorn ecdsa requests --break-system-packages

# Clone SLO
git clone https://github.com/jonathanbulkeley/sovereign-lightning-oracle.git ~/slo

# Build Aperture
git clone https://github.com/lightninglabs/aperture.git ~/aperture
cd ~/aperture
go build -o aperture ./cmd/aperture
```

## Step 3: Configure Your Oracle

### Signing Keys

Each oracle generates a fresh secp256k1 key pair on startup. The public key is returned with every response so clients can verify signatures.

For production, you should use a persistent key so clients can pin your identity across restarts. Modify the oracle code to load a key from disk:
```python
import os
from ecdsa import SigningKey, SECP256k1

KEY_PATH = "/home/your_user/slo/keys/oracle.pem"

if os.path.exists(KEY_PATH):
    with open(KEY_PATH, "rb") as f:
        PRIVATE_KEY = SigningKey.from_pem(f.read())
else:
    PRIVATE_KEY = SigningKey.generate(curve=SECP256k1)
    os.makedirs(os.path.dirname(KEY_PATH), exist_ok=True)
    with open(KEY_PATH, "wb") as f:
        f.write(PRIVATE_KEY.to_pem())

PUBLIC_KEY = PRIVATE_KEY.get_verifying_key()
```

### Price Sources

The default oracles fetch from public exchange APIs (Coinbase, Kraken, Bitstamp). You can add or replace sources by modifying the `fetch_*` functions. Consider:

- **Redundancy** — Use at least 3 sources; the oracle takes the median
- **Rate limits** — Public APIs may throttle you; monitor for failures
- **Latency** — Slower sources add response time; set aggressive timeouts
- **Geographic diversity** — Mix US and EU exchanges to reduce correlated failures

### Pricing Your Data

Set your prices in `aperture.yaml`:
```yaml
services:
  - name: "slo-spot"
    pathregexp: "^/oracle/btcusd$"
    address: "127.0.0.1:9100"
    protocol: "http"
    price: 10          # sats per query

  - name: "slo-vwap"
    pathregexp: "^/oracle/btcusd/vwap$"
    address: "127.0.0.1:9101"
    protocol: "http"
    price: 20          # sats per query
```

Pricing considerations:
- Too cheap and you don't cover costs
- Too expensive and clients choose other oracles
- More computation or better data justifies higher prices (VWAP > spot)
- The market will tell you — if query volume drops, your price is too high

## Step 4: Configure Aperture

Create your `aperture.yaml`:
```yaml
insecure: true
listenaddr: "0.0.0.0:8080"
debuglevel: "debug"
dbbackend: "sqlite"

authenticator:
  network: "mainnet"
  lndhost: "YOUR_LND_HOST:10009"
  tlspath: "/path/to/tls.cert"
  macdir: "/path/to/macaroon/directory"

services:
  - name: "slo-spot"
    hostregexp: ".*"
    pathregexp: "^/oracle/btcusd$"
    address: "127.0.0.1:9100"
    protocol: "http"
    price: 10

  - name: "slo-vwap"
    hostregexp: ".*"
    pathregexp: "^/oracle/btcusd/vwap$"
    address: "127.0.0.1:9101"
    protocol: "http"
    price: 20
```

**Important:** Aperture looks for `invoice.macaroon` in the `macdir` directory. If you only have `admin.macaroon`, copy it:
```bash
cp admin.macaroon invoice.macaroon
```

## Step 5: Launch
```bash
# Start oracles
python3 ~/slo/oracle/liveoracle_btcusd_spot.py &
python3 ~/slo/oracle/liveoracle_btcusd_vwap.py &

# Start Aperture
~/aperture/aperture --configfile=~/slo/config/aperture.yaml &
```

### Verify
```bash
curl -v http://localhost:8080/oracle/btcusd
# Should return 402 with a Lightning invoice
```

## Step 6: Keep It Running

Use systemd to survive reboots and SSH disconnects:
```bash
sudo tee /etc/systemd/system/slo-spot.service << 'EOF'
[Unit]
Description=SLO Spot Oracle
After=network.target

[Service]
User=YOUR_USER
ExecStart=/usr/bin/python3 /home/YOUR_USER/slo/oracle/liveoracle_btcusd_spot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable slo-spot
sudo systemctl start slo-spot
```

Repeat for `slo-vwap` and `aperture`.

## Monitoring

### Check oracle health
```bash
curl http://localhost:9100/health
curl http://localhost:9101/health
```

### Check channel balance
```bash
curl -k --header "Grpc-Metadata-macaroon: YOUR_HEX_MACAROON" \
  https://YOURNODE.m.voltageapp.io:8080/v1/balance/channels
```

### Check earnings
```bash
curl -k --header "Grpc-Metadata-macaroon: YOUR_HEX_MACAROON" \
  https://YOURNODE.m.voltageapp.io:8080/v1/invoices?reversed=true&num_max_invoices=10
```

### Watch for problems

- **Oracle returning errors** — Exchange APIs may be down; check logs
- **Aperture not starting** — Usually a macaroon or TLS cert path issue
- **No payments arriving** — Check inbound liquidity; channel may be depleted
- **Channel force-closed** — Peer went offline; need to open a new channel

## Adding New Data Types

To create a new oracle (e.g., ETHUSD), copy the spot oracle and modify:

1. Change the exchange API calls to fetch ETH prices
2. Update the canonical format: `v1|ETHUSD|...|ethereum sources|median`
3. Run on a new port (e.g., 9102)
4. Add a new service block in `aperture.yaml`

The protocol is data-agnostic. Any verifiable assertion can be sold this way — prices, rates, weather, election results, sports scores. If a client will pay for it and you can sign it, it's an oracle.

## Economics

A rough model for a BTCUSD spot oracle:

| Item | Monthly Cost |
|---|---|
| GCP e2-small VM | $15 |
| Voltage Standard node | $27 |
| **Total operating cost** | **$42** |

At 10 sats per query (~$0.007):
- **Break even:** ~6,000 queries/month (~200/day)
- **At 1,000 queries/day:** ~$210/month revenue, ~$168 profit

The real value comes from serving multiple data types on the same infrastructure. Each new oracle endpoint is incremental revenue on the same fixed costs.
```

---

That's the operator guide. Add it to `docs/OPERATOR_GUIDE.md` in your repo. Also check that channel:
```
curl -k --header "Grpc-Metadata-macaroon: %MAC%" https://mycelia.m.voltageapp.io:8080/v1/channels/pending
