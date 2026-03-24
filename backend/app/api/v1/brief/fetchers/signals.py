"""
brief/fetchers/signals.py — Economic signal fetchers (enriched/optional layers).

These are TIMEOUT_SIGNAL and TIMEOUT_ENRICHED tier — ok to fail gracefully.
Each function is a plain callable with no shared state.
"""
import logging
from ..cache import lazy

logger = logging.getLogger(__name__)


def fetch_adp_prediction() -> dict:
    try:
        from live_monitoring.enrichment.apis.adp_predictor import ADPPredictor
        return lazy('adp', ADPPredictor).predict()
    except Exception as e:
        logger.warning(f"ADP Predictor failed: {e}")
        return {'error': str(e)}


def fetch_gdp_nowcast() -> dict:
    try:
        from live_monitoring.enrichment.apis.atlanta_fed_gdpnow import AtlantaFedGDPNow
        return lazy('gdpnow', AtlantaFedGDPNow).get_estimate()
    except Exception as e:
        logger.warning(f"GDPNow failed: {e}")
        return {'error': str(e)}


def fetch_jobless_claims() -> dict:
    try:
        from live_monitoring.enrichment.apis.jobless_claims_predictor import JoblessClaimsPredictor
        return lazy('jobless', JoblessClaimsPredictor).predict()
    except Exception as e:
        logger.warning(f"Jobless Claims Predictor failed: {e}")
        return {'error': str(e)}


def fetch_pmi() -> dict:
    try:
        from live_monitoring.enrichment.apis.pmi_predictor import PMIPredictor
        return lazy('pmi', PMIPredictor).predict()
    except Exception as e:
        logger.warning(f"PMI Predictor failed: {e}")
        return {'error': str(e)}


def fetch_current_account() -> dict:
    try:
        from live_monitoring.enrichment.apis.current_account_monitor import CurrentAccountMonitor
        return lazy('current_account', CurrentAccountMonitor).predict()
    except Exception as e:
        logger.warning(f"Current Account Monitor failed: {e}")
        return {'error': str(e)}


def fetch_umich_sentiment() -> dict:
    try:
        from live_monitoring.enrichment.apis.michigan_monitors import MichiganSentimentMonitor
        return lazy('umich_sent', MichiganSentimentMonitor).predict()
    except Exception as e:
        logger.warning(f"Michigan Sentiment Monitor failed: {e}")
        return {'error': str(e)}


def fetch_umich_expectations() -> dict:
    try:
        from live_monitoring.enrichment.apis.michigan_monitors import MichiganExpectationsMonitor
        return lazy('umich_exp', MichiganExpectationsMonitor).predict()
    except Exception as e:
        logger.warning(f"Michigan Expectations Monitor failed: {e}")
        return {'error': str(e)}


def fetch_pivots() -> dict:
    """Pivot levels + EMA-200 + confluence zones for SPY."""
    try:
        from live_monitoring.enrichment.apis.pivot_calculator import PivotCalculator
        calc   = lazy('pivots', PivotCalculator)
        result = calc.compute('SPY')
        if not result:
            return {'error': 'PivotCalculator returned None'}

        spot = 0
        try:
            from live_monitoring.enrichment.apis.gex_calculator import GEXCalculator
            _gex = lazy('gex', lambda: GEXCalculator(cache_ttl=300))
            _r   = _gex.compute_gex('SPY')
            spot = _r.spot_price if _r else 0
        except Exception:
            pass

        THRESH      = 1.5
        sorted_lvls = sorted(result.all_levels_flat(), key=lambda x: x['price'])
        used, zones = set(), []
        for i, l1 in enumerate(sorted_lvls):
            if i in used:
                continue
            cluster = [l1]
            for j, l2 in enumerate(sorted_lvls):
                if j != i and j not in used and abs(l1['price'] - l2['price']) <= THRESH and l1['set'] != l2['set']:
                    cluster.append(l2)
                    used.add(j)
            if len(cluster) >= 3:
                used.add(i)
                avg = round(sum(c['price'] for c in cluster) / len(cluster), 2)
                zones.append({'level': avg, 'count': len(cluster)})
        zones.sort(key=lambda z: z['level'])

        return {
            'ema_200':          round(result.ema_200, 2) if result.ema_200 else None,
            'confluence_zones': zones,
            'next_above':       next((z['level'] for z in zones if z['level'] > spot), None) if spot else None,
            'next_below':       next((z['level'] for z in reversed(zones) if z['level'] < spot), None) if spot else None,
        }
    except Exception as e:
        logger.warning(f"Pivots fetch failed: {e}")
        return {'error': str(e)}


def fetch_squeeze_context() -> dict:
    """Short squeeze risk snapshot for SPY via yfinance."""
    try:
        import yfinance as yf
        t            = yf.Ticker('SPY')
        info         = t.info
        si_pct       = float(info.get('shortPercentOfFloat') or 0) * 100
        short_ratio  = float(info.get('shortRatio') or 0)
        current_price = float(info.get('currentPrice') or info.get('regularMarketPrice') or 0)

        _null = {'has_signal': False, 'score': None, 'short_interest_pct': None,
                 'days_to_cover': None, 'volume_ratio': None, 'price_change_5d': None,
                 'entry_price': None, 'stop_price': None, 'target_price': None, 'risk_reward_ratio': None}

        if current_price <= 0 or si_pct <= 0:
            return _null

        si_score     = min((si_pct / 30) * 40, 40)
        borrow_score = min(short_ratio * 2, 30)
        hist         = t.history(period='5d')
        if hist.empty:
            return {**_null, 'short_interest_pct': round(si_pct, 2), 'days_to_cover': round(short_ratio, 1)}

        cur          = float(hist['Close'].iloc[-1])
        ago          = float(hist['Close'].iloc[0])
        price_change = round(((cur - ago) / ago) * 100 if ago > 0 else 0.0, 2)
        vol_cur      = float(hist['Volume'].iloc[-1])
        vol_avg      = float(hist['Volume'].mean())
        vol_ratio    = round(vol_cur / vol_avg if vol_avg > 0 else 1.0, 2)
        vol_score    = min((vol_ratio - 1.0) * 10, 20) if vol_ratio > 1.0 else 0.0
        mom_score    = min(max(price_change, 0) * 0.5, 10)
        total_score  = round(si_score + borrow_score + vol_score + mom_score, 1)

        atr_proxy = (float(hist['High'].max()) - float(hist['Low'].min())) / 5
        entry = round(cur, 2)
        return {
            'has_signal':       total_score >= 30,
            'score':            total_score,
            'short_interest_pct': round(si_pct, 2),
            'days_to_cover':    round(short_ratio, 1) if short_ratio > 0 else None,
            'volume_ratio':     vol_ratio,
            'price_change_5d':  price_change,
            'entry_price':      entry,
            'stop_price':       round(entry - atr_proxy, 2),
            'target_price':     round(entry + atr_proxy * 3, 2),
            'risk_reward_ratio': round(3.0 if atr_proxy > 0 else 0.0, 2),
        }
    except Exception as e:
        logger.warning(f"Squeeze context fetch failed: {e}")
        return {'has_signal': False, 'score': None, 'short_interest_pct': None,
                'days_to_cover': None, 'volume_ratio': None, 'price_change_5d': None,
                'entry_price': None, 'stop_price': None, 'target_price': None,
                'risk_reward_ratio': None, 'error': str(e)}


def fetch_squeeze_watchlist() -> dict:
    """Score top squeeze candidates from watchlist (score >= 50)."""
    _WATCHLIST = [
        'GME', 'AMC', 'BBBY', 'MEME', 'SPCE', 'CLOV', 'WISH', 'WKHS',
        'LCID', 'RIVN', 'NKLA', 'RIDE', 'GOEV', 'HYLN', 'IDEX', 'SOLO',
        'BYND', 'OPAD', 'BARK', 'ZOME', 'EXPR', 'UPST', 'AFRM', 'OPEN',
    ]
    try:
        import yfinance as yf
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _score_one(sym: str):
            try:
                t    = yf.Ticker(sym)
                info = t.info
                si_pct      = float(info.get('shortPercentOfFloat') or 0) * 100
                short_ratio = float(info.get('shortRatio') or 0)
                if si_pct < 10:
                    return None
                price = float(info.get('currentPrice') or info.get('regularMarketPrice') or 0)
                if price <= 0:
                    return None
                si_score     = min((si_pct / 30) * 40, 40)
                borrow_score = min(short_ratio * 2, 30)
                hist = t.history(period='5d')
                if hist.empty:
                    vol_score = mom_score = 0.0
                else:
                    vol_cur = float(hist['Volume'].iloc[-1])
                    vol_avg = float(hist['Volume'].mean())
                    vol_ratio   = vol_cur / vol_avg if vol_avg > 0 else 1.0
                    vol_score   = min((vol_ratio - 1.0) * 10, 20) if vol_ratio > 1.0 else 0.0
                    cur, ago    = float(hist['Close'].iloc[-1]), float(hist['Close'].iloc[0])
                    pct5d       = ((cur - ago) / ago) * 100 if ago > 0 else 0.0
                    mom_score   = min(max(pct5d, 0) * 0.5, 10)
                total = round(si_score + borrow_score + vol_score + mom_score, 1)
                if total < 50:
                    return None
                return {'symbol': sym, 'score': total, 'short_interest_pct': round(si_pct, 1),
                        'days_to_cover': round(short_ratio, 1) if short_ratio > 0 else None,
                        'signal': 'SQUEEZE_CANDIDATE'}
            except Exception:
                return None

        results_list: list = []
        with ThreadPoolExecutor(max_workers=8) as inner:
            for f in as_completed({inner.submit(_score_one, sym): sym for sym in _WATCHLIST}):
                r = f.result()
                if r:
                    results_list.append(r)

        return {'top3': sorted(results_list, key=lambda x: x['score'], reverse=True)[:3]}
    except Exception as e:
        logger.warning(f"Squeeze watchlist fetch failed: {e}")
        return {'top3': [], 'error': str(e)}
