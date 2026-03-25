"""
kc_mismatch_lite.py — Lightweight Kill Chain mismatch detector.

Same logic as kc_mismatch_detector.py but operates on pre-fetched
shared dicts instead of a KillChainReport object. This avoids
creating a full KillChainEngine + LayerRegistry (which duplicates
GEX/COT/FedWatch calls and causes OOM).

Called from core.build_kill_chain() with shared data.
"""
import logging
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


class LiteMismatch:
    """Minimal mismatch record — no dataclass import needed."""
    __slots__ = ('severity', 'title', 'description')
    def __init__(self, severity: str, title: str, description: str):
        self.severity = severity
        self.title = title
        self.description = description


# ── Thresholds (same as kill_chain_config) ───────────────────────────────────
SPECS_HEAVY_SHORT = -100_000
HEAVY_POSITION_DOLLARS = 1_000_000_000
DIVERGENCE_MAGNITUDE = 50_000
HIGH_SHORT_VOLUME_PCT = 45.0


def detect_mismatches_from_shared(
    gex: dict, cot: dict, fedwatch: dict, darkpool: Optional[dict] = None
) -> List[LiteMismatch]:
    """Detect cross-layer mismatches from pre-fetched shared data."""
    mismatches: List[LiteMismatch] = []

    # Rule 1: FedWatch hold + COT specs heavily short → RED
    if fedwatch and not fedwatch.get('error') and cot and not cot.get('error'):
        rate_path = fedwatch.get('rate_path', {})
        # "hold" = next meeting p_hold > 60%
        p_hold = rate_path.get('may_p_hold', 0)
        specs_net = cot.get('specs_net', 0)
        if p_hold > 60 and specs_net < SPECS_HEAVY_SHORT:
            mismatches.append(LiteMismatch(
                severity='RED',
                title='FedWatch Hold + Specs Heavy Short',
                description=(
                    f"FedWatch shows hold probability {p_hold:.0f}% (public complacent) "
                    f"but specs are NET SHORT {specs_net:,} — institutional bearish bet "
                    f"not reflected in rate expectations."
                ),
            ))

    # Rule 2: COT specs/commercials divergence → YELLOW
    if cot and not cot.get('error'):
        if cot.get('divergent'):
            mismatches.append(LiteMismatch(
                severity='YELLOW',
                title='COT Specs/Commercials Divergence',
                description=cot.get('description', 'Major positioning divergence detected'),
            ))

    # Rule 3: Negative gamma → YELLOW (amplifies moves)
    if gex and not gex.get('error'):
        if gex.get('gamma_regime') == 'NEGATIVE':
            total = gex.get('total_gex', 0)
            mismatches.append(LiteMismatch(
                severity='YELLOW',
                title='Negative Gamma Regime',
                description=(
                    f"SPY in NEGATIVE gamma (total GEX: {total/1e6:.1f}M). "
                    f"Dealer hedging amplifies moves in BOTH directions."
                ),
            ))

    return mismatches


def compute_alert_level(mismatches: List[LiteMismatch]) -> str:
    """Compute overall alert level from detected mismatches."""
    if any(m.severity == 'RED' for m in mismatches):
        return 'RED'
    if any(m.severity == 'YELLOW' for m in mismatches):
        return 'YELLOW'
    return 'GREEN'


def generate_narrative(
    alert_level: str,
    mismatches: List[LiteMismatch],
    gex: dict, cot: dict, fedwatch: dict,
) -> str:
    """Generate unified kill chain narrative from pre-fetched data."""
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    layers_active = sum(1 for d in [gex, cot, fedwatch] if d and not d.get('error'))

    parts = [
        f"🐺 KILL CHAIN REPORT — {now}",
        f"Alert: {alert_level} | Layers: {layers_active + 2}/5 active",
        "",
    ]

    # FedWatch summary
    if fedwatch and not fedwatch.get('error'):
        rp = fedwatch.get('rate_path', {})
        rate = rp.get('current_rate', '?')
        rng = rp.get('current_range', [])
        parts.append(f"📊 FED: Fed Funds Rate: {rate}% (range: {rng[0]}-{rng[1]}%)" if len(rng) == 2 else f"📊 FED: Rate {rate}%")

    # COT summary
    if cot and not cot.get('error'):
        parts.append(f"📋 COT: Specs NET {cot.get('specs_net', 0):,} | {cot.get('description', '')}")

    # GEX summary
    if gex and not gex.get('error'):
        total = gex.get('total_gex', 0)
        regime = gex.get('gamma_regime', '?')
        parts.append(f"⚡ GEX: {regime} regime, total GEX {total/1e6:.1f}M")

    # Mismatches
    if mismatches:
        parts.append("")
        parts.append(f"⚠️ MISMATCHES DETECTED ({len(mismatches)}):")
        for m in mismatches:
            emoji = "🔴" if m.severity == "RED" else "🟡"
            parts.append(f"  {emoji} {m.title}: {m.description}")
    else:
        parts.append("")
        parts.append("✅ No significant mismatches detected")

    return "\n".join(parts)


def generate_signals_from_shared(gex: dict, cot: dict) -> List[dict]:
    """Generate typed Kill Chain signals from pre-fetched shared dictionaries."""
    signals = []
    today_str = datetime.utcnow().strftime('%Y-%m-%d')

    if cot and not cot.get('error'):
        es_specs = cot.get('specs_net', 0)
        comms = cot.get('comm_net', 0)
        divergent = cot.get('divergent', False)

        if divergent and es_specs < -100_000 and comms > 50_000:
            signals.append({
                "id": f"cot-extreme-div-{today_str}",
                "source": "COT",
                "type": "BULLISH",
                "strength": "HIGH",
                "headline": f"Specs net short {es_specs:,} contracts",
                "detail": "Major smart-money divergence setup. Retail is trapped short.",
                "data": {"spec_net": es_specs, "comm_net": comms, "side": "SHORT"}
            })
        elif divergent and es_specs < -50_000 and comms > 25_000:
            signals.append({
                "id": f"cot-mod-div-{today_str}",
                "source": "COT",
                "type": "BULLISH",
                "strength": "MEDIUM",
                "headline": f"Specs net short {es_specs:,} contracts",
                "detail": "Mild divergence. Commercials buying into spec shorts.",
                "data": {"spec_net": es_specs, "comm_net": comms, "side": "SHORT"}
            })
        elif es_specs < -50_000 and not divergent:
            signals.append({
                "id": f"cot-spec-short-{today_str}",
                "source": "COT",
                "type": "BEARISH",
                "strength": "MEDIUM",
                "headline": f"Specs net short {es_specs:,} contracts",
                "detail": "Spec trap loaded — squeeze fuel if market rallies, but currently bearish.",
                "data": {"spec_net": es_specs, "side": "SHORT"}
            })

    if gex and not gex.get('error'):
        regime = gex.get('gamma_regime', '')
        total_gex = gex.get('total_gex', 0)
        current_spot = gex.get('spot_price', 0)
        
        if "NEGATIVE" in regime and abs(total_gex) > 1e6:
            signals.append({
                "id": f"gex-gravity-{today_str}",
                "source": "GEX",
                "type": "BEARISH",
                "strength": "HIGH",
                "headline": f"NEGATIVE gamma · spot ${current_spot:.2f}",
                "detail": "Gravitational pull downwards. Dealers short options, amplifying moves.",
                "data": {"spot": current_spot, "total_gex": round(total_gex/1e6, 2)}
            })
        elif "POSITIVE" in regime:
            signals.append({
                "id": f"gex-suppression-{today_str}",
                "source": "GEX",
                "type": "BULLISH",
                "strength": "LOW",
                "headline": "POSITIVE gamma regime",
                "detail": "Volatility suppressed. Dealers buying dips and selling rips.",
                "data": {"spot": current_spot, "total_gex": round(total_gex/1e6, 2)}
            })

    return signals

