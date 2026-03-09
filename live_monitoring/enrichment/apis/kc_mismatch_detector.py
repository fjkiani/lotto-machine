"""
Kill Chain — Mismatch Detector

Pure functions for detecting mismatches between public market expectations
and institutional positioning. Each rule is config-driven via kill_chain_config.

Extracted from kill_chain_engine.py for modularity.
Testable in isolation — pass a KillChainReport in, get mismatches out.
"""

import logging
from typing import List

from backend.app.core import kill_chain_config as config
from .kc_models import MismatchAlert, KillChainReport

logger = logging.getLogger(__name__)


def detect_mismatches(report: KillChainReport) -> List[MismatchAlert]:
    """
    Detect mismatches using thresholds from config.
    
    Each rule checks cross-layer disagreements.
    Returns list of MismatchAlert objects.
    """
    mismatches = []
    
    # Rule 1: FedWatch hold + COT specs heavily short
    m = _check_fedwatch_cot(report)
    if m:
        mismatches.append(m)
    
    # Rule 2: Negative gamma + dark pool heavy position
    m = _check_gex_darkpool_heavy(report)
    if m:
        mismatches.append(m)
    
    # Rule 3: COT divergence (specs vs commercials)
    m = _check_cot_divergence(report)
    if m:
        mismatches.append(m)
    
    # Rule 4: High short volume + negative gamma
    m = _check_short_vol_neg_gamma(report)
    if m:
        mismatches.append(m)
    
    return mismatches


def compute_alert_level(mismatches: List[MismatchAlert]) -> str:
    """Compute overall alert level from detected mismatches."""
    if any(m.severity == "RED" for m in mismatches):
        return "RED"
    elif any(m.severity == "YELLOW" for m in mismatches):
        return "YELLOW"
    return "GREEN"


# ── Individual Mismatch Rules ───────────────────────────────────────────────

def _check_fedwatch_cot(report: KillChainReport):
    """FedWatch hold + COT specs heavily short → RED."""
    if not report.fedwatch or not report.cot:
        return None
    
    summary = str(report.fedwatch.get("summary", "")).lower()
    specs_net = report.cot.get("specs_net", 0)
    threshold = config.COT_THRESHOLDS["SPECS_HEAVY_SHORT"]
    
    if "hold" in summary and specs_net < threshold:
        return MismatchAlert(
            severity="RED",
            title="FedWatch Hold + Specs Heavy Short",
            description=(
                f"FedWatch shows 'hold' (public complacent) but specs are "
                f"NET SHORT {specs_net:,} — institutional bearish bet "
                f"not reflected in rate expectations."
            ),
            signals=["fedwatch_hold", "cot_specs_short"],
            timestamp=report.timestamp,
        )
    return None


def _check_gex_darkpool_heavy(report: KillChainReport):
    """Negative gamma + dark pool heavy position → RED."""
    if not report.gex or not report.dark_pool:
        return None
    
    neg_gamma = report.gex.get("gamma_regime") == "NEGATIVE"
    spy_pos = abs(report.dark_pool.get("spy_position_dollars", 0))
    threshold = config.DP_THRESHOLDS["HEAVY_POSITION_DOLLARS"]
    
    if neg_gamma and spy_pos > threshold:
        return MismatchAlert(
            severity="RED",
            title="Negative Gamma + Dark Pool Heavy Position",
            description=(
                f"SPX in NEGATIVE gamma (volatility amplifier) with "
                f"SPY dark pool position at ${spy_pos/1e9:.1f}B — "
                f"institutional loading while risk is high."
            ),
            signals=["gex_negative", "dark_pool_heavy"],
            timestamp=report.timestamp,
        )
    return None


def _check_cot_divergence(report: KillChainReport):
    """COT specs/commercials divergence → YELLOW."""
    if not report.cot:
        return None
    
    div = report.cot.get("divergence", {})
    threshold = config.COT_THRESHOLDS["DIVERGENCE_MAGNITUDE"]
    
    if div.get("divergent") and div.get("magnitude", 0) > threshold:
        return MismatchAlert(
            severity="YELLOW",
            title="COT Specs/Commercials Divergence",
            description=div.get("description", "Major positioning divergence detected"),
            signals=["cot_divergence"],
            timestamp=report.timestamp,
        )
    return None


def _check_short_vol_neg_gamma(report: KillChainReport):
    """High short volume + negative gamma → YELLOW."""
    if not report.dark_pool or not report.gex:
        return None
    
    short_pct = report.dark_pool.get("spy_short_vol_pct", 0)
    neg_gamma = report.gex.get("gamma_regime") == "NEGATIVE"
    threshold = config.DP_THRESHOLDS["HIGH_SHORT_VOLUME_PCT"]
    
    if short_pct > threshold and neg_gamma:
        return MismatchAlert(
            severity="YELLOW",
            title="High Short Volume + Negative Gamma",
            description=(
                f"SPY short volume at {short_pct:.1f}% (limit {threshold}%) "
                f"while dealers are in negative gamma regime."
            ),
            signals=["dark_pool_short_heavy", "gex_negative"],
            timestamp=report.timestamp,
        )
    return None
