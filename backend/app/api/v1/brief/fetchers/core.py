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
    try:
        from dotenv import load_dotenv
        load_dotenv()
        from live_monitoring.core.brain_manager import BrainManager
        report = BrainManager().get_report()
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


def fetch_derivatives() -> dict:
    deriv: dict = {}
    try:
        from live_monitoring.enrichment.apis.gex_calculator import GEXCalculator
        calc  = lazy('gex', lambda: GEXCalculator(cache_ttl=300))
        gex   = calc.compute_gex('SPY')
        spot  = gex.spot_price if gex else 0
        max_pain = gex.max_pain if gex else None
        deriv = {
            'gex_regime':             gex.gamma_regime if gex else 'UNKNOWN',
            'total_gex':              gex.total_gex if gex else 0,
            'spot':                   spot,
            'gamma_flip':             gex.gamma_flip if gex else None,
            'max_pain':               max_pain,
            'distance_from_max_pain': round(spot - max_pain, 2) if spot and max_pain else None,
            'put_wall':               None,
            'call_wall':              None,
            'top_walls':              [],
        }
        if gex and gex.negative_zones:
            deriv['put_wall'] = gex.negative_zones[0].strike
        if gex and gex.gamma_walls:
            deriv['call_wall'] = gex.gamma_walls[0].strike
            deriv['top_walls'] = [
                {'strike': w.strike, 'gex': round(w.gex, 2), 'signal': w.signal or 'SUPPORT'}
                for w in gex.gamma_walls[:3]
            ]
    except Exception as e:
        logger.warning(f"GEX failed: {e}")
        deriv = {'error': str(e)}

    try:
        from live_monitoring.enrichment.apis.cot_client import COTClient
        cot    = COTClient(cache_ttl=300)
        es_pos = cot.get_position('ES')
        if es_pos:
            es_div = cot.get_divergence_signal('ES')
            deriv['cot_spec_net']  = es_pos.specs_net
            deriv['cot_spec_side'] = 'SHORT' if es_pos.specs_net < 0 else 'LONG'
            deriv['cot_divergent'] = es_div.get('divergent', False)
            deriv['cot_trap']      = es_div.get('description', '')
    except Exception as e:
        logger.warning(f"COT failed: {e}")

    return deriv


def fetch_kill_chain() -> dict:
    try:
        from live_monitoring.enrichment.apis.kill_chain_engine import KillChainEngine
        report = lazy('kc', KillChainEngine).run_full_scan()
        return {
            'alert_level':    report.alert_level,
            'layers_active':  report.layers_active,
            'narrative':      (report.narrative or '')[:200],
            'mismatches_count': len(report.mismatches or []),
        }
    except Exception as e:
        logger.warning(f"Kill Chain failed: {e}")
        return {'error': str(e)}
