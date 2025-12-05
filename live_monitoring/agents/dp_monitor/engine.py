"""
🔒 DP Monitor Engine
====================
Main orchestrator for dark pool monitoring.
"""

import logging
from datetime import datetime
from typing import List, Dict, Optional, Callable, Any

from .models import DPAlert, AlertType, AlertPriority, TradeDirection
from .battleground import BattlegroundAnalyzer
from .alert_generator import AlertGenerator

logger = logging.getLogger(__name__)


class DPMonitorEngine:
    """
    Main engine for dark pool monitoring.
    
    Orchestrates:
    - Battleground fetching and analysis
    - Smart alert generation (with debouncing)
    - Integration with DP Learning Engine
    - Discord alert formatting
    """
    
    def __init__(
        self,
        api_key: str = None,
        dp_client: Any = None,  # Existing UltimateChartExchangeClient
        learning_engine: Any = None,  # DPLearningEngine instance
        debounce_minutes: int = 30,
    ):
        self.battleground_analyzer = BattlegroundAnalyzer(api_key=api_key, dp_client=dp_client)
        self.alert_generator = AlertGenerator(debounce_minutes)
        self.learning_engine = learning_engine
        
        logger.info("🔒 DP Monitor Engine initialized")
        logger.info(f"   Debounce: {debounce_minutes} min")
        logger.info(f"   Learning Engine: {'✅' if learning_engine else '❌'}")
        logger.info(f"   DP Client: {'✅ (reusing)' if dp_client else '🆕 (new)'}")
    
    def check_symbol(self, symbol: str) -> List[DPAlert]:
        """
        Check a single symbol for DP alerts.
        
        Args:
            symbol: Stock symbol (e.g., 'SPY')
            
        Returns:
            List of DPAlert objects
        """
        # Get nearby battlegrounds
        battlegrounds = self.battleground_analyzer.get_nearby_battlegrounds(
            symbol, max_distance_pct=0.5
        )
        
        if not battlegrounds:
            return []
        
        # Get AI predictions if learning engine available
        ai_predictions = {}
        if self.learning_engine:
            for bg in battlegrounds:
                try:
                    prediction = self.learning_engine.predict(
                        symbol=symbol,
                        level_price=bg.price,
                        level_volume=bg.volume,
                        level_type=bg.level_type.value if bg.level_type else 'SUPPORT'
                    )
                    if prediction:
                        ai_predictions[bg.price] = {
                            'probability': prediction.bounce_probability,
                            'confidence': prediction.confidence,
                            'patterns': prediction.patterns_matched,
                        }
                except Exception as e:
                    logger.debug(f"AI prediction error: {e}")
        
        # Generate alerts
        alerts = self.alert_generator.generate_alerts(battlegrounds, ai_predictions)
        
        return alerts
    
    def check_all_symbols(self, symbols: List[str]) -> List[DPAlert]:
        """
        Check multiple symbols for DP alerts.
        
        Args:
            symbols: List of stock symbols
            
        Returns:
            List of all DPAlert objects
        """
        all_alerts = []
        
        for symbol in symbols:
            try:
                alerts = self.check_symbol(symbol)
                all_alerts.extend(alerts)
            except Exception as e:
                logger.error(f"❌ Error checking {symbol}: {e}")
        
        return all_alerts
    
    def format_discord_alert(self, alert: DPAlert) -> Dict:
        """
        Format an alert for Discord.
        
        Args:
            alert: DPAlert object
            
        Returns:
            Discord embed dictionary
        """
        bg = alert.battleground
        ts = alert.trade_setup
        
        # Priority colors
        colors = {
            AlertPriority.CRITICAL: 15158332,  # Red
            AlertPriority.HIGH: 15105570,      # Orange
            AlertPriority.MEDIUM: 16776960,    # Yellow
            AlertPriority.LOW: 3447003,        # Blue
        }
        
        # Alert type emojis
        type_emojis = {
            AlertType.AT_LEVEL: "🚨",
            AlertType.APPROACHING: "⚠️",
            AlertType.NEAR: "📊",
        }
        
        # Direction emojis
        direction_emojis = {
            TradeDirection.LONG: "📈 LONG",
            TradeDirection.SHORT: "📉 SHORT",
            TradeDirection.WAIT: "⏸️ WAIT",
        }
        
        # Position indicator
        if bg.level_type:
            if bg.level_type.value == "SUPPORT":
                pos_indicator = f"📈 Price is {bg.distance_pct:.2f}% ABOVE"
            else:
                pos_indicator = f"📉 Price is {bg.distance_pct:.2f}% BELOW"
        else:
            pos_indicator = f"📊 Distance: {bg.distance_pct:.2f}%"
        
        # Build fields
        fields = [
            {"name": "💰 Current Price", "value": f"${bg.current_price:.2f}", "inline": True},
            {"name": "🎯 Battleground", "value": f"${bg.price:.2f}", "inline": True},
            {"name": "📏 Distance", "value": f"{bg.distance_pct:.2f}%", "inline": True},
            {"name": "📊 Volume", "value": f"{bg.volume:,} shares ({bg.volume_tier})", "inline": True},
            {"name": "🏷️ Type", "value": bg.level_type.value if bg.level_type else "UNKNOWN", "inline": True},
            {"name": "💪 Confidence", "value": f"{bg.confidence:.0%}", "inline": True},
        ]
        
        # Add trade setup if available
        if ts and ts.direction != TradeDirection.WAIT:
            trade_block = (
                f"```\n"
                f"Direction: {direction_emojis[ts.direction]}\n"
                f"Entry:     ${ts.entry:.2f}\n"
                f"Stop:      ${ts.stop:.2f} ({ts.risk_pct:.2f}% risk)\n"
                f"Target:    ${ts.target:.2f} ({ts.reward_pct:.2f}% reward)\n"
                f"R/R:       {ts.risk_reward}:1\n"
                f"Hold:      {ts.hold_time_min}-{ts.hold_time_max} min\n"
                f"```"
            )
            fields.append({"name": "🎯 TRADE SETUP", "value": trade_block, "inline": False})
        
        # Add AI prediction if available
        if alert.ai_prediction:
            ai_emoji = "🧠"
            ai_text = f"{alert.ai_prediction:.0%} bounce | {alert.ai_confidence or 'N/A'} confidence"
            if alert.ai_patterns:
                ai_text += f"\nPatterns: {', '.join(alert.ai_patterns[:3])}"
            fields.append({"name": f"{ai_emoji} AI Prediction", "value": ai_text, "inline": False})
        
        # Build embed
        embed = {
            "title": f"{type_emojis[alert.alert_type]} {alert.priority.value}: {alert.symbol} @ ${bg.price:.2f}",
            "description": f"🔒 **DARK POOL {alert.alert_type.value}**\n{pos_indicator}",
            "color": colors[alert.priority],
            "fields": fields,
            "footer": {"text": f"Dark Pool Intelligence | Data from {bg.date}"},
            "timestamp": alert.timestamp.isoformat(),
        }
        
        return embed
    
    def log_to_learning_engine(self, alert: DPAlert) -> Optional[int]:
        """
        Log an alert to the learning engine for outcome tracking.
        
        Args:
            alert: The DPAlert to log
            
        Returns:
            Interaction ID if logged, None otherwise
        """
        if not self.learning_engine:
            return None
        
        try:
            from live_monitoring.agents.dp_learning.models import DPInteraction
            
            bg = alert.battleground
            
            interaction = DPInteraction(
                symbol=bg.symbol,
                level_price=bg.price,
                level_volume=bg.volume,
                level_type=bg.level_type.value if bg.level_type else 'SUPPORT',
                level_date=bg.date,
                approach_price=bg.current_price or bg.price,
                approach_direction='DOWN' if bg.level_type and bg.level_type.value == 'SUPPORT' else 'UP',
                touch_count=1,
            )
            
            interaction_id = self.learning_engine.log_interaction(interaction)
            logger.debug(f"📝 Logged interaction #{interaction_id}")
            return interaction_id
            
        except Exception as e:
            logger.error(f"❌ Error logging to learning engine: {e}")
            return None
    
    def get_stats(self) -> dict:
        """Get engine statistics."""
        return {
            'alert_generator': self.alert_generator.get_stats(),
            'learning_engine_active': self.learning_engine is not None,
        }

