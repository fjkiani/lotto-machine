#!/usr/bin/env python3
"""
SIGNAL GENERATOR - Pure signal generation logic
- Takes institutional context + current price
- Generates signals based on rules
- Returns structured signal objects
"""

from dataclasses import dataclass
from typing import Optional, List, Union
from datetime import datetime
import logging
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add paths
sys.path.append(str(Path(__file__).parent.parent.parent / 'core'))
sys.path.append(str(Path(__file__).parent))

from ultra_institutional_engine import UltraInstitutionalEngine, UltraSignal, InstitutionalContext
from reddit_sentiment import RedditSentimentAnalyzer
from gamma_exposure import GammaExposureTracker
from lottery_signals import SignalType, SignalAction, LiveSignal, LotterySignal
from zero_dte_strategy import ZeroDTEStrategy
from volatility_expansion import VolatilityExpansionDetector

# Import narrative pipeline for signal enrichment
try:
    sys.path.append(str(Path(__file__).parent.parent / 'enrichment'))
    from market_narrative_pipeline import market_narrative_pipeline
    NARRATIVE_AVAILABLE = True
except ImportError:
    NARRATIVE_AVAILABLE = False
    logger.warning("⚠️  Narrative pipeline not available - signals will not be enriched")

# Import economic calendar (FRED-based, replaces dead Trading Economics exploiter)
try:
    from live_monitoring.enrichment.apis.econ_calendar import EconCalendar
    ECONOMIC_EXPLOITER_AVAILABLE = True
except ImportError:
    ECONOMIC_EXPLOITER_AVAILABLE = False

# Import TE Calendar for CPI/GDP/PPI veto (FRED misses these as market movers)
try:
    from live_monitoring.enrichment.apis.te_calendar_scraper import TECalendarScraper
    TE_CALENDAR_AVAILABLE = True
except ImportError:
    TE_CALENDAR_AVAILABLE = False

logger = logging.getLogger(__name__)

# Note: LiveSignal is now imported from lottery_signals.py (new structure)
# Removed old LiveSignal definition to use new structure

# Import Trap Matrix Orchestrator
try:
    sys.path.append(str(Path(__file__).parent.parent / 'enrichment' / 'apis'))
    from trap_matrix_orchestrator import TrapMatrixOrchestrator
    TRAP_MATRIX_AVAILABLE = True
except ImportError:
    TRAP_MATRIX_AVAILABLE = False
    logger.warning("⚠️  Trap Matrix not available - signals will not be vetoed by danger zones")

# Import Config for Mismatch Rules
try:
    sys.path.append(str(Path(__file__).parent.parent.parent / 'backend' / 'app' / 'core'))
    import kill_chain_config as kc_config
except ImportError as e:
    kc_config = None
    logger.warning(f"⚠️  Kill Chain Config not found: {e}")

class SignalGenerator:
    """Generate signals from institutional intelligence"""
    
    def __init__(self, min_master_confidence: float = 0.75,
                 min_high_confidence: float = 0.50,  # LOWERED from 0.60 for testing
                 api_key: str = None,
                 use_sentiment: bool = True,
                 use_gamma: bool = True,
                 use_lottery_mode: bool = True,
                 lottery_confidence_threshold: float = 0.80,
                 use_narrative: bool = True):
        self.min_master_confidence = min_master_confidence
        self.min_high_confidence = min_high_confidence
        self.use_sentiment = use_sentiment
        self.use_gamma = use_gamma
        self.use_lottery_mode = use_lottery_mode
        self.lottery_threshold = lottery_confidence_threshold
        self.use_narrative = use_narrative and NARRATIVE_AVAILABLE
        self.narrative_cache = {}  # Cache narrative by (symbol, date)
        
        # Initialize trap matrix orchestrator
        if TRAP_MATRIX_AVAILABLE:
            try:
                self.trap_orchestrator = TrapMatrixOrchestrator()
            except Exception as e:
                logger.warning(f"Failed to init Trap Matrix: {e}")
                self.trap_orchestrator = None
        else:
            self.trap_orchestrator = None
        self.narrative_cache = {}  # Cache narrative by (symbol, date)
        
        # Initialize sentiment analyzer if enabled
        if self.use_sentiment and api_key:
            try:
                self.sentiment_analyzer = RedditSentimentAnalyzer(api_key=api_key)
                logger.info("📱 Reddit sentiment analyzer enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize sentiment analyzer: {e}")
                self.sentiment_analyzer = None
                self.use_sentiment = False
        else:
            self.sentiment_analyzer = None
        
        # Initialize gamma tracker if enabled
        if self.use_gamma:
            try:
                self.gamma_tracker = GammaExposureTracker(api_key=api_key)
                logger.info("📊 Gamma exposure tracker enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize gamma tracker: {e}")
                self.gamma_tracker = None
                self.use_gamma = False
        else:
            self.gamma_tracker = None
        
        # Initialize lottery components if enabled
        if self.use_lottery_mode:
            try:
                self.zero_dte_strategy = ZeroDTEStrategy()
                self.vol_detector = VolatilityExpansionDetector()
                logger.info("🎰 Lottery mode enabled")
                logger.info(f"   Lottery threshold: {lottery_confidence_threshold:.0%}")
            except Exception as e:
                logger.warning(f"Failed to initialize lottery components: {e}")
                self.zero_dte_strategy = None
                self.vol_detector = None
                self.use_lottery_mode = False
        else:
            self.zero_dte_strategy = None
            self.vol_detector = None
        
        logger.info("🎯 Signal Generator initialized")
        logger.info(f"   Master threshold: {min_master_confidence:.0%}")
        logger.info(f"   High confidence threshold: {min_high_confidence:.0%}")
        logger.info(f"   Sentiment filtering: {'enabled' if self.use_sentiment else 'disabled'}")
        logger.info(f"   Gamma filtering: {'enabled' if self.use_gamma else 'disabled'}")
        logger.info(f"   Lottery mode: {'enabled' if self.use_lottery_mode else 'disabled'}")
        logger.info(f"   Narrative enrichment: {'enabled' if self.use_narrative else 'disabled'}")
    
    def generate_signals(self, symbol: str, current_price: float,
                        inst_context: InstitutionalContext,
                        minute_bars=None,
                        order_flow_imbalance: Optional[object] = None, # New parameter
                        account_value: float = 100000.0) -> List[Union[LiveSignal, LotterySignal]]:
        """
        Generate signals from institutional context + real-time momentum + lottery opportunities
        
        Args:
            symbol: Ticker symbol
            current_price: Current price
            inst_context: Institutional context (yesterday's data)
            minute_bars: Optional DataFrame with recent minute bars for momentum detection
            account_value: Account value for position sizing
        
        Returns:
            List of LiveSignal or LotterySignal objects (regular + lottery)
        """
        all_signals = []
        
        try:
            # STEP 1: Generate regular signals (always)
            regular_signals = self._generate_regular_signals(
                symbol, current_price, inst_context, minute_bars
            )
            all_signals.extend(regular_signals)
            
            # STEP 2: If lottery mode enabled, check for lottery opportunities
            if self.use_lottery_mode and self.zero_dte_strategy and self.vol_detector:
                lottery_signals = self._generate_lottery_signals(
                    symbol,
                    current_price,
                    regular_signals,
                    account_value,
                    minute_bars=minute_bars,
                )
                all_signals.extend(lottery_signals)
            
            # STEP 3: Apply narrative enrichment (if enabled)
            if self.use_narrative and all_signals:
                enriched_signals = self._apply_narrative_enrichment(symbol, all_signals)
            else:
                enriched_signals = all_signals
            
            # STEP 4: Apply economic risk management
            risk_adjusted_signals = self._apply_economic_risk_management(
                symbol, enriched_signals
            )

            # STEP 4.5: Trap Matrix Vetoes & Narrative Divergence (ALPHA'S KILL SHOT)
            risk_adjusted_signals = self._apply_holistic_kill_shots(
                symbol, current_price, inst_context, risk_adjusted_signals
            )

            # STEP 5: Apply master filters
            filtered_signals = self._apply_master_filters(risk_adjusted_signals)

            return filtered_signals
            
        except Exception as e:
            logger.error(f"Error generating signals: {e}")
            return []
            
    def _apply_holistic_kill_shots(self, symbol: str, current_price: float, inst_context: InstitutionalContext, signals: List) -> List:
        """Apply Trap Matrix vetoes and Narrative divergence rules (Alpha's Kill Shots)."""
        valid_signals = []
        
        # 1. Get Trap Matrix Zones
        is_danger_zone = False
        if TRAP_MATRIX_AVAILABLE and self.trap_orchestrator:
            try:
                # Get current state from the orchestrator
                # Note: For backtesting, this must be mocked or cached per timestamp
                trap_state = self.trap_orchestrator.get_current_state(symbol)
                
                # Check if current price is within any active trap zone
                for t in (trap_state.traps or []):
                    # We consider it a danger zone if we are inside the trap price bounds
                    if t.price_min <= current_price <= t.price_max:
                        is_danger_zone = True
                        logger.warning(f"⚠️ {symbol} is in Trap Matrix Danger Zone: {t.trap_type}")
                        break
            except Exception as e:
                logger.error(f"Trap Matrix evaluation failed: {e}")
                
        # 2. Get Narrative Divergence
        divergence_score = 0
        narrative_obj = getattr(inst_context, 'narrative', None)
        if NARRATIVE_AVAILABLE and narrative_obj:
            divergences = getattr(narrative_obj, 'divergences', []) or []
            for div in divergences:
                sev = div.get('severity', 'LOW').upper()
                if sev == 'HIGH': divergence_score += 5
                elif sev == 'MEDIUM': divergence_score += 3
                else: divergence_score += 1
                
        # 2.5 Fed Tone vs Shadow Dark Loading (The Ultimate Kill Shot Divergence)
        macro_ctx = getattr(inst_context, 'macro_context', None)
        if macro_ctx:
            fed_tone = getattr(macro_ctx, 'fed_official_sentiment', 'NEUTRAL').upper()
            dp_vol = getattr(inst_context, 'dp_total_volume', 0)
            dp_spike = dp_vol > (kc_config.DP_THRESHOLDS["SPIKE_VOLUME"] if kc_config else 2_000_000)
            
            if fed_tone == 'HAWKISH' and dp_spike:
                # Fed is projecting fear, but shadows are loading heavy long volume
                logger.warning(f"🚨 FED DIVERGENCE: Hawkish tone but massive Dark Pool loading ({dp_vol:,.0f})")
                divergence_score += 7
            elif fed_tone == 'DOVISH' and dp_vol < (kc_config.DP_THRESHOLDS["LOW_VOLUME"] if kc_config else 500_000):
                # Fed is projecting safety, but shadows are completely absent
                logger.warning(f"🚨 FED DIVERGENCE: Dovish tone but ghost town Dark Pools ({dp_vol:,.0f})")
                divergence_score += 7

        # 2.7 Hidden Conviction Layer (Fed Officials Brain)
        try:
            from live_monitoring.core.brain_manager import BrainManager
            brain_manager = BrainManager()
            brain_report = brain_manager.get_report()
            
            if brain_report:
                boost = brain_report.get("divergence_boost", 0)
                if boost != 0:
                    divergence_score += boost
                    for reason in brain_report.get("reasons", []):
                        logger.warning(f"🧠 BRAIN: {reason}")
                        
        except Exception as e:
            logger.debug(f"Hidden conviction layer skipped: {e}")

        # 2.8 COT Extreme Divergence — Regime Indicator
        # Backtest: specs < -100K + comms > +50K → 72.9% 1-month win rate (N=48, p=0.053)
        # This is a REGIME overlay, not a timing signal. Bias long for next 30 days.
        try:
            from live_monitoring.enrichment.apis.cot_client import COTClient
            cot_client = COTClient(cache_ttl=3600)  # 1hr cache — COT is weekly
            cot_div = cot_client.get_divergence_signal("ES")
            
            if cot_div and cot_div.get("divergent"):
                specs_net = cot_div.get("specs_net", 0)
                comm_net = cot_div.get("comm_net", 0)
                
                # EXTREME divergence: specs heavy short + comms heavy long
                if specs_net < -100_000 and comm_net > 50_000:
                    divergence_score += 3  # Conservative (+3 not +7, p=0.053 is borderline)
                    logger.warning(
                        f"📋 COT EXTREME DIVERGENCE: Specs {specs_net:+,} | Comms {comm_net:+,} "
                        f"→ +3 divergence boost (72.9% 1-month WR, N=48)"
                    )
                elif specs_net < -50_000 and comm_net > 25_000:
                    divergence_score += 1  # Mild divergence, small boost
                    logger.info(f"📋 COT divergence: Specs {specs_net:+,} | Comms {comm_net:+,} → +1 boost")
        except Exception as e:
            logger.debug(f"COT divergence check skipped: {e}")

        # 2.9 GEX Regime Detection — Volatility Predictor
        # Backtest: GEX predicts vol (p<0.0001), NOT direction.
        # Pos GEX: fwd vol 10.9%, tail risk 8.7%. Neg GEX: fwd vol 57.1%, tail risk 85.7%.
        # GEX regime determines HOW MUCH to trust other signals, not direction.
        gex_regime = "UNKNOWN"
        try:
            gex_pressure = inst_context.gamma_pressure
            if gex_pressure >= 0.6:
                gex_regime = "STRONG_POSITIVE"
                # Low vol regime — signals are MORE reliable, moves are dampened
                divergence_score += 1
                logger.info(f"📊 GEX REGIME: Strong Positive ({gex_pressure:.2f}) → low vol, signals reliable")
            elif gex_pressure >= 0.4:
                gex_regime = "MILD_POSITIVE"
                logger.info(f"📊 GEX REGIME: Mild Positive ({gex_pressure:.2f}) → moderate vol")
            elif gex_pressure >= 0.2:
                gex_regime = "MILD_NEGATIVE"
                # Higher vol — signals less reliable, but bounces bigger
                logger.warning(f"📊 GEX REGIME: Mild Negative ({gex_pressure:.2f}) → elevated vol, wider stops needed")
            else:
                gex_regime = "STRONG_NEGATIVE"
                # Extreme vol — tail risk 85.7%, but V-shaped bounces
                logger.warning(
                    f"📊 GEX REGIME: Strong Negative ({gex_pressure:.2f}) → "
                    f"EXTREME vol (85.7% tail risk), force paper trade"
                )
        except Exception as e:
            logger.debug(f"GEX regime check skipped: {e}")

        # 2.10 Combined Signal: GEX+ AND COT Divergence (THE MONEY SIGNAL)
        # Backtest: 73.4% 20d win rate (N=670, p<0.0001 on vol)
        # This is the strongest kill chain signal we have.
        cot_extreme_active = False
        try:
            # Check if COT extreme was triggered in 2.8
            if 'cot_div' in dir() and cot_div and cot_div.get("divergent"):
                specs_net_check = cot_div.get("specs_net", 0)
                comm_net_check = cot_div.get("comm_net", 0)
                cot_extreme_active = specs_net_check < -100_000 and comm_net_check > 50_000
        except Exception:
            pass

        if cot_extreme_active and gex_regime in ("STRONG_POSITIVE", "MILD_POSITIVE"):
            divergence_score += 2  # Combined boost on top of individual COT +3
            logger.warning(
                f"🔥 COMBINED SIGNAL: GEX+ ({gex_regime}) + COT Extreme Divergence → "
                f"+2 extra boost (73.4% 20d WR, N=670)"
            )

        # 3. Apply Vetoes and Boosts
        for sig in signals:
            # Alpha Kill Shot A: Trap Matrix Veto
            if is_danger_zone:
                logger.warning(f"🚫 VETO {sig.symbol} {sig.direction}: Trap Matrix Danger Zone")
                continue # Kill signal
                
            # Alpha Kill Shot B: Narrative Divergence Kill/Boost
            if divergence_score > 7:
                logger.info(f"🚀 BOOST {sig.symbol} {sig.direction}: High Narrative Divergence ({divergence_score})")
                sig.confidence = min(0.99, sig.confidence + 0.15)
                # Also attach divergence info for session replay reporting
                sig.divergence_score = divergence_score
            elif divergence_score < 5 and narrative_obj:
                # If we parsed narrative and divergence is low, kill the signal
                logger.warning(f"🚫 VETO {sig.symbol} {sig.direction}: Low Narrative Divergence ({divergence_score} < 5)")
                continue
                
            # Alpha Kill Shot C: Dark Position Spike + GEX Flip = Force Paper Trade
            # We approximate "GEX flip" via the 0-DTE proxy or institutional proxy
            gex_pressure = inst_context.gamma_pressure
            dp_spike = inst_context.dp_total_volume > (kc_config.DP_THRESHOLDS["SPIKE_VOLUME"] if kc_config else 2_000_000)
            
            flip_lower = kc_config.GEX_THRESHOLDS["FLIP_NORMALIZED_LOWER"] if kc_config else 0.3
            flip_upper = kc_config.GEX_THRESHOLDS["FLIP_NORMALIZED_UPPER"] if kc_config else 0.8
            
            if dp_spike and (gex_pressure < flip_lower or gex_pressure > flip_upper):
                logger.info(f"📜 PAPER TRADE FORCED {sig.symbol}: Dark spike + GEX flip proxy")
                sig.is_paper_trade = True
                
            sig.divergence_score = divergence_score
                
            valid_signals.append(sig)
            
        return valid_signals
    
    def _generate_regular_signals(
        self, symbol: str, current_price: float,
        inst_context: InstitutionalContext,
        minute_bars=None
    ) -> List[LiveSignal]:
        """
        Generate regular stock trading signals
        
        Returns:
            List of LiveSignal objects
        """
        signals = []
        
        try:
            # FIRST: Check for real-time momentum signals (SELLOFF + RALLY)
            if minute_bars is not None and len(minute_bars) >= 10:
                # Check for selloff (rapid drop)
                selloff_signal = self._detect_realtime_selloff(
                    symbol, current_price, minute_bars, context=inst_context
                )
                if selloff_signal:
                    signals.append(selloff_signal)
                
                # Check for rally (rapid rise) - COUNTERPART to selloff
                rally_signal = self._detect_realtime_rally(
                    symbol, current_price, minute_bars, context=inst_context
                )
                if rally_signal:
                    signals.append(rally_signal)
                    
            # Check squeeze potential (LOWERED THRESHOLD: 0.5 → 0.3 for testing)
            if inst_context.squeeze_potential >= 0.3:
                signal = self._create_squeeze_signal(symbol, current_price, inst_context)
                if signal:
                    signals.append(signal)
            
            # Check gamma pressure (LOWERED THRESHOLD: 0.5 → 0.3 for testing)
            if inst_context.gamma_pressure >= 0.3:
                signal = self._create_gamma_signal(symbol, current_price, inst_context)
                if signal:
                    signals.append(signal)
            
            # Check institutional buying (breakout/bounce) (LOWERED THRESHOLD: 0.5 → 0.3 for testing)
            if inst_context.institutional_buying_pressure >= 0.3:
                signal = self._create_dp_signal(symbol, current_price, inst_context)
                if signal:
                    signals.append(signal)
            
            # Check for BEARISH signals (breakdown, rejection, bearish flow)
            # Breakdown: Price breaks below DP support with volume
            breakdown_signal = self._create_breakdown_signal(symbol, current_price, inst_context)
            if breakdown_signal:
                signals.append(breakdown_signal)
            
            # Bearish institutional flow: DP sell ratio high
            if inst_context.dp_buy_sell_ratio < 0.7 and inst_context.dp_total_volume > 1_000_000:
                bearish_signal = self._create_bearish_flow_signal(symbol, current_price, inst_context)
                if bearish_signal:
                    signals.append(bearish_signal)
            
            # Filter by confidence
            signals = [s for s in signals if s.confidence >= self.min_high_confidence]
            
            # Apply sentiment filter if enabled
            if self.use_sentiment and self.sentiment_analyzer:
                filtered_signals = []
                for signal in signals:
                    try:
                        analysis = self.sentiment_analyzer.fetch_reddit_sentiment(signal.symbol, days=7)
                        if analysis:
                            # Convert enum to string if needed
                            action_str = signal.action.value if isinstance(signal.action, SignalAction) else str(signal.action)
                            should_trade, reason = self.sentiment_analyzer.should_trade_based_on_sentiment(
                                analysis, action_str
                            )
                            if not should_trade:
                                logger.info(f"   ❌ Sentiment veto for {signal.symbol}: {reason}")
                                continue  # Skip this signal
                            else:
                                logger.debug(f"   ✅ Sentiment approved: {reason}")
                    except Exception as e:
                        logger.warning(f"Error checking sentiment for {signal.symbol}: {e}")
                        # Continue with signal if sentiment check fails
                    
                    filtered_signals.append(signal)
                
                signals = filtered_signals
            
            # Apply gamma filter if enabled
            if self.use_gamma and self.gamma_tracker:
                filtered_signals = []
                for signal in signals:
                    try:
                        gamma_data = self.gamma_tracker.calculate_gamma_exposure(
                            signal.symbol, current_price
                        )
                        if gamma_data:
                            # Convert enum to string if needed
                            action_str = signal.action.value if isinstance(signal.action, SignalAction) else str(signal.action)
                            should_trade, reason = self.gamma_tracker.should_trade_based_on_gamma(
                                current_price, gamma_data, action_str
                            )
                            if not should_trade:
                                logger.info(f"   ❌ Gamma veto for {signal.symbol}: {reason}")
                                continue  # Skip this signal
                            else:
                                logger.debug(f"   ✅ Gamma approved: {reason}")
                                # Boost confidence if gamma regime favors the trade
                                if "favored" in reason.lower():
                                    signal.confidence = min(signal.confidence * 1.1, 1.0)
                    except Exception as e:
                        logger.warning(f"Error checking gamma for {signal.symbol}: {e}")
                        # Continue with signal if gamma check fails
                    
                    filtered_signals.append(signal)
                
                signals = filtered_signals
            
            logger.info(f"Generated {len(signals)} regular signals for {symbol}")
            
        except Exception as e:
            logger.error(f"Error generating regular signals: {e}")
        
        return signals

    def _detect_realtime_selloff(
        self,
        symbol: str,
        current_price: float,
        minute_bars: pd.DataFrame,
        context: InstitutionalContext = None,
    ) -> Optional[LiveSignal]:
        """
        Detect real-time selloff using MULTIPLE detection methods:
        
        1. FROM OPEN: Price drops X% from day's open (EARLY WARNING)
        2. MOMENTUM: Rapid decline with consecutive red bars
        3. ACCELERATION: Rate of decline increasing
        
        This catches selloffs EARLY, not after they've happened!
        """
        try:
            if minute_bars is None or len(minute_bars) < 5:
                return None

            closes = minute_bars["Close"]
            volumes = minute_bars["Volume"]
            
            # Get key prices
            # CRITICAL: Use FIRST bar of the day as day_open, not first of minute_bars
            day_open = float(minute_bars["Open"].iloc[0])  # First bar's open = day open
            current_close = float(closes.iloc[-1])
            
            # For momentum detection, use only recent bars (last 30)
            if len(minute_bars) > 30:
                recent_bars_for_momentum = minute_bars.tail(30)
                recent_closes = recent_bars_for_momentum["Close"]
                recent_volumes = recent_bars_for_momentum["Volume"]
            else:
                recent_closes = closes
                recent_volumes = volumes
            
            # ═══════════════════════════════════════════════════════════════
            # METHOD 1: FROM OPEN DETECTION (EARLY WARNING!)
            # ═══════════════════════════════════════════════════════════════
            pct_from_open = (current_close - day_open) / day_open
            
            # Trigger at -0.25% from open (catches weakness EARLY)
            from_open_triggered = pct_from_open <= -0.0025
            
            # ═══════════════════════════════════════════════════════════════
            # METHOD 2: CONSECUTIVE RED BARS (MOMENTUM)
            # ═══════════════════════════════════════════════════════════════
            # Use recent_closes for momentum (not full day)
            consecutive_red = 0
            for i in range(len(recent_closes) - 1, max(0, len(recent_closes) - 10), -1):
                if recent_closes.iloc[i] < recent_closes.iloc[i-1]:
                    consecutive_red += 1
                else:
                    break
            
            # 3+ consecutive red bars = momentum selling
            momentum_triggered = consecutive_red >= 3
            
            # ═══════════════════════════════════════════════════════════════
            # METHOD 3: ROLLING DECLINE (original method, kept as backup)
            # ═══════════════════════════════════════════════════════════════
            # Use momentum bars for rolling check too (avoid variable collision)
            lookback = min(10, len(recent_closes))  # Shortened from 20 to 10
            rolling_window_closes = recent_closes.tail(lookback)
            rolling_window_volumes = recent_volumes.tail(lookback)
            
            start_price = float(rolling_window_closes.iloc[0])
            end_price = float(rolling_window_closes.iloc[-1])
            rolling_change = (end_price - start_price) / start_price
            
            rolling_triggered = rolling_change <= -0.002  # -0.2% in 10 bars
            
            # ═══════════════════════════════════════════════════════════════
            # COMBINED TRIGGER: Any method can fire, but need at least 2 for HIGH confidence
            # ═══════════════════════════════════════════════════════════════
            triggers_hit = sum([from_open_triggered, momentum_triggered, rolling_triggered])
            
            if triggers_hit == 0:
                return None
            
            # Volume check (relaxed - just need above average) - use momentum volumes
            avg_volume = float(recent_volumes.iloc[:-1].mean()) if len(recent_volumes) > 1 else 0
            last_volume = float(recent_volumes.iloc[-1])
            volume_elevated = avg_volume > 0 and last_volume > avg_volume * 1.0  # Just above average
            
            # Skip if volume is dead (no conviction)
            if not volume_elevated and triggers_hit < 2:
                return None

            # Step 2: Base confidence based on trigger strength
            # More triggers = higher confidence
            base_confidence = 0.50 + (triggers_hit * 0.15)  # 50% base + 15% per trigger
            
            # Boost for larger moves from open
            if abs(pct_from_open) >= 0.005:  # -0.5% or more from open
                base_confidence += 0.10
            
            # Boost for strong momentum (5+ red bars)
            if consecutive_red >= 5:
                base_confidence += 0.10
            
            # Build detection method string for rationale
            detection_methods = []
            if from_open_triggered:
                detection_methods.append(f"FROM_OPEN ({pct_from_open*100:.2f}%)")
            if momentum_triggered:
                detection_methods.append(f"MOMENTUM ({consecutive_red} red bars)")
            if rolling_triggered:
                detection_methods.append(f"ROLLING ({rolling_change*100:.2f}%)")

            # Step 3: INSTITUTIONAL EDGE - adjust confidence based on DP context
            if context:
                # Check if at DP battleground
                at_battleground = False
                nearest_battleground = None
                distance_to_battleground = 999
                
                if context.dp_battlegrounds:
                    # Find nearest support level
                    supports = [bg for bg in context.dp_battlegrounds if bg <= current_price * 1.02]
                    if supports:
                        nearest_battleground = max(supports)
                        distance_pct = abs(current_price - nearest_battleground) / current_price
                        at_battleground = distance_pct < 0.01  # Within 1%
                        distance_to_battleground = distance_pct * 100
                
                # Adjust confidence based on DP flow
                if context.institutional_buying_pressure < 0.3:  # Institutions selling
                    # Selling pressure + price drop = STRONG bearish
                    base_confidence += 0.10
                    flow_signal = "SELLING"
                elif context.institutional_buying_pressure > 0.7 and at_battleground:
                    # Institutions buying at support but price dropping = TRAP/BOUNCE COMING
                    base_confidence -= 0.15  # Reduce bearish confidence
                    flow_signal = "BUYING (potential bounce)"
                else:
                    flow_signal = "NEUTRAL"
                
                # Lit exchange % adjustment (distribution signal)
                # High lit % = institutions dumping publicly = strong bearish
                lit_exchange_pct = 100 - context.dark_pool_pct if context.dark_pool_pct else 50
                if lit_exchange_pct > 70:
                    base_confidence += 0.10
                    distribution_signal = f"PUBLIC DISTRIBUTION ({lit_exchange_pct:.0f}% lit)"
                else:
                    distribution_signal = f"Dark pool {context.dark_pool_pct:.0f}%"
            else:
                # No institutional context available
                flow_signal = "N/A"
                distribution_signal = "N/A"
                nearest_battleground = None
                at_battleground = False
                distance_to_battleground = 999

            confidence = min(base_confidence, 0.95)  # Cap at 95%

            # Stops/targets
            stop_price = current_price * 1.01
            target_price = current_price * 0.985

            # Step 4: Build FULL rationale with DETECTION METHODS
            rationale_parts = [
                f"🚨 EARLY SELLOFF DETECTED: {' + '.join(detection_methods)}",
                f"From open: {pct_from_open * 100:.2f}%",
            ]
            
            if volume_elevated:
                vol_ratio = last_volume/avg_volume if avg_volume > 0 else 1.0
                rationale_parts.append(f"Volume: {vol_ratio:.1f}x avg")
            
            if context:
                rationale_parts.append(f"FLOW: {flow_signal}")
                if nearest_battleground:
                    rationale_parts.append(
                        f"DP: ${nearest_battleground:.2f} "
                        f"({'AT SUPPORT' if at_battleground else f'{distance_to_battleground:.1f}% away'})"
                    )
            
            rationale = " | ".join(rationale_parts)

            # Build supporting factors
            supporting_factors = [
                f"Detection: {', '.join(detection_methods)}",
                f"From open: {pct_from_open * 100:.2f}%",
                f"Consecutive red bars: {consecutive_red}",
                f"Volume: {last_volume/avg_volume:.1f}x avg" if avg_volume > 0 else "Volume: N/A",
            ]
            
            if context:
                supporting_factors.extend([
                    f"Institutional flow: {flow_signal}",
                    f"Buying pressure: {context.institutional_buying_pressure:.0%}" if context.institutional_buying_pressure else "Buying pressure: N/A",
                    distribution_signal,
                    f"DP battleground: ${nearest_battleground:.2f} ({distance_to_battleground:.1f}% away)" if nearest_battleground else "No DP levels nearby"
                ])

            return LiveSignal(
                symbol=symbol,
                action=SignalAction.SELL,
                timestamp=datetime.now(),
                entry_price=current_price,
                target_price=target_price,
                stop_price=stop_price,
                confidence=confidence,
                signal_type=SignalType.SELLOFF,
                rationale=rationale,
                dp_level=nearest_battleground if nearest_battleground else 0.0,
                dp_volume=context.dp_total_volume if context else 0,
                institutional_score=context.institutional_buying_pressure if context else 0.0,
                supporting_factors=supporting_factors,
                warnings=[],
                is_master_signal=confidence >= self.min_master_confidence,
                is_actionable=True,
                position_size_pct=0.01 if confidence >= 0.75 else 0.005,
                risk_reward_ratio=(
                    (current_price - target_price) / (stop_price - current_price)
                    if (stop_price - current_price) > 0
                    else 0.0
                ),
            )
        except Exception as e:
            logger.warning(f"Error detecting realtime selloff for {symbol}: {e}")
            return None
    
    def _detect_realtime_rally(
        self,
        symbol: str,
        current_price: float,
        minute_bars: pd.DataFrame,
        context: InstitutionalContext = None,
    ) -> Optional[LiveSignal]:
        """
        Detect real-time rally using MULTIPLE detection methods:
        
        1. FROM OPEN: Price rises X% from day's open (EARLY WARNING)
        2. MOMENTUM: Rapid rise with consecutive green bars
        3. ACCELERATION: Rate of rise increasing
        
        This catches rallies EARLY!
        """
        try:
            if minute_bars is None or len(minute_bars) < 5:
                return None

            closes = minute_bars["Close"]
            volumes = minute_bars["Volume"]
            
            # Get key prices
            # CRITICAL: Use FIRST bar of the day as day_open (now that we pass full day data)
            day_open = float(minute_bars["Open"].iloc[0])
            current_close = float(closes.iloc[-1])
            
            # For momentum detection, use only recent bars (last 30)
            if len(minute_bars) > 30:
                recent_bars_for_momentum = minute_bars.tail(30)
                momentum_closes = recent_bars_for_momentum["Close"]
                momentum_volumes = recent_bars_for_momentum["Volume"]
            else:
                momentum_closes = closes
                momentum_volumes = volumes
            
            # ═══════════════════════════════════════════════════════════════
            # METHOD 1: FROM OPEN DETECTION (EARLY WARNING!)
            # ═══════════════════════════════════════════════════════════════
            pct_from_open = (current_close - day_open) / day_open
            
            # Trigger at +0.25% from open
            from_open_triggered = pct_from_open >= 0.0025
            
            # ═══════════════════════════════════════════════════════════════
            # METHOD 2: CONSECUTIVE GREEN BARS (MOMENTUM)
            # ═══════════════════════════════════════════════════════════════
            # Use momentum_closes for momentum (not full day)
            consecutive_green = 0
            for i in range(len(momentum_closes) - 1, max(0, len(momentum_closes) - 10), -1):
                if momentum_closes.iloc[i] > momentum_closes.iloc[i-1]:
                    consecutive_green += 1
                else:
                    break
            
            # 3+ consecutive green bars = momentum buying
            momentum_triggered = consecutive_green >= 3
            
            # ═══════════════════════════════════════════════════════════════
            # METHOD 3: ROLLING RISE (original method, kept as backup)
            # ═══════════════════════════════════════════════════════════════
            # Use momentum bars for rolling check too (avoid variable collision)
            lookback = min(10, len(momentum_closes))
            rolling_window_closes = momentum_closes.tail(lookback)
            rolling_window_volumes = momentum_volumes.tail(lookback)
            
            start_price = float(rolling_window_closes.iloc[0])
            end_price = float(rolling_window_closes.iloc[-1])
            rolling_change = (end_price - start_price) / start_price
            
            rolling_triggered = rolling_change >= 0.002  # +0.2% in 10 bars
            
            # ═══════════════════════════════════════════════════════════════
            # COMBINED TRIGGER
            # ═══════════════════════════════════════════════════════════════
            triggers_hit = sum([from_open_triggered, momentum_triggered, rolling_triggered])
            
            if triggers_hit == 0:
                return None
            
            # Volume check (relaxed) - use momentum volumes
            avg_volume = float(momentum_volumes.iloc[:-1].mean()) if len(momentum_volumes) > 1 else 0
            last_volume = float(momentum_volumes.iloc[-1])
            volume_elevated = avg_volume > 0 and last_volume > avg_volume * 1.0
            
            if not volume_elevated and triggers_hit < 2:
                return None

            # Step 2: Base confidence based on trigger strength
            base_confidence = 0.50 + (triggers_hit * 0.15)
            
            if abs(pct_from_open) >= 0.005:
                base_confidence += 0.10
            
            if consecutive_green >= 5:
                base_confidence += 0.10
            
            # Build detection method string
            detection_methods = []
            if from_open_triggered:
                detection_methods.append(f"FROM_OPEN ({pct_from_open*100:+.2f}%)")
            if momentum_triggered:
                detection_methods.append(f"MOMENTUM ({consecutive_green} green bars)")
            if rolling_triggered:
                detection_methods.append(f"ROLLING ({rolling_change*100:+.2f}%)")

            # Step 3: INSTITUTIONAL EDGE - adjust confidence based on DP context
            if context:
                # Check if at DP battleground (resistance)
                at_battleground = False
                nearest_battleground = None
                distance_to_battleground = 999
                
                if context.dp_battlegrounds:
                    # Find nearest resistance level
                    resistances = [bg for bg in context.dp_battlegrounds if bg >= current_price * 0.98]
                    if resistances:
                        nearest_battleground = min(resistances)
                        distance_pct = abs(current_price - nearest_battleground) / current_price
                        at_battleground = distance_pct < 0.01  # Within 1%
                        distance_to_battleground = distance_pct * 100
                
                # Adjust confidence based on DP flow
                if context.institutional_buying_pressure > 0.7:  # Institutions buying
                    # Buying pressure + price rise = STRONG bullish
                    base_confidence += 0.10
                    flow_signal = "ACCUMULATION"
                elif context.institutional_buying_pressure < 0.3 and at_battleground:
                    # Institutions selling at resistance but price rising = potential rejection
                    base_confidence -= 0.15  # Reduce bullish confidence
                    flow_signal = "SELLING (potential rejection)"
                else:
                    flow_signal = "NEUTRAL"
                
                # Dark pool % adjustment (accumulation signal)
                # High dark pool % = institutions accumulating quietly = strong bullish
                if context.dark_pool_pct and context.dark_pool_pct > 50:
                    base_confidence += 0.10
                    accumulation_signal = f"QUIET ACCUMULATION ({context.dark_pool_pct:.0f}% dark)"
                else:
                    lit_pct = 100 - (context.dark_pool_pct or 50)
                    accumulation_signal = f"Lit exchange {lit_pct:.0f}%"
            else:
                flow_signal = "N/A"
                accumulation_signal = "N/A"
                nearest_battleground = None
                at_battleground = False
                distance_to_battleground = 999

            confidence = min(base_confidence, 0.95)  # Cap at 95%

            # Stops/targets (LONG trade)
            stop_price = current_price * 0.99  # 1% stop loss
            target_price = current_price * 1.015  # 1.5% target

            # Step 4: Build FULL rationale with DETECTION METHODS
            rationale_parts = [
                f"🚀 EARLY RALLY DETECTED: {' + '.join(detection_methods)}",
                f"From open: {pct_from_open * 100:+.2f}%",
            ]
            
            if volume_elevated:
                vol_ratio = last_volume/avg_volume if avg_volume > 0 else 1.0
                rationale_parts.append(f"Volume: {vol_ratio:.1f}x avg")
            
            if context:
                rationale_parts.append(f"FLOW: {flow_signal}")
                if nearest_battleground:
                    rationale_parts.append(
                        f"DP BATTLEGROUND: ${nearest_battleground:.2f} "
                        f"({'AT RESISTANCE' if at_battleground else f'{distance_to_battleground:.1f}% away'})"
                    )
            
            rationale = " | ".join(rationale_parts)

            # Build supporting factors
            supporting_factors = [
                f"Detection: {', '.join(detection_methods)}",
                f"From open: {pct_from_open * 100:+.2f}%",
                f"Consecutive green bars: {consecutive_green}",
                f"Volume: {last_volume/avg_volume:.1f}x avg" if avg_volume > 0 else "Volume: N/A",
            ]
            
            if context:
                supporting_factors.extend([
                    f"Institutional flow: {flow_signal}",
                    f"Buying pressure: {context.institutional_buying_pressure:.0%}" if context.institutional_buying_pressure else "Buying pressure: N/A",
                    accumulation_signal,
                    f"DP battleground: ${nearest_battleground:.2f} ({distance_to_battleground:.1f}% away)" if nearest_battleground else "No DP levels nearby"
                ])

            return LiveSignal(
                symbol=symbol,
                action=SignalAction.BUY,
                timestamp=datetime.now(),
                entry_price=current_price,
                target_price=target_price,
                stop_price=stop_price,
                confidence=confidence,
                signal_type=SignalType.RALLY,  # Momentum-based rally signal
                rationale=rationale,
                dp_level=nearest_battleground if nearest_battleground else 0.0,
                dp_volume=context.dp_total_volume if context else 0,
                institutional_score=context.institutional_buying_pressure if context else 0.0,
                supporting_factors=supporting_factors,
                warnings=[],
                is_master_signal=confidence >= self.min_master_confidence,
                is_actionable=True,
                position_size_pct=0.01 if confidence >= 0.75 else 0.005,
                risk_reward_ratio=(
                    (target_price - current_price) / (current_price - stop_price)
                    if (current_price - stop_price) > 0
                    else 0.0
                ),
            )
        except Exception as e:
            logger.warning(f"Error detecting realtime rally for {symbol}: {e}")
            return None
    
    def _generate_lottery_signals(
        self,
        symbol: str,
        current_price: float,
        regular_signals: List[LiveSignal],
        account_value: float,
        minute_bars=None,
    ) -> List[LotterySignal]:
        """
        Generate lottery signals from high-confidence regular signals + volatility expansion
        
        Returns:
            List of LotterySignal objects
        """
        lottery_signals = []
        
        try:
            # Check volatility expansion using realized intraday volatility
            vol_status = self.vol_detector.detect_expansion(
                symbol, minute_bars=minute_bars, lookback_minutes=30
            )
            
            if not vol_status:
                return lottery_signals  # No volatility data available
            
            # Check if we have volatility expansion with lottery potential
            if vol_status.lottery_potential in ['HIGH', 'MEDIUM']:
                logger.info(f"   🎰 Volatility expansion detected: {vol_status.status} ({vol_status.lottery_potential} potential)")
                
                # Convert high-confidence regular signals to lottery signals
                for signal in regular_signals:
                    if signal.confidence >= self.lottery_threshold:
                        lottery_signal = self._convert_to_lottery_signal(
                            signal, current_price, vol_status, account_value
                        )
                        if lottery_signal and lottery_signal.is_valid:
                            lottery_signals.append(lottery_signal)
                            logger.info(f"   🎰 Converted {signal.signal_type} to lottery signal")
            
            # TODO: Check for event-driven lottery setups (Phase 2)
            # event_lotteries = self._check_event_lottery_setups(symbol, current_price)
            # lottery_signals.extend(event_lotteries)
            
            logger.info(f"Generated {len(lottery_signals)} lottery signals for {symbol}")
            
        except Exception as e:
            logger.error(f"Error generating lottery signals: {e}")
        
        return lottery_signals
    
    def _convert_to_lottery_signal(
        self, regular_signal: LiveSignal, current_price: float,
        vol_status, account_value: float
    ) -> Optional[LotterySignal]:
        """
        Convert high-confidence regular signal to 0DTE lottery play
        
        Args:
            regular_signal: High-confidence regular signal
            current_price: Current stock price
            vol_status: VolatilityExpansionStatus
            account_value: Account value for position sizing
        
        Returns:
            LotterySignal or None
        """
        try:
            # Convert signal to 0DTE trade
            zero_dte_trade = self.zero_dte_strategy.convert_signal_to_0dte(
                signal_symbol=regular_signal.symbol,
                signal_action=regular_signal.action.value if isinstance(regular_signal.action, SignalAction) else regular_signal.action,
                signal_confidence=regular_signal.confidence,
                current_price=current_price,
                account_value=account_value
            )
            
            if not zero_dte_trade.is_valid or not zero_dte_trade.strike_recommendation:
                return None
            
            strike_rec = zero_dte_trade.strike_recommendation
            
            # Determine signal type
            if regular_signal.action == SignalAction.BUY or (isinstance(regular_signal.action, str) and regular_signal.action == 'BUY'):
                signal_type = SignalType.LOTTERY_0DTE_CALL
            else:
                signal_type = SignalType.LOTTERY_0DTE_PUT
            
            # Build LotterySignal
            lottery_signal = LotterySignal(
                symbol=regular_signal.symbol,
                action=regular_signal.action if isinstance(regular_signal.action, SignalAction) else SignalAction.BUY,
                timestamp=regular_signal.timestamp,
                entry_price=strike_rec.mid_price,
                target_price=zero_dte_trade.take_profit_levels[0][0] * strike_rec.mid_price if zero_dte_trade.take_profit_levels else strike_rec.mid_price * 2.0,
                stop_price=zero_dte_trade.stop_loss if zero_dte_trade.stop_loss else strike_rec.mid_price * 0.5,
                confidence=regular_signal.confidence,
                signal_type=signal_type,
                rationale=f"LOTTERY: {regular_signal.rationale} + {vol_status.lottery_potential} IV expansion",
                position_size_pct=zero_dte_trade.position_size_pct,
                position_size_dollars=zero_dte_trade.max_risk_dollars,
                risk_reward_ratio=zero_dte_trade.risk_reward_ratio,
                is_master_signal=regular_signal.confidence >= self.min_master_confidence,
                is_actionable=True,
                # Lottery-specific fields
                strike=strike_rec.strike,
                expiry=strike_rec.expiry.strftime('%Y-%m-%d') if hasattr(strike_rec.expiry, 'strftime') else str(strike_rec.expiry),
                option_type=strike_rec.option_type,
                delta=strike_rec.delta,
                gamma=strike_rec.gamma,
                iv=strike_rec.iv,
                iv_rank=vol_status.iv_spike_pct / 100.0,  # Convert % to decimal
                lottery_potential=vol_status.lottery_potential,
                open_interest=strike_rec.open_interest,
                volume=strike_rec.volume,
                bid=strike_rec.bid,
                ask=strike_rec.ask,
                spread_pct=strike_rec.spread_pct,
                liquidity_score=strike_rec.liquidity_score,
                take_profit_levels=zero_dte_trade.take_profit_levels,
                supporting_factors=[
                    f"IV expansion: {vol_status.iv_spike_pct:.1f}%",
                    f"Volatility status: {vol_status.status}",
                    f"Strike: ${strike_rec.strike:.2f} ({strike_rec.option_type})",
                    f"Delta: {strike_rec.delta:.3f}",
                    f"Premium: ${strike_rec.mid_price:.2f}",
                ]
            )
            
            return lottery_signal
            
        except Exception as e:
            logger.error(f"Error converting to lottery signal: {e}")
            return None

    def _apply_economic_risk_management(self, symbol: str,
                                       signals: List[Union[LiveSignal, LotterySignal]]) -> List[Union[LiveSignal, LotterySignal]]:
        """
        Apply economic event risk management to signals.

        Checks BOTH FRED-based EconCalendar AND TECalendarScraper for
        upcoming high-impact economic events. Adjusts signal confidence
        or blocks signals entirely during risky periods.
        
        TE Calendar catches CPI/GDP/PPI that FRED misses as market movers.
        """
        if not ECONOMIC_EXPLOITER_AVAILABLE:
            logger.debug("Economic risk management disabled - exploiter not available")
            return signals

        try:
            # Initialize EconCalendar (FRED-based, cached for performance)
            if not hasattr(self, '_econ_cal'):
                self._econ_cal = EconCalendar()

            risk_check = {'trading_allowed': True, 'reason': '', 'risk_level': 'NONE'}

            # ── Source 1: FRED-based market movers (FOMC, rate decisions) ──
            next_mover = self._econ_cal.get_next_market_mover()
            if next_mover and next_mover.hours_until > 0:
                if next_mover.hours_until <= 0.5:
                    risk_check = {
                        'trading_allowed': False,
                        'reason': f"{next_mover.short_name} releases in {next_mover.hours_until:.1f}h",
                        'risk_level': 'EXTREME',
                    }
                elif next_mover.hours_until <= 2.0:
                    risk_check = {
                        'trading_allowed': False,
                        'reason': f"{next_mover.short_name} releases in {next_mover.hours_until:.1f}h",
                        'risk_level': 'HIGH',
                    }

            # ── Source 2: TE Calendar for CPI/GDP/PPI (FRED misses these) ──
            if TE_CALENDAR_AVAILABLE and risk_check['trading_allowed']:
                try:
                    if not hasattr(self, '_te_cal'):
                        self._te_cal = TECalendarScraper(cache_ttl=300)  # 5-min cache

                    # get_high_impact returns BOTH critical AND high events
                    # (get_upcoming_critical only returns CRITICAL, missing HIGH events like Existing Home Sales)
                    upcoming_critical = [e for e in self._te_cal.get_high_impact() if not e.has_actual]
                    try:
                        from live_monitoring.utils.tz_mapper import now_et
                        now = now_et()
                    except ImportError:
                        now = datetime.now()

                    for te_event in upcoming_critical:
                        # Parse TE date/time to compute hours until release
                        hours_until = self._te_hours_until(te_event, now)
                        if hours_until is None or hours_until <= 0:
                            continue

                        if hours_until <= 0.5:
                            risk_check = {
                                'trading_allowed': False,
                                'reason': f"[TE] {te_event.event} releases in {hours_until:.1f}h",
                                'risk_level': 'EXTREME',
                            }
                            break
                        elif hours_until <= 2.0:
                            # HIGH risk: reduce confidence, don't block trading
                            risk_check = {
                                'trading_allowed': True,
                                'confidence_multiplier': 0.7,
                                'reason': f"[TE] {te_event.event} releases in {hours_until:.1f}h",
                                'risk_level': 'HIGH',
                            }
                            break
                except Exception as te_err:
                    logger.debug(f"TE calendar check failed (non-fatal): {te_err}")

            # ── Apply risk check ──
            if not risk_check['trading_allowed']:
                logger.warning(f"🛑 ECONOMIC RISK: {risk_check['reason']}")
                logger.warning("🚫 EXTREME RISK: Blocking all signals during economic event")
                return []

            # Apply confidence reduction if risk is elevated but not blocking
            if risk_check.get('confidence_multiplier'):
                multiplier = risk_check['confidence_multiplier']
                logger.warning(f"⚠️ {risk_check.get('risk_level', 'HIGH')} RISK: "
                             f"Reducing signal confidence by {(1 - multiplier)*100:.0f}% — {risk_check['reason']}")
                for signal in signals:
                    if hasattr(signal, 'confidence'):
                        signal.confidence = max(0.1, signal.confidence * multiplier)
                    if hasattr(signal, 'master_confidence'):
                        signal.master_confidence = max(0.1, signal.master_confidence * multiplier)

            # Log upcoming high-impact releases for context
            upcoming_high = self._econ_cal.get_high_impact(days=3)
            for rel in upcoming_high[:3]:
                if rel.hours_until > 0:
                    logger.info(f"📅 Upcoming: {rel.short_name} on {rel.date} {rel.time} ET "
                               f"({rel.hours_until:.0f}h) [{rel.category.value}]")

            return signals

        except Exception as e:
            logger.error(f"Error in economic risk management: {e}")
            return signals

    @staticmethod
    def _te_hours_until(te_event, now: datetime = None) -> Optional[float]:
        """
        Parse a TEEvent's date/time (GMT) and compute hours until release in ET.
        
        Uses centralized tz_mapper for proper GMT→ET conversion.
        """
        try:
            from live_monitoring.utils.tz_mapper import hours_until_release, now_et
            
            ref_time = now if now else now_et()
            return hours_until_release(te_event.date, te_event.time, from_time=ref_time)
        except ImportError:
            # Fallback: naive math (WRONG timezone but won't crash)
            logger.warning("⚠️ tz_mapper not available — timezone math may be wrong")
            try:
                if not te_event.date:
                    return None
                date_parts = te_event.date.strip().split(' ', 1)
                if len(date_parts) < 2:
                    return None
                date_str = date_parts[1]
                time_str = te_event.time.strip() if te_event.time else "08:30 AM"
                dt_str = f"{date_str} {time_str}"
                release_dt = None
                for fmt in ["%B %d %Y %I:%M %p", "%B %d %Y %H:%M"]:
                    try:
                        release_dt = datetime.strptime(dt_str, fmt)
                        break
                    except ValueError:
                        continue
                if release_dt is None:
                    return None
                ref = now if now else datetime.now()
                delta = release_dt - ref
                return delta.total_seconds() / 3600.0
            except (ValueError, AttributeError):
                return None


    def _apply_master_filters(self, signals: List[Union[LiveSignal, LotterySignal]]) -> List[Union[LiveSignal, LotterySignal]]:
        """
        Apply master filters to all signals (regular + lottery)
        
        Returns:
            Filtered list of signals
        """
        filtered = []
        
        for signal in signals:
            # Confidence filter
            if signal.confidence < self.min_high_confidence:
                continue
            
            # Apply sentiment filter if enabled
            if self.use_sentiment and self.sentiment_analyzer:
                try:
                    analysis = self.sentiment_analyzer.fetch_reddit_sentiment(signal.symbol, days=7)
                    if analysis:
                        should_trade, reason = self.sentiment_analyzer.should_trade_based_on_sentiment(
                            analysis, signal.action.value if isinstance(signal.action, SignalAction) else signal.action
                        )
                        if not should_trade:
                            logger.info(f"   ❌ Sentiment veto for {signal.symbol}: {reason}")
                            continue
                except Exception as e:
                    logger.warning(f"Error checking sentiment: {e}")
            
            # Apply gamma filter if enabled
            if self.use_gamma and self.gamma_tracker:
                try:
                    # For lottery signals, skip gamma filter (options have their own dynamics)
                    if isinstance(signal, LotterySignal):
                        pass  # Skip gamma filter for lottery
                    else:
                        # Regular signal gamma check
                        gamma_data = self.gamma_tracker.calculate_gamma_exposure(signal.symbol, current_price=signal.entry_price)
                        if gamma_data:
                            should_trade, reason = self.gamma_tracker.should_trade_based_on_gamma(
                                signal.entry_price, gamma_data, 
                                signal.action.value if isinstance(signal.action, SignalAction) else signal.action
                            )
                            if not should_trade:
                                logger.info(f"   ❌ Gamma veto for {signal.symbol}: {reason}")
                                continue
                except Exception as e:
                    logger.warning(f"Error checking gamma: {e}")
            
            filtered.append(signal)
        
        return filtered
    
    def _calculate_confidence_score(self, context: InstitutionalContext, 
                                    signal_type: str, price: float,
                                    order_flow: Optional[object] = None) -> float:
        """
        EXACT CONFIDENCE CALCULATION FORMULA
        
        Confidence = weighted sum of signal components (0-1 scale)
        
        Components:
        - Dark Pool Signal Strength: 40% weight
        - Options Flow Signal: 30% weight  
        - Sentiment Score: 15% weight
        - Gamma Exposure Signal: 15% weight
        
        Each component normalized to 0-1 scale
        """
        # 1. Dark Pool Signal Strength (40% weight)
        # Based on: DP buy/sell ratio, DP volume, battleground proximity
        dp_score = 0.0
        
        # DP buy/sell ratio (0-1)
        if context.dp_buy_sell_ratio > 1.5:
            dp_score += 0.4
        elif context.dp_buy_sell_ratio > 1.2:
            dp_score += 0.3
        elif context.dp_buy_sell_ratio > 1.0:
            dp_score += 0.2
        elif context.dp_buy_sell_ratio < 0.7:
            dp_score -= 0.2  # Bearish DP flow
        
        # DP volume strength (0-1)
        if context.dp_total_volume > 10_000_000:
            dp_score += 0.3
        elif context.dp_total_volume > 5_000_000:
            dp_score += 0.2
        elif context.dp_total_volume > 1_000_000:
            dp_score += 0.1
        
        # Battleground proximity (0-1)
        if context.dp_battlegrounds:
            nearest_bg = min([abs(bg - price) / price for bg in context.dp_battlegrounds])
            if nearest_bg < 0.001:  # Within 0.1%
                dp_score += 0.3
            elif nearest_bg < 0.003:  # Within 0.3%
                dp_score += 0.2
        
        dp_component = min(max(dp_score, 0.0), 1.0) * 0.40  # 40% weight
        
        # 2. Options Flow Signal (30% weight)
        # Based on: Put/call ratio, max pain, total OI
        options_score = 0.0
        
        # Put/call ratio (low = bullish)
        if context.put_call_ratio < 0.7:
            options_score += 0.4
        elif context.put_call_ratio < 0.9:
            options_score += 0.3
        elif context.put_call_ratio < 1.0:
            options_score += 0.2
        
        # Max pain alignment (if available)
        if context.max_pain and abs(context.max_pain - price) / price < 0.02:
            options_score += 0.3
        
        # High OI (institutional interest)
        if context.total_option_oi > 10_000_000:
            options_score += 0.3
        elif context.total_option_oi > 5_000_000:
            options_score += 0.2
        
        options_component = min(max(options_score, 0.0), 1.0) * 0.30  # 30% weight
        
        # 3. Sentiment Score (15% weight)
        # Note: Reddit sentiment handled separately, this is institutional sentiment
        # Use short volume as proxy (low shorting = bullish sentiment)
        sentiment_score = 0.0
        if context.short_volume_pct < 25:
            sentiment_score = 1.0
        elif context.short_volume_pct < 30:
            sentiment_score = 0.7
        elif context.short_volume_pct < 35:
            sentiment_score = 0.4
        
        sentiment_component = sentiment_score * 0.15  # 15% weight
        
        # 4. Gamma Exposure Signal (15% weight)
        # Based on: Gamma pressure from context
        gamma_component = context.gamma_pressure * 0.15  # 15% weight
        
        # Final confidence = sum of components
        confidence = dp_component + options_component + sentiment_component + gamma_component
        
        # Clamp to 0-1
        return min(max(confidence, 0.0), 1.0)
    
    def _create_squeeze_signal(self, symbol: str, price: float,
                               context: InstitutionalContext) -> Optional[LiveSignal]:
        """Create squeeze signal if criteria met"""
        
        # Find nearest support battleground
        supports = [bg for bg in context.dp_battlegrounds if bg <= price * 1.01]
        if not supports:
            return None
        
        nearest_support = max(supports)
        
        # Calculate stops and targets
        stop = nearest_support * 0.97  # 3% below support
        risk = price - stop
        target = price + (risk * 3.0)  # 3:1 R/R for squeeze
        
        # Calculate EXACT confidence score
        base_confidence = self._calculate_confidence_score(context, "SQUEEZE", price)
        
        # Boost for squeeze-specific factors
        squeeze_boost = 0.0
        if context.short_volume_pct > 40:
            squeeze_boost += 0.15
        if context.borrow_fee_rate > 5.0:
            squeeze_boost += 0.10
        if context.days_to_cover and context.days_to_cover > 5:
            squeeze_boost += 0.05
        
        confidence = min(base_confidence + squeeze_boost, 1.0)
        
        # Position sizing based on confidence
        if confidence >= 0.85:
            position_pct = 0.02  # Full 2%
        else:
            position_pct = 0.01  # Half size
        
        # Build rationale (was 'primary_reason')
        rationale = (
            f"SQUEEZE SETUP: {context.short_volume_pct:.0f}% short, "
            f"{context.borrow_fee_rate:.1f}% borrow fee, "
            f"DTC {context.days_to_cover:.1f}" if context.days_to_cover else ""
        )
        
        supporting_factors = [
            f"Days to cover: {context.days_to_cover:.1f}" if context.days_to_cover else "",
            f"Institutional buying: {context.institutional_buying_pressure:.0%}",
            f"DP support @ ${nearest_support:.2f}",
            f"Short volume: {context.short_volume_pct:.0f}%"
        ]
        
        return LiveSignal(
            symbol=symbol,
            action=SignalAction.BUY,  # Was string "BUY"
            timestamp=datetime.now(),
            entry_price=price,  # Was 'current_price'
            target_price=target,  # Was 'take_profit'
            stop_price=stop,  # Was 'stop_loss'
            confidence=confidence,
            signal_type=SignalType.SQUEEZE,  # Was string "SQUEEZE"
            rationale=rationale,  # Was 'primary_reason'
            dp_level=nearest_support,
            dp_volume=0,  # Would need to look up
            institutional_score=context.institutional_buying_pressure,
            supporting_factors=supporting_factors,
            warnings=[],
            is_master_signal=context.squeeze_potential >= self.min_master_confidence,
            is_actionable=True,
            position_size_pct=position_pct,
            risk_reward_ratio=(target - price) / (price - stop) if (price - stop) > 0 else 0
        )
    
    def _create_gamma_signal(self, symbol: str, price: float,
                            context: InstitutionalContext) -> Optional[LiveSignal]:
        """Create gamma ramp signal"""
        
        if not context.max_pain or context.max_pain <= price:
            return None
        
        # Find support
        supports = [bg for bg in context.dp_battlegrounds if bg <= price * 1.01]
        if not supports:
            return None
        
        nearest_support = max(supports)
        
        stop = nearest_support * 0.97
        target = context.max_pain
        risk = price - stop
        
        # Calculate EXACT confidence score
        base_confidence = self._calculate_confidence_score(context, "GAMMA_RAMP", price)
        
        # Boost for gamma-specific factors
        gamma_boost = 0.0
        if context.put_call_ratio < 0.7:
            gamma_boost += 0.15
        if context.max_pain and abs(context.max_pain - price) / price < 0.01:
            gamma_boost += 0.10
        
        confidence = min(base_confidence + gamma_boost, 1.0)
        
        position_pct = 0.02 if confidence >= 0.85 else 0.01
        
        # Build rationale (was 'primary_reason')
        max_pain_str = f"${context.max_pain:.2f}" if context.max_pain else "N/A"
        rationale = (
            f"GAMMA RAMP: P/C {context.put_call_ratio:.2f}, "
            f"Max Pain {max_pain_str}, "
            f"Call OI {context.total_option_oi:,}"
        )
        
        supporting_factors = [
            f"Call OI: {context.total_option_oi:,}",
            f"Max pain ${(context.max_pain - price) / price * 100:+.1f}% above" if context.max_pain else "Max pain: N/A",
            f"DP support @ ${nearest_support:.2f}",
            f"P/C ratio: {context.put_call_ratio:.2f}"
        ]
        
        return LiveSignal(
            symbol=symbol,
            action=SignalAction.BUY,  # Was string "BUY"
            timestamp=datetime.now(),
            entry_price=price,  # Was 'current_price'
            target_price=target,  # Was 'take_profit'
            stop_price=stop,  # Was 'stop_loss'
            confidence=confidence,
            signal_type=SignalType.GAMMA_RAMP,  # Was string "GAMMA_RAMP"
            rationale=rationale,  # Was 'primary_reason'
            dp_level=nearest_support,
            dp_volume=0,
            institutional_score=context.institutional_buying_pressure,
            supporting_factors=supporting_factors,
            warnings=[],
            is_master_signal=context.gamma_pressure >= self.min_master_confidence,
            is_actionable=True,
            position_size_pct=position_pct,
            risk_reward_ratio=(target - price) / risk if risk > 0 else 0
        )
    
    def _create_dp_signal(self, symbol: str, price: float,
                         context: InstitutionalContext) -> Optional[LiveSignal]:
        """Create DP breakout/bounce signal"""
        
        if not context.dp_battlegrounds:
            return None
        
        # Check if at support (bounce) or near resistance (breakout)
        # FIXED: Support = levels BELOW price, Resistance = levels ABOVE price
        supports = [bg for bg in context.dp_battlegrounds if bg < price and bg >= price * 0.98]  # Within 2% below
        resistances = [bg for bg in context.dp_battlegrounds if bg > price and bg <= price * 1.02]  # Within 2% above
        
        if supports:
            # At support - bounce play
            nearest_support = max(supports)
            signal_type = "BOUNCE"
            stop = nearest_support * 0.997  # Tighter stop: 0.3% below support (was 0.5%)
            
            # Target next resistance or 2:1 R/R - ENFORCE minimum R/R
            risk = price - stop
            target_2r = price + (risk * 2.0)  # 2:1 R/R target
            
            if resistances and min(resistances) > price:
                resistance_target = min(resistances)
                resistance_rr = (resistance_target - price) / risk if risk > 0 else 0
                # Only use resistance if it gives at least 1.5:1 R/R
                if resistance_rr >= 1.5:
                    target = resistance_target
                else:
                    target = target_2r
            else:
                target = target_2r
        
        elif resistances:
            # Near resistance - potential breakout
            nearest_resistance = min(resistances)
            
            # Signal if close enough (< 1.0%) - was 0.2%, expanded to find more trades
            if (nearest_resistance - price) / price > 0.01:
                return None
            
            signal_type = "BREAKOUT"
            stop = nearest_resistance * 0.997  # Below broken resistance
            risk = price - stop
            target = price + (risk * 2.0)
        
        else:
            return None
        
        # Calculate EXACT confidence score
        base_confidence = self._calculate_confidence_score(context, signal_type, price)
        
        # Boost for DP-specific factors
        dp_boost = 0.0
        if context.dp_buy_sell_ratio > 1.5:
            dp_boost += 0.15
        if context.dark_pool_pct > 50:
            dp_boost += 0.10
        
        confidence = min(base_confidence + dp_boost, 1.0)
        
        position_pct = 0.02 if confidence >= 0.85 else 0.01
        
        level = nearest_support if signal_type == "BOUNCE" else nearest_resistance
        
        # Determine signal type enum
        if signal_type == "BREAKOUT":
            signal_type_enum = SignalType.BREAKOUT
        else:
            signal_type_enum = SignalType.BOUNCE
        
        # Build rationale (was 'primary_reason')
        rationale = (
            f"INSTITUTIONAL {signal_type}: "
            f"{context.dp_total_volume:,} DP volume, "
            f"{context.dp_buy_sell_ratio:.2f} B/S"
        )
        
        supporting_factors = [
            f"Buying pressure: {context.institutional_buying_pressure:.0%}",
            f"Dark pool: {context.dark_pool_pct:.0f}%",
            f"DP level @ ${level:.2f}",
            f"DP volume: {context.dp_total_volume:,} shares"
        ]
        
        return LiveSignal(
            symbol=symbol,
            action=SignalAction.BUY,  # Was string "BUY"
            timestamp=datetime.now(),
            entry_price=price,  # Was 'current_price'
            target_price=target,  # Was 'take_profit'
            stop_price=stop,  # Was 'stop_loss'
            confidence=confidence,
            signal_type=signal_type_enum,  # Was string
            rationale=rationale,  # Was 'primary_reason'
            dp_level=level,
            dp_volume=context.dp_total_volume,
            institutional_score=context.institutional_buying_pressure,
            supporting_factors=supporting_factors,
            warnings=[],
            is_master_signal=context.institutional_buying_pressure >= self.min_master_confidence,
            is_actionable=True,
            position_size_pct=position_pct,
            risk_reward_ratio=(target - price) / (price - stop) if (price - stop) > 0 else 0
        )

    def _create_breakdown_signal(self, symbol: str, price: float,
                                context: InstitutionalContext) -> Optional[LiveSignal]:
        """
        Create SELL signal when price breaks below DP support
        
        This catches selloffs like the one we just missed!
        """
        if not context.dp_battlegrounds:
            return None
        
        # Find supports that price has broken below
        supports = [bg for bg in context.dp_battlegrounds if bg > price * 0.99 and bg < price * 1.02]
        
        if not supports:
            return None
        
        # Check if we just broke below a support (within 0.3%)
        nearest_support = min(supports, key=lambda x: abs(x - price))
        distance_below = (price - nearest_support) / nearest_support
        
        # Only signal if we're below support (breakdown)
        if distance_below < -0.003:  # More than 0.3% below
            return None  # Too far below, already broken
        
        if distance_below > 0.003:  # More than 0.3% above
            return None  # Not broken yet
        
        # We're at or just broke support - check for bearish confirmation
        # Need: Bearish DP flow OR high put/call ratio OR negative momentum
        
        bearish_confirmation = False
        reasons = []
        
        # Check DP flow
        if context.dp_buy_sell_ratio < 0.8:  # More selling than buying
            bearish_confirmation = True
            reasons.append(f"Bearish DP flow (B/S: {context.dp_buy_sell_ratio:.2f})")
        
        # Check put/call ratio
        if context.put_call_ratio > 1.2:  # High put activity
            bearish_confirmation = True
            reasons.append(f"High P/C ratio ({context.put_call_ratio:.2f})")
        
        # Check short volume
        if context.short_volume_pct > 35:  # High shorting
            bearish_confirmation = True
            reasons.append(f"High short volume ({context.short_volume_pct:.0f}%)")
        
        if not bearish_confirmation:
            return None  # No bearish confirmation
        
        # Calculate stops and targets
        stop = nearest_support * 1.005  # 0.5% above broken support (now resistance)
        risk = stop - price
        target = price - (risk * 2.0)  # 2:1 R/R for breakdown
        
        # Calculate confidence
        base_confidence = self._calculate_confidence_score(context, "BREAKDOWN", price)
        
        # Boost for breakdown-specific factors
        breakdown_boost = 0.0
        if context.dp_buy_sell_ratio < 0.7:
            breakdown_boost += 0.15
        if context.put_call_ratio > 1.3:
            breakdown_boost += 0.10
        if context.short_volume_pct > 40:
            breakdown_boost += 0.05
        
        confidence = min(base_confidence + breakdown_boost, 1.0)
        
        position_pct = 0.02 if confidence >= 0.85 else 0.01
        
        # Build rationale (was 'primary_reason')
        rationale = f"BREAKDOWN below DP support ${nearest_support:.2f}"
        
        return LiveSignal(
            symbol=symbol,
            action=SignalAction.SELL,  # Was string "SELL"
            timestamp=datetime.now(),
            entry_price=price,  # Was 'current_price'
            target_price=target,  # Was 'take_profit'
            stop_price=stop,  # Was 'stop_loss'
            confidence=confidence,
            signal_type=SignalType.BREAKDOWN,  # Was string "BREAKDOWN"
            rationale=rationale,  # Was 'primary_reason'
            dp_level=nearest_support,
            dp_volume=context.dp_total_volume,
            institutional_score=1.0 - context.institutional_buying_pressure,  # Inverted for bearish
            supporting_factors=reasons,
            warnings=[],
            is_master_signal=confidence >= self.min_master_confidence,
            is_actionable=True,
            position_size_pct=position_pct,
            risk_reward_ratio=(price - target) / (stop - price) if (stop - price) > 0 else 0
        )
    
    def _create_bearish_flow_signal(self, symbol: str, price: float,
                                   context: InstitutionalContext) -> Optional[LiveSignal]:
        """
        Create SELL signal from bearish institutional flow
        
        Detects when institutions are selling heavily (DP sell ratio high)
        """
        # Need strong bearish flow
        if context.dp_buy_sell_ratio >= 0.7:
            return None  # Not bearish enough
        
        if context.dp_total_volume < 1_000_000:
            return None  # Not enough volume
        
        # Find nearest resistance for target
        resistances = [bg for bg in context.dp_battlegrounds if bg >= price * 0.99]
        if not resistances:
            return None
        
        nearest_resistance = min(resistances)
        
        # Calculate stops and targets
        stop = price * 1.01  # 1% above entry
        risk = stop - price
        target = price - (risk * 2.0)  # 2:1 R/R
        
        # Calculate confidence
        base_confidence = self._calculate_confidence_score(context, "BEARISH_FLOW", price)
        
        # Boost for bearish flow
        bearish_boost = 0.0
        if context.dp_buy_sell_ratio < 0.6:
            bearish_boost += 0.20
        elif context.dp_buy_sell_ratio < 0.7:
            bearish_boost += 0.10
        
        confidence = min(base_confidence + bearish_boost, 1.0)
        
        position_pct = 0.02 if confidence >= 0.85 else 0.01
        
        # Build rationale (was 'primary_reason')
        rationale = (
            f"BEARISH INSTITUTIONAL FLOW: "
            f"DP B/S {context.dp_buy_sell_ratio:.2f}, "
            f"{context.dp_total_volume:,} shares"
        )
        
        supporting_factors = [
            f"Put/call ratio: {context.put_call_ratio:.2f}",
            f"Short volume: {context.short_volume_pct:.0f}%",
            f"DP buy/sell ratio: {context.dp_buy_sell_ratio:.2f}",
            f"DP volume: {context.dp_total_volume:,} shares"
        ]
        
        return LiveSignal(
            symbol=symbol,
            action=SignalAction.SELL,  # Was string "SELL"
            timestamp=datetime.now(),
            entry_price=price,  # Was 'current_price'
            target_price=target,  # Was 'take_profit'
            stop_price=stop,  # Was 'stop_loss'
            confidence=confidence,
            signal_type=SignalType.BEARISH_FLOW,  # Was string "BEARISH_FLOW"
            rationale=rationale,  # Was 'primary_reason'
            dp_level=nearest_resistance,
            dp_volume=context.dp_total_volume,
            institutional_score=1.0 - context.institutional_buying_pressure,
            supporting_factors=supporting_factors,
            warnings=[],
            is_master_signal=confidence >= self.min_master_confidence,
            is_actionable=True,
            position_size_pct=position_pct,
            risk_reward_ratio=(price - target) / (stop - price) if (stop - price) > 0 else 0
        )
    
    def _apply_narrative_enrichment(self, symbol: str, signals: List[Union[LiveSignal, LotterySignal]]) -> List[Union[LiveSignal, LotterySignal]]:
        """
        Apply narrative enrichment to all signals.
        
        Fetches market narrative for symbol and adjusts confidence based on:
        - Direction alignment (narrative BEARISH + signal SELL = boost)
        - Conviction level (HIGH conviction = stronger boost)
        - Causal chain (adds to rationale)
        
        Manager's Doctrine:
        "Narrative intelligence = catch them lying. When headlines say 'panic' 
        but DP shows accumulation, that's the edge. Confidence hits 90%+."
        
        Args:
            symbol: Ticker symbol
            signals: List of signals to enrich
        
        Returns:
            Enriched signals with narrative context
        """
        try:
            # Check cache first (narrative per symbol per day)
            today = datetime.now().strftime('%Y-%m-%d')
            cache_key = (symbol, today)
            
            if cache_key not in self.narrative_cache:
                logger.info(f"🧠 Fetching narrative for {symbol}...")
                narrative = market_narrative_pipeline(symbol, today, enable_logging=True)
                self.narrative_cache[cache_key] = narrative
            else:
                narrative = self.narrative_cache[cache_key]
                logger.debug(f"🧠 Using cached narrative for {symbol}")
            
            # Enrich each signal
            enriched = []
            for signal in signals:
                enriched_signal = self._enrich_single_signal(signal, narrative)
                enriched.append(enriched_signal)
            
            return enriched
            
        except Exception as e:
            logger.error(f"❌ Error applying narrative enrichment: {e}")
            return signals  # Return un-enriched on error
    
    def _enrich_single_signal(self, signal: Union[LiveSignal, LotterySignal], narrative) -> Union[LiveSignal, LotterySignal]:
        """
        Enrich a single signal with narrative context.
        
        Confidence Adjustments:
        - HIGH conviction + aligned direction: +15%
        - MEDIUM conviction + aligned direction: +10%
        - HIGH conviction + contradicting direction: -30% (VETO)
        - MEDIUM conviction + contradicting direction: -15%
        
        Args:
            signal: Signal to enrich
            narrative: MarketNarrative object
        
        Returns:
            Enriched signal
        """
        try:
            initial_confidence = signal.confidence
            
            # Check direction alignment
            narrative_bearish = narrative.overall_direction == "BEARISH"
            narrative_bullish = narrative.overall_direction == "BULLISH"
            signal_sell = signal.action == SignalAction.SELL
            signal_buy = signal.action == SignalAction.BUY
            
            aligned = (narrative_bearish and signal_sell) or (narrative_bullish and signal_buy)
            contradicts = (narrative_bearish and signal_buy) or (narrative_bullish and signal_sell)
            
            # Apply confidence adjustments
            if aligned:
                if narrative.conviction == "HIGH":
                    signal.confidence = min(signal.confidence * 1.15, 1.0)  # +15%
                    logger.info(f"   🎯 HIGH conviction narrative confirms {signal.action.value}: +15%")
                elif narrative.conviction == "MEDIUM":
                    signal.confidence = min(signal.confidence * 1.10, 1.0)  # +10%
                    logger.info(f"   🎯 MEDIUM conviction narrative confirms {signal.action.value}: +10%")
            
            elif contradicts:
                if narrative.conviction == "HIGH":
                    signal.confidence = max(signal.confidence * 0.70, 0.0)  # -30%
                    signal.warnings.append(f"HIGH conviction narrative contradicts: {narrative.causal_chain}")
                    logger.warning(f"   ⚠️  HIGH conviction narrative contradicts {signal.action.value}: -30%")
                elif narrative.conviction == "MEDIUM":
                    signal.confidence = max(signal.confidence * 0.85, 0.0)  # -15%
                    signal.warnings.append(f"MEDIUM conviction narrative contradicts: {narrative.causal_chain}")
                    logger.warning(f"   ⚠️  MEDIUM conviction narrative contradicts {signal.action.value}: -15%")
            
            # Add FULL narrative to rationale (Manager's fix: 8,154 chars not 6 words!)
            if narrative.causal_chain and narrative.causal_chain != "No clear causal chain (V1 heuristic).":
                # Build comprehensive narrative summary
                narrative_parts = []
                
                # Add causal chain (short version for CSV)
                narrative_parts.append(f"CAUSAL: {narrative.causal_chain[:100]}")
                
                # Add macro context (condensed)
                if narrative.macro_narrative and len(narrative.macro_narrative) > 50:
                    macro_summary = narrative.macro_narrative[:200].replace('\n', ' ')
                    narrative_parts.append(f"MACRO: {macro_summary}")
                
                # Add institutional reality (if available)
                if narrative.institutional_reality and 'summary' in narrative.institutional_reality:
                    inst_summary = narrative.institutional_reality['summary'][:150].replace('\n', ' ')
                    narrative_parts.append(f"INSTITUTIONAL: {inst_summary}")
                
                # Add divergences (if any)
                if narrative.divergences and len(narrative.divergences) > 0:
                    div_types = [d.get('type', 'UNKNOWN') for d in narrative.divergences[:2]]
                    narrative_parts.append(f"DIVERGENCE: {', '.join(div_types)}")
                
                signal.rationale += f" | NARRATIVE: {' | '.join(narrative_parts)}"
            
            # Log enrichment
            confidence_change = signal.confidence - initial_confidence
            if abs(confidence_change) > 0.01:
                logger.info(f"   📊 Narrative enrichment: {initial_confidence:.0%} → {signal.confidence:.0%} ({confidence_change:+.0%})")
            
            return signal
            
        except Exception as e:
            logger.error(f"❌ Error enriching signal: {e}")
            return signal  # Return un-enriched on error



