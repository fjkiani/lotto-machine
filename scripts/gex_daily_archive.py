#!/usr/bin/env python3
"""
GEX Daily Archive Scraper
─────────────────────────
Fetches CBOE SPY options chain daily and computes GEX.
Run via cron or scheduler: python scripts/gex_daily_archive.py

Stores to: data/external/cboe_gex/history/gex_YYYYMMDD.json
After 30+ days → can backtest GEX regime vs SPY returns.
"""
import json
import os
import urllib.request
import urllib.error
from datetime import datetime, date
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CBOE_URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/SPY.json"
HISTORY_DIR = "data/external/cboe_gex/history"
SUMMARY_FILE = "data/external/cboe_gex/gex_archive.jsonl"


def fetch_cboe_chain():
    """Fetch live CBOE SPY options chain."""
    req = urllib.request.Request(CBOE_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def compute_gex(data):
    """Compute Net GEX, max pain, call/put walls from CBOE chain.
    
    CBOE format: each option has:
      - "option": "SPY260309C00500000" (symbol string, C=call P=put, strike encoded)
      - "gamma", "delta", "open_interest" etc. as top-level fields
    """
    d = data.get("data", data)
    spot = d.get("current_price", 0)
    options = d.get("options", [])

    if not spot or not options:
        return None

    gex_by_strike = {}
    call_oi_by_strike = {}
    put_oi_by_strike = {}

    for opt in options:
        if not isinstance(opt, dict):
            continue

        # Parse option symbol: e.g. "SPY260309C00500000"
        sym = opt.get("option", "")
        if not sym or len(sym) < 15:
            continue

        # Extract type (C/P) and strike from OCC symbol
        # Format: SYMBOL + YYMMDD + C/P + strike*1000 (8 digits)
        try:
            opt_type = sym[-9]  # C or P
            strike = int(sym[-8:]) / 1000  # e.g. 00500000 → 500.0
        except (ValueError, IndexError):
            continue

        oi = opt.get("open_interest", 0) or 0
        gamma = opt.get("gamma", 0) or 0

        if strike == 0 or oi == 0 or gamma == 0:
            continue

        contract_gex = gamma * 100 * oi * spot * spot * 0.01

        if opt_type == "C":
            gex_by_strike[strike] = gex_by_strike.get(strike, 0) + contract_gex
            call_oi_by_strike[strike] = call_oi_by_strike.get(strike, 0) + oi
        elif opt_type == "P":
            gex_by_strike[strike] = gex_by_strike.get(strike, 0) - contract_gex
            put_oi_by_strike[strike] = put_oi_by_strike.get(strike, 0) + oi

    net_gex = sum(gex_by_strike.values())

    # Max pain = strike where total OI is highest
    total_oi = {}
    for s in set(list(call_oi_by_strike.keys()) + list(put_oi_by_strike.keys())):
        total_oi[s] = call_oi_by_strike.get(s, 0) + put_oi_by_strike.get(s, 0)
    max_pain = max(total_oi, key=total_oi.get) if total_oi else 0

    # Call wall = strike with highest call OI
    call_wall = max(call_oi_by_strike, key=call_oi_by_strike.get) if call_oi_by_strike else 0
    # Put wall = strike with highest put OI
    put_wall = max(put_oi_by_strike, key=put_oi_by_strike.get) if put_oi_by_strike else 0

    # Gamma flip = strike where cumulative GEX crosses zero
    sorted_strikes = sorted(gex_by_strike.keys())
    cumulative = 0
    gamma_flip = spot
    for s in sorted_strikes:
        prev = cumulative
        cumulative += gex_by_strike[s]
        if prev <= 0 and cumulative > 0:
            gamma_flip = s
            break

    return {
        "date": date.today().isoformat(),
        "timestamp": datetime.now().isoformat(),
        "spot": spot,
        "net_gex": round(net_gex, 0),
        "net_gex_billions": round(net_gex / 1e9, 2),
        "regime": "POSITIVE" if net_gex > 0 else "NEGATIVE",
        "max_pain": max_pain,
        "call_wall": call_wall,
        "put_wall": put_wall,
        "gamma_flip": gamma_flip,
        "total_contracts": len(options),
    }


def archive():
    """Fetch, compute, and save daily GEX snapshot."""
    os.makedirs(HISTORY_DIR, exist_ok=True)

    today = date.today().isoformat().replace("-", "")
    daily_file = os.path.join(HISTORY_DIR, f"gex_{today}.json")

    # Skip if already run today
    if os.path.exists(daily_file):
        logger.info(f"Already archived today: {daily_file}")
        return

    try:
        logger.info("Fetching CBOE SPY chain...")
        data = fetch_cboe_chain()
        logger.info(f"Got {len(data.get('data', {}).get('options', []))} contracts")

        result = compute_gex(data)
        if not result:
            logger.error("GEX computation failed — no data")
            return

        # Save daily snapshot
        with open(daily_file, "w") as f:
            json.dump(result, f, indent=2)
        logger.info(f"Saved: {daily_file}")

        # Append to archive JSONL
        with open(SUMMARY_FILE, "a") as f:
            f.write(json.dumps(result) + "\n")
        logger.info(f"Appended to archive: {SUMMARY_FILE}")

        # Print summary
        logger.info(
            f"GEX={result['net_gex_billions']:.2f}B ({result['regime']}) "
            f"spot={result['spot']} max_pain={result['max_pain']} "
            f"call_wall={result['call_wall']} put_wall={result['put_wall']}"
        )

        # Count archive days
        archive_files = [f for f in os.listdir(HISTORY_DIR) if f.endswith(".json")]
        logger.info(f"Archive: {len(archive_files)} days collected. Need 30+ for backtest.")

    except urllib.error.URLError as e:
        logger.error(f"CBOE fetch failed: {e}")
    except Exception as e:
        logger.exception(f"GEX archive error: {e}")


if __name__ == "__main__":
    archive()
