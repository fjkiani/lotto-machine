"""
Market Narrative Pipeline - V1

Goal (from narrative-master-strategy.mdc):
- For SPY / QQQ (initially), produce a structured narrative object explaining
  * WHY the market moved
  * Macro + sector + cross-asset (crypto) context
  * A → B → C causal chain
  * Direction, conviction, duration, risk environment
  * Sources (from Perplexity and internal data)

This is V1:
- Uses PerplexitySearchClient (real-time web narrative)
- Uses CryptoCorrelationDetector (BTC/ETH vs SPY)
- Uses UltimateChartExchangeClient (institutional overlay) if API key present
- Does NOT yet use a real EventLoader (stub only), but is structured to add it.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from live_monitoring.enrichment.narrative_logger import NarrativeLogger
from live_monitoring.enrichment.models.enriched_signal import RiskEnvironment
from live_monitoring.enrichment.narrative_validation import NarrativeValidationOrchestrator

# Modular pipeline components
from live_monitoring.enrichment.pipeline.perplexity_adapter import (
    build_perplexity_queries,
    run_perplexity_queries,
    NarrativeSource,
)
from live_monitoring.enrichment.pipeline.date_resolver import (
    resolve_trading_date,
    build_realized_move_header,
)
from live_monitoring.enrichment.pipeline.event_loader import (
    load_economic_events,
    extract_macro_data,
)
from live_monitoring.enrichment.pipeline.crypto_analyzer import (
    analyze_crypto_correlation,
    extract_cross_asset_data,
)
from live_monitoring.enrichment.pipeline.institutional_loader import (
    load_institutional_context,
    detect_divergences,
    synthesize_institutional_narrative,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class NarrativeSource:
    url: str
    snippet: str


@dataclass
class MarketNarrative:
    symbol: str
    date: str
    macro_narrative: str
    sector_narrative: str
    asset_narrative: str
    cross_asset_narrative: str
    causal_chain: str
    overall_direction: str  # "BULLISH" | "BEARISH" | "NEUTRAL"
    conviction: str         # "HIGH" | "MEDIUM" | "LOW"
    duration: str           # "INTRADAY" | "MULTI_DAY" | "WEEK"
    risk_environment: str   # "RISK_ON" | "RISK_OFF" | "NEUTRAL"
    sources: List[NarrativeSource]
    uncertainties: List[str]
    # Institutional vs mainstream breakdown (optional V1+ fields)
    institutional_reality: Optional[Dict[str, Any]] = None
    mainstream_narrative: Optional[Dict[str, Any]] = None
    divergences: Optional[List[Dict[str, Any]]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["sources"] = [asdict(s) for s in self.sources]
        return d


# ---------------------------------------------------------------------------
# EventLoader + Logger (PRODUCTION READY)
# ---------------------------------------------------------------------------

def load_event_schedule(date: Optional[str] = None) -> Dict[str, Any]:
    """
    Load economic calendar events with surprise scoring.
    
    Now uses real EventLoader instead of stub!
    """
    if date is None:
        date = datetime.utcnow().strftime("%Y-%m-%d")
    
    try:
        event_loader = EventLoader()
        events = event_loader.load_events(date)
        return events
    except Exception as e:
        logger.warning(f"⚠️  EventLoader failed, using empty schedule: {e}")
        return {
            "date": date,
            "macro_events": [],
            "earnings": [],
            "opex": False,
            "has_events": False
        }


def resolve_trading_date(symbol: str, requested_date: str) -> str:
    """
    Map a requested calendar date to the last completed trading session.
    """
    trading_date_str = requested_date
    try:
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d", interval="1d")
        if not hist.empty:
            last_trading_date = hist.index[-1].date()
            requested = datetime.strptime(requested_date, "%Y-%m-%d").date()
            if last_trading_date < requested:
                trading_date_str = last_trading_date.strftime("%Y-%m-%d")
    except Exception as e:
        logger.error("Error resolving trading date for %s: %s", symbol, e)
        trading_date_str = requested_date

    return trading_date_str


def collect_cross_asset_data(symbol: str, crypto_sent) -> Dict[str, Any]:
    """
    Collect cross-asset data for validation (Bitcoin, VIX, etc.)
    """
    import yfinance as yf
    
    data = {
        'btc_10day_change': 0.0,
        'btc_drawdown_from_high': 0.0,
        'btc_consecutive_losses': 0,
        'btc_1day_change': 0.0,
        'spy_1day_change': 0.0,
        'vix': 0.0
    }
    
    try:
        # Bitcoin 10-day change
        btc_ticker = yf.Ticker('BTC-USD')
        btc_hist = btc_ticker.history(period='1mo', interval='1d')
        if not btc_hist.empty and len(btc_hist) >= 10:
            btc_current = float(btc_hist['Close'].iloc[-1])
            btc_10d_ago = float(btc_hist['Close'].iloc[-10])
            data['btc_10day_change'] = ((btc_current / btc_10d_ago) - 1) * 100.0
            
            # Drawdown from high
            btc_high = float(btc_hist['Close'].max())
            data['btc_drawdown_from_high'] = ((btc_high - btc_current) / btc_high) * 100.0
            
            # Consecutive losses
            losses = 0
            for i in range(len(btc_hist) - 1, max(0, len(btc_hist) - 10), -1):
                if btc_hist['Close'].iloc[i] < btc_hist['Close'].iloc[i-1]:
                    losses += 1
                else:
                    break
            data['btc_consecutive_losses'] = losses
            
            # 1-day change
            if len(btc_hist) >= 2:
                btc_prev = float(btc_hist['Close'].iloc[-2])
                data['btc_1day_change'] = ((btc_current / btc_prev) - 1) * 100.0
        
        # SPY 1-day change
        spy_ticker = yf.Ticker(symbol)
        spy_hist = spy_ticker.history(period='5d', interval='1d')
        if not spy_hist.empty and len(spy_hist) >= 2:
            spy_current = float(spy_hist['Close'].iloc[-1])
            spy_prev = float(spy_hist['Close'].iloc[-2])
            data['spy_1day_change'] = ((spy_current / spy_prev) - 1) * 100.0
        
        # VIX
        vix_ticker = yf.Ticker('^VIX')
        vix_hist = vix_ticker.history(period='1d', interval='1d')
        if not vix_hist.empty:
            data['vix'] = float(vix_hist['Close'].iloc[-1])
    
    except Exception as e:
        logger.error(f"Error collecting cross-asset data: {e}")
    
    return data


def collect_price_action_data(symbol: str) -> Dict[str, Any]:
    """
    Collect price trend data for validation
    """
    import yfinance as yf
    
    data = {
        'spy_3day_trend': 'NEUTRAL'
    }
    
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period='5d', interval='1d')
        
        if not hist.empty and len(hist) >= 4:
            # Calculate 3-day trend
            close_today = float(hist['Close'].iloc[-1])
            close_3d_ago = float(hist['Close'].iloc[-4])
            pct_change = ((close_today / close_3d_ago) - 1) * 100.0
            
            if pct_change > 1.0:
                data['spy_3day_trend'] = 'UP'
            elif pct_change < -1.0:
                data['spy_3day_trend'] = 'DOWN'
            else:
                data['spy_3day_trend'] = 'NEUTRAL'
    
    except Exception as e:
        logger.error(f"Error collecting price action data: {e}")
    
    return data


def collect_macro_data(event_schedule: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract macro data from event schedule and narrative
    """
    data = {
        'pmi_services_miss': False,
        'pmi_manufacturing_miss': False,
        'consumer_sentiment': None
    }
    
    # Check event schedule for actual vs expected
    macro_events = event_schedule.get('macro_events', [])
    for event in macro_events:
        title = event.get('title', '').lower()
        
        # PMI misses
        if 'pmi' in title or 's&p global' in title:
            # If event has actual/forecast data, check for miss
            actual = event.get('actual')
            forecast = event.get('forecast')
            if actual is not None and forecast is not None:
                try:
                    if float(actual) < float(forecast):
                        if 'services' in title or 'service' in title:
                            data['pmi_services_miss'] = True
                        elif 'manufacturing' in title or 'manufact' in title:
                            data['pmi_manufacturing_miss'] = True
                except (ValueError, TypeError):
                    pass
        
        # Consumer sentiment
        if 'consumer sentiment' in title or 'michigan' in title:
            actual = event.get('actual')
            if actual is not None:
                try:
                    data['consumer_sentiment'] = float(actual)
                except (ValueError, TypeError):
                    pass
    
    return data


#
# Perplexity-specific helpers now live in
# live_monitoring/enrichment/pipeline/perplexity_adapter.py


def prepend_realized_move_header(
    symbol: str,
    trading_date_str: str,
    macro_narr: str,
) -> str:
    """
    Prepend a deterministic realized move line (close-to-close) to macro_narr.
    """
    try:
        import yfinance as yf

        tkr = yf.Ticker(symbol)
        hist_px = tkr.history(period="10d", interval="1d")
        if not hist_px.empty:
            tgt_date = datetime.strptime(trading_date_str, "%Y-%m-%d").date()
            idx_matches = [i for i, dt in enumerate(hist_px.index.date) if dt == tgt_date]
            if idx_matches:
                i = idx_matches[0]
                close_today = float(hist_px["Close"].iloc[i])
                if i > 0:
                    close_prev = float(hist_px["Close"].iloc[i - 1])
                    pct = (close_today / close_prev - 1.0) * 100.0
                    direction_label = "UP" if pct > 0 else "DOWN" if pct < 0 else "FLAT"
                    header = (
                        f"Realized {symbol} move on {trading_date_str}: "
                        f"closed at ${close_today:.2f} vs ${close_prev:.2f} "
                        f"({pct:+.2f}%), overall {direction_label} day.\n\n"
                    )
                    return header + macro_narr
    except Exception as e:
        logger.error("Error computing realized move header for %s: %s", symbol, e)

    return macro_narr


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

def market_narrative_pipeline(symbol: str, date: Optional[str] = None, 
                              enable_logging: bool = True) -> MarketNarrative:
    """
    End-to-end narrative for one symbol/date (V1 PRODUCTION).

    - Uses EventLoader for economic calendar + surprise scoring
    - Uses Perplexity for macro/sector/asset + BTC vs equities
    - Uses CryptoCorrelationDetector for structured crypto risk regime
    - Integrates institutional overlay from ChartExchange
    - Logs all outputs to logs/narratives/{DATE}/ for review
    
    Args:
        symbol: Ticker (SPY, QQQ, etc.)
        date: Date in YYYY-MM-DD (defaults to today)
        enable_logging: If True, persist all outputs via NarrativeLogger
    
    Returns:
        MarketNarrative object with complete context
    """
    symbol = symbol.upper()
    if date is None:
        date = datetime.utcnow().strftime("%Y-%m-%d")

    # Resolve the actual trading date we have data for
    trading_date_str = resolve_trading_date(symbol, date)
    
    # Compute daily move (kept inline for now, could be modularized later)
    daily_move: Dict[str, Any] = {
        "close": None,
        "prev_close": None,
        "pct_change": None,
        "direction": "UNKNOWN",
    }
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d", interval="1d")
        if not hist.empty and len(hist) > 1:
            close_today = float(hist["Close"].iloc[-1])
            prev_close = float(hist["Close"].iloc[-2])
            pct_change = (close_today / prev_close - 1) * 100.0
            direction = "UP" if pct_change > 0.25 else "DOWN" if pct_change < -0.25 else "FLAT"
            daily_move.update({
                "close": close_today,
                "prev_close": prev_close,
                "pct_change": pct_change,
                "direction": direction,
            })
    except Exception as e:
        logger.error("Error computing daily move for %s: %s", symbol, e)

    logger.info(
        "🧠 Running market_narrative_pipeline for %s on %s (trading_date=%s, move=%s)",
        symbol, date, trading_date_str, daily_move,
    )

    # Initialize logger
    narrative_logger = NarrativeLogger() if enable_logging else None

    # 1) Event schedule - use trading_date
    event_schedule_raw = load_economic_events(symbol, trading_date_str)
    # event_schedule_raw is a dict with "macro_events" key already
    event_schedule = event_schedule_raw if isinstance(event_schedule_raw, dict) else {"macro_events": event_schedule_raw}
    if narrative_logger:
        narrative_logger.log_event_schedule(symbol, event_schedule, trading_date_str)

    # 2) Crypto correlation analysis
    crypto_result = analyze_crypto_correlation(symbol, trading_date_str)
    crypto_regime = crypto_result.get("regime", "NEUTRAL")

    # 3) Institutional context (dark pool, max pain, etc.)
    inst_ctx = load_institutional_context(symbol, trading_date_str, crypto_regime)

    # 4) Build and run Perplexity queries (modularized)
    # Build price summary to anchor Perplexity to REAL direction
    price_summary = ""
    if daily_move["pct_change"] is not None and daily_move["close"] is not None:
        dir_word = {
            "UP": "up", "DOWN": "down", "FLAT": "flat", "UNKNOWN": "mixed"
        }.get(daily_move["direction"], "mixed")
        price_summary = (
            f"{symbol} closed {dir_word} {daily_move['pct_change']:.2f}% at "
            f"${daily_move['close']:.2f} on {trading_date_str}. "
        )
    
    queries = build_perplexity_queries(symbol, trading_date_str, inst_ctx)
    # Prepend price summary to first query for factual anchoring
    if queries and price_summary:
        queries[0] = price_summary + queries[0]
    
    pplx_narratives = run_perplexity_queries(queries)
    
    macro_narr = pplx_narratives.get("macro", "")
    sector_narr = pplx_narratives.get("sector", "")
    asset_narr = pplx_narratives.get("asset", "")
    cross_asset_narr = pplx_narratives.get("cross", "")
    uniq_sources = pplx_narratives.get("sources", [])

    # 5) Build causal chain & meta labels (very simple V1 logic)
    overall_direction = "NEUTRAL"
    conviction = "MEDIUM"
    duration = "INTRADAY"
    risk_env = "NEUTRAL"
    uncertainties: List[str] = []

    # If narratives mention downgrade/Fed/tech selloff, mark BEARISH / RISK_OFF
    macro_lower = macro_narr.lower()
    sector_lower = sector_narr.lower()
    cross_lower = cross_asset_narr.lower()

    if any(k in macro_lower for k in ["downgrade", "hawkish", "selloff", "risk-off", "risk off"]):
        overall_direction = "BEARISH"
        risk_env = "RISK_OFF"
        conviction = "HIGH"
        duration = "MULTI_DAY"
    elif any(k in macro_lower for k in ["rally", "risk-on", "risk on", "bullish"]):
        overall_direction = "BULLISH"
        risk_env = "RISK_ON"
        conviction = "HIGH"
        duration = "MULTI_DAY"

    # Use crypto regime as tie-breaker
    if crypto_regime:
        env = crypto_regime  # String: "RISK_OFF", "RISK_ON", "NEUTRAL"
        if env == "RISK_OFF" and overall_direction == "BEARISH":
            conviction = "HIGH"
        elif env == "RISK_ON" and overall_direction == "BULLISH":
            conviction = "HIGH"
        elif env != "NEUTRAL":
            uncertainties.append(f"Crypto regime {env} differs from equity narrative.")

    # Simple causal chain assembly (macro → cross-asset → price)
    causal_parts = []
    if "downgrade" in macro_lower:
        causal_parts.append("Moody's downgrade")
    if any(k in macro_lower for k in ["hawkish", "fed"]):
        causal_parts.append("hawkish Fed tone")
    if "yield" in macro_lower or "treasury" in macro_lower:
        causal_parts.append("Treasury yields spike")

    if "selloff" in macro_lower or "sell-off" in macro_lower or "selloff" in sector_lower:
        causal_parts.append(f"{symbol} selloff")
    if "tech" in sector_lower or "semis" in sector_lower or "chip" in sector_lower:
        causal_parts.append("tech/semis lead downside")

    if crypto_regime and crypto_regime == "RISK_OFF":
        causal_parts.append("BTC/crypto breakdown confirms risk-off")

    if len(causal_parts) >= 2:
        causal_chain = " → ".join(causal_parts)
    else:
        causal_chain = " | ".join(part for part in causal_parts) or "No clear causal chain (V1 heuristic)."

    # Prepend realized price move for the trading date (modularized)
    header = build_realized_move_header(symbol, trading_date_str)
    if header:
        macro_narr = header + macro_narr

    # Log mainstream narrative
    if narrative_logger:
        narrative_logger.log_mainstream_narrative(symbol, {
            "macro": macro_narr,
            "sector": sector_narr,
            "asset": asset_narr,
            "cross_asset": cross_asset_narr,
            "sources": [asdict(s) for s in uniq_sources]
        }, trading_date_str)

    # 6) Divergence detection + institutional narrative (modularized)
    # Pass trading_date to inst_ctx for divergence detection
    inst_ctx["date"] = trading_date_str
    
    divergences_result = detect_divergences(symbol, inst_ctx, pplx_narratives)
    divergences = divergences_result["detected"]
    
    # Log institutional stats
    if narrative_logger:
        narrative_logger.log_institutional_stats(symbol, inst_ctx, trading_date_str)
        narrative_logger.log_divergences(symbol, divergences, trading_date_str)
    
    # Synthesize institutional narrative
    institutional_narrative_text = synthesize_institutional_narrative(symbol, inst_ctx, divergences)
    inst_package = {
        "institutional_reality": {"summary": institutional_narrative_text},
        "mainstream_narrative": {"summary": macro_narr},
        "divergences": divergences
    }

    # 7) CRITICAL: Validate narrative with real-time data (Fix for feedback.mdc)
    logger.info("🔍 Running narrative validation...")
    
    # Collect validation data (modularized)
    cross_asset_data = extract_cross_asset_data(crypto_result)
    price_action_data = collect_price_action_data(symbol)  # TODO: modularize
    macro_data = extract_macro_data(event_schedule.get("macro_events", []))
    
    # Check if we have dark pool data
    has_dp_data = (inst_ctx.get('dark_pool', {}).get('pct') is not None)
    
    # Run validation
    validator = NarrativeValidationOrchestrator()
    validation_result = validator.validate_narrative(
        symbol=symbol,
        date=trading_date_str,
        narrative_direction=overall_direction,
        narrative_risk_env=risk_env,
        narrative_conviction=conviction,
        macro_data=macro_data,
        cross_asset_data=cross_asset_data,
        price_action=price_action_data,
        has_dp_data=has_dp_data
    )
    
    # Apply validated results
    overall_direction = validation_result['final_direction']
    risk_env = validation_result['final_risk_env']
    conviction = validation_result['final_conviction']
    
    # CRITICAL FIX: If direction is BEARISH, risk_env should be RISK_OFF
    if overall_direction == 'BEARISH' and risk_env == 'RISK_ON':
        risk_env = 'RISK_OFF'
        uncertainties.append("OVERRIDE: Direction BEARISH → Risk Environment changed to RISK_OFF")
    
    # Add validation details to uncertainties
    if validation_result['validation_errors']:
        for err in validation_result['validation_errors']:
            uncertainties.append(f"VALIDATION ERROR: {err}")
    
    if validation_result['validation_warnings']:
        for warn in validation_result['validation_warnings']:
            uncertainties.append(f"VALIDATION WARNING: {warn}")
    
    if validation_result['overrides_applied']:
        for override in validation_result['overrides_applied']:
            uncertainties.append(f"OVERRIDE: {override['type']} - {override['reason']}")

    narrative = MarketNarrative(
        symbol=symbol,
        date=trading_date_str,
        macro_narrative=macro_narr,
        sector_narrative=sector_narr,
        asset_narrative=asset_narr,
        cross_asset_narrative=cross_asset_narr,
        causal_chain=causal_chain,
        overall_direction=overall_direction,
        conviction=conviction,
        duration=duration,
        risk_environment=risk_env,
        sources=uniq_sources,
        uncertainties=uncertainties,
        institutional_reality=inst_package.get("institutional_reality"),
        mainstream_narrative=inst_package.get("mainstream_narrative"),
        divergences=inst_package.get("divergences"),
    )
    
    # Log final narrative
    if narrative_logger:
        narrative_logger.log_final_narrative(symbol, narrative.to_dict(), trading_date_str)

    logger.info("✅ market_narrative_pipeline complete for %s on %s (trading_date=%s)", symbol, date, trading_date_str)
    logger.info(f"   Final call: {overall_direction} / {risk_env} / {conviction}")
    return narrative


def _demo() -> None:
    """
    Quick demo:
        PERPLEXITY_API_KEY=... python -m live_monitoring.enrichment.market_narrative_pipeline
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    today = datetime.utcnow().strftime("%Y-%m-%d")

    for symbol in ["SPY", "QQQ"]:
        print("=" * 120)
        print(f"🧪 MARKET NARRATIVE PIPELINE DEMO - {symbol} {today}")
        print("=" * 120)
        try:
            mn = market_narrative_pipeline(symbol, today)
        except Exception as e:
            print(f"❌ Pipeline failed for {symbol}: {e}")
            continue

        d = mn.to_dict()
        print(json.dumps(d, indent=2)[:4000])  # truncate for console
        print()


if __name__ == "__main__":
    _demo()


