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
from .checkers import (
    FedChecker,
    TrumpChecker,
    EconomicChecker,
    DarkPoolChecker,
    SynthesisChecker,
    NarrativeChecker,
    TradyticsChecker,
    SqueezeChecker,
    GammaChecker,
    ScannerChecker,
    FTDChecker,
    DailyRecapChecker,
    RedditChecker,
    PreMarketGapChecker,
    OptionsFlowChecker,
)

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
        self.reddit_interval = 3600   # 1 hour - Reddit sentiment (Phase 5)
        self.premarket_gap_interval = 300  # 5 minutes - only runs pre-market
        self.options_flow_interval = 1800  # 30 minutes - options flow analysis
        
        # Track last run times
        self.last_fed_check = None
        self.last_trump_check = None
        self.last_econ_check = None
        self.last_dp_check = None
        self.last_synthesis_check = None
        self.last_tradytics_analysis = None
        self.last_squeeze_check = None
        self.last_reddit_check = None
        self.last_premarket_gap_check = None
        self.last_options_flow_check = None
        
        # Initialize modular components
        self.alert_manager = AlertManager()
        self.regime_detector = RegimeDetector()
        
        # State tracking (MUST BE BEFORE _init_monitors and _init_exploitation_modules)
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
        
        # Initialize monitors (this will set up all components)
        self._init_monitors()
        
        # Initialize exploitation modules
        self._init_exploitation_modules()
        
        # Initialize momentum detector (needs signal_generator)
        self.momentum_detector = MomentumDetector(
            signal_generator=getattr(self, 'signal_generator', None),
            institutional_engine=getattr(self, 'institutional_engine', None)
        )
        
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
        
        # Squeeze candidates - SEED list only!
        # The opportunity scanner DYNAMICALLY discovers new candidates each check
        # This is just a starting point for known high-SI stocks
        self.squeeze_candidates = ['GME', 'AMC', 'LCID', 'RIVN', 'MARA', 'RIOT']
        
        # Reddit Exploiter (Phase 5)
        self.reddit_enabled = False
        self.reddit_exploiter = None
        
        try:
            from live_monitoring.exploitation.reddit_exploiter import RedditExploiter
            
            api_key = os.getenv('CHARTEXCHANGE_API_KEY') or os.getenv('CHART_EXCHANGE_API_KEY')
            if api_key:
                self.reddit_exploiter = RedditExploiter(api_key=api_key)
                self.reddit_enabled = True
                logger.info("   ✅ Reddit Exploiter initialized")
            else:
                logger.warning("   ⚠️ Reddit Exploiter: No API key found")
        except Exception as e:
            logger.warning(f"   ⚠️ Reddit Exploiter failed: {e}")
        
        logger.info(f"   Squeeze Detector: {'✅' if self.squeeze_enabled else '❌'}")
        logger.info(f"   Gamma Tracker: {'✅' if self.gamma_enabled else '❌'}")
        logger.info(f"   Opportunity Scanner: {'✅' if self.scanner_enabled else '❌'}")
        logger.info(f"   FTD Analyzer: {'✅' if self.ftd_enabled else '❌'}")
        logger.info(f"   Reddit Exploiter: {'✅' if self.reddit_enabled else '❌'}")
        
        # Initialize all checkers
        self._init_checkers()
    
    def _init_checkers(self):
        """Initialize all checker modules."""
        logger.info("🔧 Initializing checker modules...")
        
        # Fed Checker
        self.fed_checker = FedChecker(
            alert_manager=self.alert_manager,
            fed_watch=self.fed_watch,
            fed_officials=self.fed_officials,
            unified_mode=self.unified_mode
        ) if self.fed_enabled else None
        
        # Trump Checker
        self.trump_checker = TrumpChecker(
            alert_manager=self.alert_manager,
            trump_pulse=self.trump_pulse,
            trump_news=self.trump_news,
            unified_mode=self.unified_mode
        ) if self.trump_enabled else None
        
        # Economic Checker
        self.economic_checker = EconomicChecker(
            alert_manager=self.alert_manager,
            econ_calendar=self.econ_calendar,
            econ_engine=self.econ_engine,
            econ_calendar_type=self.econ_calendar_type,
            prev_fed_status=self.prev_fed_status,
            unified_mode=self.unified_mode
        ) if self.econ_enabled else None
        
        # Dark Pool Checker
        self.dp_checker = DarkPoolChecker(
            alert_manager=self.alert_manager,
            dp_monitor_engine=self.dp_monitor_engine,
            symbols=self.symbols,
            unified_mode=self.unified_mode,
            on_synthesis_trigger=lambda: None  # Synthesis handled separately
        ) if self.dp_enabled else None
        
        # Synthesis Checker
        self.synthesis_checker = SynthesisChecker(
            alert_manager=self.alert_manager,
            signal_brain=self.signal_brain,
            macro_provider=self.macro_provider,
            unified_mode=self.unified_mode
        ) if self.brain_enabled else None
        
        # Narrative Checker
        self.narrative_checker = NarrativeChecker(
            alert_manager=self.alert_manager,
            narrative_brain=self.narrative_brain,
            regime_detector=self.regime_detector,
            dp_monitor_engine=self.dp_monitor_engine,
            unified_mode=self.unified_mode
        ) if self.narrative_enabled else None
        
        # Tradytics Checker
        self.tradytics_checker = TradyticsChecker(
            alert_manager=self.alert_manager,
            tradytics_llm_available=self.tradytics_llm_available,
            tradytics_analysis_interval=self.tradytics_analysis_interval,
            unified_mode=self.unified_mode
        ) if self.tradytics_llm_available else None
        
        # Squeeze Checker
        self.squeeze_checker = SqueezeChecker(
            alert_manager=self.alert_manager,
            squeeze_detector=self.squeeze_detector,
            opportunity_scanner=self.opportunity_scanner,
            squeeze_candidates=self.squeeze_candidates,
            unified_mode=self.unified_mode
        ) if self.squeeze_enabled else None
        
        # Gamma Checker
        # Get gamma_exposure_tracker from signal_generator if available
        gamma_exposure_tracker = None
        if hasattr(self, 'signal_generator') and hasattr(self.signal_generator, 'gamma_tracker'):
            gamma_exposure_tracker = self.signal_generator.gamma_tracker
        
        self.gamma_checker = GammaChecker(
            alert_manager=self.alert_manager,
            gamma_tracker=self.gamma_tracker,
            gamma_exposure_tracker=gamma_exposure_tracker,
            symbols=self.symbols,
            unified_mode=self.unified_mode
        ) if self.gamma_enabled else None
        
        # Scanner Checker
        self.scanner_checker = ScannerChecker(
            alert_manager=self.alert_manager,
            opportunity_scanner=self.opportunity_scanner,
            squeeze_detector=self.squeeze_detector,
            unified_mode=self.unified_mode
        ) if self.scanner_enabled else None
        
        # FTD Checker
        self.ftd_checker = FTDChecker(
            alert_manager=self.alert_manager,
            ftd_analyzer=self.ftd_analyzer,
            ftd_candidates=self.ftd_candidates,
            unified_mode=self.unified_mode
        ) if self.ftd_enabled else None
        
        # Daily Recap Checker
        self.daily_recap_checker = DailyRecapChecker(
            alert_manager=self.alert_manager,
            gamma_tracker=self.gamma_tracker,
            symbols=self.symbols,
            squeeze_enabled=self.squeeze_enabled,
            gamma_enabled=self.gamma_enabled,
            unified_mode=self.unified_mode
        )
        
        # Reddit Checker (Phase 5)
        api_key = os.getenv('CHARTEXCHANGE_API_KEY') or os.getenv('CHART_EXCHANGE_API_KEY')
        self.reddit_checker = RedditChecker(
            alert_manager=self.alert_manager,
            reddit_exploiter=self.reddit_exploiter,
            api_key=api_key
        ) if self.reddit_enabled else None
        
        # Pre-Market Gap Checker (Phase 6)
        self.premarket_gap_checker = PreMarketGapChecker(
            alert_manager=self.alert_manager,
            api_key=api_key,
            unified_mode=self.unified_mode
        )
        
        # Options Flow Checker (Phase 6)
        self.options_flow_checker = OptionsFlowChecker(
            alert_manager=self.alert_manager,
            api_key=api_key,
            unified_mode=self.unified_mode
        )
        
        logger.info("   ✅ All checkers initialized (including Phase 6: PreMarketGap, OptionsFlow)")
    
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
    # HELPER METHODS (kept for compatibility)
    # ═══════════════════════════════════════════════════════════════
    
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
    
    # NOTE: check_synthesis() and _check_narrative_brain_signals() removed
    # Now handled by SynthesisChecker and NarrativeChecker
    
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
            "description": "Complete institutional intelligence system activated\n**All signals operational and tested**",
            "fields": [
                # === MACRO INTELLIGENCE ===
                {"name": "🏦 Fed Watch", "value": "✅ FOMC + Officials" if self.fed_enabled else "❌ Disabled", "inline": True},
                {"name": "🎯 Trump Intel", "value": "✅ Real-time Tweets" if self.trump_enabled else "❌ Disabled", "inline": True},
                {"name": "📊 Economic AI", "value": "✅ Calendar Events" if self.econ_enabled else "❌ Disabled", "inline": True},
                
                # === PRICE ACTION SIGNALS ===
                {"name": "🚨 Selloff/Rally", "value": "✅ FIXED & ACTIVE\n-0.25% threshold", "inline": True},
                {"name": "🔒 Dark Pool", "value": f"✅ {', '.join(self.symbols)}\nBattlegrounds" if self.dp_enabled else "❌ Disabled", "inline": True},
                {"name": "📱 Reddit Exploiter", "value": "✅ Contrarian Logic\nDP Synthesis", "inline": True},
                
                # === INSTITUTIONAL SIGNALS ===
                {"name": "🔥 Squeeze Detector", "value": "✅ Short Interest\nBorrow Fees", "inline": True},
                {"name": "📊 Gamma Tracker", "value": "✅ Max Pain\nDealer Flow", "inline": True},
                {"name": "📈 Short Interest", "value": "✅ Live Tracking\nDaily Updates", "inline": True},
                
                # === PHASE 6: NEW STRATEGIES ===
                {"name": "🌅 Pre-Market Gap", "value": "✅ Gap + DP Confluence\n20-25% edge", "inline": True},
                {"name": "📊 Options Flow", "value": "✅ P/C Ratio + Sweeps\n15-20% edge", "inline": True},
                {"name": "🎲 Gamma Flip", "value": "✅ Flip Level Retest\nDealer Hedging", "inline": True},
                
                # === SYNTHESIS ===
                {"name": "🧠 Signal Brain", "value": "✅ Multi-Factor\n75%+ Threshold" if self.brain_enabled else "❌ Disabled", "inline": False},
                {"name": "⚡ Status", "value": "**ALL SYSTEMS GO**\nReady for RTH 9:30-4:00 ET\n12 Active Strategies", "inline": False},
            ],
            "footer": {"text": "Modular v2.1 | Phase 6 Strategies Dec 17"},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.send_discord(embed, alert_type="startup", source="monitor")
        self.startup_alert_sent = True
    
    # NOTE: All old checker methods removed - now handled by modular checker classes:
    # - FedChecker, TrumpChecker, EconomicChecker
    # - DarkPoolChecker, SynthesisChecker, NarrativeChecker
    # - TradyticsChecker, SqueezeChecker, GammaChecker, ScannerChecker, FTDChecker
    # - DailyRecapChecker
    #
    # Legacy methods below are kept for backward compatibility but NOT called in run()
    # They can be safely removed in a future cleanup
    
    def check_squeeze_setups(self):
        """
        🔥 Check for short squeeze setups (PHASE 1 EXPLOITATION).
        FULLY DYNAMIC - Uses opportunity scanner to discover candidates first!
        Runs hourly during market hours.
        """
        if not self.squeeze_enabled or not self.squeeze_detector:
            return
        
        logger.info("🔥 Checking for SQUEEZE setups (DYNAMIC DISCOVERY)...")
        
        try:
            # STEP 1: DYNAMIC DISCOVERY - Use opportunity scanner to find ALL high SI stocks
            if self.scanner_enabled and self.opportunity_scanner:
                # Use the new comprehensive squeeze candidate scanner
                logger.info("   🔍 Running FULL dynamic squeeze scan...")
                try:
                    squeeze_opportunities = self.opportunity_scanner.scan_for_squeeze_candidates(
                        self.squeeze_detector,
                        min_score=55  # Slightly lower for discovery, will filter at 60 for alerts
                    )
                    
                    if squeeze_opportunities:
                        logger.info(f"   📡 Found {len(squeeze_opportunities)} squeeze candidates!")
                        for opp in squeeze_opportunities:
                            logger.info(f"      • {opp.symbol}: Score {opp.score:.0f} | SI: {opp.short_interest:.1f}%")
                    else:
                        logger.info("   📊 No squeeze candidates found above threshold")
                    
                    # Process signals directly from scan results
                    for opp in squeeze_opportunities:
                        if opp.score >= 60:  # Alert threshold
                            # Get full signal for detailed alert
                            signal = self.squeeze_detector.analyze(opp.symbol)
                            if signal:
                                self._send_squeeze_alert(signal)
                    
                    return  # Dynamic scan complete
                    
                except Exception as e:
                    logger.warning(f"   ⚠️ Dynamic scan failed, falling back to seed list: {e}")
            
            # FALLBACK: Use seed list if scanner not available
            candidates_to_check = set(self.squeeze_candidates)
            logger.info(f"   📊 Using seed list: {len(candidates_to_check)} candidates")
            
            # STEP 2: Run squeeze detector on all candidates
            signals_found = 0
            for symbol in candidates_to_check:
                signal = self.squeeze_detector.analyze(symbol)
                
                if signal and signal.score >= 60:
                    signals_found += 1
                    self._send_squeeze_alert(signal)
            
            logger.info(f"   📊 Squeeze check complete: {signals_found} signals found")
                    
        except Exception as e:
            logger.error(f"   ❌ Squeeze check error: {e}")
    
    def _send_squeeze_alert(self, signal):
        """
        Send a squeeze alert to Discord.
        Extracted to avoid code duplication.
        """
        # Check for duplicate alert
        alert_key = f"squeeze_{signal.symbol}_{datetime.now().strftime('%Y-%m-%d')}"
        if self.alert_manager.is_alert_duplicate(alert_key, cooldown_minutes=60):
            logger.debug(f"   ⏭️ Skipping duplicate squeeze alert for {signal.symbol}")
            return
        
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
            "footer": {"text": f"Exploitation Phase 1 • Dynamic Squeeze Detection"},
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
        self.alert_manager.add_alert_to_history(alert_key)
        
        logger.info(f"   🔥 Squeeze signal sent for {signal.symbol}!")
    
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
            
            # Run market scan (lowered threshold from 50 to 45 to catch more opportunities)
            opportunities = self.opportunity_scanner.scan_market(min_score=45, max_results=10)
            
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
        self.last_reddit_check = now
        self.last_premarket_gap_check = None  # Run immediately on first check
        self.last_options_flow_check = None  # Run immediately on first check
        self.gamma_interval = 1800  # Check gamma every 30 min (was hourly)
        
        while self.running:
            try:
                now = datetime.now()
                
                # Fed Checker
                if self.fed_checker and (self.last_fed_check is None or (now - self.last_fed_check).seconds >= self.fed_interval):
                    # Update prev_fed_status in checker before checking
                    self.fed_checker.prev_fed_status = self.prev_fed_status
                    alerts = self.fed_checker.check()
                    for alert in alerts:
                        self.send_discord(alert.embed, alert.content, alert.alert_type, alert.source, alert.symbol)
                    # Update prev_fed_status from checker after checking
                    if hasattr(self.fed_checker, 'prev_fed_status'):
                        self.prev_fed_status = self.fed_checker.prev_fed_status
                    self.last_fed_check = now
                
                # Trump Checker
                if self.trump_checker and (self.last_trump_check is None or (now - self.last_trump_check).seconds >= self.trump_interval):
                    alerts = self.trump_checker.check()
                    for alert in alerts:
                        self.send_discord(alert.embed, alert.content, alert.alert_type, alert.source, alert.symbol)
                    self.last_trump_check = now
                
                # Economic Checker
                if self.economic_checker and (self.last_econ_check is None or (now - self.last_econ_check).seconds >= self.econ_interval):
                    alerts = self.economic_checker.check()
                    for alert in alerts:
                        self.send_discord(alert.embed, alert.content, alert.alert_type, alert.source, alert.symbol)
                    self.last_econ_check = now
                
                is_market_hours = self._is_market_hours()
                
                # Get current prices for synthesis/narrative checkers
                spy_price = 0.0
                qqq_price = 0.0
                if is_market_hours:
                    try:
                        import yfinance as yf
                        spy_ticker = yf.Ticker('SPY')
                        qqq_ticker = yf.Ticker('QQQ')
                        spy_hist = spy_ticker.history(period='1d', interval='1m')
                        qqq_hist = qqq_ticker.history(period='1d', interval='1m')
                        if not spy_hist.empty:
                            spy_price = float(spy_hist['Close'].iloc[-1])
                        if not qqq_hist.empty:
                            qqq_price = float(qqq_hist['Close'].iloc[-1])
                    except:
                        pass
                
                # Dark Pool Checker
                if is_market_hours and self.dp_checker and (self.last_dp_check is None or (now - self.last_dp_check).seconds >= self.dp_interval):
                    alerts = self.dp_checker.check()
                    for alert in alerts:
                        self.send_discord(alert.embed, alert.content, alert.alert_type, alert.source, alert.symbol)
                    # Get recent_dp_alerts from checker for synthesis/narrative
                    self.recent_dp_alerts = self.dp_checker.get_recent_alerts()
                    self.last_dp_check = now
                
                # Synthesis Checker (returns alerts + result for narrative checker)
                synthesis_result = None
                if is_market_hours and self.synthesis_checker and (self.last_synthesis_check is None or (now - self.last_synthesis_check).seconds >= self.synthesis_interval):
                    alerts, synthesis_result = self.synthesis_checker.check(
                        recent_dp_alerts=self.recent_dp_alerts,
                        spy_price=spy_price,
                        qqq_price=qqq_price
                    )
                    for alert in alerts:
                        self.send_discord(alert.embed, alert.content, alert.alert_type, alert.source, alert.symbol)
                    self.last_synthesis_check = now
                    
                    # Check Narrative Brain signals (needs synthesis_result)
                    if synthesis_result and self.narrative_checker:
                        narrative_alerts = self.narrative_checker.check(
                            recent_dp_alerts=self.recent_dp_alerts,
                            synthesis_result=synthesis_result,
                            spy_price=spy_price,
                            qqq_price=qqq_price
                        )
                        for alert in narrative_alerts:
                            self.send_discord(alert.embed, alert.content, alert.alert_type, alert.source, alert.symbol)
                        if not narrative_alerts:
                            self.recent_dp_alerts = []  # Clear if no narrative signal
                
                # Squeeze Checker
                if is_market_hours and self.squeeze_checker and (self.last_squeeze_check is None or (now - self.last_squeeze_check).seconds >= self.squeeze_interval):
                    alerts = self.squeeze_checker.check()
                    for alert in alerts:
                        self.send_discord(alert.embed, alert.content, alert.alert_type, alert.source, alert.symbol)
                    self.last_squeeze_check = now
                
                # Gamma Checker
                if is_market_hours and self.gamma_checker and (self.last_gamma_check is None or (now - self.last_gamma_check).seconds >= self.gamma_interval):
                    alerts = self.gamma_checker.check()
                    for alert in alerts:
                        self.send_discord(alert.embed, alert.content, alert.alert_type, alert.source, alert.symbol)
                    self.last_gamma_check = now
                
                # Scanner Checker
                if is_market_hours and self.scanner_checker and (self.last_scanner_check is None or (now - self.last_scanner_check).seconds >= self.scanner_interval):
                    alerts = self.scanner_checker.check()
                    for alert in alerts:
                        self.send_discord(alert.embed, alert.content, alert.alert_type, alert.source, alert.symbol)
                    self.last_scanner_check = now
                
                # FTD Checker
                if is_market_hours and self.ftd_checker and (self.last_ftd_check is None or (now - self.last_ftd_check).seconds >= self.ftd_interval):
                    alerts = self.ftd_checker.check()
                    for alert in alerts:
                        self.send_discord(alert.embed, alert.content, alert.alert_type, alert.source, alert.symbol)
                    self.last_ftd_check = now
                
                # Reddit Checker (Phase 5)
                if is_market_hours and self.reddit_checker and (self.last_reddit_check is None or (now - self.last_reddit_check).seconds >= self.reddit_interval):
                    alerts = self.reddit_checker.check()
                    for alert in alerts:
                        self.send_discord(alert.embed, alert.content, alert.alert_type, alert.source, alert.symbol)
                    self.last_reddit_check = now
                
                # Pre-Market Gap Checker (Phase 6) - Runs ONCE per day before market open
                if self.premarket_gap_checker and (self.last_premarket_gap_check is None or (now - self.last_premarket_gap_check).seconds >= self.premarket_gap_interval):
                    alerts = self.premarket_gap_checker.check()
                    for alert in alerts:
                        self.send_discord(alert.embed, alert.content, alert_type="premarket_gap", source="premarket_gap_checker", symbol=alert.fields.get("Symbol", ""))
                    self.last_premarket_gap_check = now
                
                # Options Flow Checker (Phase 6) - Runs during RTH every 30 min
                if is_market_hours and self.options_flow_checker and (self.last_options_flow_check is None or (now - self.last_options_flow_check).seconds >= self.options_flow_interval):
                    alerts = self.options_flow_checker.check()
                    for alert in alerts:
                        self.send_discord(alert.embed, alert.content, alert_type="options_flow", source="options_flow_checker", symbol=alert.fields.get("Symbol", ""))
                    self.last_options_flow_check = now
                
                # 🚨 MOMENTUM: Selloff/Rally Detection (every minute during RTH)
                if is_market_hours and (self.last_dp_check is None or (now - self.last_dp_check).seconds >= 60):
                    self._check_selloffs()
                    self._check_rallies()
                
                # Tradytics Checker
                if self.tradytics_checker and (self.last_tradytics_analysis is None or (now - self.last_tradytics_analysis).seconds >= self.tradytics_analysis_interval):
                    alerts = self.tradytics_checker.check()
                    for alert in alerts:
                        self.send_discord(alert.embed, alert.content, alert.alert_type, alert.source, alert.symbol)
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
                
                # Daily Recap Checker
                recap_alerts = self.daily_recap_checker.check(now)
                for alert in recap_alerts:
                    self.send_discord(alert.embed, alert.content, alert.alert_type, alert.source, alert.symbol)
                
                time.sleep(30)
                
            except KeyboardInterrupt:
                logger.info("\n🛑 Monitor stopped by user")
                break
            except Exception as e:
                logger.error(f"❌ Main loop error: {e}")
                time.sleep(60)

