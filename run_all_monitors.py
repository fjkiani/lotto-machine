#!/usr/bin/env python3
"""
🎯 ALPHA INTELLIGENCE - UNIFIED MONITOR (MODULAR VERSION)

Runs ALL monitoring systems in parallel using modular components:
1. 🏦 Fed Watch - Rate cut/hike probabilities + Fed official comments
2. 🎯 Trump Intelligence - Trump statements + market exploitation
3. 📊 Economic Learning - LEARNED patterns predict Fed Watch moves
4. 🚨 Proactive Alerts - Pre-event positioning alerts

This is the MASTER DEPLOYMENT script for 24/7 monitoring.

MODULAR ARCHITECTURE:
- AlertManager: Handles all Discord alerting
- RegimeDetector: Multi-factor market regime detection
- MomentumDetector: Selloff/rally detection
- MonitorInitializer: Component initialization
- UnifiedAlphaMonitor: Main orchestrator (uses all modules)

Usage:
    python3 run_all_monitors.py

Environment Variables Required:
    PERPLEXITY_API_KEY: For news fetching
    DISCORD_WEBHOOK_URL: For alerts
    CHARTEXCHANGE_API_KEY: For dark pool data
"""

import os
import sys
import time
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add paths
base_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_path)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# IMPORT MODULAR VERSION
# ═══════════════════════════════════════════════════════════════
try:
    from live_monitoring.orchestrator.unified_monitor import UnifiedAlphaMonitor
    logger.info("✅ Using MODULAR UnifiedAlphaMonitor")
except ImportError as e:
    logger.error(f"❌ Failed to import modular UnifiedAlphaMonitor: {e}")
    logger.error("   Make sure live_monitoring/orchestrator/unified_monitor.py exists")
    raise


# ═══════════════════════════════════════════════════════════════
# IMPORT MODULAR VERSION
# ═══════════════════════════════════════════════════════════════
try:
    from live_monitoring.orchestrator.unified_monitor import UnifiedAlphaMonitor
    logger.info("   ✅ Using MODULAR UnifiedAlphaMonitor from live_monitoring.orchestrator")
except ImportError as e:
    logger.error(f"   ❌ Failed to import modular UnifiedAlphaMonitor: {e}")
    logger.error("   Falling back to legacy implementation...")
    raise  # For now, require modular version

# ═══════════════════════════════════════════════════════════════
# LEGACY IMPLEMENTATION (kept for reference, but not used)
# ═══════════════════════════════════════════════════════════════
# The original 2546-line implementation is now in:
# live_monitoring/orchestrator/unified_monitor.py (modular version)
# 
# If you need the legacy version, it's still in git history.
# ═══════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════
# LEGACY CLASS COMMENTED OUT - Using modular version instead
# ═══════════════════════════════════════════════════════════════
# The original 2546-line implementation has been modularized into:
# - live_monitoring/orchestrator/unified_monitor.py (main class)
# - live_monitoring/orchestrator/alert_manager.py
# - live_monitoring/orchestrator/regime_detector.py
# - live_monitoring/orchestrator/momentum_detector.py
# - live_monitoring/orchestrator/monitor_initializer.py
#
# If you need the legacy version, check git history.
# ═══════════════════════════════════════════════════════════════

class _LegacyUnifiedAlphaMonitor_DEPRECATED:
    """
    Master orchestrator for all monitoring systems.
    """
    
    def __init__(self):
        self.discord_webhook = os.getenv('DISCORD_WEBHOOK_URL')
        self.running = True
        
        # Intervals (in seconds)
        self.fed_interval = 300      # 5 minutes for Fed
        self.trump_interval = 180    # 3 minutes for Trump
        self.news_interval = 300     # 5 minutes for news
        self.econ_interval = 3600    # 1 hour for economic calendar check
        self.dp_interval = 60        # 1 minute for dark pool (need real-time!)
        
        # Track last run times
        self.last_fed_check = None
        self.last_trump_check = None
        self.last_news_check = None
        self.last_econ_check = None
        self.last_dp_check = None
        self.last_tradytics_analysis = None
        
        # Dark Pool tracking
        self.dp_battlegrounds = {}  # symbol -> list of levels
        self.dp_alerted_levels = set()  # Avoid duplicate alerts
        self.symbols = ['SPY', 'QQQ']  # Symbols to monitor
        
        # Alerted events (avoid duplicate alerts)
        self.alerted_events = set()
        self.seen_fed_comments = set()  # Track sent Fed comments
        self.unified_mode = False  # Will be enabled if Signal Brain is active
        
        # Global alert deduplication (prevents spam)
        self.sent_alerts = {}  # alert_hash -> timestamp
        self.alert_cooldown_seconds = 300  # 5 minutes cooldown between identical alerts
        
        # Import monitors
        self._init_monitors()
        
        logger.info("=" * 70)
        logger.info("🎯 ALPHA INTELLIGENCE - UNIFIED MONITOR STARTED")
        logger.info("   🧠 WITH ECONOMIC LEARNING ENGINE")
        logger.info("   🔒 WITH DARK POOL INTELLIGENCE")
        logger.info("=" * 70)
        logger.info(f"   Discord: {'✅' if self.discord_webhook else '❌'}")
        logger.info(f"   Fed Watch: Every {self.fed_interval/60:.0f} min")
        logger.info(f"   Trump Intel: Every {self.trump_interval/60:.0f} min")
        logger.info(f"   Economic AI: Every {self.econ_interval/60:.0f} min")
        logger.info(f"   Dark Pool: Every {self.dp_interval} sec (real-time)")
        logger.info(f"   Symbols: {', '.join(self.symbols)}")
        logger.info("=" * 70)
    
    def _init_monitors(self):
        """Initialize all monitor components."""
        
        # Fed Watch Monitor
        try:
            from live_monitoring.agents.fed_watch_monitor import FedWatchMonitor
            from live_monitoring.agents.fed_officials_monitor import FedOfficialsMonitor
            self.fed_watch = FedWatchMonitor(alert_threshold=5.0)
            self.fed_officials = FedOfficialsMonitor()
            self.fed_enabled = True
            logger.info("   ✅ Fed monitors initialized")
        except Exception as e:
            logger.warning(f"   ⚠️ Fed monitors failed: {e}")
            self.fed_enabled = False
        
        # Trump Intelligence
        try:
            from live_monitoring.agents.trump_pulse import TrumpPulse
            from live_monitoring.agents.trump_news_monitor import TrumpNewsMonitor
            self.trump_pulse = TrumpPulse()
            self.trump_news = TrumpNewsMonitor()
            self.trump_enabled = True
            logger.info("   ✅ Trump monitors initialized")
        except Exception as e:
            logger.warning(f"   ⚠️ Trump monitors failed: {e}")
            self.trump_enabled = False
        
        # Dark Pool Intelligence
        try:
            api_key = os.getenv('CHARTEXCHANGE_API_KEY')
            if api_key:
                from core.ultra_institutional_engine import UltraInstitutionalEngine
                from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
                self.dp_client = UltimateChartExchangeClient(api_key)
                self.dp_engine = UltraInstitutionalEngine(api_key)
                self.dp_enabled = True
                logger.info("   ✅ Dark Pool monitors initialized")
            else:
                logger.warning("   ⚠️ CHARTEXCHANGE_API_KEY not set - DP disabled")
                self.dp_enabled = False
        except Exception as e:
            logger.warning(f"   ⚠️ Dark Pool monitors failed: {e}")
            self.dp_enabled = False
        
        # Dark Pool LEARNING Engine
        try:
            from live_monitoring.agents.dp_learning import DPLearningEngine
            self.dp_learning = DPLearningEngine(
                on_outcome=self._on_dp_outcome,
                on_prediction=None  # We'll handle predictions inline
            )
            self.dp_learning.start()
            self.dp_learning_enabled = True
            logger.info("   ✅ Dark Pool Learning Engine initialized")
        except Exception as e:
            logger.warning(f"   ⚠️ DP Learning Engine failed: {e}")
            self.dp_learning_enabled = False
            self.dp_learning = None
        
        # Dark Pool MONITOR Engine (NEW MODULAR!)
        try:
            from live_monitoring.agents.dp_monitor import DPMonitorEngine
            self.dp_monitor_engine = DPMonitorEngine(
                api_key=os.getenv('CHARTEXCHANGE_API_KEY'),
                dp_client=self.dp_client if self.dp_enabled else None,  # Reuse existing client
                learning_engine=self.dp_learning if self.dp_learning_enabled else None,
                debounce_minutes=30  # Only alert once per level per 30 min
            )
            logger.info("   ✅ Dark Pool Monitor Engine (modular) initialized")
        except Exception as e:
            logger.warning(f"   ⚠️ DP Monitor Engine failed: {e}")
            self.dp_monitor_engine = None
        
        # Signal Synthesis BRAIN (NEW!) - NOW WITH DP LEARNING + NARRATIVE!
        try:
            from live_monitoring.agents.signal_brain import SignalBrainEngine
            from live_monitoring.agents.signal_brain.narrative import NarrativeEnricher
            from live_monitoring.agents.signal_brain.macro import MacroContextProvider
            
            # Initialize Narrative Enricher
            narrative_enricher = None
            try:
                narrative_enricher = NarrativeEnricher()
                logger.info("   📰 Narrative Enricher initialized")
            except Exception as ne:
                logger.warning(f"   ⚠️ Narrative Enricher failed: {ne}")
            
            # Initialize MacroContextProvider - REAL DATA, NO HARDCODING!
            self.macro_provider = None
            try:
                self.macro_provider = MacroContextProvider(
                    fed_watch=self.fed_watch if self.fed_enabled else None,
                    fed_officials=self.fed_officials if self.fed_enabled else None,
                    economic_engine=self.econ_engine if self.econ_enabled else None,
                    economic_calendar=self.econ_calendar if self.econ_enabled else None,
                    trump_monitor=self.trump_pulse if self.trump_enabled else None,
                )
                logger.info("   📊 MacroContextProvider initialized (REAL DATA!)")
            except Exception as me:
                logger.warning(f"   ⚠️ MacroContextProvider failed: {me}")
            
            # Pass DP Learning Engine + Narrative to Signal Brain
            self.signal_brain = SignalBrainEngine(
                dp_learning_engine=self.dp_learning if self.dp_learning_enabled else None,
                narrative_enricher=narrative_enricher
            )
            self.brain_enabled = True
            self.last_synthesis_check = None
            self.synthesis_interval = 60  # 1 minute - faster synthesis for unified alerts
            self.recent_dp_alerts = []  # Buffer for Signal Brain synthesis
            self.unified_mode = True  # Suppress individual alerts, only send synthesis
            logger.info("   ✅ Signal Synthesis Brain initialized (THINKING LAYER)")
            logger.info(f"   🔇 UNIFIED MODE: ENABLED - Individual alerts suppressed, only synthesis will be sent")

            # 🧠 NARRATIVE BRAIN (NEW!) - CONTEXTUAL STORYTELLING
            try:
                from live_monitoring.agents.narrative_brain import NarrativeBrain
                from live_monitoring.agents.narrative_brain.schedule_manager import NarrativeScheduler

                self.narrative_brain = NarrativeBrain()
                self.narrative_scheduler = NarrativeScheduler(self.narrative_brain)
                self.narrative_enabled = True
                logger.info("   🧠 Narrative Brain initialized (CONTEXTUAL STORYTELLING)")
                logger.info("   📚 Memory system active - AI learns from previous analyses")
            except Exception as ne:
                logger.warning(f"   ⚠️ Narrative Brain failed: {ne}")
                self.narrative_brain = None
                self.narrative_scheduler = None
                self.narrative_enabled = False
            if self.dp_learning_enabled:
                logger.info("   🧠 Brain integrated with DP Learning Engine!")
            if narrative_enricher:
                logger.info("   📰 Brain integrated with Narrative Engine!")
            if self.macro_provider:
                logger.info("   📊 Brain uses REAL macro data (no hardcoding)!")
        except Exception as e:
            logger.warning(f"   ⚠️ Signal Brain failed: {e}")
            self.signal_brain = None
            self.brain_enabled = False
            self.macro_provider = None
            self.unified_mode = False  # Disable unified mode if brain fails
        
        # Economic Learning Engine (NEW MODULAR VERSION)
        try:
            from live_monitoring.agents.economic import EconomicIntelligenceEngine
            from live_monitoring.agents.economic.calendar import EconomicCalendar, Importance
            from live_monitoring.agents.economic.models import EconomicRelease, EventType
            
            self.econ_engine = EconomicIntelligenceEngine()
            
            # Try EventLoader first (REAL API), fallback to hard-coded EconomicCalendar
            try:
                from live_monitoring.enrichment.apis.event_loader import EventLoader
                self.econ_calendar = EventLoader()
                self.econ_calendar_type = "api"  # Track which we're using
                logger.info("   ✅ Economic Calendar: REAL API (EventLoader - Baby-Pips)")
            except Exception as e:
                logger.warning(f"   ⚠️ EventLoader failed, using static calendar: {e}")
                self.econ_calendar = EconomicCalendar()
                self.econ_calendar_type = "static"
                logger.info("   ⚠️ Economic Calendar: STATIC (fallback - hard-coded)")
            
            # Seed with sample historical data
            historical = [
                EconomicRelease(
                    date="2024-12-06", time="08:30", event_type=EventType.NFP,
                    event_name="Nonfarm Payrolls", actual=227, forecast=200, previous=36,
                    surprise_pct=13.5, surprise_sigma=1.35,
                    fed_watch_before=66, fed_watch_after_1hr=74, fed_watch_shift_1hr=8,
                    days_to_fomc=12
                ),
                EconomicRelease(
                    date="2024-11-01", time="08:30", event_type=EventType.NFP,
                    event_name="Nonfarm Payrolls", actual=12, forecast=100, previous=254,
                    surprise_pct=-88, surprise_sigma=-2.2,
                    fed_watch_before=70, fed_watch_after_1hr=82, fed_watch_shift_1hr=12,
                    days_to_fomc=6
                ),
                EconomicRelease(
                    date="2024-10-04", time="08:30", event_type=EventType.NFP,
                    event_name="Nonfarm Payrolls", actual=254, forecast=140, previous=159,
                    surprise_pct=81, surprise_sigma=2.5,
                    fed_watch_before=95, fed_watch_after_1hr=85, fed_watch_shift_1hr=-10,
                    days_to_fomc=33
                ),
                EconomicRelease(
                    date="2024-09-06", time="08:30", event_type=EventType.NFP,
                    event_name="Nonfarm Payrolls", actual=142, forecast=160, previous=89,
                    surprise_pct=-11, surprise_sigma=-0.9,
                    fed_watch_before=60, fed_watch_after_1hr=70, fed_watch_shift_1hr=10,
                    days_to_fomc=12
                ),
                EconomicRelease(
                    date="2024-08-02", time="08:30", event_type=EventType.NFP,
                    event_name="Nonfarm Payrolls", actual=114, forecast=175, previous=179,
                    surprise_pct=-35, surprise_sigma=-1.8,
                    fed_watch_before=75, fed_watch_after_1hr=90, fed_watch_shift_1hr=15,
                    days_to_fomc=46
                ),
            ]
            self.econ_engine.add_historical_data(historical)
            
            self.econ_enabled = True
            logger.info("   ✅ Economic Intelligence Engine initialized")
            logger.info("   ✅ Economic Calendar initialized")
        except Exception as e:
            logger.warning(f"   ⚠️ Economic engine failed: {e}")
            self.econ_enabled = False
            self.econ_calendar = None
            self.econ_calendar_type = None
        
        # Autonomous Tradytics Analysis
        try:
            from src.data.llm_api import query_llm
            self.tradytics_llm_available = True
            logger.info("   ✅ Tradytics LLM analysis available")
        except Exception as e:
            logger.warning(f"   ⚠️ Tradytics LLM analysis unavailable: {e}")
            self.tradytics_llm_available = False

        # Tradytics analysis state
        self.last_tradytics_analysis = None
        self.tradytics_analysis_interval = 300  # 5 minutes
        self.tradytics_alerts_processed = 0

        # Track previous states
        self.prev_fed_status = None
        self.prev_trump_sentiment = None
        self.seen_trump_news = set()
        
        # Deduplication tracking
        self.startup_alert_sent = False  # Only send startup alert once
        self.last_synthesis_hash = None  # Track last synthesis to avoid duplicates
        self.sent_synthesis_hashes = set()  # Track all sent synthesis (keep last 10)
        self.seen_tradytics_alerts = set()  # Track processed Tradytics alerts
        
        # Alert logging database
        self.alert_db_path = "data/alerts_history.db"
        self._init_alert_database()
    
    def _init_alert_database(self):
        """Initialize database for storing all alerts."""
        try:
            import sqlite3
            import os
            
            # Ensure data directory exists
            os.makedirs(os.path.dirname(self.alert_db_path), exist_ok=True)
            
            conn = sqlite3.connect(self.alert_db_path)
            cursor = conn.cursor()
            
            # Create alerts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    title TEXT,
                    description TEXT,
                    content TEXT,
                    embed_json TEXT,
                    source TEXT,
                    symbol TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index for queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON alerts(timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_alert_type ON alerts(alert_type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol ON alerts(symbol)
            """)
            
            conn.commit()
            conn.close()
            logger.info(f"   ✅ Alert database initialized: {self.alert_db_path}")
        except Exception as e:
            logger.warning(f"   ⚠️ Failed to initialize alert database: {e}")
    
    def _log_alert_to_database(self, alert_type: str, embed: dict, content: str = None, source: str = "monitor", symbol: str = None):
        """Log alert to database for historical tracking."""
        try:
            import sqlite3
            import json
            
            conn = sqlite3.connect(self.alert_db_path)
            cursor = conn.cursor()
            
            timestamp = datetime.utcnow().isoformat()
            title = embed.get('title', '')
            description = embed.get('description', '')
            embed_json = json.dumps(embed)
            
            cursor.execute("""
                INSERT INTO alerts (timestamp, alert_type, title, description, content, embed_json, source, symbol)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (timestamp, alert_type, title, description, content, embed_json, source, symbol))
            
            conn.commit()
            conn.close()
            logger.debug(f"   📝 Alert logged to database: {alert_type}")
        except Exception as e:
            logger.debug(f"   ⚠️ Failed to log alert to database: {e}")
    
    def send_discord(self, embed: dict, content: str = None, alert_type: str = "general", source: str = "monitor", symbol: str = None) -> bool:
        """Send Discord notification and log to database with deduplication."""
        # Generate unique hash for this alert
        alert_hash = self._generate_alert_hash(embed, content, alert_type, source, symbol)
        
        # Check if we've sent this alert recently
        if alert_hash in self.sent_alerts:
            last_sent = self.sent_alerts[alert_hash]
            elapsed = time.time() - last_sent
            if elapsed < self.alert_cooldown_seconds:
                logger.debug(f"   ⏭️ Alert duplicate (sent {elapsed:.0f}s ago) - skipping: {alert_type} {symbol or ''}")
                # Still log to database for tracking
                self._log_alert_to_database(alert_type, embed, content, source, symbol)
                return False
        
        # Mark as sent
        self.sent_alerts[alert_hash] = time.time()
        
        # Cleanup old entries (keep last 100, remove entries older than 1 hour)
        if len(self.sent_alerts) > 100:
            cutoff = time.time() - 3600
            self.sent_alerts = {k: v for k, v in self.sent_alerts.items() if v > cutoff}
        
        # ALWAYS log to database FIRST (for memory/recall) - regardless of Discord status
        # This ensures we have complete history even if Discord fails
        self._log_alert_to_database(alert_type, embed, content, source, symbol)
        
        if not self.discord_webhook:
            logger.warning("   ⚠️ DISCORD_WEBHOOK_URL not set! (Alert logged to database)")
            return False
        
        try:
            payload = {"embeds": [embed]}
            if content:
                payload["content"] = content
            
            response = requests.post(self.discord_webhook, json=payload, timeout=10)
            
            if response.status_code in [200, 204]:
                logger.debug(f"   ✅ Discord sent successfully (status: {response.status_code})")
                return True
            else:
                logger.error(f"   ❌ Discord returned status {response.status_code}: {response.text[:200]} (Alert logged to database)")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"   ❌ Discord request error: {e} (Alert logged to database)")
            return False
        except Exception as e:
            logger.error(f"   ❌ Discord error: {e} (Alert logged to database)")
            import traceback
            logger.debug(traceback.format_exc())
            return False
    
    def _generate_alert_hash(self, embed: dict, content: str, alert_type: str, source: str, symbol: str) -> str:
        """Generate unique hash for alert deduplication."""
        import hashlib
        import re
        
        # Extract key identifying information
        title = embed.get('title', '')
        description = embed.get('description', '')
        
        # Create hash from key fields
        key_data = f"{alert_type}:{symbol or ''}:{source}:{title}"
        
        # Extract key numbers from title/description (confluence %, prices, etc.)
        text = f"{title} {description} {content or ''}"
        numbers = re.findall(r'\d+\.?\d*', text)
        if numbers:
            key_data += f":{':'.join(numbers[:3])}"  # First 3 numbers
        
        # Add embed fields that uniquely identify the alert
        if 'fields' in embed:
            for field in embed.get('fields', [])[:4]:  # First 4 fields
                field_name = field.get('name', '')
                field_value = str(field.get('value', ''))
                # Extract key numbers from field values
                numbers = re.findall(r'\d+\.?\d*', field_value)
                if numbers:
                    key_data += f":{field_name}:{':'.join(numbers[:2])}"
                else:
                    key_data += f":{field_name}:{field_value[:30]}"  # Truncate
        
        # Hash it
        return hashlib.md5(key_data.encode()).hexdigest()[:16]
    
    def check_fed(self):
        """Check Fed Watch and officials."""
        if not self.fed_enabled:
            return
        
        logger.info("🏦 Checking Fed Watch...")
        
        try:
            # Get current status
            status = self.fed_watch.get_current_status(force_refresh=True)
            
            # Check for significant changes
            if self.prev_fed_status:
                cut_change = abs(status.prob_cut - self.prev_fed_status.prob_cut)
                hold_change = abs(status.prob_hold - self.prev_fed_status.prob_hold)
                
                # Only alert on SIGNIFICANT changes (10% threshold, not 5%)
                # In unified mode, suppress unless it's a MAJOR shift (15%+)
                threshold = 15.0 if self.unified_mode else 10.0
                
                if cut_change >= threshold or hold_change >= threshold:
                    logger.info(f"   🚨 MAJOR CHANGE! Cut: {status.prob_cut:.1f}% ({cut_change:+.1f}%)")
                    
                    # Send alert (always send major Fed Watch changes - they're critical)
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
                elif cut_change >= 5.0 or hold_change >= 5.0:
                    logger.info(f"   📊 Moderate change: Cut: {status.prob_cut:.1f}% ({cut_change:+.1f}%) - buffered for synthesis")
            
            self.prev_fed_status = status
            logger.info(f"   Cut: {status.prob_cut:.1f}% | Hold: {status.prob_hold:.1f}% | Most Likely: {status.most_likely_outcome}")
            
            # Check Fed officials
            logger.info("   🎤 Checking Fed officials...")
            report = self.fed_officials.get_report()
            
            if report.comments:
                import hashlib
                for comment in report.comments[:3]:
                    # Create unique ID from hash of full content + official name
                    content_hash = hashlib.md5(
                        f"{comment.official.name}:{comment.content}".encode()
                    ).hexdigest()[:12]
                    comment_id = f"{comment.official.name}:{content_hash}"
                    
                    # Only alert if we haven't seen this exact comment before
                    if comment_id not in self.seen_fed_comments:
                        self.seen_fed_comments.add(comment_id)
                        
                        # Keep set size manageable (last 100 comments)
                        if len(self.seen_fed_comments) > 100:
                            # Remove oldest (convert to list, remove first, convert back)
                            self.seen_fed_comments = set(list(self.seen_fed_comments)[-100:])
                        
                        # In unified mode, suppress individual alerts (Signal Brain will synthesize)
                        # Only send CRITICAL alerts (Powell with high confidence)
                        is_critical = comment.official.name == "Jerome Powell" and comment.confidence >= 0.8
                        should_alert = comment.official.name == "Jerome Powell" or comment.confidence >= 0.5
                        
                        if should_alert and (not self.unified_mode or is_critical):
                            # Alert on significant Fed comments
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
                        elif should_alert:
                            logger.debug(f"   📊 Fed comment buffered for synthesis: {comment.official.name} - {comment.sentiment}")
            
        except Exception as e:
            logger.error(f"   ❌ Fed check error: {e}")
    
    def check_trump(self):
        """Check Trump intelligence."""
        if not self.trump_enabled:
            return
        
        logger.info("🎯 Checking Trump Intelligence...")
        
        try:
            # Get current pulse
            situation = self.trump_pulse.get_current_situation()
            
            # Check for exploitable news
            exploitable = self.trump_news.get_exploitable_news()
            
            # Initialize topic tracker if not exists
            if not hasattr(self, 'trump_topic_tracker'):
                self.trump_topic_tracker = {}  # topic -> last_alert_time
                self.trump_cooldown_minutes = 60  # Only alert on same topic once per hour
            
            for exp in exploitable[:3]:
                # Extract key topics from headline for better deduplication
                headline_lower = exp.news.headline.lower()
                
                # Identify major topics
                topics = []
                if 'farm' in headline_lower or 'farmer' in headline_lower or 'agriculture' in headline_lower:
                    topics.append('farm_aid')
                if 'tariff' in headline_lower or 'trade war' in headline_lower or 'china' in headline_lower:
                    topics.append('trade_war')
                if 'ai' in headline_lower or 'artificial intelligence' in headline_lower:
                    topics.append('ai_regulation')
                if 'ukraine' in headline_lower or 'zelensk' in headline_lower:
                    topics.append('ukraine')
                if 'trade deal' in headline_lower or 'britain' in headline_lower or 'uk' in headline_lower:
                    topics.append('uk_trade')
                
                # If no specific topic detected, use first 3 significant words
                if not topics:
                    import re
                    words = re.findall(r'\b[a-z]{4,}\b', headline_lower)
                    topics = ['_'.join(words[:3])] if words else ['unknown']
                
                # Check if we've alerted on this topic recently
                now = datetime.now()
                topic_key = topics[0] if topics else 'unknown'
                
                last_alert_time = self.trump_topic_tracker.get(topic_key)
                if last_alert_time:
                    minutes_since = (now - last_alert_time).total_seconds() / 60
                    if minutes_since < self.trump_cooldown_minutes:
                        logger.debug(f"   📊 Trump topic '{topic_key}' on cooldown ({minutes_since:.0f}m < {self.trump_cooldown_minutes}m) - skipping")
                        continue
                
                # Update tracker
                self.trump_topic_tracker[topic_key] = now
                
                # Only alert if score >= 60
                if exp.exploit_score < 60:
                    continue
                
                # In unified mode, suppress individual alerts (Signal Brain will synthesize)
                # Only send CRITICAL alerts (score >= 90)
                is_critical = exp.exploit_score >= 90
                
                if not self.unified_mode or is_critical:
                    # Send alert
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
                    logger.info(f"   ✅ Trump alert sent: {topic_key} (Score: {exp.exploit_score:.0f})")
                else:
                    logger.debug(f"   📊 Trump exploit buffered for synthesis: {exp.suggested_action} (Score: {exp.exploit_score:.0f})")
            
            activity = getattr(situation, 'activity_level', 'N/A')
            sentiment = getattr(situation, 'overall_sentiment', 'UNKNOWN')
            logger.info(f"   Sentiment: {sentiment} | Exploits: {len(exploitable)}")
            
        except Exception as e:
            logger.error(f"   ❌ Trump check error: {e}")
    
    def check_economics(self):
        """
        Check for upcoming economic events and generate PROACTIVE alerts.
        
        Uses the MODULAR Economic Intelligence Engine with proper calendar!
        """
        if not self.econ_enabled:
            logger.warning("   ⚠️ Economic engine disabled")
            return
        
        if not self.econ_calendar:
            logger.warning("   ⚠️ Economic calendar not initialized")
            return
        
        logger.info("📊 Checking Economic Calendar...")
        
        try:
            from live_monitoring.agents.economic.calendar import Importance
            from datetime import datetime, timedelta
            
            # Get current Fed Watch for context
            current_cut_prob = 89.0
            if self.prev_fed_status:
                current_cut_prob = self.prev_fed_status.prob_cut
            
            # Use EventLoader API if available, else fallback to static calendar
            if self.econ_calendar_type == "api":
                # EventLoader returns dict with "macro_events"
                today = datetime.now().strftime('%Y-%m-%d')
                tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
                
                # Get today's events
                today_data = self.econ_calendar.load_events(date=today, min_impact="medium")
                today_events = today_data.get('macro_events', [])
                
                # Get tomorrow's events
                tomorrow_data = self.econ_calendar.load_events(date=tomorrow, min_impact="medium")
                tomorrow_events = tomorrow_data.get('macro_events', [])
                
                all_events = today_events + tomorrow_events
                
                logger.info(f"   📅 Found {len(today_events)} events today (API)")
                logger.info(f"   📅 Found {len(tomorrow_events)} events tomorrow (API)")
                
                # Convert EventLoader format to CalendarEvent-like format for processing
                upcoming = []
                for event_dict in all_events:
                    # Create a simple object that mimics CalendarEvent interface
                    class EventWrapper:
                        def __init__(self, data):
                            from live_monitoring.agents.economic.calendar import EventCategory
                            self.name = data.get('name', 'Unknown')
                            self.date = data.get('date', today)
                            self.time = data.get('time', '08:30')
                            self.importance = Importance.HIGH if data.get('impact', '').lower() == 'high' else Importance.MEDIUM
                            # Infer category from event name
                            name_lower = self.name.lower()
                            if any(x in name_lower for x in ['payroll', 'employment', 'unemployment', 'jobless', 'adp']):
                                self.category = EventCategory.EMPLOYMENT
                            elif any(x in name_lower for x in ['cpi', 'ppi', 'pce', 'inflation']):
                                self.category = EventCategory.INFLATION
                            elif any(x in name_lower for x in ['gdp', 'growth']):
                                self.category = EventCategory.GROWTH
                            elif any(x in name_lower for x in ['retail', 'sales', 'consumer']):
                                self.category = EventCategory.CONSUMER
                            elif any(x in name_lower for x in ['fed', 'fomc', 'federal']):
                                self.category = EventCategory.FED
                            else:
                                self.category = EventCategory.OTHER
                            self.typical_surprise_impact = 3.0  # Default
                            self.release_frequency = "monthly"  # Default
                            
                        def hours_until(self):
                            try:
                                event_dt = datetime.strptime(f"{self.date} {self.time}", "%Y-%m-%d %H:%M")
                                return (event_dt - datetime.now()).total_seconds() / 3600
                            except:
                                return -1
                    
                    upcoming.append(EventWrapper(event_dict))
            else:
                # Fallback to static EconomicCalendar
                # Get upcoming HIGH importance events (next 2 days)
                upcoming = self.econ_calendar.get_upcoming_events(days=2, min_importance=Importance.HIGH)
                
                logger.info(f"   📅 Found {len(upcoming)} HIGH importance events in next 48h (static calendar)")
                
                # Also check MEDIUM for events happening soon
                medium_upcoming = self.econ_calendar.get_upcoming_events(days=2, min_importance=Importance.MEDIUM)
                logger.info(f"   📅 Found {len(medium_upcoming)} MEDIUM importance events in next 48h (static calendar)")
                upcoming.extend(medium_upcoming)
            
            for event in upcoming:
                event_id = f"{event.date}:{event.name}"
                hours = event.hours_until()
                
                logger.info(f"   📊 Event: {event.name} on {event.date} {event.time} | {hours:.1f}h away | Importance: {event.importance.value}")
                
                # Skip if already alerted or past
                if event_id in self.alerted_events:
                    logger.info(f"      ⏭️  Already alerted, skipping")
                    continue
                
                if hours < 0:
                    logger.info(f"      ⏭️  Event passed, skipping")
                    continue
                
                # Alert conditions:
                # - 24h before HIGH event
                # - 4h before ANY event
                should_alert = (hours < 24 and event.importance == Importance.HIGH) or hours < 4
                
                logger.info(f"      🎯 Should alert: {should_alert} (hours={hours:.1f}, importance={event.importance.value})")
                
                if not should_alert:
                    continue
                
                self.alerted_events.add(event_id)
                
                # Get prediction scenarios
                try:
                    alert = self.econ_engine.get_pre_event_alert(
                        event_type=event.name.lower().replace(' ', '_'),
                        event_date=event.date,
                        event_time=event.time,
                        current_fed_watch=current_cut_prob
                    )
                    
                    # Extract scenario data
                    weak_shift = alert.weak_scenario.predicted_fed_watch_shift
                    strong_shift = alert.strong_scenario.predicted_fed_watch_shift
                    weak_fw = alert.weak_scenario.predicted_fed_watch
                    strong_fw = alert.strong_scenario.predicted_fed_watch
                    swing = abs(weak_shift - strong_shift)
                    
                except Exception as e:
                    logger.debug(f"Prediction error: {e}")
                    # Use static estimate from calendar
                    swing = event.typical_surprise_impact * 2
                    weak_shift = event.typical_surprise_impact
                    strong_shift = -event.typical_surprise_impact
                    weak_fw = current_cut_prob + weak_shift
                    strong_fw = current_cut_prob + strong_shift
                
                # Send Discord alert
                imp_emoji = "🔴" if event.importance == Importance.HIGH else "🟡"
                
                embed = {
                    "title": f"{imp_emoji} ECONOMIC ALERT: {event.name}",
                    "color": 15548997 if event.importance == Importance.HIGH else 16776960,
                    "description": f"⏰ In **{hours:.0f} hours** | Potential **±{swing:.1f}%** Fed Watch swing!",
                    "fields": [
                        {"name": "📅 When", "value": f"{event.date} {event.time} ET", "inline": True},
                        {"name": "📊 Current Cut %", "value": f"{current_cut_prob:.1f}%", "inline": True},
                        {"name": "🎯 Category", "value": event.category.value.upper(), "inline": True},
                        {"name": "📉 If WEAK Data", "value": f"Fed Watch → **{weak_fw:.0f}%** ({weak_shift:+.1f}%)\n→ BUY SPY, TLT", "inline": True},
                        {"name": "📈 If STRONG Data", "value": f"Fed Watch → **{strong_fw:.0f}%** ({strong_shift:+.1f}%)\n→ Reduce exposure", "inline": True},
                    ],
                    "footer": {"text": f"Economic Intelligence Engine | {event.release_frequency.upper()} release"},
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                content = f"⚠️ **{event.name}** in {hours:.0f}h! Potential {swing:.1f}% Fed Watch swing!"
                
                logger.info(f"   📤 Sending Discord alert for {event.name}...")
                success = self.send_discord(embed, content=content, alert_type="economic_event", source="economic_monitor")
                
                if success:
                    logger.info(f"   ✅ ALERT SENT: {event.name} in {hours:.0f}h | ±{swing:.1f}% swing")
                else:
                    logger.error(f"   ❌ FAILED to send Discord alert for {event.name}")
            
            # Log today's summary
            if self.econ_calendar_type == "api":
                today_data = self.econ_calendar.load_events(date=datetime.now().strftime('%Y-%m-%d'), min_impact="medium")
                today_events = today_data.get('macro_events', [])
                if today_events:
                    event_names = [e.get('name', 'Unknown') for e in today_events]
                    logger.info(f"   📅 Today: {', '.join(event_names)}")
                else:
                    logger.info(f"   📅 No events today (API)")
            else:
                today_events = self.econ_calendar.get_today_events()
                if today_events:
                    logger.info(f"   📅 Today: {', '.join([e.name for e in today_events])}")
                else:
                    logger.info(f"   📅 No events today (static calendar)")
            
        except Exception as e:
            logger.error(f"   ❌ Economic check error: {e}")

    def autonomous_tradytics_analysis(self):
        """Autonomous Tradytics analysis - simulates analyzing bot alerts"""
        if not self.tradytics_llm_available:
            return

        try:
            logger.info("🤖 Running Autonomous Tradytics Analysis...")

            # Generate sample Tradytics-style alerts for demonstration
            # In production, this would connect to actual Tradytics webhooks or APIs
            sample_alerts = self._generate_sample_tradytics_alerts()

            for alert in sample_alerts:
                # Deduplicate alerts using hash of content
                import hashlib
                alert_hash = hashlib.md5(f"{alert['content']}:{alert['bot_name']}".encode()).hexdigest()[:12]
                if alert_hash in self.seen_tradytics_alerts:
                    logger.debug(f"   📊 Tradytics alert duplicate (hash: {alert_hash[:8]}) - skipping")
                    continue
                
                self.seen_tradytics_alerts.add(alert_hash)
                # Keep set size manageable (last 50)
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
        # DISABLED: Sample alerts were causing spam with "Analysis failed" messages
        # In production, this would connect to actual Tradytics webhooks or APIs
        # For now, return empty list - only process REAL alerts from webhooks
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

            # Use the available query_llm function with savage prompt
            try:
                from src.data.llm_api import query_llm
                response = query_llm(savage_prompt, provider="gemini")
            except ImportError:
                logger.warning("   ⚠️ query_llm not available - skipping analysis")
                return f"Analysis unavailable: query_llm not found"
            except NameError:
                logger.warning("   ⚠️ query_llm not available - skipping analysis")
                return f"Analysis unavailable: query_llm not found"

            # Extract the analysis from the response
            if isinstance(response, dict):
                # Try different possible response keys
                analysis = (response.get('detailed_analysis') or
                           response.get('market_sentiment') or
                           str(response))

                # Clean up the response
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

            # Extract alert information from webhook
            # Expected format: Discord webhook payload with message content
            if 'content' in webhook_data:
                message_content = webhook_data['content']
                author = webhook_data.get('author', {}).get('username', 'Unknown')

                # Check if this looks like a Tradytics alert
                tradytics_keywords = ['SWEEP', 'BLOCK', 'CALL', 'PUT', 'PREMIUM', 'VOLUME', 'FLOW']
                if any(keyword in message_content.upper() for keyword in tradytics_keywords):
                    logger.info(f"🎯 Detected Tradytics alert from {author}: {message_content[:100]}...")

                    # Create alert structure
                    alert = {
                        'bot_name': author,
                        'alert_type': self._classify_alert_type(message_content),
                        'content': message_content,
                        'symbols': self._extract_symbols(message_content),
                        'timestamp': webhook_data.get('timestamp', datetime.now().isoformat()),
                        'confidence': 0.8,  # Webhook alerts are typically high confidence
                        'source': 'webhook'
                    }

                    # Analyze the alert
                    analysis = self._analyze_tradytics_alert(alert)
                    if analysis:
                        # Send analysis to Discord
                        self._send_tradytics_analysis_alert(alert, analysis)
                        logger.info(f"✅ Processed webhook alert from {author}")
                        return {"status": "analyzed", "alert_processed": True, "analysis": analysis[:200]}
                    else:
                        logger.warning(f"⚠️ Analysis failed for webhook alert from {author}")
                        return {"status": "analysis_failed", "alert_processed": False}
                else:
                    logger.info(f"ℹ️ Webhook message from {author} doesn't appear to be Tradytics alert")
                    return {"status": "not_tradytics_alert", "alert_processed": False}
            else:
                logger.warning("⚠️ Webhook data missing 'content' field")
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

        # Common stock symbol patterns (1-5 uppercase letters)
        symbols = re.findall(r'\b[A-Z]{1,5}\b', content)

        # Filter out common words that might match
        exclude_words = ['A', 'I', 'ON', 'AT', 'IN', 'IS', 'IT', 'TO', 'OF', 'BY', 'OR', 'AS', 'AN', 'BE', 'DO', 'FOR', 'IF', 'IN', 'IS', 'IT', 'NO', 'SO', 'UP', 'US', 'WE', 'YES']

        filtered_symbols = [s for s in symbols if s not in exclude_words and len(s) >= 2]

        return list(set(filtered_symbols))  # Remove duplicates

    def _send_tradytics_analysis_alert(self, alert, analysis):
        """Send autonomous Tradytics analysis to Discord"""
        try:
            # Don't send if analysis failed
            if not analysis or "Analysis failed" in analysis or "unavailable" in analysis.lower():
                logger.debug(f"   ⏭️  Skipping Tradytics alert - analysis failed or unavailable")
                return
            
            embed = {
                "title": f"🧠 **SAVAGE ANALYSIS** - {alert['bot_name']} Alert",
                "description": f"**Alert:** {alert['content']}\n\n{analysis}",
                "color": 0xff0000,  # Red for savage
                "timestamp": alert['timestamp'],
                "footer": {"text": "Alpha Intelligence | Autonomous Tradytics Integration"}
            }

            content = f"🧠 **AUTONOMOUS ANALYSIS** | {alert['bot_name']} detected significant activity"

            success = self.send_discord(embed, content, alert_type="tradytics", source="tradytics_analysis", symbol=",".join(alert.get('symbols', [])) if alert.get('symbols') else None)
            if success:
                logger.info(f"   ✅ Autonomous Tradytics analysis sent for {alert['bot_name']}")
            else:
                logger.error(f"   ❌ Failed to send autonomous Tradytics analysis")

        except Exception as e:
            logger.error(f"   ❌ Send autonomous Tradytics alert error: {e}")
    
    def _fetch_economic_events(self, date: str) -> list:
        """
        Fetch economic events using Perplexity.
        """
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
            
            # Parse for known events
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
                        # Extract time if present
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
    
    def check_dark_pools(self):
        """
        🔒 DARK POOL INTELLIGENCE (MODULAR VERSION)
        Uses the new DPMonitorEngine for:
        - Smart debouncing (no spam)
        - Trade direction (LONG/SHORT)
        - Entry/Stop/Target calculation
        - Volume-based confidence
        - AI predictions from learning engine
        """
        if not self.dp_enabled:
            return
        
        # Use modular engine if available
        if self.dp_monitor_engine:
            self._check_dark_pools_modular()
        else:
            self._check_dark_pools_legacy()
    
    def _check_dark_pools_modular(self):
        """Use the new modular DP Monitor Engine + Selloff Detection."""
        logger.info("🔒 Checking Dark Pool levels (modular)...")
        
        try:
            # ═══════════════════════════════════════════════════════════════
            # 🚨 MOMENTUM DETECTION (Selloff + Rally)
            # Check for rapid moves BEFORE checking DP levels
            # ═══════════════════════════════════════════════════════════════
            self._check_selloffs()  # Rapid drops
            self._check_rallies()   # Rapid rises (counterpart)
            
            # Check all symbols using the engine
            alerts = self.dp_monitor_engine.check_all_symbols(self.symbols)
            
            if not alerts:
                logger.info("   📊 No DP alerts triggered (debounced or too far)")
                return
            
            # Process each alert
            for alert in alerts:
                # Format for Discord
                embed = self.dp_monitor_engine.format_discord_alert(alert)
                
                # Generate content text
                bg = alert.battleground
                ts = alert.trade_setup
                
                # Calculate expected move size (for warning)
                expected_move_pct = 0.0
                if ts:
                    if ts.direction.value == "LONG":
                        expected_move_pct = ((ts.target - ts.entry) / ts.entry) * 100
                    else:
                        expected_move_pct = ((ts.entry - ts.target) / ts.entry) * 100
                
                # Add warning for small moves (scalping signals)
                warning = ""
                if expected_move_pct > 0 and expected_move_pct < 0.5:
                    warning = " ⚠️ **SCALPING SIGNAL** - Small move expected (~{:.2f}%)".format(expected_move_pct)
                elif expected_move_pct >= 0.5:
                    warning = " ✅ **STRONGER MOVE** - Expected ~{:.2f}%".format(expected_move_pct)
                
                if alert.alert_type.value == "AT_LEVEL":
                    if ts:
                        content = f"🚨 **{alert.symbol} AT {bg.level_type.value} ${bg.price:.2f}** | {ts.direction.value} opportunity | {bg.volume:,} shares{warning}"
                    else:
                        content = f"🚨 **{alert.symbol} AT BATTLEGROUND ${bg.price:.2f}** - {bg.volume:,} shares!{warning}"
                elif alert.alert_type.value == "APPROACHING":
                    content = f"⚠️ **{alert.symbol} APPROACHING** ${bg.price:.2f} ({bg.level_type.value}) | {bg.volume:,} shares{warning}"
                else:
                    content = f"📊 {alert.symbol} near DP level ${bg.price:.2f}{warning}"
                
                # Store alert for Signal Brain synthesis (ALWAYS)
                self.recent_dp_alerts.append(alert)
                # Keep only last 20 alerts (prevent memory bloat)
                if len(self.recent_dp_alerts) > 20:
                    self.recent_dp_alerts = self.recent_dp_alerts[-20:]
                
                # 🧠 UNIFIED MODE: Suppress individual DP alerts, only synthesis matters
                if not self.unified_mode:
                    # Non-unified: Send each DP alert individually
                    logger.info(f"   📤 Sending DP alert: {alert.symbol} {alert.alert_type.value} ${bg.price:.2f}")
                    success = self.send_discord(embed, content=content, alert_type="dp_alert", source="dp_monitor", symbol=alert.symbol)
                    if success:
                        logger.info(f"   ✅ DP ALERT SENT: {alert.symbol} @ ${bg.price:.2f} ({alert.priority.value})")
                    else:
                        logger.error(f"   ❌ Failed to send DP alert")
                else:
                    # Unified mode: Suppress individual, log to DB for tracking
                    logger.debug(f"   🔇 DP alert buffered (unified mode): {alert.symbol} @ ${bg.price:.2f}")
                    self._log_alert_to_database("dp_alert", embed, content, "dp_monitor", alert.symbol)
                
                # Log to learning engine for outcome tracking
                if self.dp_learning_enabled:
                    interaction_id = self.dp_monitor_engine.log_to_learning_engine(alert)
                    if interaction_id:
                        logger.debug(f"   📝 Tracking interaction #{interaction_id}")
                
                # Trigger synthesis if we have 2+ alerts (lower threshold for faster synthesis)
                if len(self.recent_dp_alerts) >= 2 and self.brain_enabled:
                    logger.info(f"   🧠 {len(self.recent_dp_alerts)} alerts → Triggering synthesis...")
                    self.check_synthesis()
                
        except Exception as e:
            logger.error(f"   ❌ Modular DP check error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
    
    def _check_selloffs(self):
        """
        🚨 REAL-TIME SELLOFF DETECTION
        
        Detects rapid price drops with volume spikes (momentum-based).
        This catches selloffs that happen BEFORE price reaches battlegrounds.
        
        Threshold: -0.5% drop in 20 minutes with 1.5x volume spike
        """
        try:
            from live_monitoring.core.signal_generator import SignalGenerator
            from live_monitoring.core.ultra_institutional_engine import UltraInstitutionalEngine
            import yfinance as yf
            import pandas as pd
            
            # Check if we have SignalGenerator available
            if not hasattr(self, 'signal_generator') or self.signal_generator is None:
                # Initialize if needed
                try:
                    api_key = os.getenv('CHARTEXCHANGE_API_KEY')
                    dp_client = getattr(self, 'dp_client', None)
                    self.signal_generator = SignalGenerator(api_key=api_key, dp_client=dp_client)
                except Exception as e:
                    logger.debug(f"   ⚠️ SignalGenerator not available for selloff detection: {e}")
                    return
            
            for symbol in self.symbols:
                try:
                    # Get recent minute bars (last 30 minutes)
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period='1d', interval='1m')
                    
                    if hist.empty or len(hist) < 20:
                        continue
                    
                    # Get last 30 bars for selloff detection
                    minute_bars = hist.tail(30)
                    current_price = float(minute_bars['Close'].iloc[-1])
                    
                    # Get institutional context (for selloff detector)
                    inst_context = None
                    if hasattr(self, 'institutional_engine') and self.institutional_engine:
                        try:
                            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                            inst_context = self.institutional_engine.build_context(symbol, yesterday)
                        except Exception as e:
                            logger.debug(f"   ⚠️ Could not build institutional context for selloff: {e}")
                    
                    # Check for selloff
                    selloff_signal = self.signal_generator._detect_realtime_selloff(
                        symbol=symbol,
                        current_price=current_price,
                        minute_bars=minute_bars,
                        context=inst_context
                    )
                    
                    if selloff_signal:
                        logger.warning(f"   🚨 SELLOFF DETECTED: {symbol} @ ${current_price:.2f}")
                        logger.warning(f"      → Confidence: {selloff_signal.confidence:.0%}")
                        logger.warning(f"      → Action: {selloff_signal.action.value}")
                        
                        # Create Discord alert
                        embed = {
                            "title": f"🚨 **REAL-TIME SELLOFF** - {symbol}",
                            "description": selloff_signal.rationale or "Rapid price drop with volume spike detected",
                            "color": 0xff0000,  # Red for selloff
                            "fields": [
                                {
                                    "name": "🎯 Trade Setup",
                                    "value": f"**Action:** {selloff_signal.action.value}\n"
                                            f"**Entry:** ${selloff_signal.entry_price:.2f}\n"
                                            f"**Stop:** ${selloff_signal.stop_price:.2f}\n"
                                            f"**Target:** ${selloff_signal.target_price:.2f}\n"
                                            f"**Confidence:** {selloff_signal.confidence:.0%}",
                                    "inline": False
                                }
                            ],
                            "footer": {"text": "Real-time momentum detection"},
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        content = f"🚨 **REAL-TIME SELLOFF** | {symbol} | {selloff_signal.action.value} @ ${current_price:.2f}"
                        
                        # Check regime before sending (apply our smart filters)
                        market_regime = self._detect_market_regime(current_price)
                        signal_direction = selloff_signal.action.value
                        
                        # Block LONG selloff signals in DOWNTREND (contradictory)
                        if market_regime in ["DOWNTREND", "STRONG_DOWNTREND"] and signal_direction == "LONG":
                            logger.warning(f"   ⛔ REGIME FILTER: Blocking LONG selloff signal in {market_regime}")
                            continue
                        
                        # Send alert
                        logger.info(f"   📤 Sending SELLOFF alert: {symbol}")
                        success = self.send_discord(embed, content=content, alert_type="selloff", source="selloff_detector", symbol=symbol)
                        
                        if success:
                            logger.info(f"   ✅ SELLOFF ALERT SENT: {symbol}")
                            
                except Exception as e:
                    logger.debug(f"   ⚠️ Selloff check error for {symbol}: {e}")
                    continue
                    
        except Exception as e:
            logger.debug(f"   ⚠️ Selloff detection error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
    
    def _check_rallies(self):
        """
        🚀 REAL-TIME RALLY DETECTION (Counterpart to selloff)
        
        Detects rapid price rises with volume spikes (momentum-based).
        This catches rallies that happen BEFORE price reaches battlegrounds.
        
        Threshold: +0.5% gain in 20 minutes with 1.5x volume spike
        """
        try:
            from live_monitoring.core.signal_generator import SignalGenerator
            from live_monitoring.core.ultra_institutional_engine import UltraInstitutionalEngine
            import yfinance as yf
            import pandas as pd
            
            # Check if we have SignalGenerator available
            if not hasattr(self, 'signal_generator') or self.signal_generator is None:
                # Initialize if needed
                try:
                    api_key = os.getenv('CHARTEXCHANGE_API_KEY')
                    dp_client = getattr(self, 'dp_client', None)
                    self.signal_generator = SignalGenerator(api_key=api_key, dp_client=dp_client)
                except Exception as e:
                    logger.debug(f"   ⚠️ SignalGenerator not available for rally detection: {e}")
                    return
            
            for symbol in self.symbols:
                try:
                    # Get recent minute bars (last 30 minutes)
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period='1d', interval='1m')
                    
                    if hist.empty or len(hist) < 20:
                        continue
                    
                    # Get last 30 bars for rally detection
                    minute_bars = hist.tail(30)
                    current_price = float(minute_bars['Close'].iloc[-1])
                    
                    # Get institutional context
                    inst_context = None
                    if hasattr(self, 'institutional_engine') and self.institutional_engine:
                        try:
                            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                            inst_context = self.institutional_engine.build_context(symbol, yesterday)
                        except Exception as e:
                            logger.debug(f"   ⚠️ Could not build institutional context for rally: {e}")
                    
                    # Check for rally
                    rally_signal = self.signal_generator._detect_realtime_rally(
                        symbol=symbol,
                        current_price=current_price,
                        minute_bars=minute_bars,
                        context=inst_context
                    )
                    
                    if rally_signal:
                        logger.warning(f"   🚀 RALLY DETECTED: {symbol} @ ${current_price:.2f}")
                        logger.warning(f"      → Confidence: {rally_signal.confidence:.0%}")
                        logger.warning(f"      → Action: {rally_signal.action.value}")
                        
                        # Create Discord alert
                        embed = {
                            "title": f"🚀 **REAL-TIME RALLY** - {symbol}",
                            "description": rally_signal.rationale or "Rapid price rise with volume spike detected",
                            "color": 0x00ff00,  # Green for rally
                            "fields": [
                                {
                                    "name": "🎯 Trade Setup",
                                    "value": f"**Action:** {rally_signal.action.value}\n"
                                            f"**Entry:** ${rally_signal.entry_price:.2f}\n"
                                            f"**Stop:** ${rally_signal.stop_price:.2f}\n"
                                            f"**Target:** ${rally_signal.target_price:.2f}\n"
                                            f"**Confidence:** {rally_signal.confidence:.0%}",
                                    "inline": False
                                }
                            ],
                            "footer": {"text": "Real-time momentum detection"},
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        content = f"🚀 **REAL-TIME RALLY** | {symbol} | {rally_signal.action.value} @ ${current_price:.2f}"
                        
                        # Check regime before sending (apply smart filters)
                        market_regime = self._detect_market_regime(current_price)
                        signal_direction = rally_signal.action.value
                        
                        # Block SHORT rally signals in UPTREND (contradictory)
                        if market_regime in ["UPTREND", "STRONG_UPTREND"] and signal_direction == "SELL":
                            logger.warning(f"   ⛔ REGIME FILTER: Blocking SHORT rally signal in {market_regime}")
                            continue
                        
                        # Block LONG rally signals in STRONG_DOWNTREND (chasing)
                        if market_regime == "STRONG_DOWNTREND" and signal_direction == "BUY":
                            logger.warning(f"   ⛔ REGIME FILTER: Blocking BUY rally signal in {market_regime} (don't chase)")
                            continue
                        
                        # Send alert
                        logger.info(f"   📤 Sending RALLY alert: {symbol}")
                        success = self.send_discord(embed, content=content, alert_type="rally", source="rally_detector", symbol=symbol)
                        
                        if success:
                            logger.info(f"   ✅ RALLY ALERT SENT: {symbol}")
                            
                except Exception as e:
                    logger.debug(f"   ⚠️ Rally check error for {symbol}: {e}")
                    continue
                    
        except Exception as e:
            logger.debug(f"   ⚠️ Rally detection error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
    
    def _check_dark_pools_legacy(self):
        """Fallback to legacy DP check if modular engine not available."""
        logger.info("🔒 Checking Dark Pool levels (legacy)...")
        
        try:
            import yfinance as yf
            
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            for symbol in self.symbols:
                # Get current price
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period='1d', interval='1m')
                    if hist.empty:
                        continue
                    current_price = float(hist['Close'].iloc[-1])
                except Exception as e:
                    continue
                
                # Fetch battlegrounds if needed
                if symbol not in self.dp_battlegrounds:
                    try:
                        dp_levels = self.dp_client.get_dark_pool_levels(symbol, yesterday)
                        if dp_levels:
                            battlegrounds = []
                            for level in dp_levels:
                                price = float(level.get('level', 0))
                                vol = float(level.get('total_vol', 0))
                                if vol >= 500000:
                                    battlegrounds.append({'price': price, 'volume': vol, 'date': yesterday})
                            self.dp_battlegrounds[symbol] = sorted(battlegrounds, key=lambda x: x['volume'], reverse=True)[:10]
                    except:
                        pass
                
                # Simple proximity check
                for bg in self.dp_battlegrounds.get(symbol, []):
                    distance_pct = abs(current_price - bg['price']) / bg['price'] * 100
                    if distance_pct <= 0.5:
                        logger.info(f"   📊 {symbol}: ${current_price:.2f} near ${bg['price']:.2f} ({distance_pct:.2f}%)")
                
        except Exception as e:
            logger.error(f"   ❌ Legacy DP check error: {e}")
    
    def _on_dp_outcome(self, interaction_id: int, outcome):
        """
        Callback when a dark pool interaction outcome is determined.
        Sends a follow-up alert to Discord.
        """
        try:
            outcome_emoji = {
                'BOUNCE': '✅ LEVEL HELD',
                'BREAK': '❌ LEVEL BROKE',
                'FADE': '⚪ NO CLEAR OUTCOME'
            }.get(outcome.outcome.value, '❓ UNKNOWN')
            
            # Color based on outcome
            if outcome.outcome.value == 'BOUNCE':
                color = 3066993  # Green
                action_result = "Support/Resistance HELD - Trade would have worked!"
            elif outcome.outcome.value == 'BREAK':
                color = 15158332  # Red
                action_result = "Level BROKE - Would have been stopped out"
            else:
                color = 9807270  # Gray
                action_result = "Unclear outcome - No trade"
            
            # Send outcome alert
            embed = {
                "title": f"🎯 DP OUTCOME: {outcome_emoji}",
                "color": color,
                "description": f"Interaction #{interaction_id} resolved after {outcome.time_to_outcome_min} min",
                "fields": [
                    {"name": "📊 Max Move", "value": f"{outcome.max_move_pct:+.2f}%", "inline": True},
                    {"name": "⏱️ Tracking Time", "value": f"{outcome.time_to_outcome_min} min", "inline": True},
                    {"name": "💡 Result", "value": action_result, "inline": False},
                ],
                "footer": {"text": "Learning from this outcome... Patterns updated!"},
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # In unified mode, suppress outcome alerts (they're just learning feedback)
            # Only log to console for debugging
            if not self.unified_mode:
                content = f"🎯 **{outcome_emoji}** after {outcome.time_to_outcome_min} min | Max move: {outcome.max_move_pct:+.2f}%"
                self.send_discord(embed, content=content, alert_type="dp_outcome", source="dp_learning", symbol=None)
            else:
                logger.debug(f"   📊 DP Outcome: {outcome_emoji} after {outcome.time_to_outcome_min} min (buffered for synthesis)")
            
            logger.info(f"📣 Outcome alert sent: #{interaction_id} {outcome.outcome.value}")
        except Exception as e:
            logger.error(f"❌ Outcome alert error: {e}")
    
    def check_synthesis(self):
        """
        🧠 SIGNAL SYNTHESIS BRAIN
        Combines all DP alerts into ONE unified analysis.
        Instead of 7 separate alerts → 1 actionable synthesis.
        """
        if not self.brain_enabled or not self.signal_brain:
            return
        
        try:
            import yfinance as yf
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            logger.info("🧠 Running Signal Synthesis Brain...")
            
            # Get current prices
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
            
            # Use RECENT ALERTS if available (better than re-fetching!)
            spy_levels = []
            qqq_levels = []
            
            if self.recent_dp_alerts:
                # Convert recent alerts to level format
                logger.info(f"   📊 Using {len(self.recent_dp_alerts)} recent DP alerts for synthesis")
                for alert in self.recent_dp_alerts:
                    bg = alert.battleground
                    level_data = {
                        'price': bg.price,
                        'volume': bg.volume
                    }
                    if alert.symbol == 'SPY':
                        spy_levels.append(level_data)
                    elif alert.symbol == 'QQQ':
                        qqq_levels.append(level_data)
            else:
                # Fallback: Get DP levels from cache or fetch
                logger.info("   📊 No recent alerts - fetching DP levels from cache")
                for symbol in ['SPY', 'QQQ']:
                    levels = []  # Initialize levels for each symbol
                    if symbol in self.dp_battlegrounds:
                        levels = [
                            {'price': bg['price'], 'volume': int(bg['volume'])}
                            for bg in self.dp_battlegrounds[symbol]
                        ]
                    else:
                        # Fetch fresh (no date = gets today's levels)
                        try:
                            dp_levels = self.dp_client.get_dark_pool_levels(symbol)
                            if dp_levels:
                                levels = []
                                for level in dp_levels:
                                    price = float(level.get('level', 0))
                                    vol = int(level.get('volume', 0))  # Fixed: was total_vol
                                    if vol >= 100000:  # Lowered from 500k (too high for intraday)
                                        levels.append({'price': price, 'volume': vol})
                                logger.info(f"   📊 Fetched {len(levels)} DP levels for {symbol} (vol >= 100k)")
                        except Exception as e:
                            logger.warning(f"   ⚠️ Failed to fetch DP levels for {symbol}: {e}")
                            levels = []

                    if symbol == 'SPY':
                        spy_levels = levels
                    else:
                        qqq_levels = levels
            
            if not spy_levels and not qqq_levels:
                logger.info("   📊 No DP levels available for synthesis")
                return
            
            # Get REAL macro context from all data sources!
            # NO MORE HARDCODING - uses FedWatch, Economic Calendar, Fed Officials, Trump!
            fed_sentiment = "NEUTRAL"
            trump_risk = "LOW"
            macro_reasoning = ""
            
            if self.macro_provider:
                try:
                    macro_context = self.macro_provider.get_context()
                    fed_sentiment = macro_context.fed_sentiment
                    trump_risk = macro_context.trump_risk
                    macro_reasoning = macro_context.reasoning
                    
                    logger.info(f"   📊 REAL Macro Data:")
                    logger.info(f"      Fed Watch: {macro_context.fed_cut_probability:.0f}% cut → {fed_sentiment}")
                    if macro_context.recent_event:
                        logger.info(f"      Economic: {macro_context.recent_event.name} → {macro_context.economic_sentiment}")
                    if macro_context.fed_official_name:
                        logger.info(f"      Fed Official: {macro_context.fed_official_name} → {macro_context.fed_official_sentiment}")
                    logger.info(f"      Trump Risk: {trump_risk}")
                    logger.info(f"      Overall Bias: {macro_context.overall_bias}")
                except Exception as me:
                    logger.warning(f"   ⚠️ Macro context error: {me}")
            else:
                # Fallback to old method if MacroContextProvider not available
                if self.fed_enabled and self.prev_fed_status:
                    try:
                        cut = getattr(self.prev_fed_status, 'prob_cut', None)
                        if cut is None:
                            cut = self.prev_fed_status.get('cut_probability', 50) if isinstance(self.prev_fed_status, dict) else 50
                        if cut > 70:
                            fed_sentiment = "DOVISH"
                        elif cut < 30:
                            fed_sentiment = "HAWKISH"
                    except:
                        pass
                
                if self.trump_enabled and self.prev_trump_sentiment:
                    if 'risk' in str(self.prev_trump_sentiment).lower():
                        trump_risk = "HIGH"
                
                logger.info(f"   ⚠️ Using fallback (no MacroProvider): fed={fed_sentiment}, trump={trump_risk}")
            
            # Run synthesis with REAL data
            result = self.signal_brain.analyze(
                spy_levels=spy_levels,
                qqq_levels=qqq_levels,
                spy_price=spy_price,
                qqq_price=qqq_price,
                fed_sentiment=fed_sentiment,
                trump_risk=trump_risk,
            )
            
            # In unified mode, ALWAYS alert if we have recent alerts (they were suppressed)
            # Otherwise, use the brain's should_alert logic
            should_send = False
            if self.unified_mode and len(self.recent_dp_alerts) > 0:
                # We suppressed individual alerts, so we MUST send synthesis
                should_send = True
                logger.info(f"   🧠 Unified mode: {len(self.recent_dp_alerts)} alerts buffered → Sending synthesis")
            elif self.signal_brain.should_alert(result):
                should_send = True
            
            # 🧠 NARRATIVE BRAIN - SEPARATE HIGH-QUALITY SIGNALS
            # Check Narrative Brain decision BEFORE clearing buffer
            narrative_sent = False
            if self.narrative_enabled and self.narrative_brain and len(self.recent_dp_alerts) > 0:
                narrative_sent = self._check_narrative_brain_signals(result, spy_price, qqq_price)
            
            if should_send:
                # 🕐 TIME-BASED DEDUPLICATION (not content-based)
                # Send synthesis max once per 5 minutes, regardless of small confluence changes
                import hashlib
                current_time = time.time()
                
                # Check last synthesis time
                if hasattr(self, 'last_synthesis_sent'):
                    elapsed = current_time - self.last_synthesis_sent
                    if elapsed < 300:  # 5 minutes cooldown
                        logger.debug(f"   ⏭️ Synthesis on cooldown ({elapsed:.0f}s < 300s) - skipping")
                        # Clear buffer even if skipped (prevent stale data)
                        if not narrative_sent:
                            self.recent_dp_alerts = []
                        return
                
                # Mark as sent
                self.last_synthesis_sent = current_time
                
                embed = self.signal_brain.to_discord(result)
                content = f"🧠 **UNIFIED MARKET SYNTHESIS** | {result.confluence.score:.0f}% {result.confluence.bias.value}"
                
                if result.recommendation and result.recommendation.wait_for:
                    content += f" | ⏳ {result.recommendation.wait_for}"
                elif result.recommendation and result.recommendation.action != "WAIT":
                    content += f" | 🎯 {result.recommendation.action} SPY"
                
                logger.info(f"   📤 Sending UNIFIED synthesis alert: {result.confluence.score:.0f}% {result.confluence.bias.value}")
                success = self.send_discord(embed, content=content, alert_type="synthesis", source="signal_brain", symbol="SPY,QQQ")
                
                if success:
                    logger.info(f"   ✅ UNIFIED SYNTHESIS ALERT SENT!")
                    # Track this synthesis
                    self.sent_synthesis_hashes.add(synthesis_hash)
                    self.last_synthesis_hash = synthesis_hash
                    # Keep only last 10 hashes
                    if len(self.sent_synthesis_hashes) > 10:
                        self.sent_synthesis_hashes = set(list(self.sent_synthesis_hashes)[-10:])
                    # Clear buffer after successful synthesis (unless Narrative Brain sent)
                    if not narrative_sent:
                        self.recent_dp_alerts = []
            else:
                logger.debug(f"   📊 Synthesis: {result.confluence.score:.0f}% {result.confluence.bias.value} (no alert needed)")
                # Clear buffer even if no alert (prevent stale data)
                if not narrative_sent:
                    self.recent_dp_alerts = []
                
        except Exception as e:
            logger.error(f"   ❌ Synthesis error: {e}")
            import traceback
            logger.debug(traceback.format_exc())

    def _check_narrative_brain_signals(self, synthesis_result, spy_price: float, qqq_price: float) -> bool:
        """
        🧠 NARRATIVE BRAIN - SEPARATE HIGH-QUALITY SIGNALS
        Checks Narrative Brain decision logic and sends separately if criteria met.
        These are HIGHER QUALITY signals with better move predictability.
        
        🔧 FIX (Dec 12): Added regime-aware filtering and synthesis alignment
        - Skip LONG signals in DOWNTREND
        - Skip SHORT signals in UPTREND
        - Require synthesis-signal direction alignment
        - Added level-direction cooldown to prevent flipping
        
        Returns:
            bool: True if signal was sent, False otherwise
        """
        if not self.narrative_enabled or not self.narrative_brain:
            return False
        
        try:
            # Calculate average confluence from recent alerts
            if not self.recent_dp_alerts:
                return False
            
            # Calculate confluence from alert attributes
            def get_alert_confluence(alert):
                """Calculate confluence score for an alert"""
                score = 50  # Base score
                
                # Volume-based confidence
                bg = alert.battleground
                if bg.volume >= 2_000_000:
                    score += 30
                elif bg.volume >= 1_000_000:
                    score += 20
                elif bg.volume >= 500_000:
                    score += 10
                
                # Priority boost
                if alert.priority.value == "CRITICAL":
                    score += 20
                elif alert.priority.value == "HIGH":
                    score += 10
                
                # Alert type boost
                if alert.alert_type.value == "AT_LEVEL":
                    score += 10
                
                # AI prediction boost
                if alert.ai_prediction and alert.ai_prediction > 0.7:
                    score += 10
                
                return min(score, 100)
            
            avg_confluence = sum(
                get_alert_confluence(alert) 
                for alert in self.recent_dp_alerts
            ) / len(self.recent_dp_alerts)
            
            # Narrative Brain decision logic (from backtesting framework)
            min_confluence = 70.0  # Minimum confluence threshold
            min_alerts = 3  # Minimum alerts for confirmation
            critical_mass = 5  # Critical mass threshold
            exceptional_confluence = 80.0  # Exceptional threshold
            
            # Check if Narrative Brain should send
            should_send = False
            reason = ""
            
            # Exceptional confluence
            if avg_confluence >= exceptional_confluence:
                should_send = True
                reason = f"Exceptional confluence ({avg_confluence:.0f}%)"
            # Strong confluence with confirmation
            elif avg_confluence >= min_confluence and len(self.recent_dp_alerts) >= min_alerts:
                should_send = True
                reason = f"Strong confluence ({avg_confluence:.0f}%) + {len(self.recent_dp_alerts)} alerts"
            # Critical mass
            elif len(self.recent_dp_alerts) >= critical_mass:
                should_send = True
                reason = f"Critical mass ({len(self.recent_dp_alerts)} alerts)"
            
            if should_send:
                # 🕐 TIME-BASED COOLDOWN (prevent spam)
                # Only send narrative brain max once per 5 minutes
                current_time = time.time()
                if hasattr(self, 'last_narrative_sent'):
                    elapsed = current_time - self.last_narrative_sent
                    if elapsed < 300:  # 5 minutes cooldown
                        logger.debug(f"   ⏭️ Narrative Brain on cooldown ({elapsed:.0f}s < 300s) - skipping")
                        return False
                
                # Get best alert for trade setup (using same confluence calculation)
                def get_alert_confluence(alert):
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
                
                best_alert = max(
                    self.recent_dp_alerts,
                    key=get_alert_confluence
                )
                
                bg = best_alert.battleground
                ts = best_alert.trade_setup
                
                # ═══════════════════════════════════════════════════════════════
                # 🧠 SMART REGIME-AWARE FILTERING
                # Multi-factor regime detection + signal alignment
                # ═══════════════════════════════════════════════════════════════
                market_regime = self._detect_market_regime(spy_price)
                signal_direction = ts.direction.value if ts else "UNKNOWN"
                
                # Get regime strength from cached details
                regime_details = getattr(self, '_last_regime_details', {})
                bullish_signals = regime_details.get('bullish_signals', 0)
                bearish_signals = regime_details.get('bearish_signals', 0)
                
                # STRONG regimes = HARD BLOCK (never trade against)
                if market_regime == "STRONG_DOWNTREND" and signal_direction == "LONG":
                    logger.warning(f"   ⛔ REGIME FILTER: Blocking LONG signal in STRONG DOWNTREND")
                    logger.warning(f"      → Market: {market_regime} (bearish signals: {bearish_signals})")
                    logger.warning(f"      → STRONG trends = NEVER trade against")
                    return False
                
                if market_regime == "STRONG_UPTREND" and signal_direction == "SHORT":
                    logger.warning(f"   ⛔ REGIME FILTER: Blocking SHORT signal in STRONG UPTREND")
                    logger.warning(f"      → Market: {market_regime} (bullish signals: {bullish_signals})")
                    logger.warning(f"      → STRONG trends = NEVER trade against")
                    return False
                
                # Normal downtrend = block LONG unless exceptional confluence
                if market_regime == "DOWNTREND" and signal_direction == "LONG":
                    if avg_confluence < 90:  # Only allow exceptional 90%+ confluence
                        logger.warning(f"   ⛔ REGIME FILTER: Blocking LONG in DOWNTREND (confluence {avg_confluence:.0f}% < 90%)")
                        logger.warning(f"      → Market: {market_regime} | Need 90%+ confluence to override")
                        return False
                    else:
                        logger.info(f"   ⚠️ REGIME OVERRIDE: Allowing LONG in DOWNTREND (exceptional {avg_confluence:.0f}% confluence)")
                
                # Normal uptrend = block SHORT unless exceptional confluence
                if market_regime == "UPTREND" and signal_direction == "SHORT":
                    if avg_confluence < 90:  # Only allow exceptional 90%+ confluence
                        logger.warning(f"   ⛔ REGIME FILTER: Blocking SHORT in UPTREND (confluence {avg_confluence:.0f}% < 90%)")
                        logger.warning(f"      → Market: {market_regime} | Need 90%+ confluence to override")
                        return False
                    else:
                        logger.info(f"   ⚠️ REGIME OVERRIDE: Allowing SHORT in UPTREND (exceptional {avg_confluence:.0f}% confluence)")
                
                # CHOPPY regime = require synthesis alignment (can't rely on trend)
                # This makes CHOPPY more restrictive, not more permissive
                
                # ═══════════════════════════════════════════════════════════════
                # 🧠 SMART SYNTHESIS-SIGNAL ALIGNMENT CHECK
                # Require alignment in ALL regimes (not just strong trends)
                # ═══════════════════════════════════════════════════════════════
                synthesis_bias = synthesis_result.confluence.bias.value if synthesis_result and hasattr(synthesis_result, 'confluence') else "NEUTRAL"
                synthesis_score = synthesis_result.confluence.score if synthesis_result and hasattr(synthesis_result, 'confluence') else 50
                
                # Skip LONG when synthesis is BEARISH
                if synthesis_bias == "BEARISH" and signal_direction == "LONG":
                    # Only exception: if synthesis score is weak (<60%)
                    if synthesis_score >= 60:
                        logger.warning(f"   ⛔ SYNTHESIS CONFLICT: Blocking LONG (synthesis {synthesis_score:.0f}% BEARISH)")
                        logger.warning(f"      → Strong BEARISH synthesis = don't fight it")
                        return False
                    else:
                        logger.info(f"   ⚠️ WEAK SYNTHESIS: Allowing LONG despite BEARISH (only {synthesis_score:.0f}%)")
                
                # Skip SHORT when synthesis is BULLISH
                if synthesis_bias == "BULLISH" and signal_direction == "SHORT":
                    # Only exception: if synthesis score is weak (<60%)
                    if synthesis_score >= 60:
                        logger.warning(f"   ⛔ SYNTHESIS CONFLICT: Blocking SHORT (synthesis {synthesis_score:.0f}% BULLISH)")
                        logger.warning(f"      → Strong BULLISH synthesis = don't fight it")
                        return False
                    else:
                        logger.info(f"   ⚠️ WEAK SYNTHESIS: Allowing SHORT despite BULLISH (only {synthesis_score:.0f}%)")
                
                # ═══════════════════════════════════════════════════════════════
                # 🔧 FIX #3: LEVEL-DIRECTION COOLDOWN
                # Don't flip direction on same level within 10 minutes
                # ═══════════════════════════════════════════════════════════════
                level_key = f"{bg.symbol}_{bg.price:.2f}"
                if not hasattr(self, '_last_level_directions'):
                    self._last_level_directions = {}
                
                if level_key in self._last_level_directions:
                    last_direction, last_time = self._last_level_directions[level_key]
                    elapsed = current_time - last_time
                    
                    # If same level but DIFFERENT direction within 10 minutes, skip
                    if last_direction != signal_direction and elapsed < 600:  # 10 min
                        logger.warning(f"   ⛔ FLIP PREVENTION: Same level ${bg.price:.2f} flipped from {last_direction} to {signal_direction}")
                        logger.warning(f"      → Last signal: {last_direction} ({elapsed:.0f}s ago)")
                        logger.warning(f"      → Waiting 10 minutes before allowing direction change")
                        return False
                
                # Record this signal's direction
                self._last_level_directions[level_key] = (signal_direction, current_time)
                # Clean old entries (>30 min)
                self._last_level_directions = {
                    k: v for k, v in self._last_level_directions.items() 
                    if current_time - v[1] < 1800
                }
                
                # ═══════════════════════════════════════════════════════════════
                # ✅ SIGNAL PASSED ALL FILTERS - SEND IT
                # ═══════════════════════════════════════════════════════════════
                logger.info(f"   ✅ SIGNAL PASSED FILTERS:")
                logger.info(f"      → Regime: {market_regime} | Signal: {signal_direction} ✓")
                logger.info(f"      → Synthesis: {synthesis_bias} | Signal: {signal_direction} ✓")
                
                # Create Narrative Brain alert
                embed = {
                    "title": f"🧠 **NARRATIVE BRAIN SIGNAL** - {best_alert.symbol}",
                    "description": f"**Higher Quality Signal** - Better move predictability\n\n"
                                   f"**Reason:** {reason}\n"
                                   f"**Confluence:** {avg_confluence:.0f}%\n"
                                   f"**Alerts Confirmed:** {len(self.recent_dp_alerts)}\n"
                                   f"**Regime:** {market_regime} | **Synthesis:** {synthesis_bias}",
                    "color": 0x00ff00,  # Green for high quality
                    "fields": []
                }
                
                if ts:
                    embed["fields"].extend([
                        {
                            "name": "🎯 Trade Setup",
                            "value": f"**Direction:** {ts.direction.value}\n"
                                    f"**Entry:** ${ts.entry:.2f}\n"
                                    f"**Stop:** ${ts.stop:.2f}\n"
                                    f"**Target:** ${ts.target:.2f}\n"
                                    f"**R/R:** {ts.risk_reward:.1f}:1",
                            "inline": False
                        }
                    ])
                
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
                    logger.info(f"   ✅ NARRATIVE BRAIN SIGNAL SENT!")
                    # Mark as sent with timestamp
                    self.last_narrative_sent = current_time
                    return True  # Signal sent
            else:
                logger.debug(f"   🧠 Narrative Brain: Not sending (confluence: {avg_confluence:.0f}%, alerts: {len(self.recent_dp_alerts)})")
            
            return False  # No signal sent
                
        except Exception as e:
            logger.error(f"   ❌ Narrative Brain check error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
    
    def _detect_market_regime(self, current_price: float) -> str:
        """
        🧠 SMART REGIME DETECTION
        
        Multi-factor regime detection that adapts to:
        - Intraday price movement (from open)
        - Recent momentum (last 30 min)
        - Volatility (ATR-based thresholds)
        - Time of day (morning chop vs afternoon trend)
        - Higher lows / Lower highs pattern
        
        Returns:
            str: "STRONG_UPTREND", "UPTREND", "STRONG_DOWNTREND", "DOWNTREND", or "CHOPPY"
        """
        try:
            import yfinance as yf
            
            # Get today's intraday data (5-min bars)
            ticker = yf.Ticker('SPY')
            hist = ticker.history(period='1d', interval='5m')
            
            if hist.empty or len(hist) < 6:
                return "CHOPPY"  # Default to choppy if no data
            
            # ═══════════════════════════════════════════════════════════════
            # 1. PRICE CHANGE FROM OPEN
            # ═══════════════════════════════════════════════════════════════
            open_price = hist['Open'].iloc[0]
            change_from_open = ((current_price - open_price) / open_price) * 100
            
            # ═══════════════════════════════════════════════════════════════
            # 2. RECENT MOMENTUM (Last 30 minutes = 6 bars)
            # ═══════════════════════════════════════════════════════════════
            recent_bars = min(6, len(hist))
            recent_prices = hist['Close'].tail(recent_bars)
            recent_high = recent_prices.max()
            recent_low = recent_prices.min()
            recent_start = recent_prices.iloc[0]
            recent_end = recent_prices.iloc[-1]
            
            recent_momentum = ((recent_end - recent_start) / recent_start) * 100
            
            # ═══════════════════════════════════════════════════════════════
            # 3. VOLATILITY-ADJUSTED THRESHOLDS (ATR-like)
            # ═══════════════════════════════════════════════════════════════
            # Calculate average range of recent bars
            ranges = (hist['High'] - hist['Low']).tail(12)  # Last 1 hour
            avg_range = ranges.mean()
            avg_range_pct = (avg_range / current_price) * 100
            
            # Thresholds scale with volatility
            # High volatility = higher threshold, Low volatility = lower threshold
            base_threshold = 0.15  # Base 0.15%
            volatility_multiplier = max(1.0, avg_range_pct / 0.10)  # Scale with volatility
            trend_threshold = base_threshold * volatility_multiplier
            strong_trend_threshold = trend_threshold * 2.5
            
            # ═══════════════════════════════════════════════════════════════
            # 4. HIGHER HIGHS / LOWER LOWS PATTERN
            # ═══════════════════════════════════════════════════════════════
            # Split into 3 segments and check pattern
            segment_size = len(hist) // 3
            if segment_size >= 2:
                seg1_high = hist['High'].iloc[:segment_size].max()
                seg2_high = hist['High'].iloc[segment_size:segment_size*2].max()
                seg3_high = hist['High'].iloc[segment_size*2:].max()
                
                seg1_low = hist['Low'].iloc[:segment_size].min()
                seg2_low = hist['Low'].iloc[segment_size:segment_size*2].min()
                seg3_low = hist['Low'].iloc[segment_size*2:].min()
                
                higher_highs = seg3_high > seg2_high > seg1_high
                higher_lows = seg3_low > seg2_low > seg1_low
                lower_highs = seg3_high < seg2_high < seg1_high
                lower_lows = seg3_low < seg2_low < seg1_low
                
                pattern_bullish = higher_highs or higher_lows
                pattern_bearish = lower_highs or lower_lows
            else:
                pattern_bullish = False
                pattern_bearish = False
            
            # ═══════════════════════════════════════════════════════════════
            # 5. TIME OF DAY ADJUSTMENT
            # ═══════════════════════════════════════════════════════════════
            from datetime import time as dt_time
            now = datetime.now()
            current_time = now.time()
            
            # First 30 min (9:30-10:00) - Higher threshold (morning chop)
            is_morning_chop = dt_time(9, 30) <= current_time < dt_time(10, 0)
            # Power hour (3:00-4:00) - Lower threshold (trends more reliable)
            is_power_hour = dt_time(15, 0) <= current_time < dt_time(16, 0)
            
            if is_morning_chop:
                trend_threshold *= 1.5  # Require stronger move in morning
                strong_trend_threshold *= 1.5
            elif is_power_hour:
                trend_threshold *= 0.8  # Trends more reliable in power hour
                strong_trend_threshold *= 0.8
            
            # ═══════════════════════════════════════════════════════════════
            # 6. COMPOSITE REGIME DETERMINATION
            # ═══════════════════════════════════════════════════════════════
            bullish_signals = 0
            bearish_signals = 0
            
            # Change from open
            if change_from_open > strong_trend_threshold:
                bullish_signals += 2
            elif change_from_open > trend_threshold:
                bullish_signals += 1
            elif change_from_open < -strong_trend_threshold:
                bearish_signals += 2
            elif change_from_open < -trend_threshold:
                bearish_signals += 1
            
            # Recent momentum
            if recent_momentum > trend_threshold * 0.5:
                bullish_signals += 1
            elif recent_momentum < -trend_threshold * 0.5:
                bearish_signals += 1
            
            # Pattern confirmation
            if pattern_bullish:
                bullish_signals += 1
            if pattern_bearish:
                bearish_signals += 1
            
            # Price position (above/below session VWAP approximation)
            session_avg = hist['Close'].mean()
            if current_price > session_avg * 1.002:
                bullish_signals += 1
            elif current_price < session_avg * 0.998:
                bearish_signals += 1
            
            # ═══════════════════════════════════════════════════════════════
            # 7. FINAL REGIME CLASSIFICATION
            # ═══════════════════════════════════════════════════════════════
            if bullish_signals >= 4:
                regime = "STRONG_UPTREND"
            elif bullish_signals >= 2 and bearish_signals < 2:
                regime = "UPTREND"
            elif bearish_signals >= 4:
                regime = "STRONG_DOWNTREND"
            elif bearish_signals >= 2 and bullish_signals < 2:
                regime = "DOWNTREND"
            else:
                regime = "CHOPPY"
            
            # Log details for debugging
            logger.info(f"   📊 REGIME: {regime}")
            logger.debug(f"      → Open: ${open_price:.2f} | Current: ${current_price:.2f} | Change: {change_from_open:+.2f}%")
            logger.debug(f"      → Momentum (30m): {recent_momentum:+.2f}% | Vol threshold: {trend_threshold:.2f}%")
            logger.debug(f"      → Bullish signals: {bullish_signals} | Bearish signals: {bearish_signals}")
            logger.debug(f"      → Pattern: {'HH/HL' if pattern_bullish else 'LH/LL' if pattern_bearish else 'None'}")
            
            # Cache the regime details for synthesis alignment
            self._last_regime_details = {
                'regime': regime,
                'change_from_open': change_from_open,
                'recent_momentum': recent_momentum,
                'bullish_signals': bullish_signals,
                'bearish_signals': bearish_signals,
                'pattern': 'bullish' if pattern_bullish else 'bearish' if pattern_bearish else 'none'
            }
            
            return regime
            
        except Exception as e:
            logger.warning(f"   ⚠️ Regime detection error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return "CHOPPY"  # Default to choppy on error
    
    def _is_market_hours(self) -> bool:
        """Check if currently in RTH (9:30 AM - 4:00 PM ET, Mon-Fri)."""
        from datetime import time as dt_time
        now = datetime.now()
        current_time = now.time()
        
        # Market hours: 9:30 AM - 4:00 PM ET
        market_open = dt_time(9, 30)  # 9:30 AM
        market_close = dt_time(16, 0)  # 4:00 PM
        
        # Check if it's a weekday (Mon=0, Sun=6)
        is_weekday = now.weekday() < 5
        
        # Check if in market hours
        in_hours = market_open <= current_time < market_close
        
        return is_weekday and in_hours
    
    def _get_current_intelligence_snapshot(self) -> dict:
        """Get current snapshot of all intelligence sources for narrative brain"""
        snapshot = {
            'fed_watch': {},
            'fed_officials': {},
            'trump_monitor': {},
            'economic_calendar': {},
            'dp_monitor': {}
        }

        # Fed Watch
        if self.fed_enabled and self.fed_watch:
            try:
                status = self.fed_watch.get_status() if hasattr(self.fed_watch, 'get_status') else self.fed_watch.get_current_status()
                snapshot['fed_watch'] = status or {}
            except Exception as e:
                logger.debug(f"Error getting fed watch status: {e}")

        # Fed Officials
        if self.fed_enabled and self.fed_officials:
            try:
                status = self.fed_officials.get_status() if hasattr(self.fed_officials, 'get_status') else self.fed_officials.get_latest_comment()
                snapshot['fed_officials'] = status or {}
            except Exception as e:
                logger.debug(f"Error getting fed officials status: {e}")

        # Trump Monitor
        if self.trump_enabled and self.trump_pulse:
            try:
                status = self.trump_pulse.get_current_situation()
                snapshot['trump_monitor'] = status or {}
            except Exception as e:
                logger.debug(f"Error getting trump monitor status: {e}")

        # Economic Calendar
        if self.econ_enabled and self.econ_engine:
            try:
                status = self.econ_engine.get_status()
                snapshot['economic_calendar'] = status or {}
            except Exception as e:
                logger.debug(f"Error getting economic status: {e}")

        # DP Monitor
        if self.dp_enabled and self.dp_monitor_engine:
            try:
                # Get current active levels and bias
                levels = self.dp_monitor_engine.get_active_levels() if hasattr(self.dp_monitor_engine, 'get_active_levels') else []
                bias = self.dp_monitor_engine.get_current_bias() if hasattr(self.dp_monitor_engine, 'get_current_bias') else 'neutral'
                snapshot['dp_monitor'] = {
                    'active_levels': levels,
                    'institutional_bias': bias
                }
            except Exception as e:
                logger.debug(f"Error getting DP monitor status: {e}")

        return snapshot

    def send_startup_alert(self):
        """Send startup notification (only once per session)."""
        if self.startup_alert_sent:
            logger.debug("   ⏭️  Startup alert already sent - skipping")
            return
            
        if not self.discord_webhook:
            logger.warning("⚠️ DISCORD_WEBHOOK_URL not set - no alerts will be sent!")
            return
        
        # Get engine status
        econ_status = ""
        if self.econ_enabled:
            try:
                status = self.econ_engine.get_status()
                patterns = status.get('learned_patterns', {})
                pattern_str = ", ".join([f"{k}: {v['base_impact']:+.1f}%" for k, v in list(patterns.items())[:2]])
                econ_status = f"Patterns: {pattern_str}" if pattern_str else "Learning..."
            except Exception as e:
                logger.debug(f"Error getting econ status: {e}")
                econ_status = "Initializing..."
        
        # Get DP learning status
        dp_learning_status = ""
        if self.dp_learning_enabled and self.dp_learning:
            try:
                status = self.dp_learning.get_status()
                db_stats = status.get('database', {})
                patterns = status.get('patterns', {})
                dp_learning_status = f"📊 {db_stats.get('total', 0)} interactions | {len(patterns)} patterns learned"
                if db_stats.get('bounce_rate', 0) > 0:
                    dp_learning_status += f" | {db_stats['bounce_rate']:.0%} bounce rate"
            except Exception as e:
                logger.debug(f"Error getting DP learning status: {e}")
                dp_learning_status = "Initializing..."
        
        # Signal Brain status
        brain_status = "❌ Disabled"
        if self.brain_enabled:
            if self.unified_mode:
                brain_status = "✅ ACTIVE - UNIFIED MODE (individual alerts suppressed)"
            else:
                brain_status = "✅ ACTIVE - Zone clustering, cross-asset, unified alerts"
        
        # Macro Context status (NO MORE HARDCODING!)
        macro_status = "❌ Disabled"
        if hasattr(self, 'macro_provider') and self.macro_provider:
            macro_status = "✅ REAL DATA (Fed + Econ + Trump)"
        
        embed = {
            "title": "🎯 ALPHA INTELLIGENCE - ONLINE",
            "color": 3066993,
            "description": "All monitoring systems activated with REAL MACRO DATA + SIGNAL BRAIN",
            "fields": [
                {"name": "🏦 Fed Watch", "value": "✅ Active" if self.fed_enabled else "❌ Disabled", "inline": True},
                {"name": "🎯 Trump Intel", "value": "✅ Active" if self.trump_enabled else "❌ Disabled", "inline": True},
                {"name": "📊 Economic AI", "value": "✅ Active" if self.econ_enabled else "❌ Disabled", "inline": True},
                {"name": "🔒 Dark Pools", "value": f"✅ {', '.join(self.symbols)}" if self.dp_enabled else "❌ Disabled", "inline": True},
                {"name": "🧠 DP Learning", "value": f"✅ {dp_learning_status}" if self.dp_learning_enabled else "❌ Disabled", "inline": False},
                {"name": "🧠 Signal Brain", "value": brain_status, "inline": False},
                {"name": "📊 Macro Context", "value": macro_status, "inline": False},
                {"name": "🧠 Narrative Brain", "value": "✅ CONTEXTUAL STORYTELLING (smart updates)" if self.narrative_enabled else "❌ Disabled", "inline": False},
                {"name": "📈 Econ Patterns", "value": econ_status or "Disabled", "inline": False},
                {"name": "⏱️ Intervals", "value": f"Fed: {self.fed_interval/60:.0f}m | Trump: {self.trump_interval/60:.0f}m | DP: {self.dp_interval}s | Brain: {self.synthesis_interval}s", "inline": False},
            ],
            "footer": {"text": "Monitoring markets 24/7 with REAL macro data + signal synthesis"},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info("📤 Sending startup alert to Discord...")
        success = self.send_discord(embed, alert_type="startup", source="monitor")
        if success:
            logger.info("   ✅ Startup alert sent successfully!")
            self.startup_alert_sent = True  # Mark as sent
        else:
            logger.error("   ❌ FAILED to send startup alert - check DISCORD_WEBHOOK_URL!")
    
    def run(self):
        """Main run loop."""
        logger.info("🚀 Starting unified monitoring...")
        
        # Startup alert
        self.send_startup_alert()
        
        # SKIP initial checks on startup (prevents spam from processing old data)
        # Let the loop handle checks with proper intervals
        logger.info("   ⏭️  Skipping initial checks (will start with first interval)")
        
        # Initialize timestamps so first checks happen after intervals
        now = datetime.now()
        self.last_fed_check = now  # Will check after fed_interval
        self.last_trump_check = now  # Will check after trump_interval
        self.last_econ_check = now  # Will check after econ_interval
        self.last_dp_check = now  # Will check after dp_interval
        self.last_synthesis_check = now  # Will check after synthesis_interval
        
        while self.running:
            try:
                now = datetime.now()
                
                # Check Fed (every 5 min)
                if self.last_fed_check is None or (now - self.last_fed_check).seconds >= self.fed_interval:
                    self.check_fed()
                    self.last_fed_check = now
                
                # Check Trump (every 3 min)
                if self.last_trump_check is None or (now - self.last_trump_check).seconds >= self.trump_interval:
                    self.check_trump()
                    self.last_trump_check = now
                
                # Check Economics (every hour)
                if self.last_econ_check is None or (now - self.last_econ_check).seconds >= self.econ_interval:
                    self.check_economics()
                    self.last_econ_check = now
                
                # Check if market is open (RTH: 9:30 AM - 4:00 PM ET, Mon-Fri)
                # Skip DP and Synthesis checks after market close (noise prevention)
                is_market_hours = self._is_market_hours()
                
                # Check Dark Pools (every 60 seconds - real-time!) - ONLY DURING RTH
                if is_market_hours and (self.last_dp_check is None or (now - self.last_dp_check).seconds >= self.dp_interval):
                    self.check_dark_pools()
                    self.last_dp_check = now
                elif not is_market_hours:
                    # Market closed - skip DP checks (no noise)
                    if self.last_dp_check is None or (now - self.last_dp_check).seconds >= 300:  # Log once every 5 min
                        logger.debug("   ⏸️  Market closed - skipping DP checks")
                        self.last_dp_check = now
                
                # Signal Synthesis Brain (every 2 minutes) - ONLY DURING RTH
                if is_market_hours and self.brain_enabled and (self.last_synthesis_check is None or (now - self.last_synthesis_check).seconds >= self.synthesis_interval):
                    self.check_synthesis()
                    self.last_synthesis_check = now
                elif not is_market_hours and self.brain_enabled:
                    # Market closed - skip synthesis (no noise)
                    if self.last_synthesis_check is None or (now - self.last_synthesis_check).seconds >= 300:  # Log once every 5 min
                        logger.debug("   ⏸️  Market closed - skipping synthesis")
                        self.last_synthesis_check = now

                # Autonomous Tradytics Analysis (every 5 minutes) - REMOVED DUPLICATE
                if self.tradytics_llm_available and (self.last_tradytics_analysis is None or (now - self.last_tradytics_analysis).seconds >= self.tradytics_analysis_interval):
                    self.autonomous_tradytics_analysis()
                    self.last_tradytics_analysis = now

                # Narrative Brain - Scheduled updates (pre-market, intra-day, end-of-day)
                if self.narrative_enabled and self.narrative_scheduler:
                    self.narrative_scheduler.check_and_run_scheduled_updates()

                    # Also check for intra-day updates triggered by intelligence changes
                    if self.narrative_scheduler.can_run_intra_day_update():
                        # Feed current intelligence state to narrative brain
                        intelligence_data = self._get_current_intelligence_snapshot()
                        update = self.narrative_brain.process_intelligence_update("intelligence_snapshot", intelligence_data)
                        if update:
                            self.narrative_scheduler.mark_intra_day_update_sent()
                            logger.info(f"🧠 Narrative update sent: {update.alert_type.value}")
                
                # Sleep for 30 seconds between checks (faster for DP)
                time.sleep(30)
                
            except KeyboardInterrupt:
                logger.info("\n🛑 Monitor stopped by user")
                break
            except Exception as e:
                logger.error(f"❌ Main loop error: {e}")
                time.sleep(60)


# ============================================================================
# WEB SERVICE WRAPPER (For Render deployment)
# ============================================================================

def create_web_app():
    """Create FastAPI app for Render web service."""
    try:
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        import uvicorn
    except ImportError:
        logger.warning("FastAPI not installed, running without web server")
        return None
    
    app = FastAPI(title="Alpha Intelligence Monitor")
    monitor = None
    
    @app.on_event("startup")
    async def startup():
        nonlocal monitor
        monitor = UnifiedAlphaMonitor()
        # Start monitoring in background thread
        import threading
        thread = threading.Thread(target=monitor.run, daemon=True)
        thread.start()
        logger.info("✅ Monitor started in background")
    
    @app.get("/")
    def root():
        return {"status": "ALPHA INTELLIGENCE ONLINE", "timestamp": datetime.now().isoformat()}
    
    @app.get("/health")
    def health():
        return JSONResponse({"status": "healthy", "monitors": {
            "fed": getattr(monitor, 'fed_enabled', False) if monitor else False,
            "trump": getattr(monitor, 'trump_enabled', False) if monitor else False,
            "dark_pools": getattr(monitor, 'dp_enabled', False) if monitor else False,
            "symbols": getattr(monitor, 'symbols', []) if monitor else [],
        }})
    
    @app.get("/status")
    def status():
        if monitor and monitor.prev_fed_status:
            return {
                "fed": {
                    "prob_cut": monitor.prev_fed_status.prob_cut,
                    "prob_hold": monitor.prev_fed_status.prob_hold,
                    "most_likely": monitor.prev_fed_status.most_likely_outcome
                }
            }
        return {"status": "initializing"}
    
    return app


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Alpha Intelligence Unified Monitor")
    parser.add_argument("--web", action="store_true", help="Run as web service (for Render)")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", 10000)), help="Port for web service")
    
    args = parser.parse_args()
    
    if args.web:
        app = create_web_app()
        if app:
            import uvicorn
            uvicorn.run(app, host="0.0.0.0", port=args.port)
        else:
            # Fallback to direct monitoring
            monitor = UnifiedAlphaMonitor()
            monitor.run()
    else:
        monitor = UnifiedAlphaMonitor()
        monitor.run()


if __name__ == "__main__":
    main()

