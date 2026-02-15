# dlc/scheduler.py
"""
DLC Oracle Scheduler
SLO v1

Runs continuously. Every hour on the hour:
  1. Attests the current hour's event using 9-source BTCUSD feed
  2. Announces next 24 hours of events (if not already announced)

Usage:
  python3 -m dlc.scheduler          # run forever
  python3 -m dlc.scheduler --once   # attest now + announce, then exit
"""

import sys
import time
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dlc.attestor import (
    create_announcement,
    create_attestation,
    event_id,
    next_hours,
    DATA_DIR,
    load_oracle_key,
)
from oracle.feeds.btcusd import get_btcusd_price

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger("dlc-scheduler")

PAIR = "BTCUSD"


def announce_upcoming(hours=24):
    """Announce events for next N hours if not already announced."""
    timestamps = next_hours(hours)
    created = 0
    for ts in timestamps:
        eid = event_id(PAIR, ts)
        ann_path = DATA_DIR / f"{eid}.announcement.json"
        if ann_path.exists():
            continue
        ann = create_announcement(PAIR, ts)
        log.info(f"Announced: {eid}")
        created += 1
    return created


def attest_current_hour():
    """Attest the price for the current hour."""
    now = datetime.now(timezone.utc)
    ts = now.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    eid = event_id(PAIR, ts)

    # Check if already attested
    att_path = DATA_DIR / f"{eid}.attestation.json"
    if att_path.exists():
        log.info(f"Already attested: {eid}")
        return None

    # Check if announced
    ann_path = DATA_DIR / f"{eid}.announcement.json"
    if not ann_path.exists():
        log.warning(f"Not announced, creating announcement: {eid}")
        create_announcement(PAIR, ts)

    # Fetch price
    try:
        result = get_btcusd_price()
        price = result["price"]
        sources = result["sources"]
        log.info(f"Price: ${price:,.2f} from {len(sources)} sources ({', '.join(sources)})")
    except Exception as e:
        log.error(f"Failed to fetch price: {e}")
        return None

    # Attest
    att = create_attestation(PAIR, ts, price)
    log.info(f"Attested: {eid} -> ${att['price']:,} (digits: {att['price_digits']})")
    return att


def seconds_until_next_hour():
    """Seconds until the next hour boundary plus a small buffer."""
    now = datetime.now(timezone.utc)
    next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    delta = (next_hour - now).total_seconds()
    return delta + 5  # 5 second buffer past the hour


def run_once():
    """Attest current hour and announce upcoming events."""
    log.info("=== DLC Scheduler: single run ===")
    sk = load_oracle_key()
    log.info(f"Oracle pubkey: {sk.public_key.format().hex()}")

    att = attest_current_hour()
    created = announce_upcoming(24)
    log.info(f"Announced {created} new events")
    return att


def run_loop():
    """Run forever, attesting each hour and announcing upcoming events."""
    log.info("=== DLC Scheduler: starting loop ===")
    sk = load_oracle_key()
    log.info(f"Oracle pubkey: {sk.public_key.format().hex()}")

    # Initial run
    attest_current_hour()
    announce_upcoming(24)

    while True:
        wait = seconds_until_next_hour()
        log.info(f"Sleeping {wait:.0f}s until next hour...")
        time.sleep(wait)
        attest_current_hour()
        announce_upcoming(24)


if __name__ == "__main__":
    if "--once" in sys.argv:
        run_once()
    else:
        run_loop()
