"""
🎯 Master Brief API — Unified Intelligence Surface

One endpoint, nine data layers, zero new computation.
Pure orchestration of existing modules.

GET /api/v1/brief/master

Returns:
  - macro_regime: MacroRegimeDetector output
  - fed_intelligence: FedWatch rate path + regime multiplier
  - hidden_hands: BrainManager hidden hands + divergence
  - economic_edge: TE calendar veto + Cleveland nowcast pre-signals
  - derivatives: GEX regime + COT positioning
  - kill_chain_state: Kill Chain verdict + confidence caps
  - alerts: Pre-signal alert engine output (priority-sorted)
"""

import logging
import time
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter

try:
    import yaml
except ImportError:
    yaml = None

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Veto Cascade Config Loader ───────────────────────────────────────────────
_veto_config = None

def _load_veto_config():
    """Load veto_cascade.yaml once at startup. Falls back to hardcoded defaults."""
    global _veto_config
    if _veto_config is not None:
        return _veto_config

    config_path = Path(__file__).resolve().parents[3] / 'config' / 'veto_cascade.yaml'
    if yaml and config_path.exists():
        try:
            with open(config_path) as f:
                _veto_config = yaml.safe_load(f)
            logger.info(f"📋 Veto config loaded from {config_path}")
            return _veto_config
        except Exception as e:
            logger.warning(f"Failed to load veto config: {e} — using hardcoded defaults")

    # Hardcoded fallback (same as before)
    _veto_config = {
        'VETO_TIERS': {
            'BLOCKED':   {'hours': 0.5, 'cap': 0},
            'HIGH_RISK': {'hours': 2.0, 'cap': 35},
            'RISK':      {'hours': 6.0, 'cap': 50},
            'AWARENESS': {'hours': 24.0, 'cap': 55},
            'NORMAL':    {'hours': None, 'cap': 65},
        },
        'EVENT_OVERRIDES': {}
    }
    return _veto_config


def _resolve_tiers(event_name: str) -> list:
    """Build tier ladder for a specific event, merging overrides with defaults."""
    cfg = _load_veto_config()
    defaults = cfg.get('VETO_TIERS', {})
    overrides = cfg.get('EVENT_OVERRIDES', {})

    # Find matching override key (case-insensitive substring match)
    event_upper = (event_name or '').upper()
    matched_overrides = {}
    for key, ovr in overrides.items():
        if key.upper() in event_upper:
            matched_overrides = ovr or {}
            break

    # Build resolved tiers: override hours if present, keep default cap
    tiers = []
    for tier_name, tier_def in defaults.items():
        hours = tier_def.get('hours')
        cap = tier_def.get('cap', 65)
        if tier_name in matched_overrides:
            hours = matched_overrides[tier_name].get('hours', hours)
            cap = matched_overrides[tier_name].get('cap', cap)
        tiers.append((tier_name, hours, cap))

    # Sort by hours ascending (tightest first), None last
    tiers.sort(key=lambda t: (t[1] is None, t[1] or 999))
    return tiers


# ── Pre-Signal Alert Engine ──────────────────────────────────────────────────

class PreSignalAlertEngine:
    """Generates prioritized alerts from the unified brief payload."""

    def get_alerts(self, brief: dict) -> list:
        alerts = []

        # Alert 1: Cleveland nowcast divergence (highest-value pre-signal)
        nowcast = brief.get('nowcast', {})
        if nowcast and not nowcast.get('error'):
            cpi_mom = nowcast.get('cpi_mom')
            if cpi_mom is not None:
                # Compare vs current TE consensus for CPI (default 0.3%)
                consensus = brief.get('dynamic_thresholds', {}).get('cpi', {}).get('consensus', 0.3)
                divergence = cpi_mom - consensus
                if abs(divergence) > 0.05:
                    direction = 'PRE_HOT' if divergence > 0 else 'PRE_COLD'
                    alerts.append({
                        'type': 'PRE_SIGNAL',
                        'priority': 'HIGH',
                        'event': 'CPI',
                        'signal': direction,
                        'nowcast_value': cpi_mom,
                        'consensus': consensus,
                        'divergence_pct': round(divergence, 3),
                        'edge': f"Cleveland nowcast {cpi_mom}% vs consensus {consensus}% → {'+' if divergence > 0 else ''}{divergence:.2f}%",
                        'action': f"Monitor TLT {'puts' if direction == 'PRE_HOT' else 'calls'} / SPY {'puts' if direction == 'PRE_HOT' else 'calls'} into print"
                    })

            pce_mom = nowcast.get('pce_mom')
            if pce_mom is not None:
                pce_consensus = brief.get('dynamic_thresholds', {}).get('core_pce', {}).get('consensus', 0.3)
                pce_div = pce_mom - pce_consensus
                if abs(pce_div) > 0.05:
                    alerts.append({
                        'type': 'PRE_SIGNAL',
                        'priority': 'HIGH',
                        'event': 'Core PCE',
                        'signal': 'PRE_HOT' if pce_div > 0 else 'PRE_COLD',
                        'nowcast_value': pce_mom,
                        'consensus': pce_consensus,
                        'divergence_pct': round(pce_div, 3),
                        'edge': f"Cleveland nowcast {pce_mom}% vs PCE consensus {pce_consensus}% → {'+' if pce_div > 0 else ''}{pce_div:.2f}%",
                        'action': 'PCE divergence — Fed\'s preferred inflation gauge'
                    })

        #  Alert 2: Economic veto approaching — fire at 48h for advance warning
        veto = brief.get('economic_veto', {})
        hours_away = veto.get('hours_away')
        if hours_away is not None and hours_away <= 48:
            priority = 'CRITICAL' if hours_away <= 2 else 'HIGH' if hours_away <= 6 else 'MEDIUM' if hours_away <= 24 else 'LOW'
            alerts.append({
                'type': 'VETO_APPROACHING',
                'priority': priority,
                'event': veto.get('next_event', 'Unknown'),
                'hours': round(hours_away, 1),
                'tier': veto.get('tier'),
                'cap': veto.get('confidence_cap'),
                'action': f"Signals capped at {veto.get('confidence_cap', '?')}% — reduce position size"
            })

        # Alert 3: Macro regime warning
        regime = brief.get('macro_regime', {})
        regime_name = regime.get('regime')
        if regime_name in ('STAGFLATION', 'RECESSION'):
            penalty = regime.get('modifier', {}).get('long_penalty', 0)
            alerts.append({
                'type': 'REGIME_WARNING',
                'priority': 'HIGH',
                'regime': regime_name,
                'inflation_score': regime.get('inflation_score'),
                'growth_score': regime.get('growth_score'),
                'penalty': penalty,
                'action': f"{regime_name} regime: LONG signals penalized {penalty}%"
            })

        # Alert 4: FedWatch hike risk
        rate_path = brief.get('fed_intelligence', {}).get('rate_path', {})
        may_hike = rate_path.get('may_p_hike', 0)
        if may_hike > 20:
            alerts.append({
                'type': 'RATE_RISK',
                'priority': 'MEDIUM',
                'event': 'Fed May Meeting',
                'p_hike': may_hike,
                'action': f"May FOMC hike probability at {may_hike}% — hawkish surprises hit 1.6x"
            })

        # Alert 5: Politician/insider divergence
        hh = brief.get('hidden_hands', {})
        for sig in hh.get('finnhub_signals', []):
            if isinstance(sig, dict) and sig.get('convergence') == 'DIVERGENCE':
                alerts.append({
                    'type': 'HIDDEN_HANDS',
                    'priority': 'MEDIUM',
                    'ticker': sig.get('ticker', '??'),
                    'signal': f"Pol {sig.get('politician_action', 'BUY')} + Insider MSPR={sig.get('insider_mspr', '?')}",
                    'edge': 'Divergence — monitor for reversal signal'
                })

        # Alert 6: GEX regime (short gamma = amplified moves)
        deriv = brief.get('derivatives', {})
        gex_regime = deriv.get('gex_regime', '')
        if gex_regime and 'NEGATIVE' in str(gex_regime).upper():
            alerts.append({
                'type': 'GEX_WARNING',
                'priority': 'MEDIUM',
                'regime': gex_regime,
                'total_gex': deriv.get('total_gex'),
                'action': 'Short gamma — dealers amplify moves, expect volatility'
            })

        # Alert 7: ADP pre-signal (leading indicator model)
        adp = brief.get('adp_prediction', {})
        adp_signal = adp.get('signal', '')
        adp_delta = abs(adp.get('delta', 0))
        if adp_signal in ('MISS_LIKELY', 'BEAT_LIKELY') and adp_delta > 30_000:
            alerts.append({
                'type': 'ADP_PRESIGNAL',
                'priority': 'HIGH' if adp_delta >= 50_000 else 'MEDIUM',
                'event': 'ADP Mar 24 08:15AM',
                'signal': adp_signal,
                'prediction': adp.get('prediction'),
                'consensus': adp.get('consensus'),
                'delta': adp.get('delta'),
                'edge': adp.get('edge'),
                'action': f"ADP model: {adp.get('edge', '')} — position accordingly"
            })

        # Alert 8: GDP pre-signal (Atlanta Fed GDPNow tracker)
        gdp = brief.get('gdp_nowcast', {})
        gdp_signal = gdp.get('signal', '')
        gdp_vs = abs(gdp.get('vs_consensus', 0))
        if gdp_signal in ('MISS', 'BEAT') and gdp_vs > 0.3:
            alerts.append({
                'type': 'GDP_PRESIGNAL',
                'priority': 'HIGH' if gdp_vs > 1.0 else 'MEDIUM',
                'event': 'GDP Q1 Estimate',
                'signal': gdp_signal,
                'estimate': gdp.get('gdp_estimate'),
                'consensus': gdp.get('consensus'),
                'edge': gdp.get('edge'),
                'action': f"GDPNow: {gdp.get('edge', '')} — growth trajectory warning"
            })

        # Sort by priority
        priority_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        return sorted(alerts, key=lambda x: priority_order.get(x.get('priority', 'LOW'), 3))


# ── Master Brief Endpoint ────────────────────────────────────────────────────

# ── Brief-level response cache (2-min TTL) ───────────────────────────────────
_brief_cache = None
_brief_cache_time = None
_BRIEF_CACHE_TTL = 120  # seconds
_alert_engine = PreSignalAlertEngine()

# ── Lazy singletons for heavy objects (init once, reuse) ─────────────────────
_singletons = {}

def _lazy(key, factory):
    if key not in _singletons:
        _singletons[key] = factory()
    return _singletons[key]


@router.get("/brief/master")
async def master_brief():
    """
    Unified intelligence brief — aggregates all 9 data layers
    into one payload consumed by the Today's Brief page.

    PARALLEL execution via ThreadPoolExecutor — target ≤8s vs 29s sequential.
    2-min TTL cache on the full response.
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    global _brief_cache, _brief_cache_time

    # Return cached response if within TTL
    if _brief_cache and _brief_cache_time:
        if time.time() - _brief_cache_time < _BRIEF_CACHE_TTL:
            logger.info(f"📋 Brief cache hit ({time.time() - _brief_cache_time:.0f}s old)")
            return _brief_cache

    t0 = time.time()

    # ── Layer functions (each self-contained, no shared state) ────────────

    def _fetch_macro_regime():
        try:
            from live_monitoring.agents.economic.macro_regime_detector import MacroRegimeDetector
            return _lazy('macro', MacroRegimeDetector).get_regime()
        except Exception as e:
            logger.warning(f"MacroRegime failed: {e}")
            return {'error': str(e)}

    def _fetch_fedwatch():
        try:
            from live_monitoring.enrichment.apis.fedwatch_diy import FedWatchEngine
            fw = _lazy('fedwatch', FedWatchEngine).get_probabilities()
            if fw and not fw.get('error'):
                next_mtg = fw.get('next_meeting', {})
                return {
                    'rate_path': {
                        'current_rate': fw.get('current_rate'),
                        'current_range': fw.get('current_range'),
                        'may_p_hike': next_mtg.get('p_hike_25', 0),
                        'may_p_hold': next_mtg.get('p_hold', 100),
                        'may_p_cut': next_mtg.get('p_cut_25', 0),
                        'terminal_bps': fw.get('total_cuts_bps', 0),
                        'meetings_count': len(fw.get('rate_path', [])),
                        'next_meeting': next_mtg.get('label', ''),
                        'days_away': next_mtg.get('days_away', 0),
                        'regime_multiplier': 1.6 if next_mtg.get('p_hike_25', 0) > 25 else (1.6 if fw.get('rate_path', [{}])[-1].get('p_cut_25', 0) > 60 else 1.0),
                    },
                    'full_path': fw.get('rate_path', []),
                }
            return {'error': fw.get('error', 'No data'), 'rate_path': {}}
        except Exception as e:
            logger.warning(f"FedWatch failed: {e}")
            return {'error': str(e), 'rate_path': {}}

    def _fetch_veto():
        try:
            from live_monitoring.enrichment.apis.te_calendar_scraper import TECalendarScraper
            te = TECalendarScraper(cache_ttl=300)
            veto_result = te.get_hours_until_next_critical()
            if veto_result is not None:
                hours, event_name = veto_result
                event_name = event_name or 'critical release'
            else:
                hours, event_name = None, None

            # Config-driven tier resolution with per-event overrides
            resolved = _resolve_tiers(event_name)
            tier = 'NORMAL'
            cap = 65
            if hours is not None:
                for tier_name, tier_hours, tier_cap in resolved:
                    if tier_hours is not None and hours <= tier_hours:
                        tier, cap = tier_name, tier_cap
                        break

            upcoming_critical = []
            try:
                all_events = te.get_us_calendar()
                crits = [e for e in all_events if e.importance == 'CRITICAL']
                for ev in crits[:5]:
                    upcoming_critical.append({
                        'event': ev.event,
                        'date': ev.date,
                        'time': ev.time,
                        'consensus': ev.consensus,
                        'previous': ev.previous,
                    })
            except Exception:
                pass

            return {
                'hours_away': round(hours, 1) if hours is not None else None,
                'next_event': event_name,
                'tier': tier,
                'confidence_cap': cap,
                'upcoming_critical': upcoming_critical,
            }
        except Exception as e:
            logger.warning(f"Economic veto failed: {e}")
            return {'error': str(e)}

    def _fetch_nowcast():
        try:
            from live_monitoring.enrichment.apis.cleveland_fed_nowcast import ClevelandFedNowcast
            cn = ClevelandFedNowcast()
            nowcast = cn.get_nowcast()
            if nowcast:
                return {
                    'cpi_mom': nowcast.cpi_mom,
                    'core_cpi_mom': nowcast.core_cpi_mom,
                    'pce_mom': nowcast.pce_mom,
                    'core_pce_mom': nowcast.core_pce_mom,
                    'cpi_yoy': nowcast.cpi_yoy,
                    'pce_yoy': nowcast.pce_yoy,
                    'updated': nowcast.updated,
                }
            return {'error': 'No data returned'}
        except Exception as e:
            logger.warning(f"Nowcast failed: {e}")
            return {'error': str(e)}

    def _fetch_thresholds():
        try:
            from dotenv import load_dotenv
            load_dotenv()
            import os
            fred_key = os.getenv("FRED_API_KEY", "")
            if not fred_key:
                logger.warning("⚠️ FRED_API_KEY not set — dynamic thresholds unavailable")
                return {'error': 'FRED_API_KEY not configured', 'fred_key_present': False}

            from live_monitoring.enrichment.apis.dynamic_threshold_engine import DynamicThresholdEngine
            # Pass key explicitly to avoid stale _lazy instances missing the key
            dte = DynamicThresholdEngine(fred_api_key=fred_key)
            thresholds = {}
            for evt_name, consensus in [('Core PCE Price Index MoM', 0.3), ('Non Farm Payrolls', 200), ('CPI MoM', 0.3)]:
                dt = dte.get_dynamic_thresholds(evt_name, te_consensus=consensus)
                if dt:
                    key = evt_name.lower().replace(' ', '_').replace('_price_index_mom', '').replace('_mom', '')
                    thresholds[key] = {
                        'HOT': dt.thresholds.get('HOT'),
                        'COLD': dt.thresholds.get('COLD'),
                        'consensus': dt.consensus,
                        'std_dev': dt.std_dev,
                    }
                else:
                    logger.warning(f"DynamicThresholdEngine returned None for {evt_name}")
            if not thresholds:
                return {'error': 'All threshold lookups returned None', 'fred_key_present': True}
            return thresholds
        except Exception as e:
            logger.warning(f"Dynamic thresholds failed: {e}")
            return {'error': str(e)}

    def _fetch_hidden_hands():
        try:
            from dotenv import load_dotenv
            load_dotenv()
            from live_monitoring.core.brain_manager import BrainManager
            bm = BrainManager()
            report = bm.get_report()
            hh = report.get('hidden_hands', {})
            return {
                'politician_cluster': hh.get('politician_cluster', hh.get('pol_cluster_count', 0)),
                'hot_tickers': hh.get('hot_tickers', []),
                'insider_net_usd': hh.get('insider_net_usd', 0),
                'divergence_boost': report.get('divergence_boost', 0),
                'fed_tone': report.get('fed_overall_tone', 'NEUTRAL'),
                'hawk_count': report.get('hawk_count', 0),
                'dove_count': report.get('dove_count', 0),
                'spouse_alerts': len(report.get('spouse_trade_alerts', [])),
                'finnhub_signals': report.get('finnhub_signals', []),
                'top_divergence': report.get('top_divergence', None),
            }
        except Exception as e:
            logger.warning(f"Hidden hands failed: {e}")
            return {'error': str(e)}

    def _fetch_derivatives():
        deriv = {}
        try:
            from live_monitoring.enrichment.apis.gex_calculator import GEXCalculator
            calc = _lazy('gex', lambda: GEXCalculator(cache_ttl=300))
            gex = calc.compute_gex('SPY')
            deriv = {
                'gex_regime': gex.gamma_regime if gex else 'UNKNOWN',
                'total_gex': gex.total_gex if gex else 0,
                'put_wall': None,
                'call_wall': None,
                'spot': gex.spot_price if gex else 0,
                'gamma_flip': gex.gamma_flip if gex else None,
                'max_pain': gex.max_pain if gex else None,
            }
            if gex and gex.negative_zones:
                deriv['put_wall'] = gex.negative_zones[0].strike if gex.negative_zones else None
            if gex and gex.gamma_walls:
                deriv['call_wall'] = gex.gamma_walls[0].strike if gex.gamma_walls else None
        except Exception as e:
            logger.warning(f"GEX failed: {e}")
            deriv = {'error': str(e)}

        # COT
        try:
            from live_monitoring.enrichment.apis.cot_client import COTClient
            cot = COTClient(cache_ttl=300)
            es_pos = cot.get_position('ES')
            if es_pos:
                es_div = cot.get_divergence_signal('ES')
                deriv['cot_spec_net'] = es_pos.specs_net
                deriv['cot_spec_side'] = 'SHORT' if es_pos.specs_net < 0 else 'LONG'
                deriv['cot_divergent'] = es_div.get('divergent', False)
                deriv['cot_trap'] = es_div.get('description', '')
        except Exception as e:
            logger.warning(f"COT failed: {e}")

        return deriv

    def _fetch_kill_chain():
        try:
            from live_monitoring.enrichment.apis.kill_chain_engine import KillChainEngine
            kc = _lazy('kc', KillChainEngine)
            report = kc.run_full_scan()
            return {
                'alert_level': report.alert_level,
                'layers_active': report.layers_active,
                'narrative': report.narrative[:200] if report.narrative else '',
                'mismatches_count': len(report.mismatches or []),
            }
        except Exception as e:
            logger.warning(f"Kill Chain failed: {e}")
            return {'error': str(e)}

    def _fetch_adp_prediction():
        try:
            from live_monitoring.enrichment.apis.adp_predictor import ADPPredictor
            return _lazy('adp', ADPPredictor).predict()
        except Exception as e:
            logger.warning(f"ADP Predictor failed: {e}")
            return {'error': str(e)}

    def _fetch_gdp_nowcast():
        try:
            from live_monitoring.enrichment.apis.atlanta_fed_gdpnow import AtlantaFedGDPNow
            return _lazy('gdpnow', AtlantaFedGDPNow).get_estimate()
        except Exception as e:
            logger.warning(f"GDPNow failed: {e}")
            return {'error': str(e)}

    def _fetch_jobless_claims():
        try:
            from live_monitoring.enrichment.apis.jobless_claims_predictor import JoblessClaimsPredictor
            return _lazy('jobless', JoblessClaimsPredictor).predict()
        except Exception as e:
            logger.warning(f"Jobless Claims Predictor failed: {e}")
            return {'error': str(e)}

    # ── PARALLEL EXECUTION — all 11 layers at once ────────────────────────

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=13) as executor:
        futures = {
            'macro_regime':      loop.run_in_executor(executor, _fetch_macro_regime),
            'fed_intelligence':  loop.run_in_executor(executor, _fetch_fedwatch),
            'economic_veto':     loop.run_in_executor(executor, _fetch_veto),
            'nowcast':           loop.run_in_executor(executor, _fetch_nowcast),
            'dynamic_thresholds': loop.run_in_executor(executor, _fetch_thresholds),
            'hidden_hands':      loop.run_in_executor(executor, _fetch_hidden_hands),
            'derivatives':       loop.run_in_executor(executor, _fetch_derivatives),
            'kill_chain_state':  loop.run_in_executor(executor, _fetch_kill_chain),
            'adp_prediction':    loop.run_in_executor(executor, _fetch_adp_prediction),
            'gdp_nowcast':       loop.run_in_executor(executor, _fetch_gdp_nowcast),
        }

        results = {}
        for key, future in futures.items():
            try:
                results[key] = await future
            except Exception as e:
                logger.error(f"Layer {key} executor failed: {e}")
                results[key] = {'error': str(e)}

    # ── Post-processing (depends on prior results — must be sequential) ──

    # Add modifiers from regime + veto to kill chain
    regime_modifier = results.get('macro_regime', {}).get('modifier', {}).get('long_penalty', 0)
    veto_cap = results.get('economic_veto', {}).get('confidence_cap', 65)

    results['kill_chain_state'] = results.get('kill_chain_state', {})
    results['kill_chain_state']['regime_modifier'] = regime_modifier
    results['kill_chain_state']['confidence_cap'] = veto_cap
    results['kill_chain_state']['cap_reason'] = (
        f"{results.get('economic_veto', {}).get('next_event', '')} "
        f"{results.get('economic_veto', {}).get('hours_away', '')}h"
    )

    # Alert engine (depends on all results)
    try:
        results['alerts'] = _alert_engine.get_alerts(results)
    except Exception as e:
        logger.warning(f"Alert engine failed: {e}")
        results['alerts'] = []

    results['scan_time'] = round(time.time() - t0, 2)
    results['as_of'] = datetime.utcnow().isoformat()

    # Save to cache
    _brief_cache = results
    _brief_cache_time = time.time()

    return results
