#!/usr/bin/env python3
"""
INSTITUTIONAL-GRADE REPLAY ENGINE
- Minute-by-minute replay of actual sessions
- Real DP data integration
- Complete cycle logging with reasoning
- NO MOCK DATA, NO SKIPPED CYCLES
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import logging
import json
import yfinance as yf
import sys
from pathlib import Path

# Add detectors to path
sys.path.append(str(Path(__file__).parent / 'detectors'))

from dp_magnet_tracker import DPMagnetTracker, MagnetAlert

logger = logging.getLogger(__name__)

@dataclass
class CycleState:
    """State for a single replay cycle"""
    timestamp: datetime
    price: float
    volume: int
    open: float
    high: float
    low: float
    close: float
    
    # DP structure
    nearest_support: Optional[float]
    nearest_resistance: Optional[float]
    distance_to_support: Optional[float]
    distance_to_resistance: Optional[float]
    support_volume: Optional[int]
    resistance_volume: Optional[int]
    
    # Regime
    regime: str
    trend_strength: float
    volatility: float
    momentum: float
    
    # Volume analysis
    volume_vs_avg: float
    volume_spike: bool
    
    # Decision
    decision: str  # SIGNAL_BUY, SIGNAL_SELL, NO_SIGNAL, AWAITING_LEVEL
    reasoning: str
    signal_confidence: float
    
    # Flow confirmation
    volume_confirmed: bool
    momentum_confirmed: bool
    dp_confirmed: bool
    
    # Magnet alerts
    magnet_alerts: List[str]  # List of alert descriptions
    approaching_magnet: Optional[float]
    magnet_eta: Optional[float]

class ReplayEngine:
    """Minute-by-minute replay engine with institutional-grade logging"""
    
    def __init__(self, dp_levels_df: pd.DataFrame):
        """
        Initialize replay engine with real DP data
        
        Args:
            dp_levels_df: DataFrame with columns [level, volume, trades, premium]
        """
        self.dp_levels_df = dp_levels_df
        
        # Extract key DP battlegrounds (>1M shares)
        self.battlegrounds = dp_levels_df[dp_levels_df['volume'] > 1000000].sort_values('volume', ascending=False)
        
        # All DP levels sorted by price
        self.all_dp_levels = dp_levels_df.sort_values('level')['level'].values
        
        # Regime detection parameters
        self.regime_window = 20  # 20-minute window
        self.trend_threshold = 0.005  # 0.5% move = trend
        self.chop_threshold = 0.002  # <0.2% = chop
        
        # Signal thresholds
        self.distance_threshold = 0.003  # 0.3% distance to trigger "near level"
        self.volume_multiplier = 1.5  # 1.5x avg volume = spike
        
        # Initialize magnet tracker
        dp_levels_list = [(row['level'], int(row['volume'])) for _, row in dp_levels_df.iterrows()]
        self.magnet_tracker = DPMagnetTracker(dp_levels_list)
        
        logger.info(f"🎯 Replay Engine initialized")
        logger.info(f"   Total DP levels: {len(self.all_dp_levels)}")
        logger.info(f"   Battlegrounds (>1M): {len(self.battlegrounds)}")
        logger.info(f"   Price range: ${self.all_dp_levels.min():.2f} - ${self.all_dp_levels.max():.2f}")
    
    def load_intraday_data(self, ticker: str, date: str) -> pd.DataFrame:
        """
        Load intraday price/volume data for a specific date
        
        Args:
            ticker: Stock symbol (e.g., 'SPY')
            date: Date string (e.g., '2025-10-17')
        
        Returns:
            DataFrame with minute-level OHLCV data
        """
        logger.info(f"📊 Loading intraday data for {ticker} on {date}")
        
        try:
            # Download 1-minute data for the date
            ticker_obj = yf.Ticker(ticker)
            
            # Get data for the specific date
            start_date = pd.to_datetime(date)
            end_date = start_date + timedelta(days=1)
            
            df = ticker_obj.history(start=start_date, end=end_date, interval='1m')
            
            if df.empty:
                logger.error(f"❌ No data returned for {ticker} on {date}")
                return pd.DataFrame()
            
            # Ensure timezone-naive
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            
            logger.info(f"✅ Loaded {len(df)} minute bars for {ticker}")
            logger.info(f"   Time range: {df.index.min()} to {df.index.max()}")
            logger.info(f"   Price range: ${df['Close'].min():.2f} - ${df['Close'].max():.2f}")
            
            return df
            
        except Exception as e:
            logger.error(f"❌ Error loading data: {e}")
            return pd.DataFrame()
    
    def find_nearest_dp_levels(self, price: float) -> Tuple[Optional[float], Optional[float], Optional[int], Optional[int]]:
        """
        Find nearest DP support and resistance levels
        
        Returns:
            (support_price, resistance_price, support_volume, resistance_volume)
        """
        # Find nearest support (below price)
        supports = self.all_dp_levels[self.all_dp_levels < price]
        if len(supports) > 0:
            nearest_support = supports[-1]  # Closest below
            support_volume = int(self.dp_levels_df[self.dp_levels_df['level'] == nearest_support]['volume'].iloc[0])
        else:
            nearest_support = None
            support_volume = None
        
        # Find nearest resistance (above price)
        resistances = self.all_dp_levels[self.all_dp_levels > price]
        if len(resistances) > 0:
            nearest_resistance = resistances[0]  # Closest above
            resistance_volume = int(self.dp_levels_df[self.dp_levels_df['level'] == nearest_resistance]['volume'].iloc[0])
        else:
            nearest_resistance = None
            resistance_volume = None
        
        return nearest_support, nearest_resistance, support_volume, resistance_volume
    
    def detect_regime(self, price_series: pd.Series) -> Tuple[str, float, float, float]:
        """
        Detect market regime from price action
        
        Returns:
            (regime, trend_strength, volatility, momentum)
        """
        if len(price_series) < 5:
            return "INSUFFICIENT_DATA", 0.0, 0.0, 0.0
        
        # Calculate trend strength (normalized slope)
        returns = price_series.pct_change().dropna()
        if len(returns) == 0:
            return "INSUFFICIENT_DATA", 0.0, 0.0, 0.0
        
        trend_strength = returns.mean()
        volatility = returns.std()
        momentum = (price_series.iloc[-1] - price_series.iloc[0]) / price_series.iloc[0]
        
        # Classify regime
        if abs(momentum) > self.trend_threshold:
            if momentum > 0:
                regime = "UPTREND"
            else:
                regime = "DOWNTREND"
        elif volatility > 0.01:  # High vol but no direction
            regime = "CHOP"
        else:
            regime = "RANGE"
        
        return regime, trend_strength, volatility, momentum
    
    def check_flow_confirmation(self, volume: int, avg_volume: float, momentum: float, 
                                 at_support: bool, at_resistance: bool) -> Tuple[bool, bool]:
        """
        Check if volume and momentum confirm the DP structure
        
        Returns:
            (volume_confirmed, momentum_confirmed)
        """
        # Volume confirmation
        volume_confirmed = volume > (avg_volume * self.volume_multiplier)
        
        # Momentum confirmation
        if at_support:
            # At support, need bullish momentum (bouncing)
            momentum_confirmed = momentum > 0
        elif at_resistance:
            # At resistance, need bearish momentum (rejecting) OR strong bull breakout
            momentum_confirmed = momentum < 0 or momentum > 0.01  # Allow strong breakouts
        else:
            momentum_confirmed = False
        
        return volume_confirmed, momentum_confirmed
    
    def make_signal_decision(self, state_dict: Dict) -> Tuple[str, str, float]:
        """
        Make signal decision based on all factors
        
        Returns:
            (decision, reasoning, confidence)
        """
        price = state_dict['price']
        nearest_support = state_dict['nearest_support']
        nearest_resistance = state_dict['nearest_resistance']
        distance_to_support = state_dict['distance_to_support']
        distance_to_resistance = state_dict['distance_to_resistance']
        volume_confirmed = state_dict['volume_confirmed']
        momentum_confirmed = state_dict['momentum_confirmed']
        regime = state_dict['regime']
        
        # Check if at DP level
        at_support = nearest_support and abs(distance_to_support / price) < self.distance_threshold
        at_resistance = nearest_resistance and abs(distance_to_resistance / price) < self.distance_threshold
        
        # BUY logic: At support + volume + momentum + favorable regime
        if at_support:
            if volume_confirmed and momentum_confirmed:
                confidence = 0.8
                if regime in ["UPTREND", "RANGE"]:
                    confidence = 0.9
                return "SIGNAL_BUY", f"At DP support ${nearest_support:.2f}, volume+momentum confirmed, regime={regime}", confidence
            elif volume_confirmed:
                return "NO_SIGNAL", f"At DP support ${nearest_support:.2f}, volume OK but momentum NOT confirmed", 0.3
            elif momentum_confirmed:
                return "NO_SIGNAL", f"At DP support ${nearest_support:.2f}, momentum OK but volume NOT confirmed", 0.3
            else:
                return "NO_SIGNAL", f"At DP support ${nearest_support:.2f}, but NO volume/momentum confirmation", 0.1
        
        # SELL logic: At resistance + volume + momentum + favorable regime
        elif at_resistance:
            if volume_confirmed and momentum_confirmed:
                confidence = 0.8
                if regime in ["DOWNTREND", "RANGE"]:
                    confidence = 0.9
                return "SIGNAL_SELL", f"At DP resistance ${nearest_resistance:.2f}, volume+momentum confirmed, regime={regime}", confidence
            else:
                return "NO_SIGNAL", f"At DP resistance ${nearest_resistance:.2f}, but flow NOT confirmed", 0.2
        
        # AWAITING logic: Approaching DP level
        elif nearest_support and abs(distance_to_support / price) < 0.01:  # Within 1%
            return "AWAITING_LEVEL", f"Approaching DP support ${nearest_support:.2f} ({distance_to_support:.2f}), awaiting touch", 0.0
        elif nearest_resistance and abs(distance_to_resistance / price) < 0.01:  # Within 1%
            return "AWAITING_LEVEL", f"Approaching DP resistance ${nearest_resistance:.2f} (+{distance_to_resistance:.2f}), awaiting touch", 0.0
        
        # NO_SIGNAL: Not near any DP level
        else:
            return "NO_SIGNAL", f"Not near any DP level (support: {distance_to_support:.2f}, resistance: +{distance_to_resistance:.2f})", 0.0
    
    def process_cycle(self, timestamp: datetime, bar: pd.Series, 
                      price_window: pd.Series, volume_window: pd.Series) -> CycleState:
        """
        Process a single replay cycle
        
        Returns:
            CycleState with all data and decision
        """
        price = bar['Close']
        volume = int(bar['Volume'])
        
        # Find nearest DP levels
        nearest_support, nearest_resistance, support_volume, resistance_volume = self.find_nearest_dp_levels(price)
        
        distance_to_support = price - nearest_support if nearest_support else None
        distance_to_resistance = nearest_resistance - price if nearest_resistance else None
        
        # Detect regime
        regime, trend_strength, volatility, momentum = self.detect_regime(price_window)
        
        # Volume analysis
        avg_volume = volume_window.mean() if len(volume_window) > 0 else volume
        volume_vs_avg = volume / avg_volume if avg_volume > 0 else 1.0
        volume_spike = volume > (avg_volume * self.volume_multiplier)
        
        # Check if at DP level
        at_support = nearest_support and abs(distance_to_support / price) < self.distance_threshold
        at_resistance = nearest_resistance and abs(distance_to_resistance / price) < self.distance_threshold
        
        # Flow confirmation
        volume_confirmed, momentum_confirmed = self.check_flow_confirmation(
            volume, avg_volume, momentum, at_support, at_resistance
        )
        
        # DP confirmation (at a significant level)
        dp_confirmed = (at_support or at_resistance)
        
        # Build state dict for decision
        state_dict = {
            'price': price,
            'nearest_support': nearest_support,
            'nearest_resistance': nearest_resistance,
            'distance_to_support': distance_to_support,
            'distance_to_resistance': distance_to_resistance,
            'volume_confirmed': volume_confirmed,
            'momentum_confirmed': momentum_confirmed,
            'regime': regime
        }
        
        # Initialize decision variables
        decision = "NO_SIGNAL"
        reasoning = ""
        confidence = 0.0
        
        # Update magnet tracker and get alerts
        magnet_alerts = self.magnet_tracker.update(timestamp, price, volume, momentum)
        
        # Process magnet alerts
        alert_descriptions = []
        approaching_magnet = None
        magnet_eta = None
        
        for alert in magnet_alerts:
            if alert.alert_type == "BOUNCING":
                alert_descriptions.append(f"🎯 BOUNCING off ${alert.magnet_level:.2f} magnet ({alert.magnet_volume:,} shares)")
                # Override decision if we have a strong bounce
                if alert.strength > 0.8 and volume_confirmed:
                    decision = "SIGNAL_BUY"
                    reasoning = f"STRONG BOUNCE off institutional magnet ${alert.magnet_level:.2f} ({alert.magnet_volume:,} shares)"
                    confidence = 0.95
            
            elif alert.alert_type == "BREAKING":
                alert_descriptions.append(f"💥 BREAKING through ${alert.magnet_level:.2f} magnet ({alert.magnet_volume:,} shares)")
                # Override decision if we have a strong break
                if alert.strength > 0.8 and volume_confirmed:
                    if alert.magnet_level < price:  # Breaking above resistance
                        decision = "SIGNAL_BUY"
                        reasoning = f"BREAKOUT above institutional resistance ${alert.magnet_level:.2f} ({alert.magnet_volume:,} shares)"
                        confidence = 0.95
                    else:  # Breaking below support
                        decision = "SIGNAL_SELL"
                        reasoning = f"BREAKDOWN below institutional support ${alert.magnet_level:.2f} ({alert.magnet_volume:,} shares)"
                        confidence = 0.95
            
            elif alert.alert_type == "APPROACHING":
                alert_descriptions.append(f"🧲 Approaching ${alert.magnet_level:.2f} magnet (ETA: {alert.eta_minutes:.0f}min)" if alert.eta_minutes else f"🧲 Approaching ${alert.magnet_level:.2f} magnet")
                approaching_magnet = alert.magnet_level
                magnet_eta = alert.eta_minutes
            
            elif alert.alert_type == "REJECTING":
                alert_descriptions.append(f"🚫 REJECTING from ${alert.magnet_level:.2f} magnet ({alert.magnet_volume:,} shares)")
            
            elif alert.alert_type == "AT_LEVEL":
                alert_descriptions.append(f"📍 AT ${alert.magnet_level:.2f} magnet - awaiting direction")
            
            elif alert.alert_type == "STALLING":
                alert_descriptions.append(f"⏸️ STALLING at ${alert.magnet_level:.2f} magnet - battleground")
        
        # Make signal decision (if not overridden by magnet logic)
        if not alert_descriptions or decision == "NO_SIGNAL":
            decision, reasoning, confidence = self.make_signal_decision(state_dict)
        
        # Create cycle state
        state = CycleState(
            timestamp=timestamp,
            price=price,
            volume=volume,
            open=bar['Open'],
            high=bar['High'],
            low=bar['Low'],
            close=bar['Close'],
            nearest_support=nearest_support,
            nearest_resistance=nearest_resistance,
            distance_to_support=distance_to_support,
            distance_to_resistance=distance_to_resistance,
            support_volume=support_volume,
            resistance_volume=resistance_volume,
            regime=regime,
            trend_strength=trend_strength,
            volatility=volatility,
            momentum=momentum,
            volume_vs_avg=volume_vs_avg,
            volume_spike=volume_spike,
            decision=decision,
            reasoning=reasoning,
            signal_confidence=confidence,
            volume_confirmed=volume_confirmed,
            momentum_confirmed=momentum_confirmed,
            dp_confirmed=dp_confirmed,
            magnet_alerts=alert_descriptions,
            approaching_magnet=approaching_magnet,
            magnet_eta=magnet_eta
        )
        
        return state
    
    def replay_session(self, ticker: str, date: str, output_file: str = None) -> List[CycleState]:
        """
        Replay entire session with minute-by-minute logging
        
        Args:
            ticker: Stock symbol
            date: Date to replay
            output_file: Optional CSV file path for logging
        
        Returns:
            List of CycleState objects
        """
        logger.info(f"🎬 STARTING SESSION REPLAY: {ticker} on {date}")
        logger.info("=" * 80)
        
        # Load intraday data
        df = self.load_intraday_data(ticker, date)
        if df.empty:
            logger.error("❌ REPLAY ABORTED: No data available")
            return []
        
        # Process each minute
        states = []
        
        for i, (timestamp, bar) in enumerate(df.iterrows()):
            # Get rolling windows
            start_idx = max(0, i - self.regime_window)
            price_window = df['Close'].iloc[start_idx:i+1]
            volume_window = df['Volume'].iloc[start_idx:i+1]
            
            # Process cycle
            state = self.process_cycle(timestamp, bar, price_window, volume_window)
            states.append(state)
            
            # Log cycle
            self._log_cycle(state, i+1, len(df))
        
        logger.info("=" * 80)
        logger.info(f"🏁 REPLAY COMPLETE: {len(states)} cycles processed")
        
        # Generate summary
        self._generate_summary(states)
        
        # Save to CSV if requested
        if output_file:
            self._save_to_csv(states, output_file)
        
        return states
    
    def _log_cycle(self, state: CycleState, cycle_num: int, total_cycles: int):
        """Log a single cycle"""
        logger.info(f"[{state.timestamp}] CYCLE {cycle_num}/{total_cycles}")
        logger.info(f"Price: ${state.price:.2f} | Volume: {state.volume:,} | Regime: {state.regime}")
        logger.info(f"Nearest Support: ${state.nearest_support:.2f} ({state.distance_to_support:+.2f}) | Vol: {state.support_volume:,}" if state.nearest_support else "Nearest Support: NONE")
        logger.info(f"Nearest Resistance: ${state.nearest_resistance:.2f} ({state.distance_to_resistance:+.2f}) | Vol: {state.resistance_volume:,}" if state.nearest_resistance else "Nearest Resistance: NONE")
        logger.info(f"Volume vs Avg: {state.volume_vs_avg:.2f}x | Spike: {state.volume_spike}")
        logger.info(f"Momentum: {state.momentum:+.4f} | Trend: {state.trend_strength:+.4f} | Vol: {state.volatility:.4f}")
        logger.info(f"Flow: Vol={state.volume_confirmed}, Mom={state.momentum_confirmed}, DP={state.dp_confirmed}")
        
        # Log magnet alerts
        if state.magnet_alerts:
            for alert in state.magnet_alerts:
                logger.info(f"MAGNET: {alert}")
        
        logger.info(f"DECISION: {state.decision} | Confidence: {state.signal_confidence:.2f}")
        logger.info(f"REASONING: {state.reasoning}")
        logger.info("-" * 80)
    
    def _generate_summary(self, states: List[CycleState]):
        """Generate summary statistics"""
        total_cycles = len(states)
        signal_buys = sum(1 for s in states if s.decision == "SIGNAL_BUY")
        signal_sells = sum(1 for s in states if s.decision == "SIGNAL_SELL")
        awaiting = sum(1 for s in states if s.decision == "AWAITING_LEVEL")
        no_signals = sum(1 for s in states if s.decision == "NO_SIGNAL")
        
        at_dp_levels = sum(1 for s in states if s.dp_confirmed)
        away_from_dp = total_cycles - at_dp_levels
        
        logger.info("")
        logger.info("📊 SESSION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total Cycles: {total_cycles}")
        logger.info(f"Signal BUY: {signal_buys} ({signal_buys/total_cycles*100:.1f}%)")
        logger.info(f"Signal SELL: {signal_sells} ({signal_sells/total_cycles*100:.1f}%)")
        logger.info(f"Awaiting Level: {awaiting} ({awaiting/total_cycles*100:.1f}%)")
        logger.info(f"No Signal: {no_signals} ({no_signals/total_cycles*100:.1f}%)")
        logger.info("")
        logger.info(f"At DP Levels: {at_dp_levels} ({at_dp_levels/total_cycles*100:.1f}%)")
        logger.info(f"Away from DP: {away_from_dp} ({away_from_dp/total_cycles*100:.1f}%)")
        logger.info("=" * 80)
    
    def _save_to_csv(self, states: List[CycleState], output_file: str):
        """Save states to CSV"""
        records = []
        for state in states:
            records.append({
                'timestamp': state.timestamp,
                'price': state.price,
                'volume': state.volume,
                'open': state.open,
                'high': state.high,
                'low': state.low,
                'close': state.close,
                'nearest_support': state.nearest_support,
                'nearest_resistance': state.nearest_resistance,
                'distance_to_support': state.distance_to_support,
                'distance_to_resistance': state.distance_to_resistance,
                'support_volume': state.support_volume,
                'resistance_volume': state.resistance_volume,
                'regime': state.regime,
                'trend_strength': state.trend_strength,
                'volatility': state.volatility,
                'momentum': state.momentum,
                'volume_vs_avg': state.volume_vs_avg,
                'volume_spike': state.volume_spike,
                'decision': state.decision,
                'reasoning': state.reasoning,
                'signal_confidence': state.signal_confidence,
                'volume_confirmed': state.volume_confirmed,
                'momentum_confirmed': state.momentum_confirmed,
                'dp_confirmed': state.dp_confirmed
            })
        
        df = pd.DataFrame(records)
        df.to_csv(output_file, index=False)
        logger.info(f"💾 Saved replay log to: {output_file}")

