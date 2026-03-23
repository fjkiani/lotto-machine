"""
Macro Regime Detector — Stagflation Composite Signal

Classifies current macroeconomic environment from FRED data:
  STAGFLATION         — high inflation + weakening growth
  INFLATIONARY_BOOM   — high inflation + strong growth
  GOLDILOCKS          — low inflation + moderate growth
  DEFLATIONARY_BUST   — falling inflation + contracting growth
  RECESSION           — rising unemployment + negative GDP
  NEUTRAL             — no clear signal

Kill Chain regime modifiers:
  STAGFLATION       → reduce all LONG confidence by 15%, add warning
  DEFLATIONARY_BUST → reduce all SHORT confidence by 10%
  GOLDILOCKS        → no modifier
"""
import os
import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class MacroRegimeDetector:
    """
    Detects macroeconomic regime from live FRED data + Cleveland Fed nowcast.
    
    Scoring:
      inflation_score = f(core_pce_yoy, cpi_yoy_trend, cleveland_nowcast)
      growth_score = f(nfp_3mo_avg, gdp_qoq, unemployment_trend)
      regime = matrix(inflation_score, growth_score)
    """

    FRED_BASE = "https://api.stlouisfed.org/fred"

    # Regime classification matrix
    REGIMES = [
        'STAGFLATION',
        'INFLATIONARY_BOOM',
        'GOLDILOCKS',
        'DEFLATIONARY_BUST',
        'RECESSION',
        'NEUTRAL',
    ]

    # Kill Chain modifiers per regime
    REGIME_MODIFIERS = {
        'STAGFLATION':       {'long_penalty': -15, 'short_penalty': 0,   'warning': 'STAGFLATION regime: weak growth + high inflation'},
        'INFLATIONARY_BOOM': {'long_penalty': -5,  'short_penalty': -10, 'warning': 'Inflationary boom: hot economy may trigger hawkish Fed'},
        'GOLDILOCKS':        {'long_penalty': 0,   'short_penalty': 0,   'warning': None},
        'DEFLATIONARY_BUST': {'long_penalty': 0,   'short_penalty': -10, 'warning': 'Deflationary bust: falling prices, watch for policy pivot'},
        'RECESSION':         {'long_penalty': -20, 'short_penalty': 0,   'warning': 'RECESSION regime: contracting economy'},
        'NEUTRAL':           {'long_penalty': 0,   'short_penalty': 0,   'warning': None},
    }

    def __init__(self, fred_api_key: Optional[str] = None):
        self.api_key = fred_api_key or os.getenv("FRED_API_KEY", "")
        if not self.api_key:
            logger.warning("⚠️ FRED_API_KEY not set — MacroRegimeDetector degraded")
        logger.info("📊 MacroRegimeDetector initialized")

    def get_regime(self) -> Dict[str, Any]:
        """
        Compute current macroeconomic regime from live data.
        
        Returns:
            {
                'regime': 'STAGFLATION',
                'inflation_score': 0.75,
                'growth_score': -0.4,
                'components': {...},
                'modifier': {'long_penalty': -15, ...},
            }
        """
        components = {}

        # ── Inflation Score ──
        # Core PCE YoY (gold standard for Fed)
        core_pce = self._get_fred_latest('PCEPILFE', limit=13)
        core_pce_yoy = None
        if core_pce and len(core_pce) >= 13:
            core_pce_yoy = ((core_pce[0] - core_pce[12]) / core_pce[12]) * 100
            components['core_pce_yoy'] = round(core_pce_yoy, 2)

        # CPI YoY
        cpi = self._get_fred_latest('CPIAUCSL', limit=13)
        cpi_yoy = None
        if cpi and len(cpi) >= 13:
            cpi_yoy = ((cpi[0] - cpi[12]) / cpi[12]) * 100
            components['cpi_yoy'] = round(cpi_yoy, 2)

        # Cleveland Fed nowcast (if available)
        nowcast_cpi = None
        try:
            from live_monitoring.enrichment.apis.cleveland_fed_nowcast import ClevelandFedNowcast
            cfn = ClevelandFedNowcast()
            snap = cfn.get_nowcast()
            if snap and snap.cpi_yoy:
                nowcast_cpi = snap.cpi_yoy
                components['cleveland_cpi_yoy_nowcast'] = nowcast_cpi
        except Exception:
            pass

        # Composite inflation score (0 = low, 1 = high)
        inflation_inputs = [v for v in [core_pce_yoy, cpi_yoy, nowcast_cpi] if v is not None]
        if inflation_inputs:
            avg_inflation = sum(inflation_inputs) / len(inflation_inputs)
            # Scale: 2% = 0 (target), 4% = 1 (high), 6%+ = 1.0 (capped)
            inflation_score = min(max((avg_inflation - 2.0) / 2.0, -0.5), 1.0)
        else:
            inflation_score = 0.0
        components['inflation_score'] = round(inflation_score, 3)

        # ── Growth Score ──
        # NFP 3-month average change
        nfp = self._get_fred_latest('PAYEMS', limit=4)
        nfp_3mo_avg = None
        if nfp and len(nfp) >= 4:
            changes = [nfp[i] - nfp[i + 1] for i in range(3)]
            nfp_3mo_avg = sum(changes) / 3
            components['nfp_3mo_avg_change'] = round(nfp_3mo_avg, 1)

        # Unemployment trend (rising = bad)
        unrate = self._get_fred_latest('UNRATE', limit=6)
        unrate_trend = None
        if unrate and len(unrate) >= 6:
            unrate_trend = unrate[0] - unrate[5]  # positive = rising unemployment
            components['unemployment_rate'] = unrate[0]
            components['unemployment_6mo_change'] = round(unrate_trend, 2)

        # Composite growth score (-1 = contraction, 0 = normal, +1 = boom)
        growth_score = 0.0
        if nfp_3mo_avg is not None:
            # NFP: 0K = neutral, +200K = strong, -100K = weak
            growth_score += min(max(nfp_3mo_avg / 200.0, -1.0), 1.0) * 0.6

        if unrate_trend is not None:
            # Unemployment rising = negative signal
            growth_score -= min(max(unrate_trend / 0.5, -1.0), 1.0) * 0.4

        components['growth_score'] = round(growth_score, 3)

        # ── Regime Classification ──
        regime = self._classify(inflation_score, growth_score)
        modifier = self.REGIME_MODIFIERS.get(regime, self.REGIME_MODIFIERS['NEUTRAL'])

        return {
            'regime': regime,
            'inflation_score': round(inflation_score, 3),
            'growth_score': round(growth_score, 3),
            'components': components,
            'modifier': modifier,
        }

    def get_kill_chain_adjustment(self, signal_direction: str) -> Dict[str, Any]:
        """
        Get Kill Chain confidence adjustment for current regime.
        
        Args:
            signal_direction: 'LONG' or 'SHORT'
        
        Returns:
            {'penalty': -15, 'regime': 'STAGFLATION', 'warning': '...'}
        """
        regime_data = self.get_regime()
        regime = regime_data['regime']
        modifier = regime_data['modifier']

        if signal_direction.upper() == 'LONG':
            penalty = modifier.get('long_penalty', 0)
        else:
            penalty = modifier.get('short_penalty', 0)

        return {
            'penalty': penalty,
            'regime': regime,
            'warning': modifier.get('warning'),
            'inflation_score': regime_data['inflation_score'],
            'growth_score': regime_data['growth_score'],
        }

    def _classify(self, inflation_score: float, growth_score: float) -> str:
        """Classify regime from inflation and growth scores."""
        high_inflation = inflation_score > 0.3
        low_inflation = inflation_score < -0.1
        strong_growth = growth_score > 0.3
        weak_growth = growth_score < -0.2
        contracting = growth_score < -0.5

        if contracting:
            return 'RECESSION'
        elif high_inflation and weak_growth:
            return 'STAGFLATION'
        elif high_inflation and strong_growth:
            return 'INFLATIONARY_BOOM'
        elif low_inflation and weak_growth:
            return 'DEFLATIONARY_BUST'
        elif not high_inflation and not weak_growth:
            return 'GOLDILOCKS'
        else:
            return 'NEUTRAL'

    def _get_fred_latest(self, series_id: str, limit: int = 13) -> Optional[list]:
        """Fetch latest N observations from FRED as float list (newest first)."""
        if not self.api_key:
            return None
        try:
            r = requests.get(
                f"{self.FRED_BASE}/series/observations",
                params={
                    "series_id": series_id,
                    "api_key": self.api_key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": limit,
                },
                timeout=10,
            )
            r.raise_for_status()
            obs = r.json().get("observations", [])
            return [float(o["value"]) for o in obs if o.get("value", ".") != "."]
        except Exception as e:
            logger.warning(f"FRED fetch failed for {series_id}: {e}")
            return None


# ─── Standalone Test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    from dotenv import load_dotenv
    load_dotenv()

    logging.basicConfig(level=logging.INFO)
    detector = MacroRegimeDetector()

    regime = detector.get_regime()
    print("=== MACRO REGIME ===")
    print(json.dumps(regime, indent=2))

    print("\n=== KILL CHAIN ADJUSTMENTS ===")
    for direction in ['LONG', 'SHORT']:
        adj = detector.get_kill_chain_adjustment(direction)
        print(f"  {direction}: penalty={adj['penalty']}%, regime={adj['regime']}, warning={adj['warning']}")
