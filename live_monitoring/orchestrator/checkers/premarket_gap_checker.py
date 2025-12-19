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
        Create a CheckerAlert from a PreMarketGapSignal with FULL CONTEXT.
        
        Args:
            signal: The gap signal from the strategy
            
        Returns:
            CheckerAlert formatted for Discord with actionable trade setup
        """
        # Map signal type to emoji and color
        type_config = {
            SignalType.GAP_BREAKOUT: ("🚀", 0x00FF00, "BULLISH", "LONG"),
            SignalType.GAP_BREAKDOWN: ("📉", 0xFF0000, "BEARISH", "SHORT"),
            SignalType.GAP_FILL: ("🔄", 0xFFAA00, "NEUTRAL", "FADE"),
            SignalType.GAP_UP: ("⬆️", 0x00FF00, "BULLISH", "LONG"),
            SignalType.GAP_DOWN: ("⬇️", 0xFF0000, "BEARISH", "SHORT"),
        }
        
        emoji, color, bias, action = type_config.get(
            signal.signal_type, 
            ("📊", 0x808080, "NEUTRAL", "WAIT")
        )
        
        # Calculate risk/reward
        risk = abs(signal.entry_price - signal.stop_price)
        reward = abs(signal.target_price - signal.entry_price)
        rr_ratio = reward / risk if risk > 0 else 0
        
        # Build the embed title
        title = f"{emoji} PRE-MARKET GAP: {signal.symbol} | {signal.signal_type.value}"
        
        # Format the FULL CONTEXT message
        message_parts = [
            f"**🎯 ACTION: {action}**",
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "**📊 GAP ANALYSIS:**",
            f"• Gap Size: **{signal.gap_percent:+.2f}%**",
            f"• Pre-Market: **${signal.premarket_price:.2f}**",
            f"• Prev Close: ${signal.prev_close:.2f}",
            f"• Direction: {bias}",
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "**💰 TRADE SETUP:**",
            f"• Entry: **${signal.entry_price:.2f}**",
            f"• Stop Loss: **${signal.stop_price:.2f}** ({(abs(signal.entry_price - signal.stop_price) / signal.entry_price * 100):.2f}%)",
            f"• Take Profit: **${signal.target_price:.2f}** ({(abs(signal.target_price - signal.entry_price) / signal.entry_price * 100):.2f}%)",
            f"• Risk/Reward: **{rr_ratio:.1f}:1**",
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "**📈 HOW TO TRADE:**",
        ]
        
        # Add specific trading instructions based on signal type
        if signal.signal_type == SignalType.GAP_BREAKOUT:
            message_parts.extend([
                "1️⃣ Wait for market open (9:30 AM ET)",
                "2️⃣ Watch first 5-min candle close above pre-market high",
                "3️⃣ Enter LONG on breakout confirmation",
                "4️⃣ Stop below first hour low",
                "5️⃣ Target: Gap extension (2:1 R/R)",
            ])
        elif signal.signal_type == SignalType.GAP_BREAKDOWN:
            message_parts.extend([
                "1️⃣ Wait for market open (9:30 AM ET)",
                "2️⃣ Watch first 5-min candle close below pre-market low",
                "3️⃣ Enter SHORT on breakdown confirmation",
                "4️⃣ Stop above first hour high",
                "5️⃣ Target: Gap extension (2:1 R/R)",
            ])
        elif signal.signal_type == SignalType.GAP_FILL:
            message_parts.extend([
                "1️⃣ Wait for initial move to stall",
                "2️⃣ Look for reversal candle pattern",
                "3️⃣ Enter FADE trade toward previous close",
                "4️⃣ Stop above/below gap open",
                "5️⃣ Target: 50-100% gap fill",
            ])
        else:  # GAP_UP or GAP_DOWN
            message_parts.extend([
                "1️⃣ Gap detected - wait for confirmation",
                "2️⃣ Watch first 30-min price action",
                "3️⃣ Follow gap direction if momentum continues",
                "4️⃣ Fade if gap starts filling",
            ])
        
        # Add DP context if available
        if signal.nearest_dp_level:
            message_parts.extend([
                "",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                "**🏛️ INSTITUTIONAL CONTEXT:**",
                f"• Nearest DP Level: **${signal.nearest_dp_level:.2f}**",
                f"• Distance: {signal.dp_distance_pct:.2f}%",
            ])
            if abs(signal.dp_distance_pct) < 0.5:
                message_parts.append("• ⚠️ **AT DP LEVEL** - High confluence!")
            elif signal.dp_distance_pct > 0:
                message_parts.append("• Price ABOVE DP support")
            else:
                message_parts.append("• Price BELOW DP resistance")
        
        # Add reasoning
        if signal.reasoning:
            message_parts.extend([
                "",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                "**🧠 SIGNAL REASONING:**",
                signal.reasoning
            ])
        
        # Add confidence and risk warning
        message_parts.extend([
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"**💯 Confidence:** {signal.confidence:.0%}",
            "",
            "⚠️ **RISK WARNING:** Gaps can be volatile.",
            "Use proper position sizing (max 2% risk).",
            "Paper trade this setup first!",
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

