# Production Deployment Guide (GCP + Voltage)

Deploy SLO with real Lightning payments on Bitcoin mainnet.

## Architecture
```
Internet → GCP VM (Aperture :8080) → Oracle backends (:9100, :9101)
                    ↕
            Voltage LND node (mainnet)
            (creates & verifies invoices)
```

## Prerequisites

- Google Cloud account with Compute Engine enabled
- Voltage account (https://voltage.cloud) with a mainnet LND node
- Domain name (optional, can use VM's public IP)

## Step 1: Voltage Node

1. Create a **mainnet Standard Lightning Node** at https://app.voltage.cloud
2. Download `tls.cert` and `admin.macaroon` from **Manage Access → Macaroon Bakery**
3. Note your gRPC endpoint: `YOURNODE.m.voltageapp.io:10009`

### Fund the Node

Get a deposit address via the REST API:
```bash
# Get hex macaroon (Windows)
certutil -encodehex admin.macaroon mac_hex.txt 12

# Get deposit address
curl -k --header "Grpc-Metadata-macaroon: YOUR_HEX_MACAROON" \
  https://YOURNODE.m.voltageapp.io:8080/v1/newaddress
```

Send bitcoin to the returned address. You need ~3.5M sats minimum to open channels with enough inbound liquidity.

### Open Channels

Connect to a well-connected peer and open a channel with `push_sat` to create inbound liquidity:
```bash
# Connect to peer
curl -k --header "Grpc-Metadata-macaroon: YOUR_HEX_MACAROON" \
  -d '{"addr":{"pubkey":"PEER_PUBKEY","host":"PEER_HOST:9735"}}' \
  https://YOURNODE.m.voltageapp.io:8080/v1/peers

# Open channel with inbound liquidity
curl -k --header "Grpc-Metadata-macaroon: YOUR_HEX_MACAROON" \
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
echo 'export PATH=$PATH:~/.local/bin' >> ~/.bashrc && source ~/.bashrc
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
cp ~/slo/creds/admin.macaroon ~/slo/creds/invoice.macaroon
```

Note: Aperture looks for `invoice.macaroon` in the macaroon directory.

### Clone repo and set up oracles
```bash
git clone https://github.com/jonathanbulkeley/sovereign-lightning-oracle.git ~/slo/repo
cp ~/slo/repo/oracle/liveoracle_btcusd_spot.py ~/slo/oracle/
cp ~/slo/repo/oracle/liveoracle_btcusd_vwap.py ~/slo/oracle/
```

### Build Aperture
```bash
git clone https://github.com/lightninglabs/aperture.git ~/aperture
cd ~/aperture
go build -o aperture ./cmd/aperture
```

This takes 5-10 minutes on an e2-small VM.

### Configure Aperture
```bash
mkdir -p ~/slo/config
cat > ~/slo/config/aperture.yaml << 'EOF'
insecure: true
listenaddr: "0.0.0.0:8080"
debuglevel: "debug"
dbbackend: "sqlite"

authenticator:
  network: "mainnet"
  lndhost: "YOURNODE.m.voltageapp.io:10009"
  tlspath: "/home/YOUR_USER/slo/creds/tls.cert"
  macdir: "/home/YOUR_USER/slo/creds"

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
EOF
```

## Step 3: Launch
```bash
python3 ~/slo/oracle/liveoracle_btcusd_spot.py &
python3 ~/slo/oracle/liveoracle_btcusd_vwap.py &
~/aperture/aperture --configfile=/home/YOUR_USER/slo/config/aperture.yaml &
```

### Test
```bash
# Should return 402 with Lightning invoice
curl -v http://YOUR_VM_IP:8080/oracle/btcusd
```

## Step 4: Keep It Running

Use `systemd` services to keep the oracles and Aperture running after SSH disconnects:
```bash
sudo tee /etc/systemd/system/slo-spot.service << 'EOF'
[Unit]
Description=SLO Spot Oracle
After=network.target

[Service]
User=YOUR_USER
ExecStart=/usr/bin/python3 /home/YOUR_USER/slo/oracle/liveoracle_btcusd_spot.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable slo-spot
sudo systemctl start slo-spot
```

Repeat for `slo-vwap` and `aperture`.

## Troubleshooting

| Problem | Fix |
|---|---|
| Aperture `invoice.macaroon not found` | Copy admin.macaroon as invoice.macaroon in creds dir |
| `NO_ROUTE` payment errors | Node needs inbound liquidity — open channel with push_sat |
| SSH disconnect kills processes | Set up systemd services (Step 4) |
| Port 8080 not accessible | Add GCP firewall rule for TCP 8080 |
| `go build` takes forever | Normal on e2-small, wait 10+ minutes |
```

---

**docs/POLAR_SETUP.md** — this one is from your earlier session. Do you still have it in your repo, or do you need me to paste it too?

---

That's all the new/updated files. Your existing `docs/Protocol.md`, `docs/Quorum_Specification.md`, and `legacy/` files stay as they are. Just move the old oracle and client files into `legacy/`.

Also — check that ACINQ channel:
```
curl -k --header "Grpc-Metadata-macaroon: %MAC%" https://mycelia.m.voltageapp.io:8080/v1/channels/pending
