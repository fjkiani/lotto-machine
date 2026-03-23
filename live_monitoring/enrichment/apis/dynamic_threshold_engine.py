"""
Dynamic Threshold Engine — Replaces ALL hardcoded thresholds

Source composition:
  1. TE Scraper → consensus for next event
  2. FRED API → last 12 actuals for historical std_dev
  3. FedWatch DIY → p_hold/p_hike/p_cut for regime multiplier
  4. Cleveland Fed Nowcast → divergence pre-signal (inflation events only)

Thresholds are computed as:  consensus ± (n × std_dev)
  HOT/STRONG   = consensus + 1.5σ
  WARM/ABOVE   = consensus + 1.0σ
  IN_LINE      = consensus
  COOL/BELOW   = consensus - 1.0σ
  COLD/WEAK    = consensus - 1.5σ

Regime multipliers adjust SPY shift magnitudes:
  p_hike > 25% → hawkish surprises hit 1.6x harder
  p_cut  > 60% → dovish surprises hit 1.6x harder
"""
import os
import logging
import statistics
import requests
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ── TE event name → FRED series ID mapping ────────────────────────────────
# Maps Trading Economics event names (lowercased substring match) to FRED series
TE_TO_FRED_MAP = {
    'core inflation rate':   {'series_id': 'CPILFESL',  'key': 'CORE_CPI',   'category': 'INFLATION'},
    'inflation rate':        {'series_id': 'CPIAUCSL',  'key': 'CPI',        'category': 'INFLATION'},
    'cpi':                   {'series_id': 'CPIAUCSL',  'key': 'CPI',        'category': 'INFLATION'},
    'core pce':              {'series_id': 'PCEPILFE',  'key': 'CORE_PCE',   'category': 'INFLATION'},
    'pce price':             {'series_id': 'PCEPI',     'key': 'PCE',        'category': 'INFLATION'},
    'non farm payrolls':     {'series_id': 'PAYEMS',    'key': 'NONFARM',    'category': 'LABOR'},
    'nonfarm payrolls':      {'series_id': 'PAYEMS',    'key': 'NONFARM',    'category': 'LABOR'},
    'unemployment rate':     {'series_id': 'UNRATE',    'key': 'UNEMPLOYMENT','category': 'LABOR'},
    'adp employment':        {'series_id': 'PAYEMS',    'key': 'NONFARM',    'category': 'LABOR'},
    'initial jobless':       {'series_id': 'ICSA',      'key': 'CLAIMS',     'category': 'LABOR'},
    'jolts':                 {'series_id': 'JTSJOL',    'key': 'JOLTS',      'category': 'LABOR'},
    'job openings':          {'series_id': 'JTSJOL',    'key': 'JOLTS',      'category': 'LABOR'},
    'gdp growth':            {'series_id': 'GDP',       'key': 'GDP',        'category': 'GROWTH'},
    'gdp third estimate':    {'series_id': 'GDP',       'key': 'GDP',        'category': 'GROWTH'},
    'gdp price index':       {'series_id': 'GDP',       'key': 'GDP',        'category': 'GROWTH'},
    'retail sales':          {'series_id': 'RSAFS',     'key': 'RETAIL_SALES','category': 'CONSUMER'},
    'durable goods':         {'series_id': 'DGORDER',   'key': 'DURABLE',    'category': 'CONSUMER'},
    'michigan':              {'series_id': 'UMCSENT',   'key': 'MICHIGAN',   'category': 'SENTIMENT'},
    'consumer confidence':   {'series_id': 'UMCSENT',   'key': 'MICHIGAN',   'category': 'SENTIMENT'},
    'ppi':                   {'series_id': 'PPIACO',    'key': 'PPI',        'category': 'INFLATION'},
}


@dataclass
class DynamicThresholds:
    """Computed thresholds for a specific economic event."""
    event: str
    category: str
    consensus: float
    std_dev: float
    thresholds: Dict[str, float]
    regime: Dict[str, Any]
    nowcast: Optional[Dict[str, Any]] = None
    fred_latest: Optional[float] = None
    fred_date: Optional[str] = None


class DynamicThresholdEngine:
    """
    Replaces hardcoded CPI/PCE/NFP thresholds with dynamic,
    data-driven thresholds computed from FRED historical std_dev,
    TE consensus, and FedWatch regime multipliers.
    """

    FRED_BASE = "https://api.stlouisfed.org/fred"

    def __init__(self, fred_api_key: Optional[str] = None, cache_ttl: int = 3600):
        self.fred_api_key = fred_api_key or os.getenv("FRED_API_KEY", "")
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = cache_ttl

        if not self.fred_api_key:
            logger.warning("⚠️ FRED_API_KEY not set — DynamicThresholdEngine degraded")

    def get_dynamic_thresholds(self, event_name: str, te_consensus: Optional[float] = None) -> Optional[DynamicThresholds]:
        """
        Compute dynamic thresholds for a given economic event.

        Args:
            event_name: TE event name (e.g., "Core PCE Price Index MoM")
            te_consensus: Override consensus value. If None, returns thresholds
                         with std_dev only (caller must supply consensus).

        Returns:
            DynamicThresholds with computed hot/warm/cool/cold bands
        """
        # Match event to FRED series
        fred_info = self._match_fred_series(event_name)
        if not fred_info:
            logger.warning(f"No FRED mapping for event: {event_name}")
            return None

        series_id = fred_info['series_id']
        category = fred_info['category']

        # Pull last 12 observations from FRED
        values, latest_date = self._fetch_fred_series(series_id, limit=13)
        if not values or len(values) < 2:
            logger.warning(f"Insufficient FRED data for {series_id}")
            return None

        # Compute MoM changes for index series (CPI, PCE, PPI are index values)
        if category == 'INFLATION':
            mom_changes = self._compute_mom_changes(values)
            if len(mom_changes) >= 2:
                std_dev = statistics.stdev(mom_changes)
                latest = mom_changes[0] if mom_changes else 0
            else:
                std_dev = 0.1  # fallback
                latest = values[0] if values else 0
        else:
            std_dev = statistics.stdev(values) if len(values) >= 2 else 0
            latest = values[0] if values else 0

        # Get regime from FedWatch
        regime = self._get_regime()

        # Compute consensus (use TE value or caller-supplied)
        consensus = te_consensus if te_consensus is not None else latest

        # Compute thresholds
        thresholds = {
            'HOT':     round(consensus + 1.5 * std_dev, 4),
            'WARM':    round(consensus + 1.0 * std_dev, 4),
            'IN_LINE': round(consensus, 4),
            'COOL':    round(consensus - 1.0 * std_dev, 4),
            'COLD':    round(consensus - 1.5 * std_dev, 4),
        }

        # Get Cleveland Fed nowcast divergence for inflation events
        nowcast_data = None
        if category == 'INFLATION':
            nowcast_data = self._get_nowcast_divergence(event_name, consensus)

        return DynamicThresholds(
            event=event_name,
            category=category,
            consensus=round(consensus, 4),
            std_dev=round(std_dev, 4),
            thresholds=thresholds,
            regime=regime,
            nowcast=nowcast_data,
            fred_latest=round(latest, 4),
            fred_date=latest_date,
        )

    def get_regime_adjusted_shifts(self, category: str) -> Dict[str, Any]:
        """
        Regime-aware SPY shift coefficients.
    
        Replaces static FedShiftPredictor coefficients with live
        FedWatch-calibrated multipliers.
        """
        regime = self._get_regime()
        p_hike = regime.get('p_hike', 0)
        p_cut = regime.get('p_cut', 0)

        base_shifts = {
            'INFLATION': {'surprise_hot': -2.5, 'surprise_cold': +2.5},
            'LABOR':     {'surprise_strong': -1.8, 'surprise_weak': +1.8},
            'GROWTH':    {'surprise_strong': -1.2, 'surprise_weak': +1.2},
            'CONSUMER':  {'surprise_strong': -0.8, 'surprise_weak': +0.8},
            'SENTIMENT': {'surprise_strong': -0.5, 'surprise_weak': +0.5},
        }

        coeff = base_shifts.get(category, {'surprise_strong': -0.5, 'surprise_weak': +0.5})

        # Regime multipliers
        if p_hike > 25:
            hawkish_mult = 1.6
            dovish_mult = 0.8
        elif p_cut > 60:
            hawkish_mult = 0.8
            dovish_mult = 1.6
        else:
            hawkish_mult = 1.0
            dovish_mult = 1.0

        adjusted = {}
        for key, val in coeff.items():
            if val < 0:  # hawkish surprise
                adjusted[key] = round(val * hawkish_mult, 2)
            else:  # dovish surprise
                adjusted[key] = round(val * dovish_mult, 2)

        adjusted['regime'] = regime.get('regime_label', 'HOLD')
        adjusted['hawkish_mult'] = hawkish_mult
        adjusted['dovish_mult'] = dovish_mult
        adjusted['p_hike'] = p_hike
        adjusted['p_cut'] = p_cut

        return adjusted

    # ── Internal helpers ──────────────────────────────────────────────────

    def _match_fred_series(self, event_name: str) -> Optional[Dict]:
        """Match TE event name to FRED series ID via substring matching."""
        lower = event_name.lower()
        for pattern, info in TE_TO_FRED_MAP.items():
            if pattern in lower:
                return info
        return None

    def _fetch_fred_series(self, series_id: str, limit: int = 13) -> tuple:
        """Fetch latest N observations from FRED. Returns (values[], latest_date)."""
        if not self.fred_api_key:
            return [], None

        try:
            url = f"{self.FRED_BASE}/series/observations"
            params = {
                "series_id": series_id,
                "api_key": self.fred_api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": limit,
            }
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            obs = r.json().get("observations", [])
            values = [float(o["value"]) for o in obs if o.get("value", ".") != "."]
            latest_date = obs[0].get("date") if obs else None
            return values, latest_date
        except Exception as e:
            logger.error(f"❌ FRED fetch error for {series_id}: {e}")
            return [], None

    def _compute_mom_changes(self, values: List[float]) -> List[float]:
        """Compute MoM percentage changes from index values (newest first)."""
        changes = []
        for i in range(len(values) - 1):
            if values[i + 1] != 0:
                pct = ((values[i] - values[i + 1]) / values[i + 1]) * 100
                changes.append(round(pct, 4))
        return changes

    def _get_regime(self) -> Dict[str, Any]:
        """Get current FedWatch regime classification."""
        try:
            from live_monitoring.enrichment.apis.fedwatch_diy import FedWatchEngine
            fw = FedWatchEngine()
            probs = fw.get_probabilities()
            if probs and 'next_meeting' in probs:
                nm = probs['next_meeting']
                p_hike = nm.get('p_hike_25', 0)
                p_cut = nm.get('p_cut_25', 0)
                p_hold = nm.get('p_hold', 100)

                if p_hike > 25:
                    label = 'HIKE_RISK'
                elif p_cut > 60:
                    label = 'CUT_CYCLE'
                else:
                    label = 'HOLD'

                return {
                    'regime_label': label,
                    'p_hike': p_hike,
                    'p_cut': p_cut,
                    'p_hold': p_hold,
                    'next_meeting': nm.get('label', ''),
                    'days_away': nm.get('days_away', 0),
                }
        except Exception as e:
            logger.warning(f"FedWatch regime check failed: {e}")

        return {'regime_label': 'UNKNOWN', 'p_hike': 0, 'p_cut': 0, 'p_hold': 100}

    def _get_nowcast_divergence(self, event_name: str, consensus: float) -> Optional[Dict]:
        """Get Cleveland Fed nowcast divergence for inflation events."""
        try:
            from live_monitoring.enrichment.apis.cleveland_fed_nowcast import ClevelandFedNowcast
            cfn = ClevelandFedNowcast()

            # Map event name to nowcast metric
            lower = event_name.lower()
            if 'core cpi' in lower:
                metric = 'core_cpi_mom'
            elif 'cpi' in lower or 'inflation rate' in lower:
                metric = 'cpi_mom'
            elif 'core pce' in lower:
                metric = 'core_pce_mom'
            elif 'pce' in lower:
                metric = 'pce_mom'
            else:
                return None

            return cfn.get_divergence(consensus, metric)

        except Exception as e:
            logger.warning(f"Cleveland Fed nowcast check failed: {e}")
            return None


# ─── Standalone Test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    from dotenv import load_dotenv
    load_dotenv()

    logging.basicConfig(level=logging.INFO)
    engine = DynamicThresholdEngine()

    test_events = [
        ("Core PCE Price Index MoMFEB", 0.3),
        ("Non Farm PayrollsMAR", 200.0),
        ("Initial Jobless Claims", 215.0),
        ("GDP Third Estimate Q4 2025", 2.3),
    ]

    for event, consensus in test_events:
        result = engine.get_dynamic_thresholds(event, te_consensus=consensus)
        if result:
            print(f"\n{'='*60}")
            print(f"Event: {result.event}")
            print(f"Category: {result.category}")
            print(f"Consensus: {result.consensus}")
            print(f"Std Dev: {result.std_dev}")
            print(f"FRED Latest: {result.fred_latest} ({result.fred_date})")
            print(f"Thresholds: {json.dumps(result.thresholds, indent=2)}")
            print(f"Regime: {json.dumps(result.regime, indent=2)}")
            if result.nowcast:
                print(f"Nowcast: {json.dumps(result.nowcast, indent=2)}")

    # Test regime-aware shifts
    print(f"\n{'='*60}")
    print("Regime-Aware Shift Coefficients:")
    for cat in ['INFLATION', 'LABOR', 'GROWTH', 'CONSUMER', 'SENTIMENT']:
        shifts = engine.get_regime_adjusted_shifts(cat)
        print(f"  {cat}: {json.dumps(shifts, indent=4)}")
