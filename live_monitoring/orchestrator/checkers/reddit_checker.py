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
            
            # Step 2: Discover emerging tickers (Task 5.11)
            emerging_tickers = self.exploiter.discover_emerging_tickers(min_mentions=20, max_mentions=100)
            
            if emerging_tickers:
                logger.info(f"   🌱 Found {len(emerging_tickers)} emerging tickers")
                
                # Alert on top 3 emerging tickers
                for ticker_data in emerging_tickers[:3]:
                    symbol = ticker_data['symbol']
                    alert_key = f"reddit_emerging_{symbol}_{today}"
                    
                    if alert_key in self.alerts_sent_today:
                        continue
                    
                    if self.alert_manager.is_alert_duplicate(alert_key, cooldown_minutes=60*6):
                        continue
                    
                    embed = self._create_emerging_ticker_embed(ticker_data)
                    content = f"🌱 **EMERGING TICKER** | {symbol} | {ticker_data['discovery_reason']}"
                    
                    alerts.append(CheckerAlert(
                        embed=embed,
                        content=content,
                        alert_type="reddit_emerging",
                        source="reddit_checker",
                        symbol=symbol
                    ))
                    
                    self.alerts_sent_today.add(alert_key)
                    self.alert_manager.add_alert_to_history(alert_key)
            
            # Step 3: Get contrarian signals
            signals = self.exploiter.get_contrarian_signals(min_strength=65)
            
            if signals:
                logger.info(f"   🎯 Found {len(signals)} contrarian signals")
                
                for signal in signals[:5]:  # Top 5 signals
                    alert_key = f"reddit_signal_{signal.symbol}_{signal.action}_{today}"
                    
                    if alert_key in self.alerts_sent_today:
                        continue
                    
                    if self.alert_manager.is_alert_duplicate(alert_key, cooldown_minutes=60*4):
                        continue
                    
                    # Get price correlation data (Task 5.9)
                    price_data = None
                    try:
                        price_data = self.exploiter.correlate_with_price(signal.symbol, signal)
                    except Exception as e:
                        logger.debug(f"Could not fetch price data for {signal.symbol}: {e}")
                    
                    embed = self._create_signal_embed(signal, price_data=price_data)
                    
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
    
    def _create_emerging_ticker_embed(self, ticker_data: dict) -> dict:
        """Create Discord embed for emerging ticker discovery - Task 5.11"""
        
        symbol = ticker_data['symbol']
        momentum_score = ticker_data.get('momentum_score', 0)
        
        # Color based on momentum
        if momentum_score > 70:
            color = 0x00ff00  # Green - high momentum
        elif momentum_score > 50:
            color = 0xffff00  # Yellow - medium momentum
        else:
            color = 0xff9900  # Orange - low momentum
        
        embed = {
            "title": f"🌱 EMERGING TICKER: {symbol}",
            "color": color,
            "description": f"**{ticker_data['discovery_reason']}**",
            "fields": [
                {"name": "📊 Mentions", "value": f"{ticker_data['mention_count']}", "inline": True},
                {"name": "🚀 Velocity", "value": f"{ticker_data['velocity']:.1f}x", "inline": True},
                {"name": "📈 Momentum", "value": f"{momentum_score:.0f}/100", "inline": True},
                {"name": "💭 Sentiment", "value": f"{ticker_data['sentiment']:+.2f}", "inline": True},
                {"name": "📱 Top Subreddit", "value": f"r/{ticker_data['top_subreddit']}", "inline": True},
            ],
            "footer": {"text": "Reddit Exploiter | Emerging Ticker Discovery"},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return embed
    
    def _create_signal_embed(self, signal, price_data=None) -> dict:
        """
        Create rich Discord embed for contrarian signal - Task 5.9.
        
        Enhanced with:
        - Sentiment sparkline (7-day trend)
        - Top 3 sample posts with sentiment scores
        - Price correlation if available
        - Trade setup when actionable
        """
        
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
        
        # Generate sentiment sparkline (Task 5.9)
        sparkline = self._generate_sentiment_sparkline(signal.symbol)
        
        embed = {
            "title": f"{action_emoji} REDDIT SIGNAL: {signal.symbol}",
            "color": color,
            "description": f"**{signal_name}** | Strength: {signal.signal_strength:.0f}%",
            "fields": [
                {"name": "🎯 Action", "value": f"**{signal.action}**", "inline": True},
                {"name": "📈 Sentiment", "value": f"{signal.avg_sentiment:+.2f}", "inline": True},
                {"name": "📊 Mentions", "value": f"{signal.total_mentions}", "inline": True},
            ],
            "footer": {"text": "Reddit Exploiter | Contrarian Signal"},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add sentiment trend sparkline (Task 5.9)
        if sparkline:
            embed["fields"].append({
                "name": "📈 Sentiment Trend (7d)",
                "value": f"`{sparkline}`",
                "inline": False
            })
        
        # Add price correlation if available (Task 5.9)
        if price_data and price_data.get('current_price', 0) > 0:
            price_change = price_data.get('price_change_7d', 0)
            correlation = price_data.get('confirmation', 'NEUTRAL')
            divergence = price_data.get('divergence', False)
            
            price_info = f"${price_data['current_price']:.2f} ({price_change:+.1f}% 7d)"
            
            if divergence:
                div_type = price_data.get('divergence_type', '')
                price_info += f"\n⚠️ **DIVERGENCE**: {div_type}"
            else:
                price_info += f"\n✅ Correlation: {correlation}"
            
            embed["fields"].append({
                "name": "💰 Price Action",
                "value": price_info,
                "inline": False
            })
        
        # Add WSB analysis if available
        if signal.wsb_dominance > 50:
            embed["fields"].append({
                "name": "🎰 WSB Analysis",
                "value": f"WSB: {signal.wsb_dominance:.0f}% dominance",
                "inline": True
            })
        
        # Add reasoning
        if signal.reasoning:
            reasoning_text = "\n".join([f"• {r}" for r in signal.reasoning[:5]])
            embed["fields"].append({
                "name": "💡 Reasoning",
                "value": reasoning_text[:1000],  # Discord limit
                "inline": False
            })
        
        # Add top sample posts with sentiment (Task 5.9)
        if signal.sample_posts:
            posts_text = "\n".join(signal.sample_posts[:3])
            embed["fields"].append({
                "name": "💬 Top Posts",
                "value": posts_text[:1000],  # Discord limit
                "inline": False
            })
        
        # Add trade setup if actionable (Task 5.9)
        if signal.action in ["LONG", "SHORT"] and price_data and price_data.get('current_price', 0) > 0:
            trade_setup = self._calculate_trade_setup(signal, price_data)
            if trade_setup:
                embed["fields"].append({
                    "name": "🎯 Trade Setup",
                    "value": trade_setup,
                    "inline": False
                })
        
        # Add warnings
        if signal.warnings:
            embed["fields"].append({
                "name": "⚠️ Warnings",
                "value": "\n".join(signal.warnings[:3]),
                "inline": False
            })
        
        return embed
    
    def _generate_sentiment_sparkline(self, symbol: str) -> Optional[str]:
        """
        Generate ASCII sparkline for sentiment trend - Task 5.9.
        
        Returns:
            Sparkline string like "▁▂▃▅▆▇█" or None
        """
        try:
            history = self.exploiter._get_sentiment_history(symbol)
            if not history:
                return None
            
            hist = history.get_history(days=7)
            if len(hist) < 3:
                return None
            
            # Extract sentiments and normalize to 0-7 (sparkline characters)
            sentiments = [s for _, s, _ in hist[-7:]]  # Last 7 days
            
            if not sentiments:
                return None
            
            min_sent = min(sentiments)
            max_sent = max(sentiments)
            range_sent = max_sent - min_sent if max_sent != min_sent else 1
            
            # Map to sparkline characters: ▁▂▃▄▅▆▇█
            sparkline_chars = "▁▂▃▄▅▆▇█"
            sparkline = ""
            
            for sent in sentiments:
                normalized = (sent - min_sent) / range_sent
                index = int(normalized * (len(sparkline_chars) - 1))
                sparkline += sparkline_chars[index]
            
            return sparkline
            
        except Exception as e:
            logger.debug(f"Error generating sparkline for {symbol}: {e}")
            return None
    
    def _calculate_trade_setup(self, signal, price_data: dict) -> Optional[str]:
        """
        Calculate trade setup (entry, stop, target) - Task 5.9.
        
        Args:
            signal: RedditTickerAnalysis
            price_data: Price correlation data
        
        Returns:
            Formatted trade setup string or None
        """
        try:
            current_price = price_data.get('current_price', 0)
            if current_price <= 0:
                return None
            
            entry = current_price
            
            # Calculate stop loss (2% for LONG, 2% for SHORT)
            stop_pct = 0.02
            if signal.action == "LONG":
                stop = entry * (1 - stop_pct)
                target = entry * (1 + stop_pct * 2)  # 2:1 R/R
            elif signal.action == "SHORT":
                stop = entry * (1 + stop_pct)
                target = entry * (1 - stop_pct * 2)  # 2:1 R/R
            else:
                return None
            
            risk = abs(entry - stop)
            reward = abs(target - entry)
            rr_ratio = reward / risk if risk > 0 else 0
            
            setup = (
                f"Entry: ${entry:.2f}\n"
                f"Stop: ${stop:.2f} ({stop_pct*100:.1f}% risk)\n"
                f"Target: ${target:.2f} ({stop_pct*2*100:.1f}% reward)\n"
                f"R/R: {rr_ratio:.1f}:1"
            )
            
            return setup
            
        except Exception as e:
            logger.debug(f"Error calculating trade setup: {e}")
            return None

