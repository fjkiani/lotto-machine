"""
brief/fetchers/core.py — Core intelligence fetchers (must succeed for a useful brief).

All functions are plain callables with no shared mutable state — safe to run
in a ThreadPoolExecutor. Each imports its dependency lazily inside the function
so module-level import failures never block the router.
"""
import logging
from ..cache import lazy
from ..config import resolve_tiers

logger = logging.getLogger(__name__)


def fetch_macro_regime() -> dict:
    try:
        from live_monitoring.agents.economic.macro_regime_detector import MacroRegimeDetector
        return lazy('macro', MacroRegimeDetector).get_regime()
    except Exception as e:
        logger.warning(f"MacroRegime failed: {e}")
        return {'error': str(e)}


def fetch_fedwatch() -> dict:
    try:
        from live_monitoring.enrichment.apis.fedwatch_diy import FedWatchEngine
        fw = lazy('fedwatch', FedWatchEngine).get_probabilities()
        if fw and not fw.get('error'):
            next_mtg = fw.get('next_meeting', {})
            return {
                'rate_path': {
                    'current_rate':     fw.get('current_rate'),
                    'current_range':    fw.get('current_range'),
                    'may_p_hike':       next_mtg.get('p_hike_25', 0),
                    'may_p_hold':       next_mtg.get('p_hold', 100),
                    'may_p_cut':        next_mtg.get('p_cut_25', 0),
                    'terminal_bps':     fw.get('total_cuts_bps', 0),
                    'meetings_count':   len(fw.get('rate_path', [])),
                    'next_meeting':     next_mtg.get('label', ''),
                    'days_away':        next_mtg.get('days_away', 0),
                    'regime_multiplier': (
                        1.6 if next_mtg.get('p_hike_25', 0) > 25
                        else 1.6 if fw.get('rate_path', [{}])[-1].get('p_cut_25', 0) > 60
                        else 1.0
                    ),
                },
                'full_path': fw.get('rate_path', []),
            }
        return {'error': fw.get('error', 'No data'), 'rate_path': {}}
    except Exception as e:
        logger.warning(f"FedWatch failed: {e}")
        return {'error': str(e), 'rate_path': {}}


def fetch_veto() -> dict:
    try:
        from live_monitoring.enrichment.apis.te_calendar_scraper import TECalendarScraper
        te          = TECalendarScraper(cache_ttl=300)
        veto_result = te.get_hours_until_next_critical()
        if veto_result is not None:
            hours, event_name = veto_result
            event_name = event_name or 'critical release'
        else:
            hours, event_name = None, None

        resolved = resolve_tiers(event_name)
        tier, cap = 'NORMAL', 65
        if hours is not None:
            for tier_name, tier_hours, tier_cap in resolved:
                if tier_hours is not None and hours <= tier_hours:
                    tier, cap = tier_name, tier_cap
                    break

        upcoming_critical = []
        try:
            for ev in [e for e in te.get_us_calendar() if e.importance == 'CRITICAL'][:5]:
                upcoming_critical.append({
                    'event': ev.event, 'date': ev.date,
                    'time': ev.time, 'consensus': ev.consensus, 'previous': ev.previous,
                })
        except Exception:
            pass

        return {
            'hours_away':        round(hours, 1) if hours is not None else None,
            'next_event':        event_name,
            'tier':              tier,
            'confidence_cap':    cap,
            'upcoming_critical': upcoming_critical,
        }
    except Exception as e:
        logger.warning(f"Economic veto failed: {e}")
        return {'error': str(e)}


def fetch_nowcast() -> dict:
    try:
        from live_monitoring.enrichment.apis.cleveland_fed_nowcast import ClevelandFedNowcast
        nowcast = ClevelandFedNowcast().get_nowcast()
        if nowcast:
            return {
                'cpi_mom':      nowcast.cpi_mom,
                'core_cpi_mom': nowcast.core_cpi_mom,
                'pce_mom':      nowcast.pce_mom,
                'core_pce_mom': nowcast.core_pce_mom,
                'cpi_yoy':      nowcast.cpi_yoy,
                'pce_yoy':      nowcast.pce_yoy,
                'updated':      nowcast.updated,
            }
        return {'error': 'No data returned'}
    except Exception as e:
        logger.warning(f"Nowcast failed: {e}")
        return {'error': str(e)}


def fetch_thresholds() -> dict:
    try:
        from dotenv import load_dotenv
        load_dotenv()
        import os
        fred_key = os.getenv("FRED_API_KEY", "")
        if not fred_key:
            return {'error': 'FRED_API_KEY not configured', 'fred_key_present': False}
        from live_monitoring.enrichment.apis.dynamic_threshold_engine import DynamicThresholdEngine
        dte = DynamicThresholdEngine(fred_api_key=fred_key)
        thresholds = {}
        for evt_name, consensus in [('Core PCE Price Index MoM', 0.3), ('Non Farm Payrolls', 200), ('CPI MoM', 0.3)]:
            dt = dte.get_dynamic_thresholds(evt_name, te_consensus=consensus)
            if dt:
                key = evt_name.lower().replace(' ', '_').replace('_price_index_mom', '').replace('_mom', '')
                thresholds[key] = {
                    'HOT': dt.thresholds.get('HOT'), 'COLD': dt.thresholds.get('COLD'),
                    'consensus': dt.consensus, 'std_dev': dt.std_dev,
                }
        return thresholds or {'error': 'All threshold lookups returned None', 'fred_key_present': True}
    except Exception as e:
        logger.warning(f"Dynamic thresholds failed: {e}")
        return {'error': str(e)}


def fetch_hidden_hands() -> dict:
    """Hidden hands via BrainManager singleton.
    use_cache=True leverages BrainManager's 15-min TTL cache.
    We do NOT call _ensure_hidden_hands_data() here — that triggers
    a full scraper run (FedOfficialsEngine) which allocates ~50MB.
    The scraper should run on a separate schedule, not per-brief."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        from live_monitoring.core.brain_manager import BrainManager
        report = lazy('brain', BrainManager).get_report(use_cache=True)
        hh = report.get('hidden_hands', {})
        return {
            'politician_cluster': hh.get('politician_cluster', hh.get('pol_cluster_count', 0)),
            'hot_tickers':        hh.get('hot_tickers', []),
            'insider_net_usd':    hh.get('insider_net_usd', 0),
            'divergence_boost':   report.get('divergence_boost', 0),
            'fed_tone':           report.get('fed_overall_tone', 'NEUTRAL'),
            'hawk_count':         report.get('hawk_count', 0),
            'dove_count':         report.get('dove_count', 0),
            'spouse_alerts':      len(report.get('spouse_trade_alerts', [])),
            'finnhub_signals':    report.get('finnhub_signals', []),
            'top_divergence':     report.get('top_divergence', None),
        }
    except Exception as e:
        logger.warning(f"Hidden hands failed: {e}")
        return {'error': str(e)}


def fetch_gex_shared() -> dict:
    """Fetch GEX data ONCE. Result is shared with fetch_derivatives and
    fetch_kill_chain_from_shared to avoid duplicate yfinance downloads (~80MB each)."""
    try:
        from live_monitoring.enrichment.apis.gex_calculator import GEXCalculator
        calc = lazy('gex', lambda: GEXCalculator(cache_ttl=300))
        gex  = calc.compute_gex('SPY')
        if not gex:
            return {'error': 'No GEX data'}
        return {
            '_raw': gex,  # pass raw object for kill chain
            'spot_price': gex.spot_price,
            'total_gex': gex.total_gex,
            'gamma_regime': gex.gamma_regime,
            'gamma_flip': gex.gamma_flip,
            'max_pain': gex.max_pain,
            'gamma_walls': [{'strike': w.strike, 'gex': round(w.gex, 2), 'signal': w.signal or 'SUPPORT'} for w in (gex.gamma_walls or [])[:5]],
            'negative_zones': [{'strike': z.strike, 'gex': round(z.gex, 2)} for z in (gex.negative_zones or [])[:3]],
            'narrative': calc.get_narrative('SPY') if hasattr(calc, 'get_narrative') else '',
        }
    except Exception as e:
        logger.warning(f"GEX shared fetch failed: {e}")
        return {'error': str(e)}


def fetch_cot_shared() -> dict:
    """Fetch COT data ONCE. Shared with fetch_derivatives and kill chain."""
    try:
        from live_monitoring.enrichment.apis.cot_client import COTClient
        cot    = lazy('cot', lambda: COTClient(cache_ttl=300))
        es_pos = cot.get_position('ES')
        if not es_pos:
            return {'error': 'No COT data'}
        es_div = cot.get_divergence_signal('ES')
        return {
            'specs_net':    es_pos.specs_net,
            'comm_net':     es_pos.comm_net,
            'open_interest': es_pos.open_interest,
            'report_date':  es_pos.report_date,
            'divergent':    es_div.get('divergent', False),
            'description':  es_div.get('description', ''),
            'divergence':   es_div,
            'narrative':    cot.get_narrative('ES') if hasattr(cot, 'get_narrative') else '',
        }
    except Exception as e:
        logger.warning(f"COT shared fetch failed: {e}")
        return {'error': str(e)}


def build_derivatives(gex_shared: dict, cot_shared: dict) -> dict:
    """Build derivatives layer from pre-fetched GEX + COT data. ZERO new API calls."""
    deriv: dict = {}
    if not gex_shared.get('error'):
        spot     = gex_shared.get('spot_price', 0)
        max_pain = gex_shared.get('max_pain')
        total_gex_raw = gex_shared.get('total_gex', 0) or 0
        deriv = {
            'gex_regime':             gex_shared.get('gamma_regime', 'UNKNOWN'),
            'total_gex':              total_gex_raw,  # backward compatible
            'total_gex_raw':          total_gex_raw,
            'total_gex_millions':     round(total_gex_raw / 1_000_000, 3),
            'gex_units':              {
                'raw_notional': 'absolute_notional',
                'millions_notional': 'USD_millions',
            },
            'gex_symbol':             'SPY',
            'spot':                   spot,
            'gamma_flip':             gex_shared.get('gamma_flip'),
            'max_pain':               max_pain,
            'distance_from_max_pain': round(spot - max_pain, 2) if spot and max_pain else None,
            'put_wall':               gex_shared['negative_zones'][0]['strike'] if gex_shared.get('negative_zones') else None,
            'call_wall':              gex_shared['gamma_walls'][0]['strike'] if gex_shared.get('gamma_walls') else None,
            'top_walls':              gex_shared.get('gamma_walls', [])[:3],
        }
    else:
        deriv = {
            'error': gex_shared.get('error', 'GEX unavailable'),
            'total_gex': 0,
            'total_gex_raw': 0,
            'total_gex_millions': 0.0,
            'gex_units': {
                'raw_notional': 'absolute_notional',
                'millions_notional': 'USD_millions',
            },
            'gex_symbol': 'SPY',
            'max_pain': None,
            'put_wall': None,
            'call_wall': None,
            'top_walls': [],
        }

    if not cot_shared.get('error'):
        deriv['cot_spec_net']  = cot_shared.get('specs_net')
        deriv['cot_spec_side'] = 'SHORT' if (cot_shared.get('specs_net', 0)) < 0 else 'LONG'
        deriv['cot_divergent'] = cot_shared.get('divergent', False)
        deriv['cot_trap']      = cot_shared.get('description', '')

    return deriv


def build_kill_chain(gex_shared: dict, cot_shared: dict, fedwatch_data: dict, darkpool_data: dict = None) -> dict:
    """Build kill chain from pre-fetched shared data.
    NO new API calls — reuses GEX/COT/FedWatch that were already fetched.
    This is the key deduplication that prevents OOM."""
    try:
        from .kc_mismatch_lite import detect_mismatches_from_shared, compute_alert_level, generate_narrative, generate_signals_from_shared
        mismatches = detect_mismatches_from_shared(gex_shared, cot_shared, fedwatch_data, darkpool_data)
        alert_level = compute_alert_level(mismatches)
        narrative = generate_narrative(alert_level, mismatches, gex_shared, cot_shared, fedwatch_data)
        signals = generate_signals_from_shared(gex_shared, cot_shared)
        layers_active = sum(1 for d in [gex_shared, cot_shared, fedwatch_data, darkpool_data] if d and not d.get('error'))
        return {
            'alert_level':      alert_level,
            'layers_active':    layers_active + 1,  # +1 for the mismatch detector itself
            'narrative':        narrative[:500],
            'mismatches_count': len(mismatches),
            'signals':          signals,
        }
    except Exception as e:
        logger.warning(f"Kill Chain (lite) failed: {e}")
        # Fallback: run the old engine if lite fails
        try:
            from live_monitoring.enrichment.apis.kill_chain_engine import KillChainEngine
            report = lazy('kc', KillChainEngine).run_full_scan()
            return {
                'alert_level':    report.alert_level,
                'layers_active':  report.layers_active,
                'narrative':      (report.narrative or '')[:200],
                'mismatches_count': len(report.mismatches or []),
                'signals': [],
            }
        except Exception as e2:
            logger.warning(f"Kill Chain fallback also failed: {e2}")
            return {'error': str(e2)}
