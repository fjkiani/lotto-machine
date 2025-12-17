#!/usr/bin/env python3
"""
PRE-MARKET GAP CHECKER - Modular checker for gap detection

Runs ONCE per day before market open (8:00-9:30 AM ET)
Detects overnight gaps vs DP levels for opening range breakouts

MOAT EDGE: Gap + DP confluence = unique institutional insight
Expected Edge: 20-25%

Architecture:
- Inherits from BaseChecker
- Uses PreMarketGapStrategy for detection logic
- Creates CheckerAlert for Discord notifications
"""

import os
import sys
from datetime import datetime, timedelta
from typing import List, Optional
import pytz

# Add paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from live_monitoring.orchestrator.checkers.base_checker import BaseChecker, CheckerAlert
from live_monitoring.strategies.premarket_gap_strategy import PreMarketGapStrategy, PreMarketGapSignal
from live_monitoring.core.lottery_signals import SignalType


class PreMarketGapChecker(BaseChecker):
    """
    Pre-Market Gap Checker
    
    Detects overnight gaps and correlates with DP levels for high-probability
    opening range breakout/breakdown signals.
    
    Schedule: Runs ONCE per day, 8:00-9:30 AM ET
    """
    
    def __init__(self, alert_manager, api_key: str = None, unified_mode: bool = False):
        """
        Initialize the pre-market gap checker.
        
        Args:
            alert_manager: AlertManager for sending Discord alerts
            api_key: ChartExchange API key for DP data
            unified_mode: If True, suppresses individual alerts
        """
        super().__init__(alert_manager, unified_mode)
        
        # Get API key from env if not provided
        self.api_key = api_key or os.getenv('CHARTEXCHANGE_API_KEY')
        
        # Initialize the strategy
        self.strategy = PreMarketGapStrategy(api_key=self.api_key)
        
        # Track last check date to ensure we only run once per day
        self._last_checked_date: Optional[str] = None
        
        # Symbols to monitor
        self.symbols = ['SPY', 'QQQ']
        
        # Timezone
        self.et_tz = pytz.timezone('US/Eastern')
    
    @property
    def name(self) -> str:
        """Checker name for logging and identification"""
        return "premarket_gap_checker"
    
    def _is_premarket_window(self) -> bool:
        """Check if we're in the pre-market analysis window (8:00-9:30 AM ET)"""
        now_et = datetime.now(self.et_tz)
        current_time = now_et.time()
        
        # Pre-market window: 8:00 AM - 9:30 AM ET
        premarket_start = datetime.strptime("08:00", "%H:%M").time()
        premarket_end = datetime.strptime("09:30", "%H:%M").time()
        
        return premarket_start <= current_time <= premarket_end
    
    def _already_checked_today(self) -> bool:
        """Check if we've already run the gap analysis today"""
        today = datetime.now(self.et_tz).strftime("%Y-%m-%d")
        return self._last_checked_date == today
    
    def check(self, symbols: List[str] = None, inst_context: dict = None) -> List[CheckerAlert]:
        """
        Run pre-market gap detection.
        
        Only runs once per day during pre-market window.
        
        Args:
            symbols: List of symbols to check (defaults to SPY, QQQ)
            inst_context: Optional institutional context with DP levels
            
        Returns:
            List of CheckerAlert objects for any detected gap signals
        """
        alerts = []
        
        # Check if we're in the pre-market window
        if not self._is_premarket_window():
            return alerts
        
        # Check if we've already analyzed today
        if self._already_checked_today():
            return alerts
        
        # Use provided symbols or defaults
        check_symbols = symbols or self.symbols
        
        for symbol in check_symbols:
            try:
                # Get DP levels from context or fetch directly
                dp_levels = None
                if inst_context and symbol in inst_context:
                    ctx = inst_context[symbol]
                    if hasattr(ctx, 'dp_levels') and ctx.dp_levels:
                        dp_levels = ctx.dp_levels
                
                # Detect gap signals
                signal = self.strategy.detect_gap_signals(
                    symbol=symbol,
                    dp_levels=dp_levels
                )
                
                if signal:
                    alert = self._create_gap_alert(signal)
                    alerts.append(alert)
                    
            except Exception as e:
                print(f"[{self.name}] ❌ Error checking {symbol}: {e}")
        
        # Mark today as checked
        self._last_checked_date = datetime.now(self.et_tz).strftime("%Y-%m-%d")
        
        return alerts
    
    def _create_gap_alert(self, signal: PreMarketGapSignal) -> CheckerAlert:
        """
        Create a CheckerAlert from a PreMarketGapSignal.
        
        Args:
            signal: The gap signal from the strategy
            
        Returns:
            CheckerAlert formatted for Discord
        """
        # Map signal type to emoji and color
        type_config = {
            SignalType.GAP_BREAKOUT: ("🚀", 0x00FF00, "BULLISH"),    # Green
            SignalType.GAP_BREAKDOWN: ("📉", 0xFF0000, "BEARISH"),   # Red
            SignalType.GAP_FILL: ("🔄", 0xFFAA00, "NEUTRAL"),        # Orange
            SignalType.GAP_UP: ("⬆️", 0x00FF00, "BULLISH"),          # Green
            SignalType.GAP_DOWN: ("⬇️", 0xFF0000, "BEARISH"),        # Red
        }
        
        emoji, color, bias = type_config.get(
            signal.signal_type, 
            ("📊", 0x808080, "NEUTRAL")
        )
        
        # Build the embed
        title = f"{emoji} PRE-MARKET GAP: {signal.symbol}"
        
        # Format the message
        message_parts = [
            f"**Signal Type:** {signal.signal_type.value}",
            f"**Gap Size:** {signal.gap_percent:.2f}%",
            f"**Pre-Market Price:** ${signal.premarket_price:.2f}",
            f"**Previous Close:** ${signal.prev_close:.2f}",
            "",
            f"**📊 Trade Setup:**",
            f"Entry: ${signal.entry_price:.2f}",
            f"Stop: ${signal.stop_price:.2f}",
            f"Target: ${signal.target_price:.2f}",
            "",
            f"**💯 Confidence:** {signal.confidence:.0%}",
        ]
        
        # Add DP context if available
        if signal.nearest_dp_level:
            message_parts.extend([
                "",
                f"**🏛️ DP Context:**",
                f"Nearest DP Level: ${signal.nearest_dp_level:.2f}",
                f"Distance to DP: {signal.dp_distance_pct:.2f}%",
            ])
        
        # Add reasoning
        if signal.reasoning:
            message_parts.extend([
                "",
                f"**🧠 Reasoning:**",
                signal.reasoning
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
                "Gap %": f"{signal.gap_percent:.2f}%",
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
    
    print("🧪 Testing PreMarketGapChecker...")
    print("=" * 50)
    
    # Mock alert manager for testing
    class MockAlertManager:
        def send_alert(self, alert):
            print(f"[MOCK ALERT] {alert.title}")
            print(alert.message)
    
    api_key = os.getenv('CHARTEXCHANGE_API_KEY')
    checker = PreMarketGapChecker(
        alert_manager=MockAlertManager(),
        api_key=api_key
    )
    
    print(f"Checker name: {checker.name}")
    print(f"Is pre-market window: {checker._is_premarket_window()}")
    print(f"Already checked today: {checker._already_checked_today()}")
    
    # Force check regardless of time for testing
    checker._last_checked_date = None
    
    # Temporarily override the time check for testing
    original_check = checker._is_premarket_window
    checker._is_premarket_window = lambda: True
    
    print("\n🔍 Running gap detection...")
    alerts = checker.check()
    
    if alerts:
        for alert in alerts:
            print(f"\n✅ Alert Generated:")
            print(f"   Title: {alert.title}")
            print(f"   Priority: {alert.priority}")
            print(f"   Fields: {alert.fields}")
    else:
        print("\n⚠️ No gap signals detected (may be outside pre-market or no significant gaps)")
    
    # Restore
    checker._is_premarket_window = original_check
    
    print("\n" + "=" * 50)
    print("✅ PreMarketGapChecker test complete!")

