# Production Deployment Guide (GCP + Voltage)

Deploy SLO with real Lightning payments on Bitcoin mainnet.

## Architecture
```
Internet → L402 Proxy (:8080) → Oracle backends (:9100-9107)
                 ↕                     ↕
          Voltage LND node       DLC Attestor (:9104)
          (creates & verifies
           invoices via REST)

Internet → x402 Proxy (:8402) → Oracle backends (:9100-9107)
                 ↕
          Base RPC (USDC verification)
```

The L402 proxy is a custom Go reverse proxy that creates invoices via the LND REST API, mints L402 macaroons, and verifies payment tokens. The x402 proxy is a Python FastAPI server that verifies USDC payments on Base, re-signs attestations with Ed25519, and handles optimistic delivery. Both proxies route to the same oracle backends. All payment logic lives in the proxies; oracle backends are pure data servers.

## Port Assignments

| Port | Service |
|---|---|
| 8080 | L402 proxy (public-facing, Lightning) |
| 8402 | x402 proxy (public-facing, USDC on Base) |
| 9100 | BTCUSD spot oracle |
| 9101 | BTCUSD VWAP oracle |
| 9102 | ETHUSD spot oracle |
| 9103 | EURUSD spot oracle |
| 9104 | DLC attestor |
| 9105 | XAU/USD gold oracle |
| 9106 | BTC/EUR cross-rate oracle |
| 9107 | SOL/USD spot oracle |

## Prerequisites

- Google Cloud account with Compute Engine enabled
- Voltage account (https://voltage.cloud) with a mainnet LND node
- Go 1.21+ (for building the L402 proxy)
- Python 3.10+ (for oracle backends)

## Step 1: Voltage Node

1. Create a **mainnet Standard Lightning Node** at https://app.voltage.cloud
2. Download `tls.cert` and `admin.macaroon` from **Manage Access → Macaroon Bakery**
3. Note your REST endpoint: `YOURNODE.m.voltageapp.io:8080`

### Fund the Node

Get a deposit address via the REST API:
```bash
# Get hex macaroon (Linux)
xxd -p admin.macaroon | tr -d '\n' > mac_hex.txt

# Get deposit address
curl -k --header "Grpc-Metadata-macaroon: $(cat mac_hex.txt)" \
  https://YOURNODE.m.voltageapp.io:8080/v1/newaddress
```

Send bitcoin to the returned address. You need ~3.5M sats minimum to open channels with enough inbound liquidity.

### Open Channels

Connect to a well-connected peer and open a channel with `push_sat` to create inbound liquidity:
```bash
# Connect to peer
curl -k --header "Grpc-Metadata-macaroon: $(cat mac_hex.txt)" \
  -d '{"addr":{"pubkey":"PEER_PUBKEY","host":"PEER_HOST:9735"}}' \
  https://YOURNODE.m.voltageapp.io:8080/v1/peers

# Open channel with inbound liquidity
curl -k --header "Grpc-Metadata-macaroon: $(cat mac_hex.txt)" \
  -d '{"node_pubkey_string":"PEER_PUBKEY","local_funding_amount":"1000000","push_sat":"500000"}' \
  https://YOURNODE.m.voltageapp.io:8080/v1/channels
```

Wait for 3 confirmations (~30 min) before the channel is active.

## Step 2: GCP VM

1. Create an **e2-small** VM in Compute Engine (Ubuntu 24.04, 20GB disk)
2. Enable HTTP/HTTPS firewall rules
3. Add a custom firewall rule for port 8080 (TCP, source 0.0.0.0/0)

### Install dependencies
```bash
sudo apt update
sudo apt install -y python3 python3-pip golang-go git nano
pip3 install fastapi uvicorn ecdsa requests --break-system-packages
```

### Upload Voltage credentials
```bash
# From your local machine
gcloud compute scp tls.cert slo-oracle:/tmp/tls.cert
gcloud compute scp admin.macaroon slo-oracle:/tmp/admin.macaroon

# On the VM
mkdir -p ~/slo/creds
cp /tmp/tls.cert ~/slo/creds/
cp /tmp/admin.macaroon ~/slo/creds/
```

### Clone repo and set up oracles
```bash
git clone https://github.com/jonathanbulkeley/sovereign-lightning-oracle.git ~/slo/repo
cp ~/slo/repo/oracle/feeds/*.py ~/slo/oracle/feeds/
cp ~/slo/repo/oracle/liveoracle_*.py ~/slo/oracle/
```

## Step 3: Build the L402 Proxy

The L402 proxy is a single Go file that handles all payment logic:
```bash
mkdir -p ~/slo-l402-proxy
cp ~/slo/repo/l402-proxy/main.go ~/slo-l402-proxy/
cp ~/slo/repo/l402-proxy/go.mod ~/slo-l402-proxy/
cp ~/slo/repo/l402-proxy/go.sum ~/slo-l402-proxy/
cd ~/slo-l402-proxy
go build -o slo-l402-proxy .
```

### Configure

Edit `main.go` to set your LND REST endpoint and credential paths:
```go
var (
    lndREST     = "https://YOURNODE.m.voltageapp.io:8080"
    macaroonHex string
    rootKey     []byte
)
```

And update the macaroon and root key paths in `main()`:
```go
macData, err := os.ReadFile("/home/YOUR_USER/slo/creds/admin.macaroon")
rootKeyPath := "/home/YOUR_USER/slo/creds/l402_root_key.bin"
```

The root key is generated automatically on first run and persisted to disk. This key is used to mint and verify L402 macaroons — keep it safe.

### Route Configuration

Routes are defined as a Go map. Each route maps a URL path to a backend port and price in sats:
```go
var routes = map[string]Route{
    "/oracle/btcusd":      {Backend: "http://127.0.0.1:9100", Price: 10},
    "/oracle/btcusd/vwap": {Backend: "http://127.0.0.1:9101", Price: 20},
    "/oracle/ethusd":      {Backend: "http://127.0.0.1:9102", Price: 10},
    "/oracle/eurusd":      {Backend: "http://127.0.0.1:9103", Price: 10},
    "/oracle/xauusd":      {Backend: "http://127.0.0.1:9105", Price: 10},
    "/oracle/btceur":      {Backend: "http://127.0.0.1:9106", Price: 10},
    "/oracle/solusd":      {Backend: "http://127.0.0.1:9107", Price: 10},
}
```

Free (ungated) routes are defined separately:
```go
var freeRoutes = map[string]string{
    "/health":                   "http://127.0.0.1:9100",
    "/oracle/status":            "http://127.0.0.1:9100",
    "/dlc/oracle/pubkey":        "http://127.0.0.1:9104",
    "/dlc/oracle/announcements": "http://127.0.0.1:9104",
    "/dlc/oracle/status":        "http://127.0.0.1:9104",
}
```

To add a new oracle: add a route entry, rebuild with `go build`, and restart.

## Step 4: Launch

Start all oracle backends, then the proxy:
```bash
# Oracle backends
python3 ~/slo/oracle/liveoracle_btcusd_spot.py &
python3 ~/slo/oracle/liveoracle_btcusd_vwap.py &
python3 ~/slo/oracle/liveoracle_ethusd_spot.py &
python3 ~/slo/oracle/liveoracle_eurusd_spot.py &
python3 ~/slo/oracle/liveoracle_xauusd_spot.py &
python3 ~/slo/oracle/liveoracle_btceur_spot.py &
python3 ~/slo/oracle/liveoracle_solusd_spot.py &

# DLC attestor
python3 ~/slo/dlc/server.py &

# L402 proxy (public-facing)
~/slo-l402-proxy/slo-l402-proxy &
```

### Test
```bash
# Should return 402 with Lightning invoice
curl -v http://YOUR_VM_IP:8080/oracle/btcusd

# Free endpoints should return data directly
curl http://YOUR_VM_IP:8080/health
curl http://YOUR_VM_IP:8080/dlc/oracle/pubkey
```

## Step 5: Keep It Running

Use `systemd` services to keep everything running after SSH disconnects and across reboots.

### Oracle service template
```bash
sudo tee /etc/systemd/system/slo-btcusd-spot.service << 'EOF'
[Unit]
Description=SLO BTCUSD Spot Oracle
After=network.target

[Service]
User=YOUR_USER
WorkingDirectory=/home/YOUR_USER/slo
ExecStart=/usr/bin/python3 /home/YOUR_USER/slo/oracle/liveoracle_btcusd_spot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable slo-btcusd-spot
sudo systemctl start slo-btcusd-spot
```

Create similar service files for each oracle backend (vwap, ethusd, eurusd, xauusd, btceur, solusd, dlc).

### L402 proxy service
```bash
sudo tee /etc/systemd/system/slo-l402-proxy.service << 'EOF'
[Unit]
Description=SLO L402 Proxy
After=network.target

[Service]
User=YOUR_USER
ExecStart=/home/YOUR_USER/slo-l402-proxy/slo-l402-proxy
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable slo-l402-proxy
sudo systemctl start slo-l402-proxy
```

## Troubleshooting

| Problem | Fix |
|---|---|
| L402 proxy `Failed to read macaroon` | Check macaroon path in main.go matches actual location |
| `NO_ROUTE` payment errors | Node needs inbound liquidity — open channel with push_sat |
| SSH disconnect kills processes | Set up systemd services (Step 5) |
| Port 8080 not accessible | Add GCP firewall rule for TCP 8080 |
| Oracle returning 500 | Exchange API may be down; check oracle logs |
| Proxy not forwarding | Verify oracle backend is running on expected port |
| `go build` fails | Run `go mod tidy` then rebuild |

## Step 6: Deploy x402 Proxy (SHO)

### Install dependencies
```bash
pip install --break-system-packages PyNaCl httpx
```

### Configure
Set your USDC receiving address on Base:
```bash
export SHO_PAYMENT_ADDRESS=0xYourUSDCAddressOnBase
```

### Test manually
```bash
python3 ~/slo/repo/sho/x402_proxy.py &
curl http://127.0.0.1:8402/sho/info
kill %1
```

### Create systemd service
```bash
sudo tee /etc/systemd/system/sho-x402-proxy.service << 'EOF'
[Unit]
Description=SHO x402 Proxy
After=network.target

[Service]
Type=simple
User=YOUR_USER
Environment=SHO_PAYMENT_ADDRESS=0xYourUSDCAddressOnBase
ExecStart=/usr/bin/python3 /home/YOUR_USER/slo/repo/sho/x402_proxy.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable sho-x402-proxy
sudo systemctl start sho-x402-proxy
```

### Open firewall
```bash
gcloud compute firewall-rules create allow-sho-x402 \
  --allow tcp:8402 --source-ranges 0.0.0.0/0 \
  --description "SHO x402 proxy"
```

### Ed25519 key
The proxy generates an Ed25519 signing key on first run at `sho/keys/sho_ed25519.key`. **Back this up.** If lost, you must generate a new key and redo the cross-certification. The key is gitignored.

## Adding a New Oracle

1. Create the feed in `oracle/feeds/newpair.py` (fetch prices, compute median)
2. Create the oracle server in `oracle/liveoracle_newpair_spot.py` (FastAPI, sign canonical message)
3. Choose the next available port (e.g., 9108)
4. Add the route to L402 proxy `main.go`: `"/oracle/newpair": {Backend: "http://127.0.0.1:9108", Price: 10},`
5. Add the route to x402 proxy `sho/x402_proxy.py` ROUTES dict: `"/oracle/newpair": {"backend": "http://127.0.0.1:9108/oracle/newpair", "price_usd": 0.001},`
6. Rebuild L402 proxy: `cd ~/slo-l402-proxy && go build -o slo-l402-proxy .`
7. Start the oracle, restart both proxies
8. Test: `curl -v http://YOUR_VM_IP:8080/oracle/newpair` (L402) and `curl http://YOUR_VM_IP:8402/oracle/newpair` (x402)
