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
Date: 2025-12-17
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple

from .base_checker import BaseChecker, CheckerAlert

# Import config
try:
    from live_monitoring.config.reddit_config import DEFAULT_CONFIG, DP_UPGRADE_POINTS, SIGNAL_TYPE_WEIGHTS
except ImportError:
    # Fallback if config not available
    DEFAULT_CONFIG = None
    DP_UPGRADE_POINTS = None
    SIGNAL_TYPE_WEIGHTS = None

logger = logging.getLogger(__name__)


# Mega-caps get special treatment (fallback if config not loaded)
MEGA_CAPS = ['TSLA', 'NVDA', 'AAPL', 'MSFT', 'META', 'AMZN', 'GOOGL', 'GOOG', 'AMD', 'NFLX']


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
    
    def __init__(self, alert_manager, api_key: str = None, 
                 reddit_exploiter=None):
        """
        Initialize Reddit Checker.
        
        Args:
            alert_manager: Alert manager for deduplication
            api_key: ChartExchange API key (if exploiter not provided)
            reddit_exploiter: Pre-initialized RedditExploiter instance
        """
        super().__init__(alert_manager)
        
        self.exploiter = reddit_exploiter
        self.api_key = api_key
        
        # Will lazy-init exploiter if needed
        self._exploiter_initialized = reddit_exploiter is not None
        
        # DP client for enhanced synthesis
        self.dp_client = None
        self._init_dp_client()
        
        # Signal tracker for storage
        self.signal_tracker = None
        self._init_signal_tracker()
        
        # Track alerts sent today
        self.alerts_sent_today = set()
        self.last_check_date = None
        
        # Load config
        self.config = DEFAULT_CONFIG
        
        # Statistics for algorithm improvement
        self.stats = {
            'signals_generated': 0,
            'signals_upgraded': 0,
            'signals_stored': 0,
            'alerts_sent': 0
        }
        
        logger.info("📱 Reddit Checker initialized (with DP synthesis + signal tracking)")
    
    def _init_dp_client(self):
        """Initialize ChartExchange client for DP data."""
        import os
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = self.api_key or os.getenv('CHARTEXCHANGE_API_KEY') or os.getenv('CHART_EXCHANGE_API_KEY')
        if api_key:
            try:
                from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
                self.dp_client = UltimateChartExchangeClient(api_key, tier=3)
                logger.info("   ✅ DP client initialized for enhanced synthesis")
            except Exception as e:
                logger.debug(f"Could not init DP client: {e}")
    
    def _init_signal_tracker(self):
        """Initialize signal tracker for storage."""
        try:
            from backtesting.simulation.reddit_signal_tracker import RedditSignalTracker
            self.signal_tracker = RedditSignalTracker()
            logger.info("   ✅ Signal tracker initialized for storage")
        except Exception as e:
            logger.debug(f"Could not init signal tracker: {e}")
    
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
    
    def _enhance_signal_with_dp(self, signal, price_data: Dict = None) -> Tuple[str, float, List[str]]:
        """
        Enhance Reddit signal with DP synthesis.
        
        For AVOID signals (VELOCITY_SURGE), check DP data to potentially upgrade:
        - AVOID → LONG if DP support + price rallying + institutional accumulation
        - AVOID → WATCH if some confirmation but not all
        
        Returns:
            Tuple of (enhanced_action, enhanced_strength, reasons)
        """
        if not self.dp_client or not signal:
            return signal.action, signal.signal_strength, []
        
        # Only enhance AVOID signals
        if signal.action != "AVOID":
            return signal.action, signal.signal_strength, []
        
        reasons = []
        upgrade_score = 0
        
        symbol = signal.symbol
        is_mega_cap = symbol in MEGA_CAPS
        
        try:
            # Get yesterday's date for DP data (T+1)
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            # Get current price info
            current_price = 0
            price_change_5d = 0
            volume_ratio = 1.0
            
            if price_data:
                current_price = price_data.get('current_price', 0)
                price_change_5d = price_data.get('price_change_5d', 0)
                volume_ratio = price_data.get('volume_ratio', 1.0)
            elif hasattr(signal, 'price_correlation') and signal.price_correlation:
                current_price = signal.price_correlation.get('current_price', 0)
                price_change_5d = signal.price_correlation.get('price_change_5d', 0)
            
            # 1. Check price momentum
            if price_change_5d > 5:
                upgrade_score += 2
                reasons.append(f"✅ Price rallying {price_change_5d:+.1f}% (5d)")
            
            # 2. Check DP data for support
            dp_levels = self.dp_client.get_dark_pool_levels(symbol, date=yesterday)
            
            if dp_levels and current_price > 0:
                # Find support levels below current price
                support_levels = []
                for level in dp_levels[:20]:
                    if isinstance(level, dict):
                        price = float(level.get('level', level.get('price', 0)))
                        volume = int(level.get('volume', 0))
                        
                        if volume > 10000 and price < current_price:
                            distance_pct = (current_price - price) / current_price * 100
                            if distance_pct < 3:  # Within 3%
                                support_levels.append({'price': price, 'volume': volume})
                
                if support_levels:
                    strongest = max(support_levels, key=lambda x: x['volume'])
                    upgrade_score += 2
                    reasons.append(f"✅ DP support at ${strongest['price']:.2f} ({strongest['volume']:,} vol)")
            
            # 3. Check institutional flow
            dp_prints = self.dp_client.get_dark_pool_prints(symbol, date=yesterday)
            
            if dp_prints and len(dp_prints) > 10:
                # Estimate buying pressure from prints
                prices = [float(p.get('price', 0)) for p in dp_prints[:100] if p.get('price')]
                volumes = [int(p.get('volume', 0)) for p in dp_prints[:100] if p.get('volume')]
                
                if prices and sum(volumes) > 0:
                    vwap = sum(p * v for p, v in zip(prices, volumes)) / sum(volumes)
                    buy_vol = sum(v for p, v in zip(prices, volumes) if p >= vwap)
                    buying_pressure = buy_vol / sum(volumes) * 100
                    
                    if buying_pressure > 60:
                        upgrade_score += 2
                        reasons.append(f"✅ Institutional accumulation ({buying_pressure:.0f}% buy)")
            
            # 4. Mega-cap bonus
            if is_mega_cap:
                upgrade_score += 1
                reasons.append("✅ Mega-cap (more reliable momentum)")
            
            # 5. Volume confirmation
            if volume_ratio > 1.5:
                upgrade_score += 1
                reasons.append(f"✅ High volume ({volume_ratio:.1f}x avg)")
            
            # Make upgrade decision
            if upgrade_score >= 4:
                enhanced_action = "LONG"
                enhanced_strength = min(85, 50 + upgrade_score * 5)
                reasons.insert(0, f"🔄 UPGRADED: AVOID → LONG (score: {upgrade_score})")
            elif upgrade_score >= 2:
                enhanced_action = "WATCH_LONG"
                enhanced_strength = 60
                reasons.insert(0, f"👀 UPGRADED: AVOID → WATCH (score: {upgrade_score})")
            else:
                enhanced_action = "AVOID"
                enhanced_strength = signal.signal_strength
                reasons.insert(0, f"⚠️ CONFIRMED: AVOID (score: {upgrade_score} < 4)")
            
            return enhanced_action, enhanced_strength, reasons
            
        except Exception as e:
            logger.debug(f"Error in DP enhancement for {symbol}: {e}")
            return signal.action, signal.signal_strength, []
    
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
                    # Get price correlation data (Task 5.9)
                    price_data = None
                    try:
                        price_data = self.exploiter.correlate_with_price(signal.symbol, signal)
                    except Exception as e:
                        logger.debug(f"Could not fetch price data for {signal.symbol}: {e}")
                    
                    # ENHANCED: Apply DP synthesis to potentially upgrade AVOID → LONG/WATCH
                    enhanced_action, enhanced_strength, enhancement_reasons = self._enhance_signal_with_dp(
                        signal, price_data
                    )
                    
                    if enhancement_reasons:
                        logger.info(f"   🔄 {signal.symbol}: {enhancement_reasons[0]}")
                    
                    # Use enhanced action for alert key (so upgraded signals get new alerts)
                    alert_key = f"reddit_signal_{signal.symbol}_{enhanced_action}_{today}"
                    
                    if alert_key in self.alerts_sent_today:
                        continue
                    
                    if self.alert_manager.is_alert_duplicate(alert_key, cooldown_minutes=60*4):
                        continue
                    
                    # Create embed with enhanced data
                    embed = self._create_signal_embed(
                        signal, 
                        price_data=price_data,
                        enhanced_action=enhanced_action,
                        enhanced_strength=enhanced_strength,
                        enhancement_reasons=enhancement_reasons
                    )
                    
                    # Determine emoji based on ENHANCED action
                    if enhanced_action == "LONG":
                        emoji = "🚀"  # Upgraded to LONG
                    elif enhanced_action == "WATCH_LONG":
                        emoji = "👀"  # Upgraded to WATCH
                    elif enhanced_action == "SHORT":
                        emoji = "🔻"
                    elif enhanced_action == "AVOID":
                        emoji = "⚡"  # Confirmed AVOID
                    else:
                        # Fallback to signal type based emoji
                        if signal.signal_type:
                            signal_val = signal.signal_type.value if hasattr(signal.signal_type, 'value') else str(signal.signal_type)
                            if signal_val == "FADE_HYPE":
                                emoji = "🔻"
                            elif signal_val == "FADE_FEAR":
                                emoji = "🔺"
                            elif signal_val == "PUMP_WARNING":
                                emoji = "🚨"
                            elif signal_val == "CONFIRMED_MOMENTUM":
                                emoji = "🚀"
                            elif signal_val == "BULLISH_DIVERGENCE":
                                emoji = "📈"
                            elif signal_val == "BEARISH_DIVERGENCE":
                                emoji = "📉"
                            elif signal_val == "VELOCITY_SURGE":
                                emoji = "⚡"
                            elif signal_val == "WSB_YOLO_WAVE":
                                emoji = "🎰"
                            elif signal_val == "WSB_CAPITULATION":
                                emoji = "😱"
                            elif signal_val == "STEALTH_ACCUMULATION":
                                emoji = "🥷"
                            else:
                                emoji = "📱"
                        else:
                            emoji = "📱"
                    
                    # Show original → enhanced if upgraded
                    if enhanced_action != signal.action:
                        content = f"{emoji} **REDDIT ENHANCED** | {signal.symbol} | {signal.action}→{enhanced_action} | {enhanced_strength:.0f}%"
                    else:
                        content = f"{emoji} **REDDIT SIGNAL** | {signal.symbol} | {enhanced_action} | {enhanced_strength:.0f}%"
                    
                    alerts.append(CheckerAlert(
                        embed=embed,
                        content=content,
                        alert_type=f"reddit_{enhanced_action.lower()}",
                        source="reddit_checker",
                        symbol=signal.symbol
                    ))
                    
                    self.alerts_sent_today.add(alert_key)
                    self.alert_manager.add_alert_to_history(alert_key)
                    self.stats['alerts_sent'] += 1
                    
                    # Store signal for tracking and algorithm improvement
                    self._store_signal(signal, enhanced_action, enhanced_strength, 
                                      enhancement_reasons, price_data)
            
            # Log stats
            logger.info(f"   ✅ Reddit check complete: {len(alerts)} alerts")
            logger.info(f"      Stats: {self.stats['signals_generated']} generated, "
                       f"{self.stats['signals_upgraded']} upgraded, {self.stats['signals_stored']} stored")
            
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
    
    def _create_signal_embed(self, signal, price_data=None, 
                              enhanced_action=None, enhanced_strength=None,
                              enhancement_reasons=None) -> dict:
        """
        Create rich Discord embed for contrarian signal - Task 5.9.
        
        Enhanced with:
        - Sentiment sparkline (7-day trend)
        - Top 3 sample posts with sentiment scores
        - Price correlation if available
        - Trade setup when actionable
        - DP synthesis enhancement reasons (NEW)
        """
        
        # Use enhanced action if provided
        action = enhanced_action or signal.action
        strength = enhanced_strength or signal.signal_strength
        
        # Color based on ENHANCED action
        if action == "SHORT":
            color = 0xff0000  # Red
            action_emoji = "🔻"
        elif action == "LONG":
            color = 0x00ff00  # Green
            action_emoji = "🚀"  # Rocket for LONG
        elif action == "WATCH_LONG":
            color = 0x00aaff  # Blue
            action_emoji = "👀"
        elif action == "AVOID":
            color = 0xff6600  # Orange
            action_emoji = "🚨"
        else:
            color = 0xffff00  # Yellow
            action_emoji = "👀"
        
        signal_name = signal.signal_type.value if signal.signal_type else "NONE"
        
        # Generate sentiment sparkline (Task 5.9)
        sparkline = self._generate_sentiment_sparkline(signal.symbol)
        
        # Check if this is an enhanced/upgraded signal
        is_upgraded = enhanced_action and enhanced_action != signal.action
        
        # Special handling for high-conviction signals
        if is_upgraded:
            title = f"🔄 ENHANCED SIGNAL: {signal.symbol}"
            description = f"**{signal.action} → {action}** | DP-Confirmed!\nStrength: {strength:.0f}%"
        elif signal_name == "CONFIRMED_MOMENTUM":
            title = f"🚀 CONFIRMED MOMENTUM: {signal.symbol}"
            description = f"**RIDE THE RALLY** | Mega-cap with confirmed price action!\nStrength: {strength:.0f}%"
        elif signal_name == "BULLISH_DIVERGENCE":
            title = f"📈 BULLISH DIVERGENCE: {signal.symbol}"
            description = f"**ACCUMULATION DETECTED** | Price down, sentiment up!\nStrength: {strength:.0f}%"
        elif signal_name == "BEARISH_DIVERGENCE":
            title = f"📉 BEARISH DIVERGENCE: {signal.symbol}"
            description = f"**DISTRIBUTION WARNING** | Price up, sentiment down!\nStrength: {strength:.0f}%"
        else:
            title = f"{action_emoji} REDDIT SIGNAL: {signal.symbol}"
            description = f"**{signal_name}** | Strength: {strength:.0f}%"
        
        embed = {
            "title": title,
            "color": color,
            "description": description,
            "fields": [
                {"name": "🎯 Action", "value": f"**{action}**", "inline": True},
                {"name": "📈 Sentiment", "value": f"{signal.avg_sentiment:+.2f}", "inline": True},
                {"name": "📊 Mentions", "value": f"{signal.total_mentions}", "inline": True},
            ],
            "footer": {"text": "Reddit Exploiter | DP-Enhanced Signal" if is_upgraded else "Reddit Exploiter | Contrarian Signal"},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add DP enhancement reasons if upgraded
        if enhancement_reasons:
            reasons_text = "\n".join([f"• {r}" for r in enhancement_reasons[:5]])
            embed["fields"].append({
                "name": "🏛️ DP Synthesis",
                "value": reasons_text[:1000],
                "inline": False
            })
        
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
        # Use enhanced action for trade setup decision
        if action in ["LONG", "SHORT"] and price_data and price_data.get('current_price', 0) > 0:
            trade_setup = self._calculate_trade_setup(signal, price_data, enhanced_action=action)
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
    
    def _calculate_trade_setup(self, signal, price_data: dict, enhanced_action: str = None) -> Optional[str]:
        """
        Calculate trade setup (entry, stop, target) - Task 5.9.
        
        Args:
            signal: RedditTickerAnalysis
            price_data: Price correlation data
            enhanced_action: Override action if DP-enhanced
        
        Returns:
            Formatted trade setup string or None
        """
        try:
            current_price = price_data.get('current_price', 0)
            if current_price <= 0:
                return None
            
            entry = current_price
            
            # Use enhanced action if provided
            action = enhanced_action or signal.action
            
            # Calculate stop loss (2% for LONG, 2% for SHORT)
            stop_pct = 0.02
            if action == "LONG":
                stop = entry * (1 - stop_pct)
                target = entry * (1 + stop_pct * 2)  # 2:1 R/R
            elif action == "SHORT":
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
    
    def _store_signal(self, signal, enhanced_action: str, enhanced_strength: float,
                      enhancement_reasons: List[str], price_data: Dict = None):
        """
        Store signal for tracking and algorithm improvement.
        
        All signals are stored to:
        1. Track win rates by signal type
        2. Validate DP enhancement effectiveness
        3. Improve algorithm over time
        """
        if not self.signal_tracker:
            return
        
        try:
            # Get current price
            current_price = 0
            if price_data:
                current_price = price_data.get('current_price', 0)
            elif hasattr(signal, 'price_correlation') and signal.price_correlation:
                current_price = signal.price_correlation.get('current_price', 0)
            
            # Build reasoning string
            reasoning = []
            if signal.reasoning:
                reasoning.extend(signal.reasoning[:3])
            if enhancement_reasons:
                reasoning.extend(enhancement_reasons[:3])
            reasoning_str = " | ".join(reasoning)
            
            # Record the signal
            self.signal_tracker.record_signal(
                symbol=signal.symbol,
                signal_type=signal.signal_type.value if signal.signal_type else "UNKNOWN",
                action=enhanced_action,
                entry_price=current_price,
                signal_strength=enhanced_strength,
                sentiment=signal.avg_sentiment,
                reasoning=reasoning_str
            )
            
            self.stats['signals_stored'] += 1
            self.stats['signals_generated'] += 1
            
            if enhanced_action != signal.action:
                self.stats['signals_upgraded'] += 1
            
            logger.debug(f"   📝 Stored signal: {signal.symbol} {enhanced_action} @ ${current_price:.2f}")
            
        except Exception as e:
            logger.debug(f"Error storing signal: {e}")
    
    def get_performance_report(self) -> Dict[str, Any]:
        """
        Get performance report for algorithm improvement.
        
        Returns win rates by signal type, DP enhancement effectiveness, etc.
        """
        if not self.signal_tracker:
            return {"error": "Signal tracker not initialized"}
        
        try:
            # Get win rates by signal type
            report = self.signal_tracker.get_performance_by_signal_type()
            
            # Add session stats
            report['session_stats'] = self.stats.copy()
            
            return report
            
        except Exception as e:
            logger.error(f"Error getting performance report: {e}")
            return {"error": str(e)}

