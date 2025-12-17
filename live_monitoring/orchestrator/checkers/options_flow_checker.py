#!/usr/bin/env python3
"""
OPTIONS FLOW CHECKER - Modular checker for options flow analysis

Runs every 30-60 minutes during RTH
Detects unusual options activity (call/put accumulation, gamma squeeze setups)

MOAT EDGE: P/C ratio + max pain + gamma squeeze detection
Expected Edge: 15-20%

Architecture:
- Inherits from BaseChecker
- Uses OptionsFlowStrategy for detection logic
- Creates CheckerAlert for Discord notifications

NOTE: Currently uses yfinance (delayed data). For real-time sweeps,
      a premium API like Unusual Whales or FlowAlgo would be needed.
"""

import os
import sys
from datetime import datetime, timedelta
from typing import List, Optional
import pytz

# Add paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from live_monitoring.orchestrator.checkers.base_checker import BaseChecker, CheckerAlert
from live_monitoring.strategies.options_flow_strategy import OptionsFlowStrategy, OptionsFlowSignal
from live_monitoring.core.lottery_signals import SignalType


class OptionsFlowChecker(BaseChecker):
    """
    Options Flow Checker
    
    Detects unusual options activity and generates signals for:
    - Heavy call accumulation (bullish)
    - Heavy put accumulation (bearish)
    - Gamma squeeze setups
    
    Schedule: Runs every 30-60 minutes during RTH
    """
    
    def __init__(self, alert_manager, api_key: str = None, unified_mode: bool = False):
        """
        Initialize the options flow checker.
        
        Args:
            alert_manager: AlertManager for sending Discord alerts
            api_key: Optional API key (for future premium data sources)
            unified_mode: If True, suppresses individual alerts
        """
        super().__init__(alert_manager, unified_mode)
        
        # Get API key from env if not provided (for future use)
        self.api_key = api_key or os.getenv('CHARTEXCHANGE_API_KEY')
        
        # Initialize the strategy
        self.strategy = OptionsFlowStrategy(api_key=self.api_key)
        
        # Track last check time to enforce interval
        self._last_check_time: Optional[datetime] = None
        
        # Check interval in minutes
        self.check_interval_minutes = 30
        
        # Symbols to monitor
        self.symbols = ['SPY', 'QQQ']
        
        # Timezone
        self.et_tz = pytz.timezone('US/Eastern')
        
        # Cache for alerts to avoid spam
        self._alert_cache: dict = {}
        self._alert_cooldown_hours = 4
    
    @property
    def name(self) -> str:
        """Checker name for logging and identification"""
        return "options_flow_checker"
    
    def _is_market_hours(self) -> bool:
        """Check if we're in regular trading hours (9:30 AM - 4:00 PM ET)"""
        now_et = datetime.now(self.et_tz)
        current_time = now_et.time()
        
        # RTH: 9:30 AM - 4:00 PM ET
        market_open = datetime.strptime("09:30", "%H:%M").time()
        market_close = datetime.strptime("16:00", "%H:%M").time()
        
        # Also check it's a weekday
        is_weekday = now_et.weekday() < 5
        
        return is_weekday and market_open <= current_time <= market_close
    
    def _should_check(self) -> bool:
        """Check if enough time has passed since last check"""
        if self._last_check_time is None:
            return True
        
        elapsed = datetime.now(self.et_tz) - self._last_check_time
        return elapsed >= timedelta(minutes=self.check_interval_minutes)
    
    def _is_alert_on_cooldown(self, symbol: str, signal_type: SignalType) -> bool:
        """Check if we've already alerted for this signal recently"""
        cache_key = f"{symbol}_{signal_type.value}"
        
        if cache_key not in self._alert_cache:
            return False
        
        last_alert_time = self._alert_cache[cache_key]
        elapsed = datetime.now(self.et_tz) - last_alert_time
        
        return elapsed < timedelta(hours=self._alert_cooldown_hours)
    
    def _record_alert(self, symbol: str, signal_type: SignalType):
        """Record that we sent an alert"""
        cache_key = f"{symbol}_{signal_type.value}"
        self._alert_cache[cache_key] = datetime.now(self.et_tz)
    
    def check(self, symbols: List[str] = None, inst_context: dict = None) -> List[CheckerAlert]:
        """
        Run options flow analysis.
        
        Runs during market hours at specified intervals.
        
        Args:
            symbols: List of symbols to check (defaults to SPY, QQQ)
            inst_context: Optional institutional context (not used currently)
            
        Returns:
            List of CheckerAlert objects for any detected signals
        """
        alerts = []
        
        # Check if we're in market hours
        if not self._is_market_hours():
            return alerts
        
        # Check if enough time has passed
        if not self._should_check():
            return alerts
        
        # Use provided symbols or defaults
        check_symbols = symbols or self.symbols
        
        for symbol in check_symbols:
            try:
                # Detect options flow signals
                signal = self.strategy.detect_options_signals(symbol)
                
                if signal:
                    # Check cooldown
                    if self._is_alert_on_cooldown(symbol, signal.signal_type):
                        print(f"[{self.name}] ⏸️ {symbol} {signal.signal_type.value} on cooldown")
                        continue
                    
                    alert = self._create_options_alert(signal)
                    alerts.append(alert)
                    
                    # Record the alert
                    self._record_alert(symbol, signal.signal_type)
                    
            except Exception as e:
                print(f"[{self.name}] ❌ Error checking {symbol}: {e}")
        
        # Update last check time
        self._last_check_time = datetime.now(self.et_tz)
        
        return alerts
    
    def _create_options_alert(self, signal: OptionsFlowSignal) -> CheckerAlert:
        """
        Create a CheckerAlert from an OptionsFlowSignal.
        
        Args:
            signal: The options flow signal from the strategy
            
        Returns:
            CheckerAlert formatted for Discord
        """
        # Map signal type to emoji and color
        type_config = {
            SignalType.CALL_ACCUMULATION: ("📈", 0x00FF00, "BULLISH"),       # Green
            SignalType.PUT_ACCUMULATION: ("📉", 0xFF0000, "BEARISH"),        # Red
            SignalType.GAMMA_SQUEEZE_OPTIONS: ("🚀", 0xFF00FF, "EXPLOSIVE"), # Magenta
        }
        
        emoji, color, bias = type_config.get(
            signal.signal_type, 
            ("📊", 0x808080, "NEUTRAL")
        )
        
        # Build the embed
        title = f"{emoji} OPTIONS FLOW: {signal.symbol}"
        
        # Format the message
        message_parts = [
            f"**Signal Type:** {signal.signal_type.value}",
            f"**Current Price:** ${signal.current_price:.2f}",
            "",
            f"**📊 Options Metrics:**",
            f"Put/Call Ratio: {signal.put_call_ratio:.2f}",
            f"Max Pain: ${signal.max_pain:.2f}",
            f"Distance to Max Pain: {signal.max_pain_distance_pct:.2f}%",
        ]
        
        if signal.total_call_oi > 0:
            message_parts.append(f"Total Call OI: {signal.total_call_oi:,}")
        if signal.total_put_oi > 0:
            message_parts.append(f"Total Put OI: {signal.total_put_oi:,}")
        
        # Add trade setup
        message_parts.extend([
            "",
            f"**📊 Trade Setup:**",
            f"Entry: ${signal.entry_price:.2f}",
            f"Stop: ${signal.stop_price:.2f}",
            f"Target: ${signal.target_price:.2f}",
            "",
            f"**💯 Confidence:** {signal.confidence:.0%}",
        ])
        
        # Add reasoning
        if signal.reasoning:
            message_parts.extend([
                "",
                f"**🧠 Reasoning:**",
                signal.reasoning
            ])
        
        # Add data source warning
        message_parts.extend([
            "",
            "⚠️ *Data from yfinance (delayed). For real-time sweeps, premium API needed.*"
        ])
        
        message = "\n".join(message_parts)
        
        return CheckerAlert(
            checker_name=self.name,
            title=title,
            message=message,
            color=color,
            fields={
                "Symbol": signal.symbol,
                "Type": signal.signal_type.value,
                "P/C Ratio": f"{signal.put_call_ratio:.2f}",
                "Max Pain": f"${signal.max_pain:.2f}",
                "Confidence": f"{signal.confidence:.0%}",
                "Bias": bias,
            },
            timestamp=datetime.now(self.et_tz),
            priority="high" if signal.confidence >= 0.7 else "medium"
        )


# Standalone test
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    print("🧪 Testing OptionsFlowChecker...")
    print("=" * 50)
    
    # Mock alert manager for testing
    class MockAlertManager:
        def send_alert(self, alert):
            print(f"[MOCK ALERT] {alert.title}")
            print(alert.message)
    
    api_key = os.getenv('CHARTEXCHANGE_API_KEY')
    checker = OptionsFlowChecker(
        alert_manager=MockAlertManager(),
        api_key=api_key
    )
    
    print(f"Checker name: {checker.name}")
    print(f"Is market hours: {checker._is_market_hours()}")
    print(f"Should check: {checker._should_check()}")
    
    # Force check regardless of time for testing
    original_market_hours = checker._is_market_hours
    checker._is_market_hours = lambda: True
    
    print("\n🔍 Running options flow detection...")
    alerts = checker.check()
    
    if alerts:
        for alert in alerts:
            print(f"\n✅ Alert Generated:")
            print(f"   Title: {alert.title}")
            print(f"   Priority: {alert.priority}")
            print(f"   Fields: {alert.fields}")
    else:
        print("\n⚠️ No options flow signals detected (thresholds not met)")
    
    # Restore
    checker._is_market_hours = original_market_hours
    
    print("\n" + "=" * 50)
    print("✅ OptionsFlowChecker test complete!")

