"""
Macro / geopolitical overlay — oil, synthetic war-risk score, regime label.

Feeds Kill Chain layer_4 and canonical_state persistence.

Oil price order: MANUAL_OIL_PRICE → yfinance → Yahoo chart v8 HTTP → Alpha Vantage WTI → conservative fallback 95.0 (not peacetime 80).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def _load_repo_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        root = Path(__file__).resolve().parents[3]
        load_dotenv(root / ".env")
    except Exception:
        pass

# Conservative assumption when all feeds fail (stress / war tail risk, not "peace" 80).
_FALLBACK_WTI_STRESS = 95.0

_YAHOO_CHART_CL = "https://query1.finance.yahoo.com/v8/finance/chart/CL=F"


def _manual_oil() -> Optional[float]:
    raw = os.getenv("MANUAL_OIL_PRICE", "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        logger.warning("MANUAL_OIL_PRICE invalid: %r", raw)
        return None


def _fetch_wti_yfinance() -> Optional[float]:
    try:
        import yfinance as yf

        t = yf.Ticker("CL=F")
        li = getattr(t, "fast_info", None) or {}
        px = li.get("last_price") or li.get("regular_market_price")
        if px and float(px) > 0:
            return float(px)
        hist = t.history(period="5d")
        if hist is not None and not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception as exc:
        logger.info("WTI yfinance failed: %s", exc)
    return None


def _fetch_wti_yahoo_chart_http() -> Optional[float]:
    try:
        import requests

        r = requests.get(
            _YAHOO_CHART_CL,
            timeout=12,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; ZetaIntel/1.0; +https://example.invalid)"
            },
        )
        r.raise_for_status()
        j = r.json()
        res = (j.get("chart") or {}).get("result") or []
        if not res:
            return None
        meta = res[0].get("meta") or {}
        for key in ("regularMarketPrice", "previousClose", "chartPreviousClose"):
            v = meta.get(key)
            if v is not None and float(v) > 0:
                return float(v)
        ind = res[0].get("indicators", {}).get("quote", [{}])[0]
        closes = ind.get("close") or []
        for c in reversed(closes):
            if c is not None and float(c) > 0:
                return float(c)
    except Exception as exc:
        logger.info("WTI Yahoo chart v8 failed: %s", exc)
    return None


def _fetch_wti_alpha_vantage() -> Optional[float]:
    key = os.getenv("ALPHA_VANTAGE_API_KEY", "").strip()
    if not key:
        return None
    try:
        import requests

        url = "https://www.alphavantage.co/query"
        r = requests.get(
            url,
            params={"function": "WTI", "interval": "daily", "apikey": key},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        if "Note" in data or "Information" in data:
            logger.info("Alpha Vantage WTI rate-limit or info: %s", data.get("Note") or data.get("Information"))
            return None
        rows = data.get("data")
        if not isinstance(rows, list) or not rows:
            return None
        val = rows[0].get("value")
        if val is None:
            return None
        return float(val)
    except Exception as exc:
        logger.info("WTI Alpha Vantage failed: %s", exc)
    return None


def _fetch_wti_with_source() -> Tuple[float, str]:
    m = _manual_oil()
    if m is not None and m > 0:
        return m, "manual"

    px = _fetch_wti_yfinance()
    if px is not None and px > 0:
        return px, "yfinance"

    px = _fetch_wti_yahoo_chart_http()
    if px is not None and px > 0:
        return px, "yahoo_chart_v8"

    px = _fetch_wti_alpha_vantage()
    if px is not None and px > 0:
        return px, "alphavantage"

    logger.warning(
        "WTI: all sources failed — using stress fallback %.1f (not peacetime 80)",
        _FALLBACK_WTI_STRESS,
    )
    return _FALLBACK_WTI_STRESS, "fallback_95_stress"


def _active_geopolitical_high() -> bool:
    """Geopolitical stress from env flag or keyword scan on MACRO_GEOPOLITICAL_TEXT."""
    v = os.getenv("MACRO_GEOPOLITICAL_HIGH", "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    sample = os.getenv("MACRO_GEOPOLITICAL_TEXT", "").strip()
    if not sample:
        return False
    try:
        from live_monitoring.enrichment.trump_intelligence import (
            MarketImpact,
            TrumpCatalystType,
            TrumpKeywordEngine,
        )

        engine = TrumpKeywordEngine()
        _, ctype, impact, _, _ = engine.analyze(sample)
        if ctype == TrumpCatalystType.GEOPOLITICAL and impact in (
            MarketImpact.VERY_BEARISH,
            MarketImpact.BEARISH,
        ):
            return True
    except Exception as exc:
        logger.debug("geopolitical scan skipped: %s", exc)
    return False


def _hormuz_blocked() -> bool:
    v = os.getenv("HORMUZ_BLOCKED", "").strip().lower()
    return v in ("1", "true", "yes", "on")


class MacroOverlay:
    """War-risk and macro regime snapshot (best-effort public data)."""

    def get_current_overlay(self) -> Dict[str, Any]:
        _load_repo_dotenv()
        oil_wti, oil_source = _fetch_wti_with_source()
        oil_wti = round(oil_wti, 2)
        hormuz_blocked = _hormuz_blocked()
        try:
            cpi_forecast = float(os.getenv("MACRO_CPI_FORECAST_YOY", "3.0") or 3.0)
        except (TypeError, ValueError):
            cpi_forecast = 3.0

        war_status = 1
        war_status_components: list = ["base=1"]
        if oil_wti > 90:
            war_status += 2
            war_status_components.append(f"oil>{90}(+2)")
        if oil_wti > 100:
            war_status += 1
            war_status_components.append(f"oil>{100}(+1)")
        if hormuz_blocked:
            war_status += 3
            war_status_components.append("HORMUZ_BLOCKED(+3)")
        geo_high = _active_geopolitical_high()
        if geo_high:
            war_status += 2
            war_status_components.append("MACRO_GEOPOLITICAL_HIGH(+2)")
        war_status = min(10, war_status)

        # Transparency: flag when manual env vars are driving the veto
        manual_oil_active = oil_source == "manual"
        manual_geo_active = os.getenv("MACRO_GEOPOLITICAL_HIGH", "").strip().lower() in ("1", "true", "yes", "on")
        manual_hormuz_active = os.getenv("HORMUZ_BLOCKED", "").strip().lower() in ("1", "true", "yes", "on")

        if war_status >= 7:
            macro_regime = "WAR_PREMIUM"
        elif oil_wti > 95 and cpi_forecast > 3.5:
            macro_regime = "STAGFLATION"
        elif oil_wti < 80 and cpi_forecast < 2.5:
            macro_regime = "GOLDILOCKS"
        else:
            macro_regime = "REFLATION"

        veto_longs = war_status >= 7
        veto_reason = (
            f"War status {war_status}/10 — LONG signals vetoed ({', '.join(war_status_components)})"
            if veto_longs
            else ""
        )
        # Warn when veto is driven by manual env overrides, not live data
        manual_override_warning = ""
        if veto_longs and (manual_oil_active or manual_geo_active or manual_hormuz_active):
            flags = []
            if manual_oil_active:
                flags.append(f"MANUAL_OIL_PRICE={oil_wti}")
            if manual_geo_active:
                flags.append("MACRO_GEOPOLITICAL_HIGH=1")
            if manual_hormuz_active:
                flags.append("HORMUZ_BLOCKED=1")
            manual_override_warning = (
                f"WAR_VETO driven by manual env vars: {', '.join(flags)} — "
                "verify these are intentional before trusting veto"
            )
            logger.warning("MacroOverlay: %s", manual_override_warning)

        return {
            "oil_wti": oil_wti,
            "oil_wti_source": oil_source,
            "hormuz_blocked": hormuz_blocked,
            "war_status": war_status,
            "war_status_breakdown": ", ".join(war_status_components),
            "cpi_forecast": cpi_forecast,
            "macro_regime": macro_regime,
            "veto_longs": veto_longs,
            "veto_reason": veto_reason,
            "manual_override_warning": manual_override_warning or None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
