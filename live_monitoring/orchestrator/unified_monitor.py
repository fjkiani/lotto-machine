"""
🎯 UNIFIED ALPHA MONITOR (MODULAR VERSION)

Main orchestrator that uses modular components:
- AlertManager: Alert sending/deduplication
- RegimeDetector: Market regime detection
- MomentumDetector: Selloff/rally detection
- MonitorInitializer: Component initialization
"""

import os
import sys
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Callable

# Add paths
base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, base_path)

from .alert_manager import AlertManager
from .regime_detector import RegimeDetector
from .momentum_detector import MomentumDetector
from .monitor_initializer import MonitorInitializer

logger = logging.getLogger(__name__)


class UnifiedAlphaMonitor:
    """
    Master orchestrator for all monitoring systems (MODULAR VERSION).
    
    Uses modular components:
    - AlertManager for all alerting
    - RegimeDetector for market regime
    - MomentumDetector for selloff/rally
    - MonitorInitializer for setup
    """
    
    def __init__(self):
        self.running = True
        self.symbols = ['SPY', 'QQQ']
        
        # Intervals (in seconds)
        self.fed_interval = 300      # 5 minutes
        self.trump_interval = 180    # 3 minutes
        self.econ_interval = 3600    # 1 hour
        self.dp_interval = 60        # 1 minute
        self.synthesis_interval = 60  # 1 minute
        self.squeeze_interval = 3600  # 1 hour - squeeze detection
        
        # Track last run times
        self.last_fed_check = None
        self.last_trump_check = None
        self.last_econ_check = None
        self.last_dp_check = None
        self.last_synthesis_check = None
        self.last_tradytics_analysis = None
        self.last_squeeze_check = None
        
        # Initialize modular components
        self.alert_manager = AlertManager()
        self.regime_detector = RegimeDetector()
        
        # Initialize monitors (this will set up all components)
        self._init_monitors()
        
        # Initialize exploitation modules
        self._init_exploitation_modules()
        
        # Initialize momentum detector (needs signal_generator)
        self.momentum_detector = MomentumDetector(
            signal_generator=getattr(self, 'signal_generator', None),
            institutional_engine=getattr(self, 'institutional_engine', None)
        )
        
        # State tracking
        self.prev_fed_status = None
        self.prev_trump_sentiment = None
        self.seen_fed_comments = set()
        self.seen_trump_news = set()
        self.alerted_events = set()
        self.recent_dp_alerts = []
        self.startup_alert_sent = False
        self.last_synthesis_sent = None
        self.last_narrative_sent = None
        self._last_level_directions = {}
        self._last_regime_details = {}
        
        logger.info("=" * 70)
        logger.info("🎯 ALPHA INTELLIGENCE - UNIFIED MONITOR STARTED (MODULAR)")
        logger.info("=" * 70)
    
    def _init_monitors(self):
        """Initialize all monitor components using MonitorInitializer."""
        initializer = MonitorInitializer(on_dp_outcome=self._on_dp_outcome)
        status = initializer.initialize_all()
        
        # Extract components from status
        fed_status = status.get('fed', {})
        self.fed_enabled = fed_status.get('enabled', False)
        self.fed_watch = fed_status.get('fed_watch')
        self.fed_officials = fed_status.get('fed_officials')
        
        trump_status = status.get('trump', {})
        self.trump_enabled = trump_status.get('enabled', False)
        self.trump_pulse = trump_status.get('trump_pulse')
        self.trump_news = trump_status.get('trump_news')
        
        dp_status = status.get('dark_pool', {})
        self.dp_enabled = dp_status.get('enabled', False)
        self.dp_client = dp_status.get('dp_client')
        self.dp_engine = dp_status.get('dp_engine')
        
        learning_status = status.get('dp_learning', {})
        self.dp_learning_enabled = learning_status.get('enabled', False)
        self.dp_learning = learning_status.get('dp_learning')
        
        monitor_status = status.get('dp_monitor_engine', {})
        self.dp_monitor_engine = monitor_status.get('dp_monitor_engine')
        
        brain_status = status.get('signal_brain', {})
        self.brain_enabled = brain_status.get('enabled', False)
        self.signal_brain = brain_status.get('signal_brain')
        self.macro_provider = brain_status.get('macro_provider')
        self.unified_mode = brain_status.get('enabled', False)  # Enable if brain works
        
        narrative_status = status.get('narrative_brain', {})
        self.narrative_enabled = narrative_status.get('enabled', False)
        self.narrative_brain = narrative_status.get('narrative_brain')
        self.narrative_scheduler = narrative_status.get('narrative_scheduler')
        
        econ_status = status.get('economic', {})
        self.econ_enabled = econ_status.get('enabled', False)
        self.econ_engine = econ_status.get('econ_engine')
        self.econ_calendar = econ_status.get('econ_calendar')
        self.econ_calendar_type = econ_status.get('econ_calendar_type')
        
        tradytics_status = status.get('tradytics', {})
        self.tradytics_llm_available = tradytics_status.get('llm_available', False)
        self.tradytics_analysis_interval = 300
        self.tradytics_alerts_processed = 0
        self.seen_tradytics_alerts = set()
        
        # Initialize signal generator for momentum detection
        try:
            from live_monitoring.core.signal_generator import SignalGenerator
            api_key = os.getenv('CHARTEXCHANGE_API_KEY')
            self.signal_generator = SignalGenerator(api_key=api_key)
            # Update momentum detector
            self.momentum_detector = MomentumDetector(
                signal_generator=self.signal_generator,
                institutional_engine=self.dp_engine
            )
        except Exception as e:
            logger.warning(f"   ⚠️ SignalGenerator not available: {e}")
            self.signal_generator = None
        
        # Set institutional_engine for momentum detector
        self.institutional_engine = self.dp_engine
        
        logger.info(f"   Fed: {'✅' if self.fed_enabled else '❌'}")
        logger.info(f"   Trump: {'✅' if self.trump_enabled else '❌'}")
        logger.info(f"   Economic: {'✅' if self.econ_enabled else '❌'}")
        logger.info(f"   Dark Pool: {'✅' if self.dp_enabled else '❌'}")
        logger.info(f"   Signal Brain: {'✅' if self.brain_enabled else '❌'}")
        logger.info(f"   Narrative Brain: {'✅' if self.narrative_enabled else '❌'}")
    
    def _init_exploitation_modules(self):
        """
        Initialize exploitation modules (Phase 1+).
        🔥 These modules exploit unused ChartExchange data for edge.
        """
        logger.info("🔥 Initializing exploitation modules...")
        
        # Squeeze Detector (Phase 1)
        self.squeeze_enabled = False
        self.squeeze_detector = None
        
        try:
            from live_monitoring.exploitation.squeeze_detector import SqueezeDetector
            from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
            
            api_key = os.getenv('CHARTEXCHANGE_API_KEY') or os.getenv('CHART_EXCHANGE_API_KEY')
            if api_key:
                # Use existing dp_client if available, else create new
                if hasattr(self, 'dp_client') and self.dp_client:
                    self.squeeze_detector = SqueezeDetector(self.dp_client)
                else:
                    client = UltimateChartExchangeClient(api_key, tier=3)
                    self.squeeze_detector = SqueezeDetector(client)
                
                self.squeeze_enabled = True
                logger.info("   ✅ Squeeze Detector initialized")
            else:
                logger.warning("   ⚠️ Squeeze Detector: No API key found")
        except Exception as e:
            logger.warning(f"   ⚠️ Squeeze Detector failed: {e}")
        
        # Gamma Tracker (Phase 2) - Uses yfinance options data
        self.gamma_enabled = False
        self.gamma_tracker = None
        
        try:
            from live_monitoring.exploitation.gamma_tracker import GammaTracker
            self.gamma_tracker = GammaTracker()
            self.gamma_enabled = True
            logger.info("   ✅ Gamma Tracker initialized")
        except Exception as e:
            logger.warning(f"   ⚠️ Gamma Tracker failed: {e}")
        
        # Opportunity Scanner (Phase 3)
        self.scanner_enabled = False
        self.opportunity_scanner = None
        
        try:
            from live_monitoring.exploitation.opportunity_scanner import OpportunityScanner
            from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
            
            api_key = os.getenv('CHARTEXCHANGE_API_KEY') or os.getenv('CHART_EXCHANGE_API_KEY')
            if api_key:
                # Use existing dp_client if available, else create new
                if hasattr(self, 'dp_client') and self.dp_client:
                    self.opportunity_scanner = OpportunityScanner(self.dp_client)
                else:
                    client = UltimateChartExchangeClient(api_key, tier=3)
                    self.opportunity_scanner = OpportunityScanner(client)
                
                self.scanner_enabled = True
                logger.info("   ✅ Opportunity Scanner initialized")
            else:
                logger.warning("   ⚠️ Opportunity Scanner: No API key found")
        except Exception as e:
            logger.warning(f"   ⚠️ Opportunity Scanner failed: {e}")
        
        # Scanner state tracking
        self.scanned_today = set()  # Track which dates we've scanned
        self.scanner_interval = 3600  # Scan every hour during RTH
        self.last_scanner_check = None
        
        # FTD Analyzer (Phase 4)
        self.ftd_enabled = False
        self.ftd_analyzer = None
        
        try:
            from live_monitoring.exploitation.ftd_analyzer import FTDAnalyzer
            from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
            
            api_key = os.getenv('CHARTEXCHANGE_API_KEY') or os.getenv('CHART_EXCHANGE_API_KEY')
            if api_key:
                # Use existing dp_client if available, else create new
                if hasattr(self, 'dp_client') and self.dp_client:
                    self.ftd_analyzer = FTDAnalyzer(self.dp_client)
                else:
                    client = UltimateChartExchangeClient(api_key, tier=3)
                    self.ftd_analyzer = FTDAnalyzer(client)
                
                self.ftd_enabled = True
                logger.info("   ✅ FTD Analyzer initialized")
            else:
                logger.warning("   ⚠️ FTD Analyzer: No API key found")
        except Exception as e:
            logger.warning(f"   ⚠️ FTD Analyzer failed: {e}")
        
        # FTD state tracking
        self.ftd_interval = 3600  # Check hourly (FTD data updates daily)
        self.last_ftd_check = None
        self.ftd_candidates = ['GME', 'AMC', 'LCID', 'RIVN', 'MARA', 'RIOT', 'SOFI', 'PLTR', 'NIO', 'BBBY']
        
        # Future: Reddit Contrarian (Phase 5)
        
        logger.info(f"   Squeeze Detector: {'✅' if self.squeeze_enabled else '❌'}")
        logger.info(f"   Gamma Tracker: {'✅' if self.gamma_enabled else '❌'}")
        logger.info(f"   Opportunity Scanner: {'✅' if self.scanner_enabled else '❌'}")
        logger.info(f"   FTD Analyzer: {'✅' if self.ftd_enabled else '❌'}")
    
    # ═══════════════════════════════════════════════════════════════
    # ALERT METHODS (delegate to AlertManager)
    # ═══════════════════════════════════════════════════════════════
    
    def send_discord(self, embed: dict, content: str = None, alert_type: str = "general", source: str = "monitor", symbol: str = None) -> bool:
        """Send Discord notification (delegates to AlertManager)."""
        return self.alert_manager.send_discord(embed, content, alert_type, source, symbol)
    
    def _log_alert_to_database(self, alert_type: str, embed: dict, content: str = None, source: str = "monitor", symbol: str = None):
        """Log alert to database (delegates to AlertManager)."""
        # AlertManager handles this internally, but we expose for compatibility
        pass
    
    # ═══════════════════════════════════════════════════════════════
    # REGIME DETECTION (delegate to RegimeDetector)
    # ═══════════════════════════════════════════════════════════════
    
    def _detect_market_regime(self, current_price: float) -> str:
        """Detect market regime (delegates to RegimeDetector)."""
        regime = self.regime_detector.detect(current_price)
        details = self.regime_detector.get_regime_details(current_price)
        self._last_regime_details = details
        return regime
    
    # ═══════════════════════════════════════════════════════════════
    # MOMENTUM DETECTION (delegate to MomentumDetector)
    # ═══════════════════════════════════════════════════════════════
    
    def _check_selloffs(self):
        """Check for selloffs (delegates to MomentumDetector)."""
        selloff_signals = self.momentum_detector.check_selloffs(self.symbols)
        
        for item in selloff_signals:
            symbol = item['symbol']
            signal = item['signal']
            current_price = item['current_price']
            
            embed = {
                "title": f"🚨 **REAL-TIME SELLOFF** - {symbol}",
                "description": signal.rationale or "Rapid price drop with volume spike detected",
                "color": 0xff0000,
                "fields": [{
                    "name": "🎯 Trade Setup",
                    "value": f"**Action:** {signal.action.value}\n"
                            f"**Entry:** ${signal.entry_price:.2f}\n"
                            f"**Stop:** ${signal.stop_price:.2f}\n"
                            f"**Target:** ${signal.target_price:.2f}\n"
                            f"**Confidence:** {signal.confidence:.0%}",
                    "inline": False
                }],
                "footer": {"text": "Real-time momentum detection"},
                "timestamp": datetime.now().isoformat()
            }
            
            content = f"🚨 **REAL-TIME SELLOFF** | {symbol} | {signal.action.value} @ ${current_price:.2f}"
            
            # Check regime before sending
            market_regime = self._detect_market_regime(current_price)
            signal_direction = signal.action.value
            
            if market_regime in ["DOWNTREND", "STRONG_DOWNTREND"] and signal_direction == "LONG":
                logger.warning(f"   ⛔ REGIME FILTER: Blocking LONG selloff signal in {market_regime}")
                continue
            
            self.send_discord(embed, content=content, alert_type="selloff", source="selloff_detector", symbol=symbol)
    
    def _check_rallies(self):
        """Check for rallies (delegates to MomentumDetector)."""
        rally_signals = self.momentum_detector.check_rallies(self.symbols)
        
        for item in rally_signals:
            symbol = item['symbol']
            signal = item['signal']
            current_price = item['current_price']
            
            embed = {
                "title": f"🚀 **REAL-TIME RALLY** - {symbol}",
                "description": signal.rationale or "Rapid price rise with volume spike detected",
                "color": 0x00ff00,
                "fields": [{
                    "name": "🎯 Trade Setup",
                    "value": f"**Action:** {signal.action.value}\n"
                            f"**Entry:** ${signal.entry_price:.2f}\n"
                            f"**Stop:** ${signal.stop_price:.2f}\n"
                            f"**Target:** ${signal.target_price:.2f}\n"
                            f"**Confidence:** {signal.confidence:.0%}",
                    "inline": False
                }],
                "footer": {"text": "Real-time momentum detection"},
                "timestamp": datetime.now().isoformat()
            }
            
            content = f"🚀 **REAL-TIME RALLY** | {symbol} | {signal.action.value} @ ${current_price:.2f}"
            
            # Check regime before sending
            market_regime = self._detect_market_regime(current_price)
            signal_direction = signal.action.value
            
            if market_regime in ["UPTREND", "STRONG_UPTREND"] and signal_direction == "SELL":
                logger.warning(f"   ⛔ REGIME FILTER: Blocking SHORT rally signal in {market_regime}")
                continue
            
            if market_regime == "STRONG_DOWNTREND" and signal_direction == "BUY":
                logger.warning(f"   ⛔ REGIME FILTER: Blocking BUY rally signal in {market_regime} (don't chase)")
                continue
            
            self.send_discord(embed, content=content, alert_type="rally", source="rally_detector", symbol=symbol)
    
    # ═══════════════════════════════════════════════════════════════
    # MONITORING METHODS (preserve original logic)
    # ═══════════════════════════════════════════════════════════════
    
    def check_fed(self):
        """Check Fed Watch and officials."""
        if not self.fed_enabled:
            return
        
        logger.info("🏦 Checking Fed Watch...")
        
        try:
            status = self.fed_watch.get_current_status(force_refresh=True)
            
            if self.prev_fed_status:
                cut_change = abs(status.prob_cut - self.prev_fed_status.prob_cut)
                hold_change = abs(status.prob_hold - self.prev_fed_status.prob_hold)
                
                threshold = 15.0 if self.unified_mode else 10.0
                
                if cut_change >= threshold or hold_change >= threshold:
                    logger.info(f"   🚨 MAJOR CHANGE! Cut: {status.prob_cut:.1f}% ({cut_change:+.1f}%)")
                    
                    embed = {
                        "title": "🏦 FED WATCH ALERT - Major Probability Change!",
                        "color": 15548997,
                        "fields": [
                            {"name": "📉 Cut Probability", "value": f"{status.prob_cut:.1f}%", "inline": True},
                            {"name": "➡️ Hold Probability", "value": f"{status.prob_hold:.1f}%", "inline": True},
                            {"name": "🎯 Most Likely", "value": status.most_likely_outcome, "inline": True},
                        ],
                        "footer": {"text": "CME FedWatch | Rate expectations move markets!"},
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    self.send_discord(embed, content="@everyone 🏦 Fed rate probability change!", alert_type="fed_watch", source="fed_monitor")
            
            self.prev_fed_status = status
            logger.info(f"   Cut: {status.prob_cut:.1f}% | Hold: {status.prob_hold:.1f}% | Most Likely: {status.most_likely_outcome}")
            
            # Check Fed officials
            if self.fed_officials:
                logger.info("   🎤 Checking Fed officials...")
                report = self.fed_officials.get_report()
                
                if report.comments:
                    import hashlib
                    for comment in report.comments[:3]:
                        content_hash = hashlib.md5(
                            f"{comment.official.name}:{comment.content}".encode()
                        ).hexdigest()[:12]
                        comment_id = f"{comment.official.name}:{content_hash}"
                        
                        if comment_id not in self.seen_fed_comments:
                            self.seen_fed_comments.add(comment_id)
                            
                            if len(self.seen_fed_comments) > 100:
                                self.seen_fed_comments = set(list(self.seen_fed_comments)[-100:])
                            
                            is_critical = comment.official.name == "Jerome Powell" and comment.confidence >= 0.8
                            should_alert = comment.official.name == "Jerome Powell" or comment.confidence >= 0.5
                            
                            if should_alert and (not self.unified_mode or is_critical):
                                sent_emoji = {"HAWKISH": "🦅", "DOVISH": "🕊️", "NEUTRAL": "➡️"}.get(comment.sentiment, "❓")
                                embed = {
                                    "title": f"🎤 {comment.official.name} - {comment.sentiment}",
                                    "color": 3066993 if comment.sentiment == "DOVISH" else 15548997 if comment.sentiment == "HAWKISH" else 3447003,
                                    "description": f'"{comment.content[:200]}..."',
                                    "fields": [
                                        {"name": f"{sent_emoji} Sentiment", "value": comment.sentiment, "inline": True},
                                        {"name": "📊 Impact", "value": comment.market_impact, "inline": True},
                                    ],
                                    "footer": {"text": "Fed Officials Monitor"},
                                    "timestamp": datetime.utcnow().isoformat()
                                }
                                self.send_discord(embed, alert_type="fed_official", source="fed_monitor", symbol="SPY")
            
        except Exception as e:
            logger.error(f"   ❌ Fed check error: {e}")
    
    def check_trump(self):
        """Check Trump intelligence."""
        if not self.trump_enabled:
            return
        
        logger.info("🎯 Checking Trump Intelligence...")
        
        try:
            situation = self.trump_pulse.get_current_situation()
            exploitable = self.trump_news.get_exploitable_news()
            
            if not hasattr(self, 'trump_topic_tracker'):
                self.trump_topic_tracker = {}
                self.trump_cooldown_minutes = 60
            
            for exp in exploitable[:3]:
                headline_lower = exp.news.headline.lower()
                
                topics = []
                if 'farm' in headline_lower or 'farmer' in headline_lower:
                    topics.append('farm_aid')
                if 'tariff' in headline_lower or 'trade war' in headline_lower:
                    topics.append('trade_war')
                
                if not topics:
                    import re
                    words = re.findall(r'\b[a-z]{4,}\b', headline_lower)
                    topics = ['_'.join(words[:3])] if words else ['unknown']
                
                now = datetime.now()
                topic_key = topics[0] if topics else 'unknown'
                
                last_alert_time = self.trump_topic_tracker.get(topic_key)
                if last_alert_time:
                    minutes_since = (now - last_alert_time).total_seconds() / 60
                    if minutes_since < self.trump_cooldown_minutes:
                        continue
                
                self.trump_topic_tracker[topic_key] = now
                
                if exp.exploit_score < 60:
                    continue
                
                is_critical = exp.exploit_score >= 90
                
                if not self.unified_mode or is_critical:
                    embed = {
                        "title": f"🎯 TRUMP EXPLOIT: {exp.suggested_action} (Score: {exp.exploit_score:.0f})",
                        "color": 16776960,
                        "description": exp.news.headline[:200],
                        "fields": [
                            {"name": "📊 Action", "value": exp.suggested_action, "inline": True},
                            {"name": "📈 Symbols", "value": ", ".join(exp.suggested_symbols[:3]), "inline": True},
                            {"name": "💯 Confidence", "value": f"{exp.confidence:.0f}%", "inline": True},
                        ],
                        "footer": {"text": f"Trump Intelligence | Topic: {topic_key}"},
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    self.send_discord(embed, alert_type="trump_exploit", source="trump_monitor", symbol=",".join(exp.suggested_symbols[:3]) if exp.suggested_symbols else None)
            
        except Exception as e:
            logger.error(f"   ❌ Trump check error: {e}")
    
    def check_economics(self):
        """Check for upcoming economic events."""
        if not self.econ_enabled or not self.econ_calendar:
            return
        
        logger.info("📊 Checking Economic Calendar...")
        
        try:
            from live_monitoring.agents.economic.calendar import Importance
            
            current_cut_prob = 89.0
            if self.prev_fed_status:
                current_cut_prob = self.prev_fed_status.prob_cut
            
            if self.econ_calendar_type == "api":
                today = datetime.now().strftime('%Y-%m-%d')
                tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
                
                today_data = self.econ_calendar.load_events(date=today, min_impact="medium")
                tomorrow_data = self.econ_calendar.load_events(date=tomorrow, min_impact="medium")
                
                today_events = today_data.get('macro_events', [])
                tomorrow_events = tomorrow_data.get('macro_events', [])
                all_events = today_events + tomorrow_events
                
                # Convert to EventWrapper format (simplified)
                upcoming = []
                for event_dict in all_events:
                    class EventWrapper:
                        def __init__(self, data):
                            self.name = data.get('name', 'Unknown')
                            self.date = data.get('date', today)
                            self.time = data.get('time', '08:30')
                            self.importance = Importance.HIGH if data.get('impact', '').lower() == 'high' else Importance.MEDIUM
                            self.category = None  # Simplified
                            self.typical_surprise_impact = 3.0
                            self.release_frequency = "monthly"
                        
                        def hours_until(self):
                            try:
                                event_dt = datetime.strptime(f"{self.date} {self.time}", "%Y-%m-%d %H:%M")
                                return (event_dt - datetime.now()).total_seconds() / 3600
                            except:
                                return -1
                    
                    upcoming.append(EventWrapper(event_dict))
            else:
                upcoming = self.econ_calendar.get_upcoming_events(days=2, min_importance=Importance.HIGH)
            
            for event in upcoming:
                event_id = f"{event.date}:{event.name}"
                hours = event.hours_until()
                
                if event_id in self.alerted_events or hours < 0:
                    continue
                
                should_alert = (hours < 24 and event.importance == Importance.HIGH) or hours < 4
                
                if not should_alert:
                    continue
                
                self.alerted_events.add(event_id)
                
                try:
                    alert = self.econ_engine.get_pre_event_alert(
                        event_type=event.name.lower().replace(' ', '_'),
                        event_date=event.date,
                        event_time=event.time,
                        current_fed_watch=current_cut_prob
                    )
                    weak_shift = alert.weak_scenario.predicted_fed_watch_shift
                    strong_shift = alert.strong_scenario.predicted_fed_watch_shift
                    weak_fw = alert.weak_scenario.predicted_fed_watch
                    strong_fw = alert.strong_scenario.predicted_fed_watch
                    swing = abs(weak_shift - strong_shift)
                except Exception as e:
                    swing = event.typical_surprise_impact * 2
                    weak_shift = event.typical_surprise_impact
                    strong_shift = -event.typical_surprise_impact
                    weak_fw = current_cut_prob + weak_shift
                    strong_fw = current_cut_prob + strong_shift
                
                imp_emoji = "🔴" if event.importance == Importance.HIGH else "🟡"
                
                embed = {
                    "title": f"{imp_emoji} ECONOMIC ALERT: {event.name}",
                    "color": 15548997 if event.importance == Importance.HIGH else 16776960,
                    "description": f"⏰ In **{hours:.0f} hours** | Potential **±{swing:.1f}%** Fed Watch swing!",
                    "fields": [
                        {"name": "📅 When", "value": f"{event.date} {event.time} ET", "inline": True},
                        {"name": "📊 Current Cut %", "value": f"{current_cut_prob:.1f}%", "inline": True},
                        {"name": "📉 If WEAK Data", "value": f"Fed Watch → **{weak_fw:.0f}%** ({weak_shift:+.1f}%)\n→ BUY SPY, TLT", "inline": True},
                        {"name": "📈 If STRONG Data", "value": f"Fed Watch → **{strong_fw:.0f}%** ({strong_shift:+.1f}%)\n→ Reduce exposure", "inline": True},
                    ],
                    "footer": {"text": f"Economic Intelligence Engine | {event.release_frequency.upper()} release"},
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                content = f"⚠️ **{event.name}** in {hours:.0f}h! Potential {swing:.1f}% Fed Watch swing!"
                self.send_discord(embed, content=content, alert_type="economic_event", source="economic_monitor")
            
        except Exception as e:
            logger.error(f"   ❌ Economic check error: {e}")
    
    def check_dark_pools(self):
        """Check Dark Pool levels (modular version)."""
        if not self.dp_enabled:
            return
        
        if self.dp_monitor_engine:
            self._check_dark_pools_modular()
        else:
            self._check_dark_pools_legacy()
    
    def _check_dark_pools_modular(self):
        """Use modular DP Monitor Engine + Momentum Detection."""
        logger.info("🔒 Checking Dark Pool levels (modular)...")
        
        try:
            # Check momentum first
            self._check_selloffs()
            self._check_rallies()
            
            # Check DP levels
            alerts = self.dp_monitor_engine.check_all_symbols(self.symbols)
            
            if not alerts:
                logger.info("   📊 No DP alerts triggered")
                return
            
            for alert in alerts:
                embed = self.dp_monitor_engine.format_discord_alert(alert)
                bg = alert.battleground
                ts = alert.trade_setup
                
                if ts:
                    content = f"🚨 **{alert.symbol} AT {bg.level_type.value} ${bg.price:.2f}** | {ts.direction.value} opportunity | {bg.volume:,} shares"
                else:
                    content = f"🚨 **{alert.symbol} AT BATTLEGROUND ${bg.price:.2f}** - {bg.volume:,} shares!"
                
                self.recent_dp_alerts.append(alert)
                if len(self.recent_dp_alerts) > 20:
                    self.recent_dp_alerts = self.recent_dp_alerts[-20:]
                
                if not self.unified_mode:
                    self.send_discord(embed, content=content, alert_type="dp_alert", source="dp_monitor", symbol=alert.symbol)
                else:
                    logger.debug(f"   🔇 DP alert buffered (unified mode): {alert.symbol} @ ${bg.price:.2f}")
                
                if len(self.recent_dp_alerts) >= 2 and self.brain_enabled:
                    self.check_synthesis()
                    
        except Exception as e:
            logger.error(f"   ❌ Modular DP check error: {e}")
    
    def _check_dark_pools_legacy(self):
        """Fallback legacy DP check."""
        logger.info("🔒 Checking Dark Pool levels (legacy)...")
        # Simplified legacy check
        pass
    
    def _on_dp_outcome(self, interaction_id: int, outcome):
        """Callback when DP interaction outcome is determined."""
        try:
            outcome_emoji = {
                'BOUNCE': '✅ LEVEL HELD',
                'BREAK': '❌ LEVEL BROKE',
                'FADE': '⚪ NO CLEAR OUTCOME'
            }.get(outcome.outcome.value, '❓ UNKNOWN')
            
            if not self.unified_mode:
                embed = {
                    "title": f"🎯 DP OUTCOME: {outcome_emoji}",
                    "color": 3066993 if outcome.outcome.value == 'BOUNCE' else 15158332,
                    "description": f"Interaction #{interaction_id} resolved after {outcome.time_to_outcome_min} min",
                    "fields": [
                        {"name": "📊 Max Move", "value": f"{outcome.max_move_pct:+.2f}%", "inline": True},
                        {"name": "⏱️ Tracking Time", "value": f"{outcome.time_to_outcome_min} min", "inline": True},
                    ],
                    "footer": {"text": "Learning from this outcome... Patterns updated!"},
                    "timestamp": datetime.utcnow().isoformat()
                }
                self.send_discord(embed, alert_type="dp_outcome", source="dp_learning")
        except Exception as e:
            logger.error(f"❌ Outcome alert error: {e}")
    
    def check_synthesis(self):
        """Check Signal Synthesis Brain."""
        if not self.brain_enabled or not self.signal_brain:
            return
        
        try:
            import yfinance as yf
            
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            spy_price = 0.0
            qqq_price = 0.0
            for symbol in ['SPY', 'QQQ']:
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period='1d', interval='1m')
                    if not hist.empty:
                        price = float(hist['Close'].iloc[-1])
                        if symbol == 'SPY':
                            spy_price = price
                        else:
                            qqq_price = price
                except:
                    continue
            
            spy_levels = []
            qqq_levels = []
            
            if self.recent_dp_alerts:
                for alert in self.recent_dp_alerts:
                    bg = alert.battleground
                    level_data = {'price': bg.price, 'volume': bg.volume}
                    if alert.symbol == 'SPY':
                        spy_levels.append(level_data)
                    elif alert.symbol == 'QQQ':
                        qqq_levels.append(level_data)
            
            if not spy_levels and not qqq_levels:
                return
            
            fed_sentiment = "NEUTRAL"
            trump_risk = "LOW"
            
            if self.macro_provider:
                try:
                    macro_context = self.macro_provider.get_context()
                    fed_sentiment = macro_context.fed_sentiment
                    trump_risk = macro_context.trump_risk
                except:
                    pass
            
            result = self.signal_brain.analyze(
                spy_levels=spy_levels,
                qqq_levels=qqq_levels,
                spy_price=spy_price,
                qqq_price=qqq_price,
                fed_sentiment=fed_sentiment,
                trump_risk=trump_risk,
            )
            
            should_send = False
            if self.unified_mode and len(self.recent_dp_alerts) > 0:
                should_send = True
            elif self.signal_brain.should_alert(result):
                should_send = True
            
            if should_send:
                current_time = time.time()
                if hasattr(self, 'last_synthesis_sent'):
                    elapsed = current_time - self.last_synthesis_sent
                    if elapsed < 300:
                        return
                
                self.last_synthesis_sent = current_time
                
                embed = self.signal_brain.to_discord(result)
                content = f"🧠 **UNIFIED MARKET SYNTHESIS** | {result.confluence.score:.0f}% {result.confluence.bias.value}"
                
                self.send_discord(embed, content=content, alert_type="synthesis", source="signal_brain", symbol="SPY,QQQ")
                
                # Check Narrative Brain signals
                narrative_sent = self._check_narrative_brain_signals(result, spy_price, qqq_price)
                
                if not narrative_sent:
                    self.recent_dp_alerts = []
                
        except Exception as e:
            logger.error(f"   ❌ Synthesis error: {e}")
    
    def _check_narrative_brain_signals(self, synthesis_result, spy_price: float, qqq_price: float) -> bool:
        """
        🧠 NARRATIVE BRAIN - SEPARATE HIGH-QUALITY SIGNALS
        
        Checks Narrative Brain decision logic and sends separately if criteria met.
        These are HIGHER QUALITY signals with better move predictability.
        
        Returns:
            bool: True if signal was sent, False otherwise
        """
        if not self.narrative_enabled or not self.narrative_brain or not self.recent_dp_alerts:
            return False
        
        try:
            # Calculate average confluence from recent alerts
            def get_alert_confluence(alert):
                """Calculate confluence score for an alert"""
                score = 50
                bg = alert.battleground
                if bg.volume >= 2_000_000:
                    score += 30
                elif bg.volume >= 1_000_000:
                    score += 20
                elif bg.volume >= 500_000:
                    score += 10
                if alert.priority.value == "CRITICAL":
                    score += 20
                elif alert.priority.value == "HIGH":
                    score += 10
                if alert.alert_type.value == "AT_LEVEL":
                    score += 10
                if alert.ai_prediction and alert.ai_prediction > 0.7:
                    score += 10
                return min(score, 100)
            
            avg_confluence = sum(
                get_alert_confluence(alert) 
                for alert in self.recent_dp_alerts
            ) / len(self.recent_dp_alerts)
            
            # Narrative Brain decision logic
            min_confluence = 70.0
            min_alerts = 3
            critical_mass = 5
            exceptional_confluence = 80.0
            
            should_send = False
            reason = ""
            
            if avg_confluence >= exceptional_confluence:
                should_send = True
                reason = f"Exceptional confluence ({avg_confluence:.0f}%)"
            elif avg_confluence >= min_confluence and len(self.recent_dp_alerts) >= min_alerts:
                should_send = True
                reason = f"Strong confluence ({avg_confluence:.0f}%) + {len(self.recent_dp_alerts)} alerts"
            elif len(self.recent_dp_alerts) >= critical_mass:
                should_send = True
                reason = f"Critical mass ({len(self.recent_dp_alerts)} alerts)"
            
            if should_send:
                current_time = time.time()
                if hasattr(self, 'last_narrative_sent'):
                    elapsed = current_time - self.last_narrative_sent
                    if elapsed < 300:
                        logger.debug(f"   ⏭️ Narrative Brain on cooldown ({elapsed:.0f}s < 300s)")
                        return False
                
                best_alert = max(self.recent_dp_alerts, key=get_alert_confluence)
                bg = best_alert.battleground
                ts = best_alert.trade_setup
                
                # Regime-aware filtering
                market_regime = self._detect_market_regime(spy_price)
                signal_direction = ts.direction.value if ts else "UNKNOWN"
                
                regime_details = getattr(self, '_last_regime_details', {})
                bullish_signals = regime_details.get('bullish_signals', 0)
                bearish_signals = regime_details.get('bearish_signals', 0)
                
                # STRONG regimes = HARD BLOCK
                if market_regime == "STRONG_DOWNTREND" and signal_direction == "LONG":
                    logger.warning(f"   ⛔ REGIME FILTER: Blocking LONG in STRONG DOWNTREND")
                    return False
                
                if market_regime == "STRONG_UPTREND" and signal_direction == "SHORT":
                    logger.warning(f"   ⛔ REGIME FILTER: Blocking SHORT in STRONG UPTREND")
                    return False
                
                # Normal downtrend = block LONG unless exceptional
                if market_regime == "DOWNTREND" and signal_direction == "LONG":
                    if avg_confluence < 90:
                        logger.warning(f"   ⛔ REGIME FILTER: Blocking LONG in DOWNTREND (confluence {avg_confluence:.0f}% < 90%)")
                        return False
                
                # Normal uptrend = block SHORT unless exceptional
                if market_regime == "UPTREND" and signal_direction == "SHORT":
                    if avg_confluence < 90:
                        logger.warning(f"   ⛔ REGIME FILTER: Blocking SHORT in UPTREND (confluence {avg_confluence:.0f}% < 90%)")
                        return False
                
                # Synthesis-signal alignment
                synthesis_bias = synthesis_result.confluence.bias.value if synthesis_result and hasattr(synthesis_result, 'confluence') else "NEUTRAL"
                synthesis_score = synthesis_result.confluence.score if synthesis_result and hasattr(synthesis_result, 'confluence') else 50
                
                if synthesis_bias == "BEARISH" and signal_direction == "LONG":
                    if synthesis_score >= 60:
                        logger.warning(f"   ⛔ SYNTHESIS CONFLICT: Blocking LONG (synthesis {synthesis_score:.0f}% BEARISH)")
                        return False
                
                if synthesis_bias == "BULLISH" and signal_direction == "SHORT":
                    if synthesis_score >= 60:
                        logger.warning(f"   ⛔ SYNTHESIS CONFLICT: Blocking SHORT (synthesis {synthesis_score:.0f}% BULLISH)")
                        return False
                
                # ═══════════════════════════════════════════════════════════════
                # GLOBAL DIRECTION LOCK - No flip-flopping between LONG/SHORT!
                # ═══════════════════════════════════════════════════════════════
                if not hasattr(self, '_last_symbol_directions'):
                    self._last_symbol_directions = {}
                
                symbol_key = bg.symbol
                if symbol_key in self._last_symbol_directions:
                    last_direction, last_time = self._last_symbol_directions[symbol_key]
                    elapsed = current_time - last_time
                    
                    # Block opposite direction for 10 minutes (600 seconds)
                    if last_direction != signal_direction and elapsed < 600:
                        logger.warning(f"   ⛔ DIRECTION LOCK: {bg.symbol} already committed to {last_direction} ({elapsed:.0f}s ago)")
                        logger.warning(f"      → Blocking {signal_direction} signal to prevent flip-flopping")
                        return False
                
                # Record this direction for the symbol
                self._last_symbol_directions[symbol_key] = (signal_direction, current_time)
                
                # Clean up old entries (older than 30 min)
                self._last_symbol_directions = {
                    k: v for k, v in self._last_symbol_directions.items() 
                    if current_time - v[1] < 1800
                }
                
                # Level-direction cooldown (original - kept for same-level protection)
                level_key = f"{bg.symbol}_{bg.price:.2f}"
                if not hasattr(self, '_last_level_directions'):
                    self._last_level_directions = {}
                
                if level_key in self._last_level_directions:
                    last_direction, last_time = self._last_level_directions[level_key]
                    elapsed = current_time - last_time
                    
                    if last_direction != signal_direction and elapsed < 600:
                        logger.warning(f"   ⛔ FLIP PREVENTION: Same level ${bg.price:.2f} flipped from {last_direction} to {signal_direction}")
                        return False
                
                self._last_level_directions[level_key] = (signal_direction, current_time)
                self._last_level_directions = {
                    k: v for k, v in self._last_level_directions.items() 
                    if current_time - v[1] < 1800
                }
                
                # Create alert
                embed = {
                    "title": f"🧠 **NARRATIVE BRAIN SIGNAL** - {best_alert.symbol}",
                    "description": f"**Higher Quality Signal** - Better move predictability\n\n"
                                   f"**Reason:** {reason}\n"
                                   f"**Confluence:** {avg_confluence:.0f}%\n"
                                   f"**Alerts Confirmed:** {len(self.recent_dp_alerts)}\n"
                                   f"**Regime:** {market_regime} | **Synthesis:** {synthesis_bias}",
                    "color": 0x00ff00,
                    "fields": []
                }
                
                if ts:
                    embed["fields"].extend([{
                        "name": "🎯 Trade Setup",
                        "value": f"**Direction:** {ts.direction.value}\n"
                                f"**Entry:** ${ts.entry:.2f}\n"
                                f"**Stop:** ${ts.stop:.2f}\n"
                                f"**Target:** ${ts.target:.2f}\n"
                                f"**R/R:** {ts.risk_reward:.1f}:1",
                        "inline": False
                    }])
                
                embed["fields"].append({
                    "name": "📊 Battleground",
                    "value": f"**Level:** ${bg.price:.2f} ({bg.level_type.value})\n"
                            f"**Volume:** {bg.volume:,} shares",
                    "inline": False
                })
                
                content = f"🧠 **NARRATIVE BRAIN SIGNAL** | {best_alert.symbol} | {reason} | ✅ **HIGHER QUALITY**"
                
                logger.info(f"   🧠 Narrative Brain: Sending HIGH-QUALITY signal ({reason})")
                success = self.send_discord(embed, content=content, alert_type="narrative_brain", source="narrative_brain", symbol=best_alert.symbol)
                
                if success:
                    self.last_narrative_sent = current_time
                    return True
            
            return False
                
        except Exception as e:
            logger.error(f"   ❌ Narrative Brain check error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
    
    def _is_market_hours(self) -> bool:
        """Check if currently in RTH."""
        from datetime import time as dt_time
        now = datetime.now()
        current_time = now.time()
        market_open = dt_time(9, 30)
        market_close = dt_time(16, 0)
        is_weekday = now.weekday() < 5
        in_hours = market_open <= current_time < market_close
        return is_weekday and in_hours
    
    def _get_current_intelligence_snapshot(self) -> dict:
        """Get current snapshot of all intelligence sources."""
        snapshot = {
            'fed_watch': {},
            'fed_officials': {},
            'trump_monitor': {},
            'economic_calendar': {},
            'dp_monitor': {}
        }
        # Simplified - would populate from all monitors
        return snapshot
    
    def send_startup_alert(self):
        """Send startup notification."""
        if self.startup_alert_sent:
            return
        
        embed = {
            "title": "🎯 ALPHA INTELLIGENCE - ONLINE (MODULAR)",
            "color": 3066993,
            "description": "All monitoring systems activated (MODULAR VERSION)",
            "fields": [
                {"name": "🏦 Fed Watch", "value": "✅ Active" if self.fed_enabled else "❌ Disabled", "inline": True},
                {"name": "🎯 Trump Intel", "value": "✅ Active" if self.trump_enabled else "❌ Disabled", "inline": True},
                {"name": "📊 Economic AI", "value": "✅ Active" if self.econ_enabled else "❌ Disabled", "inline": True},
                {"name": "🔒 Dark Pools", "value": f"✅ {', '.join(self.symbols)}" if self.dp_enabled else "❌ Disabled", "inline": True},
                {"name": "🧠 Signal Brain", "value": "✅ ACTIVE" if self.brain_enabled else "❌ Disabled", "inline": False},
            ],
            "footer": {"text": "Modular monitoring system"},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.send_discord(embed, alert_type="startup", source="monitor")
        self.startup_alert_sent = True
    
    # ═══════════════════════════════════════════════════════════════
    # TRADYTICS METHODS (preserved from original)
    # ═══════════════════════════════════════════════════════════════
    
    def autonomous_tradytics_analysis(self):
        """Autonomous Tradytics analysis - simulates analyzing bot alerts"""
        if not self.tradytics_llm_available:
            return
        
        try:
            logger.info("🤖 Running Autonomous Tradytics Analysis...")
            sample_alerts = self._generate_sample_tradytics_alerts()
            
            for alert in sample_alerts:
                import hashlib
                alert_hash = hashlib.md5(f"{alert['content']}:{alert['bot_name']}".encode()).hexdigest()[:12]
                if alert_hash in self.seen_tradytics_alerts:
                    logger.debug(f"   📊 Tradytics alert duplicate (hash: {alert_hash[:8]}) - skipping")
                    continue
                
                self.seen_tradytics_alerts.add(alert_hash)
                if len(self.seen_tradytics_alerts) > 50:
                    self.seen_tradytics_alerts = set(list(self.seen_tradytics_alerts)[-50:])
                
                analysis = self._analyze_tradytics_alert(alert)
                if analysis and "Analysis failed" not in analysis:
                    self._send_tradytics_analysis_alert(alert, analysis)
                    self.tradytics_alerts_processed += 1
            
            if sample_alerts:
                logger.info(f"   ✅ Processed {len(sample_alerts)} autonomous Tradytics analyses")
                
        except Exception as e:
            logger.error(f"   ❌ Autonomous Tradytics analysis error: {e}")
    
    def _generate_sample_tradytics_alerts(self):
        """Generate sample Tradytics alerts for demonstration"""
        # DISABLED: Sample alerts were causing spam
        return []
    
    def _analyze_tradytics_alert(self, alert):
        """Analyze a Tradytics alert using savage LLM"""
        try:
            savage_prompt = f"""
            🔥 **SAVAGE TRADYTICS ANALYSIS - GODLIKE MODE** 🔥

            Tradytics Bot: {alert['bot_name']}
            Alert Type: {alert['alert_type']}
            Symbols: {', '.join(alert.get('symbols', []))}
            Raw Alert: {alert['content']}

            **YOUR MISSION AS A RUTHLESS ALPHA PREDATOR:**
            Analyze this Tradytics alert like the market's most brutal hunter. What does this REALLY fucking mean? Is this a BUY signal, SELL signal, or RUN-FOR-YOUR-LIFE signal? Connect the institutional dots. Be savage, be precise, be profitable.

            **ALPHA WARRIOR RULES:**
            - NO MARKET BULLSHIT - Cut the crap
            - Tell REAL traders what this means RIGHT NOW
            - If the signal is weak, FUCKING SAY IT'S WEAK
            - If it's strong, EXPLAIN WHY YOU'D BET YOUR HOUSE ON IT
            - Give ACTIONABLE insight, not pussy predictions
            - Think like a hedge fund killer, not a retail chump

            **SAVAGE INSTITUTIONAL ANALYSIS:**
            """
            
            try:
                from src.data.llm_api import query_llm
                response = query_llm(savage_prompt, provider="gemini")
            except (ImportError, NameError):
                logger.warning("   ⚠️ query_llm not available - skipping analysis")
                return f"Analysis unavailable: query_llm not found"
            
            if isinstance(response, dict):
                analysis = (response.get('detailed_analysis') or
                           response.get('market_sentiment') or
                           str(response))
                if isinstance(analysis, str) and len(analysis) > 50:
                    return analysis
                else:
                    return f"Savage Analysis: {analysis}"
            else:
                return str(response)
                
        except Exception as e:
            logger.error(f"   ❌ Tradytics alert analysis error: {e}")
            return f"Analysis failed: {str(e)}"
    
    def process_tradytics_webhook(self, webhook_data):
        """Process incoming Tradytics webhook data"""
        try:
            logger.info(f"🔗 Processing Tradytics webhook: {webhook_data}")
            
            if 'content' in webhook_data:
                message_content = webhook_data['content']
                author = webhook_data.get('author', {}).get('username', 'Unknown')
                
                tradytics_keywords = ['SWEEP', 'BLOCK', 'CALL', 'PUT', 'PREMIUM', 'VOLUME', 'FLOW']
                if any(keyword in message_content.upper() for keyword in tradytics_keywords):
                    logger.info(f"🎯 Detected Tradytics alert from {author}: {message_content[:100]}...")
                    
                    alert = {
                        'bot_name': author,
                        'alert_type': self._classify_alert_type(message_content),
                        'content': message_content,
                        'symbols': self._extract_symbols(message_content),
                        'timestamp': webhook_data.get('timestamp', datetime.now().isoformat()),
                        'confidence': 0.8,
                        'source': 'webhook'
                    }
                    
                    analysis = self._analyze_tradytics_alert(alert)
                    if analysis:
                        self._send_tradytics_analysis_alert(alert, analysis)
                        logger.info(f"✅ Processed webhook alert from {author}")
                        return {"status": "analyzed", "alert_processed": True, "analysis": analysis[:200]}
                    else:
                        return {"status": "analysis_failed", "alert_processed": False}
                else:
                    return {"status": "not_tradytics_alert", "alert_processed": False}
            else:
                return {"status": "invalid_format", "alert_processed": False}
                
        except Exception as e:
            logger.error(f"❌ Webhook processing error: {e}")
            return {"status": "error", "error": str(e)}
    
    def _classify_alert_type(self, content):
        """Classify the type of Tradytics alert"""
        content_upper = content.upper()
        if 'SWEEP' in content_upper:
            return 'options_signal'
        elif 'BLOCK' in content_upper:
            return 'block_trade'
        elif 'FLOW' in content_upper:
            return 'volume_flow'
        elif any(word in content_upper for word in ['CALL', 'PUT']):
            return 'options_signal'
        else:
            return 'market_signal'
    
    def _extract_symbols(self, content):
        """Extract stock symbols from alert content"""
        import re
        symbols = re.findall(r'\b[A-Z]{1,5}\b', content)
        exclude_words = ['A', 'I', 'ON', 'AT', 'IN', 'IS', 'IT', 'TO', 'OF', 'BY', 'OR', 'AS', 'AN', 'BE', 'DO', 'FOR', 'IF', 'NO', 'SO', 'UP', 'US', 'WE', 'YES']
        filtered_symbols = [s for s in symbols if s not in exclude_words and len(s) >= 2]
        return list(set(filtered_symbols))
    
    def _send_tradytics_analysis_alert(self, alert, analysis):
        """Send autonomous Tradytics analysis to Discord"""
        try:
            if not analysis or "Analysis failed" in analysis or "unavailable" in analysis.lower():
                logger.debug(f"   ⏭️  Skipping Tradytics alert - analysis failed or unavailable")
                return
            
            embed = {
                "title": f"🧠 **SAVAGE ANALYSIS** - {alert['bot_name']} Alert",
                "description": f"**Alert:** {alert['content']}\n\n{analysis}",
                "color": 0xff0000,
                "timestamp": alert['timestamp'],
                "footer": {"text": "Alpha Intelligence | Autonomous Tradytics Integration"}
            }
            
            content = f"🧠 **AUTONOMOUS ANALYSIS** | {alert['bot_name']} detected significant activity"
            self.send_discord(embed, content, alert_type="tradytics", source="tradytics_analysis", symbol=",".join(alert.get('symbols', [])) if alert.get('symbols') else None)
            
        except Exception as e:
            logger.error(f"   ❌ Send autonomous Tradytics alert error: {e}")
    
    def _fetch_economic_events(self, date: str) -> list:
        """Fetch economic events using Perplexity."""
        try:
            api_key = os.getenv('PERPLEXITY_API_KEY')
            if not api_key:
                return []
            
            sys.path.insert(0, os.path.join(base_path, 'live_monitoring', 'enrichment', 'apis'))
            from perplexity_search import PerplexitySearchClient
            
            client = PerplexitySearchClient(api_key=api_key)
            
            query = f"""
            What major US economic data releases are scheduled for {date}?
            List ONLY high-impact events like:
            - NFP (Nonfarm Payrolls)
            - CPI / Core CPI
            - PPI / Core PPI
            - PCE / Core PCE
            - GDP
            - Retail Sales
            - ISM Manufacturing
            - Initial Jobless Claims
            
            For each, give: TIME (ET), EVENT NAME
            """
            
            result = client.search(query)
            if not result or 'answer' not in result:
                return []
            
            answer = result['answer']
            events = []
            
            import re
            event_keywords = [
                'nonfarm', 'payrolls', 'nfp',
                'cpi', 'consumer price',
                'ppi', 'producer price',
                'pce', 'personal consumption',
                'gdp', 'gross domestic',
                'retail sales',
                'ism manufacturing', 'ism services',
                'jobless claims', 'unemployment'
            ]
            
            for line in answer.split('\n'):
                line_lower = line.lower()
                for kw in event_keywords:
                    if kw in line_lower:
                        time_match = re.search(r'(\d{1,2}:\d{2})', line)
                        event_time = time_match.group(1) if time_match else "08:30"
                        
                        events.append({
                            "date": date,
                            "time": event_time,
                            "name": kw.replace('_', ' ').title()
                        })
                        break
            
            return events
            
        except Exception as e:
            logger.debug(f"Economic events fetch error: {e}")
            return []
    
    # ═══════════════════════════════════════════════════════════════
    # EXPLOITATION MODULE CHECKS
    # ═══════════════════════════════════════════════════════════════
    
    def check_squeeze_setups(self):
        """
        🔥 Check for short squeeze setups (PHASE 1 EXPLOITATION).
        Runs hourly during market hours.
        """
        if not self.squeeze_enabled or not self.squeeze_detector:
            return
        
        logger.info("🔥 Checking for SQUEEZE setups...")
        
        try:
            for symbol in self.symbols:
                signal = self.squeeze_detector.analyze(symbol)
                
                if signal:
                    # Convert to LiveSignal for alert system
                    live_signal = self.squeeze_detector.to_live_signal(signal)
                    
                    # Create Discord embed
                    score_color = 3066993 if signal.score >= 80 else 16776960  # Green if high, yellow otherwise
                    
                    embed = {
                        "title": f"🔥 SQUEEZE SETUP: {signal.symbol}",
                        "color": score_color,
                        "description": f"**Score: {signal.score:.0f}/100** | Short Interest {signal.short_interest_pct:.1f}%",
                        "fields": [
                            {"name": "📊 SI%", "value": f"{signal.short_interest_pct:.1f}% ({signal.si_score:.0f} pts)", "inline": True},
                            {"name": "💰 Borrow Fee", "value": f"{signal.borrow_fee_pct:.1f}% ({signal.borrow_fee_score:.0f} pts)", "inline": True},
                            {"name": "📈 FTD Spike", "value": f"{signal.ftd_spike_ratio:.1f}x ({signal.ftd_score:.0f} pts)", "inline": True},
                            {"name": "🔒 DP Buying", "value": f"{signal.dp_buying_pressure:.0%} ({signal.dp_support_score:.0f} pts)", "inline": True},
                            {"name": "🎯 Entry", "value": f"${signal.entry_price:.2f}", "inline": True},
                            {"name": "🛑 Stop", "value": f"${signal.stop_price:.2f}", "inline": True},
                            {"name": "🚀 Target", "value": f"${signal.target_price:.2f}", "inline": True},
                            {"name": "📐 R/R", "value": f"{signal.risk_reward_ratio:.1f}:1", "inline": True},
                            {"name": "💡 Action", "value": "**LONG** (Squeeze Play)", "inline": True},
                        ],
                        "footer": {"text": f"Exploitation Phase 1 • Squeeze Detection"},
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    
                    # Add reasoning
                    if signal.reasoning:
                        embed["fields"].append({
                            "name": "📝 Reasoning",
                            "value": "\n".join([f"• {r}" for r in signal.reasoning[:3]]),
                            "inline": False
                        })
                    
                    # Add warnings
                    if signal.warnings:
                        embed["fields"].append({
                            "name": "⚠️ Warnings",
                            "value": "\n".join([f"• {w}" for w in signal.warnings[:3]]),
                            "inline": False
                        })
                    
                    content = f"🔥 **SQUEEZE ALERT** 🔥 | {signal.symbol} Score: {signal.score:.0f}/100"
                    
                    self.send_discord(embed, content=content, alert_type="squeeze_signal", source="squeeze_detector", symbol=signal.symbol)
                    
                    logger.info(f"   🔥 Squeeze signal sent for {signal.symbol}!")
                    
        except Exception as e:
            logger.error(f"   ❌ Squeeze check error: {e}")
    
    def check_gamma_setups(self):
        """
        🎲 Check for gamma ramp setups (PHASE 2 EXPLOITATION).
        Runs hourly during market hours.
        """
        if not self.gamma_enabled or not self.gamma_tracker:
            return
        
        logger.info("🎲 Checking for GAMMA setups...")
        
        try:
            # Check multiple expirations for each symbol
            for symbol in self.symbols:
                # Check nearest and weekly expirations
                for exp_idx in [0, 4]:  # 0=nearest, 4=weekly (Friday)
                    signal = self.gamma_tracker.analyze(symbol, expiration_idx=exp_idx)
                    
                    if signal:
                        # Create Discord embed
                        direction_color = 15548997 if signal.direction == 'DOWN' else 3066993  # Red for DOWN, Green for UP
                        direction_emoji = "🔻" if signal.direction == 'DOWN' else "🔺"
                        
                        embed = {
                            "title": f"🎲 GAMMA {signal.direction}: {signal.symbol}",
                            "color": direction_color,
                            "description": f"**Score: {signal.score:.0f}/100** | Max Pain ${signal.max_pain:.2f} ({signal.max_pain_distance_pct:+.1f}%)",
                            "fields": [
                                {"name": "📊 P/C Ratio", "value": f"{signal.put_call_ratio:.2f}", "inline": True},
                                {"name": f"{direction_emoji} Direction", "value": f"**{signal.direction}**", "inline": True},
                                {"name": "🎯 Max Pain", "value": f"${signal.max_pain:.2f}", "inline": True},
                                {"name": "📈 Call OI", "value": f"{signal.total_call_oi:,}", "inline": True},
                                {"name": "📉 Put OI", "value": f"{signal.total_put_oi:,}", "inline": True},
                                {"name": "📅 Expiration", "value": signal.expiration, "inline": True},
                                {"name": "💵 Entry", "value": f"${signal.entry_price:.2f}", "inline": True},
                                {"name": "🛑 Stop", "value": f"${signal.stop_price:.2f}", "inline": True},
                                {"name": "🎯 Target", "value": f"${signal.target_price:.2f}", "inline": True},
                                {"name": "📐 R/R", "value": f"{signal.risk_reward_ratio:.1f}:1", "inline": True},
                                {"name": "💡 Action", "value": f"**{signal.action}** (Gamma Play)", "inline": True},
                            ],
                            "footer": {"text": f"Exploitation Phase 2 • Gamma Tracking"},
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        
                        # Add reasoning
                        if signal.reasoning:
                            embed["fields"].append({
                                "name": "📝 Reasoning",
                                "value": "\n".join([f"• {r}" for r in signal.reasoning[:4]]),
                                "inline": False
                            })
                        
                        content = f"🎲 **GAMMA ALERT** 🎲 | {signal.symbol} {signal.direction} Score: {signal.score:.0f}/100"
                        
                        self.send_discord(embed, content=content, alert_type="gamma_signal", source="gamma_tracker", symbol=signal.symbol)
                        
                        logger.info(f"   🎲 Gamma signal sent for {signal.symbol} ({signal.direction})!")
                        
                        # Only send one signal per symbol (break after first hit)
                        break
                    
        except Exception as e:
            logger.error(f"   ❌ Gamma check error: {e}")
    
    def check_opportunity_scanner(self):
        """
        🔍 Scan market for new opportunities (PHASE 3 EXPLOITATION).
        Runs hourly during market hours.
        """
        if not self.scanner_enabled or not self.opportunity_scanner:
            return
        
        logger.info("🔍 Scanning for NEW OPPORTUNITIES...")
        
        try:
            # Get today's date for tracking
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Run market scan
            opportunities = self.opportunity_scanner.scan_market(min_score=50, max_results=10)
            
            if not opportunities:
                logger.info("   📊 No high-score opportunities found")
                return
            
            # Filter out already-alerted symbols today
            new_opportunities = [
                opp for opp in opportunities 
                if f"{today}:{opp.symbol}" not in self.scanned_today
            ]
            
            if not new_opportunities:
                logger.info("   📊 All opportunities already alerted today")
                return
            
            # Send alerts for top 5 new opportunities
            for opp in new_opportunities[:5]:
                # Mark as alerted
                self.scanned_today.add(f"{today}:{opp.symbol}")
                
                # Create Discord embed
                score_color = 3066993 if opp.score >= 70 else 16776960  # Green if high, yellow otherwise
                
                embed = {
                    "title": f"🔍 NEW OPPORTUNITY: {opp.symbol}",
                    "color": score_color,
                    "description": f"**Score: {opp.score:.0f}/100** | Found via market scan",
                    "fields": [],
                    "footer": {"text": f"Exploitation Phase 3 • Opportunity Scanner"},
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                # Add short interest if available
                if opp.short_interest and opp.short_interest > 0:
                    embed["fields"].append({
                        "name": "📊 Short Interest",
                        "value": f"{opp.short_interest:.1f}%",
                        "inline": True
                    })
                
                # Add DP activity if available
                if opp.dp_activity and opp.dp_activity > 0:
                    embed["fields"].append({
                        "name": "🔒 DP Levels",
                        "value": f"{opp.dp_activity:.0f}",
                        "inline": True
                    })
                
                # Add squeeze score if available
                if opp.squeeze_score and opp.squeeze_score > 0:
                    embed["fields"].append({
                        "name": "🔥 Squeeze Score",
                        "value": f"{opp.squeeze_score:.0f}/100",
                        "inline": True
                    })
                
                # Add reasons
                if opp.reasons:
                    embed["fields"].append({
                        "name": "📝 Reasons",
                        "value": "\n".join([f"• {r}" for r in opp.reasons[:5]]),
                        "inline": False
                    })
                
                # Suggest action based on score
                if opp.score >= 70:
                    action = "⚡ **HIGH PRIORITY** - Add to watchlist for squeeze/gamma analysis"
                elif opp.score >= 60:
                    action = "📈 **MEDIUM PRIORITY** - Monitor for entry setup"
                else:
                    action = "👀 **LOW PRIORITY** - Keep on radar"
                
                embed["fields"].append({
                    "name": "💡 Suggested Action",
                    "value": action,
                    "inline": False
                })
                
                content = f"🔍 **NEW OPPORTUNITY** | {opp.symbol} Score: {opp.score:.0f}/100"
                
                self.send_discord(embed, content=content, alert_type="opportunity_scan", source="opportunity_scanner", symbol=opp.symbol)
                
                logger.info(f"   🔍 Opportunity alert sent for {opp.symbol} (Score: {opp.score:.0f})")
            
            # Also run squeeze detector on top opportunities
            if self.squeeze_enabled and self.squeeze_detector:
                squeeze_opportunities = self.opportunity_scanner.scan_with_squeeze_detector(
                    self.squeeze_detector, 
                    min_score=55
                )
                
                for opp in squeeze_opportunities[:3]:
                    if f"{today}:SQUEEZE:{opp.symbol}" in self.scanned_today:
                        continue
                    
                    self.scanned_today.add(f"{today}:SQUEEZE:{opp.symbol}")
                    
                    embed = {
                        "title": f"🔥 SQUEEZE CANDIDATE: {opp.symbol}",
                        "color": 15548997,  # Red for squeeze
                        "description": f"**Squeeze Score: {opp.squeeze_score:.0f}/100** | SI: {opp.short_interest:.1f}%",
                        "fields": [
                            {"name": "📊 Short Interest", "value": f"{opp.short_interest:.1f}%", "inline": True},
                            {"name": "🔥 Squeeze Score", "value": f"{opp.squeeze_score:.0f}/100", "inline": True},
                        ],
                        "footer": {"text": "Opportunity Scanner + Squeeze Detector"},
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    
                    if opp.reasons:
                        embed["fields"].append({
                            "name": "📝 Reasons",
                            "value": "\n".join([f"• {r}" for r in opp.reasons[:3]]),
                            "inline": False
                        })
                    
                    content = f"🔥 **SQUEEZE CANDIDATE** | {opp.symbol} Score: {opp.squeeze_score:.0f}/100 | SI: {opp.short_interest:.1f}%"
                    
                    self.send_discord(embed, content=content, alert_type="squeeze_candidate", source="opportunity_scanner", symbol=opp.symbol)
                    
                    logger.info(f"   🔥 Squeeze candidate alert sent for {opp.symbol}!")
            
            # Clean up old entries (older than today)
            self.scanned_today = {k for k in self.scanned_today if k.startswith(today)}
            
        except Exception as e:
            logger.error(f"   ❌ Opportunity scanner error: {e}")
    
    def check_ftd_analyzer(self):
        """
        📈 Check for FTD-based opportunities (PHASE 4 EXPLOITATION).
        Detects T+35 settlement cycles and forced covering events.
        """
        if not self.ftd_enabled or not self.ftd_analyzer:
            return
        
        now = datetime.now()
        today = now.strftime('%Y-%m-%d')
        
        logger.info("📈 Checking FTD opportunities...")
        
        try:
            # Scan FTD candidates
            signals = self.ftd_analyzer.get_ftd_candidates(self.ftd_candidates, min_score=50)
            
            if not signals:
                logger.info("   📊 No FTD signals found.")
                return
            
            for signal in signals:
                # Check for duplicate alerts
                alert_key = f"ftd_{signal.symbol}_{today}"
                if self.alert_manager.is_alert_duplicate(alert_key, cooldown_minutes=60 * 24):
                    logger.debug(f"   ⏭️ Skipping duplicate FTD alert for {signal.symbol}")
                    continue
                
                # Determine color based on signal type
                if signal.signal_type == "T35_WINDOW":
                    color = 0xff0000  # Red - urgent
                    emoji = "🚨"
                elif signal.signal_type == "SPIKE":
                    color = 0xff6600  # Orange - high priority
                    emoji = "📈"
                elif signal.signal_type == "COVERING_PRESSURE":
                    color = 0xffcc00  # Yellow - medium
                    emoji = "⚠️"
                else:
                    color = 0x00ccff  # Blue - info
                    emoji = "📊"
                
                embed = {
                    "title": f"{emoji} FTD SIGNAL: {signal.symbol}",
                    "color": color,
                    "description": f"**Type:** {signal.signal_type}\n"
                                   f"**Score:** {signal.score:.0f}/100",
                    "fields": [
                        {"name": "📊 Current FTD", "value": f"{signal.current_ftd:,}", "inline": True},
                        {"name": "📈 Spike Ratio", "value": f"{signal.ftd_spike_ratio:.1f}x", "inline": True},
                        {"name": "⏰ Days to T+35", "value": f"{signal.days_to_t35}", "inline": True},
                        {"name": "💰 Entry", "value": f"${signal.entry_price:.2f}", "inline": True},
                        {"name": "🛑 Stop", "value": f"${signal.stop_price:.2f}", "inline": True},
                        {"name": "🎯 Target", "value": f"${signal.target_price:.2f}", "inline": True},
                        {"name": "⚖️ R/R Ratio", "value": f"{signal.risk_reward_ratio:.1f}:1", "inline": True},
                    ],
                    "footer": {"text": f"Exploitation Phase 4 • FTD Analyzer"},
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                if signal.reasoning:
                    embed["fields"].append({
                        "name": "📝 Reasoning",
                        "value": "\n".join(signal.reasoning[:3]),
                        "inline": False
                    })
                
                if signal.warnings:
                    embed["fields"].append({
                        "name": "⚠️ Warnings",
                        "value": "\n".join(signal.warnings[:3]),
                        "inline": False
                    })
                
                content = f"{emoji} **FTD SIGNAL** | {signal.symbol} {signal.signal_type} | Score: {signal.score:.0f}/100"
                
                self.send_discord(embed, content=content, alert_type="ftd_signal", source="ftd_analyzer", symbol=signal.symbol)
                self.alert_manager.add_alert_to_history(alert_key)
                
                logger.info(f"   {emoji} FTD signal sent for {signal.symbol}!")
            
            # Also check T+35 calendar for upcoming deadlines
            calendar = self.ftd_analyzer.get_t35_calendar(self.ftd_candidates)
            upcoming = [c for c in calendar if c['days_until'] <= 7]  # Within 7 days
            
            if upcoming:
                logger.info(f"   📅 {len(upcoming)} upcoming T+35 deadlines within 7 days")
                for event in upcoming[:3]:  # Top 3
                    alert_key = f"t35_calendar_{event['symbol']}_{event['t35_date']}"
                    if not self.alert_manager.is_alert_duplicate(alert_key, cooldown_minutes=60 * 24):
                        embed = {
                            "title": f"📅 T+35 DEADLINE: {event['symbol']}",
                            "color": 0xff6600 if event['days_until'] <= 3 else 0xffcc00,
                            "description": f"**Forced buy-in deadline approaching!**",
                            "fields": [
                                {"name": "📅 T+35 Date", "value": event['t35_date'], "inline": True},
                                {"name": "⏰ Days Until", "value": f"{event['days_until']}", "inline": True},
                                {"name": "📊 FTD Quantity", "value": f"{event['ftd_quantity']:,}", "inline": True},
                            ],
                            "footer": {"text": f"Exploitation Phase 4 • T+35 Calendar"},
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        
                        content = f"📅 **T+35 DEADLINE** | {event['symbol']} in {event['days_until']} days | {event['ftd_quantity']:,} FTDs"
                        
                        self.send_discord(embed, content=content, alert_type="t35_calendar", source="ftd_analyzer", symbol=event['symbol'])
                        self.alert_manager.add_alert_to_history(alert_key)
            
        except Exception as e:
            logger.error(f"   ❌ FTD analyzer error: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # DAILY RECAP FEATURE
    # ═══════════════════════════════════════════════════════════════
    
    def _should_send_daily_recap(self, now: datetime) -> bool:
        """Check if we should send daily recap (4:00-4:05 PM ET on weekdays)."""
        try:
            import pytz
            et = pytz.timezone('America/New_York')
            now_et = now.astimezone(et) if now.tzinfo else et.localize(now)
            
            # Only weekdays
            if now_et.weekday() >= 5:
                return False
            
            # Between 4:00 PM and 4:05 PM ET
            if now_et.hour == 16 and now_et.minute < 5:
                # Check if we already sent today
                if not hasattr(self, '_last_recap_date'):
                    self._last_recap_date = None
                
                today = now_et.date()
                if self._last_recap_date != today:
                    return True
            
            return False
        except Exception as e:
            logger.debug(f"Daily recap check error: {e}")
            return False
    
    def _send_daily_recap(self):
        """📊 Send daily market recap to Discord."""
        try:
            import yfinance as yf
            import pytz
            
            et = pytz.timezone('America/New_York')
            now_et = datetime.now(et)
            
            logger.info("📊 Generating daily market recap...")
            
            # Get market data
            spy = yf.Ticker('SPY')
            qqq = yf.Ticker('QQQ')
            vix = yf.Ticker('^VIX')
            
            spy_hist = spy.history(period='1d', interval='5m')
            qqq_hist = qqq.history(period='1d', interval='5m')
            vix_hist = vix.history(period='1d')
            
            if spy_hist.empty:
                logger.warning("   ⚠️ No SPY data for daily recap")
                return
            
            # Calculate metrics
            spy_open = float(spy_hist['Open'].iloc[0])
            spy_close = float(spy_hist['Close'].iloc[-1])
            spy_high = float(spy_hist['High'].max())
            spy_low = float(spy_hist['Low'].min())
            spy_change = ((spy_close - spy_open) / spy_open) * 100
            spy_range = ((spy_high - spy_low) / spy_open) * 100
            
            qqq_open = float(qqq_hist['Open'].iloc[0]) if not qqq_hist.empty else 0
            qqq_close = float(qqq_hist['Close'].iloc[-1]) if not qqq_hist.empty else 0
            qqq_change = ((qqq_close - qqq_open) / qqq_open) * 100 if qqq_open > 0 else 0
            
            vix_close = float(vix_hist['Close'].iloc[-1]) if not vix_hist.empty else 0
            
            # Determine market sentiment
            if spy_change > 0.5:
                sentiment = "🟢 BULLISH"
                color = 0x00ff00
            elif spy_change < -0.5:
                sentiment = "🔴 BEARISH"
                color = 0xff0000
            else:
                sentiment = "⚪ NEUTRAL"
                color = 0x808080
            
            # Get gamma signal status
            gamma_status = "❌ No signals"
            if self.gamma_enabled and self.gamma_tracker:
                for symbol in self.symbols:
                    signal = self.gamma_tracker.analyze(symbol)
                    if signal:
                        gamma_status = f"✅ {symbol}: {signal.direction} (Score {signal.score:.0f})"
                        break
            
            # Build embed
            embed = {
                "title": f"📊 DAILY MARKET RECAP - {now_et.strftime('%B %d, %Y')}",
                "color": color,
                "description": f"**Market Sentiment:** {sentiment}",
                "fields": [
                    {
                        "name": "📈 SPY",
                        "value": f"Open: ${spy_open:.2f}\nClose: ${spy_close:.2f}\nChange: {spy_change:+.2f}%\nRange: {spy_range:.2f}%",
                        "inline": True
                    },
                    {
                        "name": "📈 QQQ",
                        "value": f"Open: ${qqq_open:.2f}\nClose: ${qqq_close:.2f}\nChange: {qqq_change:+.2f}%",
                        "inline": True
                    },
                    {
                        "name": "😰 VIX",
                        "value": f"{vix_close:.2f}",
                        "inline": True
                    },
                    {
                        "name": "📊 Intraday",
                        "value": f"High: ${spy_high:.2f}\nLow: ${spy_low:.2f}",
                        "inline": True
                    },
                    {
                        "name": "🎲 Gamma Status",
                        "value": gamma_status,
                        "inline": True
                    },
                    {
                        "name": "🔥 Exploitation",
                        "value": f"Squeeze: {'✅' if self.squeeze_enabled else '❌'}\nGamma: {'✅' if self.gamma_enabled else '❌'}",
                        "inline": True
                    }
                ],
                "footer": {"text": "Alpha Intelligence • Daily Recap"},
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Add key events
            morning_drop = ((spy_low - spy_open) / spy_open) * 100
            if morning_drop < -0.5:
                embed["fields"].append({
                    "name": "🔻 Key Event",
                    "value": f"Morning selloff: {morning_drop:.2f}%\nLow: ${spy_low:.2f}",
                    "inline": False
                })
            
            recovery = ((spy_close - spy_low) / spy_low) * 100
            if recovery > 0.3:
                embed["fields"].append({
                    "name": "📈 Recovery",
                    "value": f"+{recovery:.2f}% from lows",
                    "inline": False
                })
            
            content = f"📊 **DAILY RECAP** | SPY {spy_change:+.2f}% | QQQ {qqq_change:+.2f}% | VIX {vix_close:.2f}"
            
            self.send_discord(embed, content=content, alert_type="daily_recap", source="daily_recap", symbol="SPY,QQQ")
            
            # Mark as sent
            self._last_recap_date = now_et.date()
            
            logger.info(f"   📊 Daily recap sent! SPY {spy_change:+.2f}%")
            
        except Exception as e:
            logger.error(f"   ❌ Daily recap error: {e}")
    
    def run(self):
        """Main run loop."""
        logger.info("🚀 Starting unified monitoring (MODULAR)...")
        
        self.send_startup_alert()
        
        now = datetime.now()
        self.last_fed_check = now
        self.last_trump_check = now
        self.last_econ_check = now
        self.last_dp_check = now
        self.last_synthesis_check = now
        self.last_squeeze_check = now
        self.last_gamma_check = now
        self.gamma_interval = 1800  # Check gamma every 30 min (was hourly)
        
        while self.running:
            try:
                now = datetime.now()
                
                if self.last_fed_check is None or (now - self.last_fed_check).seconds >= self.fed_interval:
                    self.check_fed()
                    self.last_fed_check = now
                
                if self.last_trump_check is None or (now - self.last_trump_check).seconds >= self.trump_interval:
                    self.check_trump()
                    self.last_trump_check = now
                
                if self.last_econ_check is None or (now - self.last_econ_check).seconds >= self.econ_interval:
                    self.check_economics()
                    self.last_econ_check = now
                
                is_market_hours = self._is_market_hours()
                
                if is_market_hours and (self.last_dp_check is None or (now - self.last_dp_check).seconds >= self.dp_interval):
                    self.check_dark_pools()
                    self.last_dp_check = now
                
                if is_market_hours and self.brain_enabled and (self.last_synthesis_check is None or (now - self.last_synthesis_check).seconds >= self.synthesis_interval):
                    self.check_synthesis()
                    self.last_synthesis_check = now
                
                # 🔥 EXPLOITATION: Squeeze Detection (hourly during RTH)
                if is_market_hours and self.squeeze_enabled and (self.last_squeeze_check is None or (now - self.last_squeeze_check).seconds >= self.squeeze_interval):
                    self.check_squeeze_setups()
                    self.last_squeeze_check = now
                
                # 🎲 EXPLOITATION: Gamma Tracking (every 30 min during RTH - was hourly)
                if is_market_hours and self.gamma_enabled and (self.last_gamma_check is None or (now - self.last_gamma_check).seconds >= self.gamma_interval):
                    self.check_gamma_setups()
                    self.last_gamma_check = now
                
                # 🔍 EXPLOITATION: Opportunity Scanner (hourly during RTH)
                if is_market_hours and self.scanner_enabled and (self.last_scanner_check is None or (now - self.last_scanner_check).seconds >= self.scanner_interval):
                    self.check_opportunity_scanner()
                    self.last_scanner_check = now
                
                # 📈 EXPLOITATION: FTD Analyzer (hourly during RTH)
                if is_market_hours and self.ftd_enabled and (self.last_ftd_check is None or (now - self.last_ftd_check).seconds >= self.ftd_interval):
                    self.check_ftd_analyzer()
                    self.last_ftd_check = now
                
                # 🚨 MOMENTUM: Selloff/Rally Detection (every minute during RTH)
                if is_market_hours and (self.last_dp_check is None or (now - self.last_dp_check).seconds >= 60):
                    self._check_selloffs()
                    self._check_rallies()
                
                # Tradytics analysis
                if self.tradytics_llm_available and (self.last_tradytics_analysis is None or (now - self.last_tradytics_analysis).seconds >= self.tradytics_analysis_interval):
                    self.autonomous_tradytics_analysis()
                    self.last_tradytics_analysis = now
                
                # Narrative Brain scheduled updates
                if self.narrative_enabled and self.narrative_scheduler:
                    self.narrative_scheduler.check_and_run_scheduled_updates()
                    if self.narrative_scheduler.can_run_intra_day_update():
                        intelligence_data = self._get_current_intelligence_snapshot()
                        update = self.narrative_brain.process_intelligence_update("intelligence_snapshot", intelligence_data)
                        if update:
                            self.narrative_scheduler.mark_intra_day_update_sent()
                            logger.info(f"🧠 Narrative update sent: {update.alert_type.value}")
                
                # 📊 DAILY RECAP: Send at market close (4:00-4:05 PM ET)
                if self._should_send_daily_recap(now):
                    self._send_daily_recap()
                
                time.sleep(30)
                
            except KeyboardInterrupt:
                logger.info("\n🛑 Monitor stopped by user")
                break
            except Exception as e:
                logger.error(f"❌ Main loop error: {e}")
                time.sleep(60)

