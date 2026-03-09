"""
Kill Chain Engine — Shadow Intelligence Orchestrator

Combines 5 verified live data layers to detect mismatches between
public market expectations and institutional positioning.

Layers:
  1. FedWatch  → Rate probability expectations (pyfedwatch)
  2. Dark Pool → Institutional dark position & short volume (Stockgrid.io)
  3. COT       → CFTC futures positioning: specs vs commercials
  4. GEX       → Gamma exposure from CBOE options (dealer hedging pressure)
  5. 13F       → Quarterly institutional holdings (SEC EDGAR)

The kill chain fires when signals align:
  - FedWatch holds steady (public complacent)
  - Dark pool shows heavy accumulation/distribution
  - COT shows specs/commercials divergence
  - GEX shows negative gamma (dealers amplify moves)
  = INSTITUTIONAL POSITIONING MISMATCH → Shadow Alert

This is the anti-Bloomberg: exposes what they sell for $25K/yr, for free.

Architecture:
  kc_models.py            → MismatchAlert, KillChainReport dataclasses
  kc_layer_registry.py    → Import guards, client init, all 5 fetchers
  kc_mismatch_detector.py → 4 config-driven mismatch rules (pure functions)
  kill_chain_engine.py    → This file: orchestrator (scan, narrative, quick methods)
"""
import logging
import time
from typing import Optional, List
from datetime import datetime

from .kc_models import MismatchAlert, KillChainReport
from .kc_layer_registry import LayerRegistry
from .kc_mismatch_detector import detect_mismatches, compute_alert_level

logger = logging.getLogger(__name__)


class KillChainEngine:
    """
    Shadow Intelligence Orchestrator.
    
    Pulls all data layers independently, detects mismatches,
    and generates unified narratives. Each layer is optional —
    the engine works even if some sources fail.
    """

    def __init__(self, diffbot_token: Optional[str] = None):
        """Initialize the layer registry with all available clients."""
        self.registry = LayerRegistry(diffbot_token=diffbot_token)

    # ── Full Scan ────────────────────────────────────────────────────────

    def run_full_scan(self) -> KillChainReport:
        """
        Pull all data layers and generate a complete intelligence report.
        """
        scan_start = time.time()
        report = KillChainReport(timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        # Fetch all layers via registry
        fetchers = self.registry.get_all_fetchers()
        
        for name, fetcher in fetchers.items():
            data = fetcher()  # Decorator handles availability and errors
            setattr(report, name, data)
            if data:
                report.layers_active += 1
            else:
                report.layers_failed.append(name)
        
        # Detect mismatches using config-driven pure functions
        report.mismatches = detect_mismatches(report)
        report.alert_level = compute_alert_level(report.mismatches)
        report.narrative = self._generate_narrative(report)
        
        elapsed = time.time() - scan_start
        logger.info(f"🐺 Kill chain scan complete: {report.layers_active}/5 layers, "
                     f"alert={report.alert_level}, {len(report.mismatches)} mismatches, "
                     f"{elapsed:.1f}s")
        return report

    # ── Narrative Generation ─────────────────────────────────────────────

    def _generate_narrative(self, report: KillChainReport) -> str:
        """Generate unified shadow narrative combining all layers."""
        parts = []
        
        parts.append(f"🐺 KILL CHAIN REPORT — {report.timestamp}")
        parts.append(f"Alert: {report.alert_level} | Layers: {report.layers_active}/5 active")
        parts.append("")
        
        # Layer narratives
        if report.fedwatch:
            parts.append(f"📊 FED: {report.fedwatch.get('narrative', 'N/A')}")
        if report.dark_pool:
            parts.append(f"🏴 DARK: {report.dark_pool.get('narrative', 'N/A')}")
        if report.cot:
            parts.append(f"📋 COT: {report.cot.get('narrative', 'N/A')}")
        if report.gex:
            parts.append(f"⚡ GEX: {report.gex.get('narrative', 'N/A')}")
        if report.sec_13f:
            parts.append(f"🏛️ 13F: {report.sec_13f.get('narrative', 'N/A')}")
        
        # Mismatches
        if report.mismatches:
            parts.append("")
            parts.append(f"⚠️ MISMATCHES DETECTED ({len(report.mismatches)}):")
            for m in report.mismatches:
                emoji = "🔴" if m.severity == "RED" else "🟡"
                parts.append(f"  {emoji} {m.title}: {m.description}")
        else:
            parts.append("")
            parts.append("✅ No significant mismatches detected")
        
        return "\n".join(parts)

    # ── Quick Methods ────────────────────────────────────────────────────

    def get_alert_level(self) -> str:
        """Quick check — just run scan and return alert level."""
        report = self.run_full_scan()
        return report.alert_level

    def get_shadow_narrative(self) -> str:
        """Get the full shadow narrative for SavageAgents."""
        report = self.run_full_scan()
        return report.narrative


# ─── Standalone Test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    
    print("=" * 70)
    print("🐺 KILL CHAIN ENGINE — Full Scan")
    print("=" * 70)
    
    engine = KillChainEngine()
    report = engine.run_full_scan()
    
    print(f"\n{'='*70}")
    print(report.narrative)
    print(f"{'='*70}")
    
    if report.layers_failed:
        print(f"\n⚠️ Failed layers: {', '.join(report.layers_failed)}")
    
    # Print raw data summary
    print(f"\n--- Raw Layer Data ---")
    for layer in ["fedwatch", "dark_pool", "cot", "gex", "sec_13f"]:
        data = getattr(report, layer, None)
        if data:
            # Print without narrative (already shown above)
            filtered = {k: v for k, v in data.items() if k != "narrative"}
            print(f"\n{layer}:")
            print(json.dumps(filtered, indent=2, default=str))
