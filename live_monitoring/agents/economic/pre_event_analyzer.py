"""
Pre-Event Analyzer - Phase 3

Analyzes upcoming events and generates pre-positioning signals.

Runs 4 hours before each HIGH importance event.
Includes forecast/previous context, Fed Watch scenarios, and DP levels.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PreEventSignal:
    """Pre-event positioning signal"""
    event: Any  # EconomicEvent
    action: str  # LONG, SHORT, WAIT
    confidence: float
    reasoning: str
    predicted_move: float  # Expected SPY move %
    dp_levels: List[Dict]
    risk_reward: float
    entry: Optional[float] = None
    stop: Optional[float] = None
    target: Optional[float] = None


class PreEventAnalyzer:
    """
    Analyzes upcoming events and generates pre-positioning signals.
    
    Runs: 4 hours before each HIGH importance event
    Includes: Forecast/previous, Fed Watch scenarios, DP levels
    """
    
    def __init__(
        self,
        econ_engine,
        te_wrapper,
        fed_watch_monitor=None,
        dp_monitor=None,
        regime_detector=None
    ):
        """
        Initialize Pre-Event Analyzer.
        
        Args:
            econ_engine: EconomicIntelligenceEngine instance
            te_wrapper: TradingEconomicsWrapper instance
            fed_watch_monitor: FedMonitor instance (optional)
            dp_monitor: DPMonitor instance (optional)
            regime_detector: RegimeDetector instance (optional)
        """
        self.econ_engine = econ_engine
        self.te_wrapper = te_wrapper
        self.fed_watch_monitor = fed_watch_monitor
        self.dp_monitor = dp_monitor
        self.regime_detector = regime_detector
        
        logger.info("📊 PreEventAnalyzer initialized")
    
    def analyze_upcoming_event(self, event) -> Optional[PreEventSignal]:
        """
        Analyze upcoming event and generate pre-positioning recommendation.
        
        Args:
            event: EconomicEvent object
        
        Returns:
            PreEventSignal or None
        """
        try:
            # Get current Fed Watch probability
            fed_watch_prob = 89.0
            if self.fed_watch_monitor:
                status = self.fed_watch_monitor.get_status()
                if status:
                    fed_watch_prob = status.prob_cut
            
            # Get Fed Watch scenarios
            try:
                alert = self.econ_engine.get_pre_event_alert(
                    event_type=event.event.lower().replace(' ', '_'),
                    event_date=event.date,
                    event_time=event.time,
                    current_fed_watch=fed_watch_prob
                )
                
                weak_shift = alert.weak_scenario.predicted_fed_watch_shift
                strong_shift = alert.strong_scenario.predicted_fed_watch_shift
                swing = abs(weak_shift - strong_shift)
                
            except Exception as e:
                logger.debug(f"Prediction error: {e}")
                # Use static estimate
                swing = 3.0 * 2
                weak_shift = 3.0
                strong_shift = -3.0
            
            # Get DP levels near current price
            dp_levels = []
            if self.dp_monitor:
                try:
                    # Get nearby DP levels (within 0.5%)
                    # This would need to be implemented in DPMonitor
                    dp_levels = []  # Placeholder
                except:
                    pass
            
            # Get market regime
            regime = "NEUTRAL"
            if self.regime_detector:
                try:
                    regime = self.regime_detector.current_regime
                except:
                    pass
            
            # Determine action based on event category and forecast context
            action = "WAIT"
            confidence = 0.5
            reasoning = ""
            predicted_move = 0.0
            
            # Analyze based on category
            if event.category.value == "INFLATION":
                # Inflation events
                if event.forecast and event.previous:
                    try:
                        forecast_val = float(event.forecast.replace('%', ''))
                        previous_val = float(event.previous.replace('%', ''))
                        
                        if forecast_val > previous_val:
                            # Market expects higher inflation
                            # If it beats → HAWKISH → SHORT TLT
                            # If it misses → DOVISH → LONG TLT
                            action = "WAIT"  # Wait for release
                            reasoning = f"Forecast ({forecast_val}%) > Previous ({previous_val}%) → Market expects hot inflation. Wait for release."
                        else:
                            # Market expects lower inflation
                            action = "WAIT"
                            reasoning = f"Forecast ({forecast_val}%) < Previous ({previous_val}%) → Market expects cool inflation. Wait for release."
                    except:
                        pass
                
                # If Fed Watch is high (>70%), pre-position for HAWKISH scenario
                if fed_watch_prob > 70 and event.forecast:
                    try:
                        forecast_val = float(event.forecast.replace('%', ''))
                        previous_val = float(event.previous.replace('%', '')) if event.previous else 0
                        
                        if forecast_val > previous_val:
                            # Expecting hot inflation → SHORT TLT
                            action = "SHORT"
                            symbol = "TLT"
                            confidence = 0.65
                            reasoning = f"Fed Watch {fed_watch_prob:.0f}% + Hot inflation expected → Pre-position SHORT TLT"
                            predicted_move = -abs(swing) * 0.1  # Estimate TLT move
                    except:
                        pass
            
            elif event.category.value == "EMPLOYMENT":
                # Employment events (NFP, etc.)
                if fed_watch_prob > 70:
                    # High cut probability → Weak jobs = DOVISH = LONG TLT
                    action = "LONG"
                    symbol = "TLT"
                    confidence = 0.60
                    reasoning = f"Fed Watch {fed_watch_prob:.0f}% → Weak jobs expected → Pre-position LONG TLT"
                    predicted_move = abs(swing) * 0.1
            
            elif event.category.value == "GROWTH":
                # GDP events
                if regime == "RISK_ON":
                    # Risk-on regime → Strong GDP = LONG SPY
                    action = "LONG"
                    symbol = "SPY"
                    confidence = 0.55
                    reasoning = f"Risk-on regime + Strong GDP expected → Pre-position LONG SPY"
                    predicted_move = abs(swing) * 0.15
            
            # Calculate entry/stop/target if action is not WAIT
            entry = None
            stop = None
            target = None
            risk_reward = 0.0
            
            if action != "WAIT":
                # Get current price (simplified - would use real price fetcher)
                try:
                    import yfinance as yf
                    ticker = yf.Ticker(symbol if 'symbol' in locals() else "SPY")
                    hist = ticker.history(period='1d', interval='1m')
                    if not hist.empty:
                        current_price = float(hist['Close'].iloc[-1])
                        entry = current_price
                        
                        # Calculate stop/target (1.5:1 R/R minimum)
                        if predicted_move != 0:
                            move_pct = abs(predicted_move) / 100
                            if action == "LONG":
                                target = entry * (1 + move_pct * 1.5)
                                stop = entry * (1 - move_pct)
                            else:
                                target = entry * (1 - move_pct * 1.5)
                                stop = entry * (1 + move_pct)
                            
                            risk_reward = abs(target - entry) / abs(stop - entry) if stop != entry else 0
                except Exception as e:
                    logger.debug(f"Failed to calculate entry/stop/target: {e}")
            
            return PreEventSignal(
                event=event,
                action=action,
                confidence=confidence,
                reasoning=reasoning,
                predicted_move=predicted_move,
                dp_levels=dp_levels,
                risk_reward=risk_reward,
                entry=entry,
                stop=stop,
                target=target
            )
            
        except Exception as e:
            logger.error(f"Failed to analyze event: {e}")
            return None

