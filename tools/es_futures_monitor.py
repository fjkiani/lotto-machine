#!/usr/bin/env python3
"""Poll ES overnight; implied SPY ≈ last ES / 10 (rough scale).

Fetch order: Yahoo chart (several ranges) → CME JSON (if not bot-blocked) → Barchart ES*0
→ MarketWatch HTML patterns (often captcha-blocked when scripted).
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Callable, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept": "application/json,text/html;q=0.9,*/*;q=0.8"}

YAHOO_CHART_URLS = [
    "https://query1.finance.yahoo.com/v8/finance/chart/ES=F?interval=1m&range=1d",
    "https://query2.finance.yahoo.com/v8/finance/chart/ES=F?interval=5m&range=2d",
    "https://query1.finance.yahoo.com/v8/finance/chart/ES=F?interval=1d&range=5d",
]
# CME GLO-style quote JSON (may return bot-block message from many IPs).
CME_URLS = [
    "https://www.cmegroup.com/CmeWS/mvc/Quotes/Future/4258/GLO",
]
BARCHART_ES_FRONT = "https://www.barchart.com/futures/quotes/ES*0"
MARKETWATCH_ES = "https://www.marketwatch.com/investing/future/es00"


def _price_from_yahoo_chart_payload(j: dict) -> Optional[float]:
    chart = j.get("chart") or {}
    res = chart.get("result") or []
    if not res:
        return None
    r0 = res[0]
    meta = r0.get("meta") or {}
    px = meta.get("regularMarketPrice") or meta.get("previousClose")
    if px is not None:
        return float(px)
    ind = r0.get("indicators", {}).get("quote", [{}])[0]
    closes = ind.get("close") or []
    for c in reversed(closes):
        if c is not None:
            return float(c)
    return None


def fetch_es_yahoo_chart() -> Optional[float]:
    for url in YAHOO_CHART_URLS:
        try:
            r = requests.get(url, headers=HEADERS, timeout=14)
            r.raise_for_status()
            px = _price_from_yahoo_chart_payload(r.json())
            if px is not None and 1000 < px < 20000:
                return px
        except Exception as e:
            logger.debug("Yahoo chart %s failed: %s", url[:60], e)
    return None


def fetch_es_cme() -> Optional[float]:
    for url in CME_URLS:
        try:
            r = requests.get(url, headers=HEADERS, timeout=12)
            r.raise_for_status()
            text = r.text.lower()
            if "ip address is blocked" in text or "scraping" in text and "prohibited" in text:
                return None
            try:
                data = r.json()
            except json.JSONDecodeError:
                continue
            blob = json.dumps(data)

            m = re.search(r'"last"?:\s*([0-9]{3,5}(?:\.[0-9]+)?)', blob, re.I)
            if m:
                v = float(m.group(1))
                if 1000 < v < 20000:
                    return v
            m2 = re.search(r'"lastPrice"?:\s*([0-9]{3,5}(?:\.[0-9]+)?)', blob, re.I)
            if m2:
                v = float(m2.group(1))
                if 1000 < v < 20000:
                    return v
        except Exception as e:
            logger.debug("CME %s failed: %s", url, e)
    return None


def fetch_es_barchart() -> Optional[float]:
    try:
        r = requests.get(BARCHART_ES_FRONT, headers=HEADERS, timeout=14)
        r.raise_for_status()
        m = re.search(r'"lastPrice"\s*:\s*([0-9]{3,5}(?:\.[0-9]+)?)', r.text)
        if m:
            v = float(m.group(1))
            if 1000 < v < 20000:
                return v
    except Exception as e:
        logger.debug("Barchart failed: %s", e)
    return None


def fetch_es_marketwatch() -> Optional[float]:
    try:
        r = requests.get(MARKETWATCH_ES, headers=HEADERS, timeout=14)
        r.raise_for_status()
        if len(r.text) < 2000 or "captcha" in r.text.lower():
            return None
        for pat in (
            r'"Last"\s*:\s*([0-9]{3,5}(?:\.[0-9]+)?)',
            r'"last"\s*:\s*([0-9]{3,5}(?:\.[0-9]+)?)',
            r'class="[^"]*value[^"]*"[^>]*>\s*([0-9]{3,5}(?:\.[0-9]+)?)\s*<',
            r'data-quote-digits="([0-9]{3,5}(?:\.[0-9]+)?)"',
        ):
            m = re.search(pat, r.text)
            if m:
                v = float(m.group(1).replace(",", ""))
                if 1000 < v < 20000:
                    return v
    except Exception as e:
        logger.debug("MarketWatch failed: %s", e)
    return None


FETCHERS: List[Tuple[str, Callable[[], Optional[float]]]] = [
    ("yahoo_chart", fetch_es_yahoo_chart),
    ("cme", fetch_es_cme),
    ("barchart", fetch_es_barchart),
    ("marketwatch", fetch_es_marketwatch),
]


def fetch_es_price(log_source: bool = False) -> Tuple[Optional[float], str]:
    for name, fn in FETCHERS:
        px = fn()
        if px is not None:
            if log_source:
                logger.info("ES price from %s: %.2f", name, px)
            return px, name
    return None, "none"


def alert(es: float, spy_ref: float) -> str:
    implied_spy = es / 10.0
    gap = implied_spy - spy_ref
    lines = [
        f"time_et={datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}",
        f"ES={es:.2f}",
        f"implied_SPY_div10={implied_spy:.2f}",
        f"ref_SPY_close={spy_ref:.2f}",
        f"gap_vs_ref={gap:+.2f}",
    ]
    if es < 6500:
        lines.append("ALERT: ES FADING — GAP CLOSED (ES < 6500)")
    if es < 6450:
        lines.append("ALERT: PRE-MARKET BEAR SETUP CONFIRMED (ES < 6450)")
    if es >= 6550:
        lines.append("NOTE: GAP UP HOLDING — WAIT FOR ADP (ES >= 6550)")
    if es >= 6600:
        lines.append("ALERT: COUNTER-THESIS — REDUCE SIZE 50% (ES >= 6600 @ ~8:14)")
    return " | ".join(lines)


def main():
    logging.basicConfig(level=logging.INFO)
    p = argparse.ArgumentParser()
    p.add_argument("--spy-ref", type=float, default=650.0)
    p.add_argument("--interval", type=int, default=1800, help="seconds between polls")
    p.add_argument("--once", action="store_true")
    args = p.parse_args()

    while True:
        es, src = fetch_es_price(log_source=True)
        if es is None:
            ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            print(f"{ts} ES=ERROR fetch_failed sources_tried=yahoo,cme,barchart,mw", flush=True)
        else:
            ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            print(f"{ts} source={src} " + alert(es, args.spy_ref), flush=True)
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
