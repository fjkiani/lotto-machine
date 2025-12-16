#!/usr/bin/env python3
"""
📱 REDDIT CHECKER - Phase 5 Exploitation
=========================================

Monitors Reddit sentiment for contrarian trading opportunities.

Features:
1. HOT TICKER DISCOVERY - Find what retail is buzzing about
2. CONTRARIAN SIGNALS - Fade extreme bullish/bearish sentiment
3. PUMP WARNINGS - Detect potential pump & dump schemes
4. SENTIMENT MOMENTUM - Track sentiment shifts

Author: Alpha's AI Hedge Fund
Date: 2024-12-16
"""

import logging
from datetime import datetime
from typing import List, Optional

from .base_checker import BaseChecker, CheckerAlert

logger = logging.getLogger(__name__)


class RedditChecker(BaseChecker):
    """
    Reddit sentiment monitoring checker.
    
    Runs hourly during market hours to:
    1. Discover hot tickers on Reddit
    2. Generate contrarian signals (fade hype/fear)
    3. Alert on pump & dump warnings
    """
    
    @property
    def name(self) -> str:
        return "RedditChecker"
    
    def __init__(self, alert_manager, unified_mode: bool = False, 
                 reddit_exploiter=None, api_key: str = None):
        """
        Initialize Reddit Checker.
        
        Args:
            alert_manager: Alert manager for deduplication
            unified_mode: Whether running in unified monitor
            reddit_exploiter: Pre-initialized RedditExploiter instance
            api_key: ChartExchange API key (if exploiter not provided)
        """
        super().__init__(alert_manager, unified_mode)
        
        self.exploiter = reddit_exploiter
        self.api_key = api_key
        
        # Will lazy-init exploiter if needed
        self._exploiter_initialized = reddit_exploiter is not None
        
        # Track alerts sent today
        self.alerts_sent_today = set()
        self.last_check_date = None
        
        logger.info("📱 Reddit Checker initialized")
    
    def _ensure_exploiter(self):
        """Lazy initialize exploiter if needed"""
        if self._exploiter_initialized:
            return True
        
        if not self.api_key:
            logger.warning("⚠️ No API key for Reddit Exploiter")
            return False
        
        try:
            from live_monitoring.exploitation.reddit_exploiter import RedditExploiter
            self.exploiter = RedditExploiter(api_key=self.api_key)
            self._exploiter_initialized = True
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize Reddit Exploiter: {e}")
            return False
    
    def check(self, *args, **kwargs) -> List[CheckerAlert]:
        """
        Run Reddit sentiment check.
        
        Returns:
            List of CheckerAlert objects
        """
        alerts = []
        
        if not self._ensure_exploiter():
            return alerts
        
        try:
            now = datetime.now()
            today = now.strftime('%Y-%m-%d')
            
            # Reset daily tracking
            if self.last_check_date != today:
                self.alerts_sent_today = set()
                self.last_check_date = today
            
            logger.info("📱 Running Reddit sentiment check...")
            
            # Step 1: Discover hot tickers
            hot_tickers = self.exploiter.discover_hot_tickers(min_sentiment_extreme=0.35)
            
            if hot_tickers:
                logger.info(f"   🔥 Found {len(hot_tickers)} hot tickers")
                
                # Alert on top 3 new hot tickers
                for ticker in hot_tickers[:3]:
                    alert_key = f"reddit_hot_{ticker.symbol}_{today}"
                    
                    if alert_key in self.alerts_sent_today:
                        continue
                    
                    if self.alert_manager.is_alert_duplicate(alert_key, cooldown_minutes=60*4):
                        continue
                    
                    embed = self._create_hot_ticker_embed(ticker)
                    content = f"🔥 **REDDIT HOT** | {ticker.symbol} | {ticker.discovery_reason}"
                    
                    alerts.append(CheckerAlert(
                        embed=embed,
                        content=content,
                        alert_type="reddit_hot",
                        source="reddit_checker",
                        symbol=ticker.symbol
                    ))
                    
                    self.alerts_sent_today.add(alert_key)
                    self.alert_manager.add_alert_to_history(alert_key)
            
            # Step 2: Get contrarian signals
            signals = self.exploiter.get_contrarian_signals(min_strength=65)
            
            if signals:
                logger.info(f"   🎯 Found {len(signals)} contrarian signals")
                
                for signal in signals[:5]:  # Top 5 signals
                    alert_key = f"reddit_signal_{signal.symbol}_{signal.action}_{today}"
                    
                    if alert_key in self.alerts_sent_today:
                        continue
                    
                    if self.alert_manager.is_alert_duplicate(alert_key, cooldown_minutes=60*4):
                        continue
                    
                    embed = self._create_signal_embed(signal)
                    
                    # Determine emoji based on signal type
                    if signal.signal_type:
                        if signal.signal_type.value == "FADE_HYPE":
                            emoji = "🔻"
                        elif signal.signal_type.value == "FADE_FEAR":
                            emoji = "🔺"
                        elif signal.signal_type.value == "PUMP_WARNING":
                            emoji = "🚨"
                        else:
                            emoji = "📱"
                    else:
                        emoji = "📱"
                    
                    content = f"{emoji} **REDDIT SIGNAL** | {signal.symbol} | {signal.action} | {signal.signal_strength:.0f}%"
                    
                    alerts.append(CheckerAlert(
                        embed=embed,
                        content=content,
                        alert_type=f"reddit_{signal.action.lower()}",
                        source="reddit_checker",
                        symbol=signal.symbol
                    ))
                    
                    self.alerts_sent_today.add(alert_key)
                    self.alert_manager.add_alert_to_history(alert_key)
            
            logger.info(f"   ✅ Reddit check complete: {len(alerts)} alerts")
            
        except Exception as e:
            logger.error(f"❌ Reddit checker error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
        
        return alerts
    
    def _create_hot_ticker_embed(self, ticker) -> dict:
        """Create Discord embed for hot ticker discovery"""
        
        # Color based on sentiment
        if ticker.avg_sentiment > 0.3:
            color = 0x00ff00  # Green - bullish
        elif ticker.avg_sentiment < -0.2:
            color = 0xff0000  # Red - bearish
        else:
            color = 0xffff00  # Yellow - neutral
        
        embed = {
            "title": f"🔥 REDDIT HOT: {ticker.symbol}",
            "color": color,
            "description": f"**{ticker.discovery_reason}**",
            "fields": [
                {"name": "📊 Mentions", "value": f"{ticker.mention_count}", "inline": True},
                {"name": "📈 Sentiment", "value": f"{ticker.avg_sentiment:+.2f}", "inline": True},
                {"name": "🎰 WSB Posts", "value": f"{ticker.wsb_mentions}", "inline": True},
                {"name": "📈 Bullish %", "value": f"{ticker.bullish_pct:.0f}%", "inline": True},
                {"name": "🚀 Momentum", "value": f"{ticker.momentum_score:.0f}", "inline": True},
            ],
            "footer": {"text": "Reddit Exploiter | Phase 5"},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return embed
    
    def _create_signal_embed(self, signal) -> dict:
        """Create Discord embed for contrarian signal"""
        
        # Color based on action
        if signal.action == "SHORT":
            color = 0xff0000  # Red
            action_emoji = "🔻"
        elif signal.action == "LONG":
            color = 0x00ff00  # Green
            action_emoji = "🔺"
        elif signal.action == "AVOID":
            color = 0xff6600  # Orange
            action_emoji = "🚨"
        else:
            color = 0xffff00  # Yellow
            action_emoji = "👀"
        
        signal_name = signal.signal_type.value if signal.signal_type else "NONE"
        
        embed = {
            "title": f"{action_emoji} REDDIT SIGNAL: {signal.symbol}",
            "color": color,
            "description": f"**{signal_name}** | Strength: {signal.signal_strength:.0f}%",
            "fields": [
                {"name": "🎯 Action", "value": f"**{signal.action}**", "inline": True},
                {"name": "📈 Sentiment", "value": f"{signal.avg_sentiment:+.2f}", "inline": True},
                {"name": "📊 Mentions", "value": f"{signal.total_mentions}", "inline": True},
                {"name": "🔺 Bullish", "value": f"{signal.bullish_pct:.0f}%", "inline": True},
                {"name": "🔻 Bearish", "value": f"{signal.bearish_pct:.0f}%", "inline": True},
                {"name": "🎰 WSB %", "value": f"{signal.wsb_dominance:.0f}%", "inline": True},
            ],
            "footer": {"text": "Reddit Exploiter | Contrarian Signal"},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add reasoning
        if signal.reasoning:
            embed["fields"].append({
                "name": "💡 Reasoning",
                "value": "\n".join([f"• {r}" for r in signal.reasoning[:3]]),
                "inline": False
            })
        
        # Add warnings
        if signal.warnings:
            embed["fields"].append({
                "name": "⚠️ Warnings",
                "value": "\n".join(signal.warnings[:3]),
                "inline": False
            })
        
        # Add sample posts
        if signal.sample_posts:
            embed["fields"].append({
                "name": "💬 Sample Posts",
                "value": "\n".join(signal.sample_posts[:2]),
                "inline": False
            })
        
        return embed

