"""
brief/alert_engine.py — PreSignalAlertEngine: generates prioritised alerts
from the unified brief payload.
"""
import logging

logger = logging.getLogger(__name__)


class PreSignalAlertEngine:
    """Generates prioritised alerts from the unified brief payload."""

    def get_alerts(self, brief: dict) -> list:
        alerts: list = []
        self._nowcast_alerts(brief, alerts)
        self._veto_alert(brief, alerts)
        self._regime_alert(brief, alerts)
        self._rate_alert(brief, alerts)
        self._hidden_hands_alerts(brief, alerts)
        self._gex_alert(brief, alerts)
        self._adp_alert(brief, alerts)
        self._gdp_alert(brief, alerts)
        priority_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        return sorted(alerts, key=lambda x: priority_order.get(x.get('priority', 'LOW'), 3))

    # ── Individual alert generators ──────────────────────────────────────────

    def _nowcast_alerts(self, brief: dict, alerts: list) -> None:
        nowcast = brief.get('nowcast', {})
        if not nowcast or nowcast.get('error'):
            return
        cpi_mom = nowcast.get('cpi_mom')
        if cpi_mom is not None:
            consensus  = brief.get('dynamic_thresholds', {}).get('cpi', {}).get('consensus', 0.3)
            divergence = cpi_mom - consensus
            if abs(divergence) > 0.05:
                direction = 'PRE_HOT' if divergence > 0 else 'PRE_COLD'
                alerts.append({
                    'type': 'PRE_SIGNAL', 'priority': 'HIGH', 'event': 'CPI',
                    'signal': direction, 'nowcast_value': cpi_mom, 'consensus': consensus,
                    'divergence_pct': round(divergence, 3),
                    'edge': f"Cleveland nowcast {cpi_mom}% vs consensus {consensus}% → {'+' if divergence > 0 else ''}{divergence:.2f}%",
                    'action': f"Monitor TLT {'puts' if direction == 'PRE_HOT' else 'calls'} / SPY {'puts' if direction == 'PRE_HOT' else 'calls'} into print",
                })
        pce_mom = nowcast.get('pce_mom')
        if pce_mom is not None:
            pce_cons = brief.get('dynamic_thresholds', {}).get('core_pce', {}).get('consensus', 0.3)
            pce_div  = pce_mom - pce_cons
            if abs(pce_div) > 0.05:
                alerts.append({
                    'type': 'PRE_SIGNAL', 'priority': 'HIGH', 'event': 'Core PCE',
                    'signal': 'PRE_HOT' if pce_div > 0 else 'PRE_COLD',
                    'nowcast_value': pce_mom, 'consensus': pce_cons,
                    'divergence_pct': round(pce_div, 3),
                    'edge': f"Cleveland nowcast {pce_mom}% vs PCE consensus {pce_cons}% → {'+' if pce_div > 0 else ''}{pce_div:.2f}%",
                    'action': "PCE divergence — Fed's preferred inflation gauge",
                })

    def _veto_alert(self, brief: dict, alerts: list) -> None:
        veto      = brief.get('economic_veto', {})
        hours_away = veto.get('hours_away')
        if hours_away is not None and hours_away <= 48:
            priority = 'CRITICAL' if hours_away <= 2 else 'HIGH' if hours_away <= 6 else 'MEDIUM' if hours_away <= 24 else 'LOW'
            alerts.append({
                'type': 'VETO_APPROACHING', 'priority': priority,
                'event': veto.get('next_event', 'Unknown'),
                'hours': round(hours_away, 1), 'tier': veto.get('tier'),
                'cap': veto.get('confidence_cap'),
                'action': f"Signals capped at {veto.get('confidence_cap', '?')}% — reduce position size",
            })

    def _regime_alert(self, brief: dict, alerts: list) -> None:
        regime      = brief.get('macro_regime', {})
        regime_name = regime.get('regime')
        if regime_name in ('STAGFLATION', 'RECESSION'):
            penalty = regime.get('modifier', {}).get('long_penalty', 0)
            alerts.append({
                'type': 'REGIME_WARNING', 'priority': 'HIGH', 'regime': regime_name,
                'inflation_score': regime.get('inflation_score'),
                'growth_score':    regime.get('growth_score'),
                'penalty':         penalty,
                'action':          f"{regime_name} regime: LONG signals penalized {penalty}%",
            })

    def _rate_alert(self, brief: dict, alerts: list) -> None:
        rate_path = brief.get('fed_intelligence', {}).get('rate_path', {})
        may_hike  = rate_path.get('may_p_hike', 0)
        if may_hike > 20:
            alerts.append({
                'type': 'RATE_RISK', 'priority': 'MEDIUM', 'event': 'Fed May Meeting',
                'p_hike': may_hike,
                'action': f"May FOMC hike probability at {may_hike}% — hawkish surprises hit 1.6x",
            })

    def _hidden_hands_alerts(self, brief: dict, alerts: list) -> None:
        hh = brief.get('hidden_hands', {})
        for sig in hh.get('finnhub_signals', []):
            if isinstance(sig, dict) and sig.get('convergence') == 'DIVERGENCE':
                alerts.append({
                    'type': 'HIDDEN_HANDS', 'priority': 'MEDIUM',
                    'ticker': sig.get('ticker', '??'),
                    'signal': f"Pol {sig.get('politician_action', 'BUY')} + Insider MSPR={sig.get('insider_mspr', '?')}",
                    'edge':   'Divergence — monitor for reversal signal',
                })

    def _gex_alert(self, brief: dict, alerts: list) -> None:
        deriv     = brief.get('derivatives', {})
        gex_regime = deriv.get('gex_regime', '')
        if gex_regime and 'NEGATIVE' in str(gex_regime).upper():
            alerts.append({
                'type': 'GEX_WARNING', 'priority': 'MEDIUM', 'regime': gex_regime,
                'total_gex': deriv.get('total_gex'),
                'action':    'Short gamma — dealers amplify moves, expect volatility',
            })

    def _adp_alert(self, brief: dict, alerts: list) -> None:
        adp       = brief.get('adp_prediction', {})
        adp_signal = adp.get('signal', '')
        adp_delta  = abs(adp.get('delta', 0))
        if adp_signal in ('MISS_LIKELY', 'BEAT_LIKELY') and adp_delta > 30_000:
            alerts.append({
                'type': 'ADP_PRESIGNAL',
                'priority': 'HIGH' if adp_delta >= 50_000 else 'MEDIUM',
                'event': 'ADP Mar 24 08:15AM', 'signal': adp_signal,
                'prediction': adp.get('prediction'), 'consensus': adp.get('consensus'),
                'delta': adp.get('delta'), 'edge': adp.get('edge'),
                'action': f"ADP model: {adp.get('edge', '')} — position accordingly",
            })

    def _gdp_alert(self, brief: dict, alerts: list) -> None:
        gdp       = brief.get('gdp_nowcast', {})
        gdp_signal = gdp.get('signal', '')
        gdp_vs     = abs(gdp.get('vs_consensus', 0))
        if gdp_signal in ('MISS', 'BEAT') and gdp_vs > 0.3:
            alerts.append({
                'type': 'GDP_PRESIGNAL',
                'priority': 'HIGH' if gdp_vs > 1.0 else 'MEDIUM',
                'event': 'GDP Q1 Estimate', 'signal': gdp_signal,
                'estimate': gdp.get('gdp_estimate'), 'consensus': gdp.get('consensus'),
                'edge': gdp.get('edge'),
                'action': f"GDPNow: {gdp.get('edge', '')} — growth trajectory warning",
            })
